#!/usr/bin/env bash
set -euo pipefail

range_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bake_script="${range_dir}/tools/bake_bootstrap_image.sh"
input_spec="${range_dir}/packs/wordpress-smoke/bootstrap-image-inputs.json"
test_root="$(mktemp -d)"
pass_count=0
fail_count=0

# Invoked indirectly by the EXIT trap.
# shellcheck disable=SC2317
cleanup() {
  rm -rf -- "$test_root"
}
trap cleanup EXIT

fail_test() {
  printf 'FAIL: %s: %s\n' "$1" "$2"
  fail_count=$((fail_count + 1))
}

pass_test() {
  printf 'PASS: %s\n' "$1"
  pass_count=$((pass_count + 1))
}

assert_count() {
  local expected=$1
  local pattern=$2
  local file=$3
  local actual

  actual="$(grep -c -- "$pattern" "$file" || true)"
  [[ "$actual" == "$expected" ]]
}

make_harness() {
  local case_dir=$1
  local fake_bin="${case_dir}/bin"
  local input_dir="${case_dir}/inputs"
  local input_name

  mkdir -p "$fake_bin" "$input_dir" "${case_dir}/state"
  while IFS= read -r input_name; do
    : > "${input_dir}/${input_name}"
  done < <(jq -r '.packages[].file' "$input_spec")
  : > "${input_dir}/minisign-0.12-linux.tar.gz"

  cp "${range_dir}/tests/stubs/gcloud" "${fake_bin}/gcloud"
  cp "${range_dir}/tests/stubs/sha256sum" "${fake_bin}/sha256sum"
  chmod +x "${fake_bin}/gcloud" "${fake_bin}/sha256sum"
}

run_case() {
  local name=$1
  local readiness_failures=$2
  local scp_failures=$3
  local expected_status=$4
  local expected_readiness_calls=$5
  local expected_scp_calls=$6
  local expected_message=${7:-}
  local case_dir="${test_root}/${name}"
  local output="${case_dir}/output.log"
  local calls="${case_dir}/state/gcloud.log"
  local status

  make_harness "$case_dir"
  set +e
  PATH="${case_dir}/bin:${PATH}" \
    BBR_TEST_STATE_DIR="${case_dir}/state" \
    BBR_TEST_SPEC="$input_spec" \
    BBR_TEST_READINESS_FAILURES="$readiness_failures" \
    BBR_TEST_SCP_FAILURES="$scp_failures" \
    BBR_IMAGE_BAKE_EXECUTE=yes \
    BBR_BAKE_RUN_ID="test-${name}" \
    BBR_BOOTSTRAP_IMAGE_INPUT_DIR="${case_dir}/inputs" \
    BBR_IAP_READINESS_TIMEOUT_SECONDS=3 \
    BBR_IAP_READINESS_INTERVAL_SECONDS=1 \
    BBR_SCP_MAX_ATTEMPTS=3 \
    BBR_SCP_RETRY_INTERVAL_SECONDS=0 \
    bash "$bake_script" >"$output" 2>&1
  status=$?
  set -e

  if [[ "$expected_status" == "zero" && "$status" -ne 0 ]]; then
    fail_test "$name" "expected success, got exit ${status}"
    return
  fi
  if [[ "$expected_status" == "nonzero" && "$status" -eq 0 ]]; then
    fail_test "$name" "expected failure, got success"
    return
  fi
  if [[ "$expected_readiness_calls" == "at_least_3" ]]; then
    if (( $(grep -c 'compute ssh .*--command=true' "$calls" || true) < 3 )); then
      fail_test "$name" "expected at least three readiness SSH calls"
      return
    fi
  elif ! assert_count "$expected_readiness_calls" \
    'compute ssh .*--command=true' "$calls"; then
      fail_test "$name" "unexpected readiness SSH call count"
      return
  fi
  if ! assert_count "$expected_scp_calls" '^compute scp ' "$calls"; then
    fail_test "$name" "unexpected SCP call count"
    return
  fi
  if ! grep -q '^compute instances delete ' "$calls" ||
    ! grep -q '^compute disks delete ' "$calls"; then
    fail_test "$name" "cleanup delete calls missing"
    return
  fi
  if [[ -n "$expected_message" ]] && ! grep -q "$expected_message" "$output"; then
    fail_test "$name" "expected error message missing"
    return
  fi

  pass_test "$name"
}

run_case "4047_4047_4003_then_success" 3 0 zero 4 1
run_case "readiness_timeout" -1 0 nonzero at_least_3 0 \
  'IAP/SSH readiness timeout after 3s'
run_case "immediate_readiness" 0 0 zero 1 1
run_case "scp_failure_cleanup" 0 -1 nonzero 1 3 \
  'IAP-SCP failed after 3 attempts'
run_case "scp_retry_then_success" 0 1 zero 1 2

printf '\nTests: %s passed, %s failed\n' "$pass_count" "$fail_count"
[[ "$fail_count" -eq 0 ]]
exit 0
