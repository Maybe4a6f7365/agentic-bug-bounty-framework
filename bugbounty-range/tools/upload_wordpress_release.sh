#!/usr/bin/env bash
set -euo pipefail

release_dir="${BBR_RELEASE_DIR:-/home/admin/.bbr-build/wordpress-smoke-001-r4}"
target="gs://bbr-bootstrap-your-lab-name-your-researcher-handle/artifacts/wordpress/6.8.2-r4"
public_key="${BBR_MINISIGN_PUBLIC_KEY:-/home/admin/.bbr-keys/minisign.pub}"
execute="${BBR_RELEASE_UPLOAD_EXECUTE:-no}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pack_manifest="${script_dir}/../packs/wordpress-smoke/manifest.json"
files=(artifact.tar.zst artifact.tar.zst.sha256 artifact.tar.zst.minisig manifest.json package-inputs.json)
declare -A local_sha256=()
verify_dir=""

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$verify_dir" && -d "$verify_dir" ]]; then
    rm -rf -- "$verify_dir"
  fi
}
trap cleanup EXIT

verify_manifest() {
  local candidate=$1
  local release_version release_wordpress release_sha release_platform
  local release_bootstrap release_commit release_source release_build release_signature
  local pack_wordpress pack_sha pack_platform pack_bootstrap pack_commit pack_source pack_build pack_signature

  release_version="$(jq -er '.artifact_version' "$candidate")"
  release_wordpress="$(jq -er '.wordpress_version' "$candidate")"
  release_sha="$(jq -er '.artifact_sha256' "$candidate")"
  release_platform="$(jq -er '.supported_platform' "$candidate")"
  release_bootstrap="$(jq -er '.bootstrap_version' "$candidate")"
  release_commit="$(jq -er '.git_commit' "$candidate")"
  release_build="$(jq -er '.build_id' "$candidate")"
  release_signature="$(jq -er '.artifact_signature' "$candidate")"
  release_source="$release_commit"

  pack_wordpress="$(jq -er '.topology.nodes[0].driver_payload.wordpress_version' "$pack_manifest")"
  pack_sha="$(jq -er '.topology.nodes[0].driver_payload.artifact_sha256' "$pack_manifest")"
  pack_platform="$(jq -er '.topology.nodes[0].driver_payload.supported_platform' "$pack_manifest")"
  pack_bootstrap="$(jq -er '.topology.nodes[0].driver_payload.bootstrap_version' "$pack_manifest")"
  pack_commit="$(jq -er '.topology.nodes[0].driver_payload.git_commit' "$pack_manifest")"
  pack_source="$(jq -er '.topology.nodes[0].driver_payload.source_commit' "$pack_manifest")"
  pack_build="$(jq -er '.topology.nodes[0].driver_payload.build_id' "$pack_manifest")"
  pack_signature="$(jq -er '.topology.nodes[0].driver_payload.artifact_signature' "$pack_manifest")"

  [[ "$release_version" == "6.8.2-r4" ]] || fail "release manifest version mismatch"
  [[ "$release_wordpress" == "$pack_wordpress" ]] || fail "WordPress version differs from pack manifest"
  [[ "$release_sha" == "$pack_sha" ]] || fail "artifact SHA-256 differs from pack manifest"
  [[ "$release_platform" == "$pack_platform" ]] || fail "supported platform differs from pack manifest"
  [[ "$release_bootstrap" == "$pack_bootstrap" ]] || fail "bootstrap version differs from pack manifest"
  [[ "$release_commit" == "$pack_commit" && "$release_source" == "$pack_source" ]] ||
    fail "source commit differs from pack manifest"
  [[ "$release_build" == "$pack_build" ]] || fail "build ID differs from pack manifest"
  [[ "$release_signature" == "$pack_signature" ]] || fail "artifact signature differs from pack manifest"
}

verify_release_set() {
  local directory=$1
  (
    cd "$directory"
    sha256sum -c artifact.tar.zst.sha256
  )
  minisign -V -p "$public_key" -m "${directory}/artifact.tar.zst" \
    -x "${directory}/artifact.tar.zst.minisig"
  verify_manifest "${directory}/manifest.json"
}

for name in "${files[@]}"; do
  [[ -f "${release_dir}/${name}" ]] || fail "missing ${name}"
  local_sha256["$name"]="$(sha256sum "${release_dir}/${name}" | awk '{print $1}')"
done
verify_release_set "$release_dir"

printf 'PLAN: immutable target prefix: %s/\n' "$target"
for name in "${files[@]}"; do
  printf 'PLAN: %s sha256=%s; accept identical existing object or upload missing object with generation-match=0\n' \
    "$name" "${local_sha256[$name]}"
done
printf 'PLAN: abort immediately on divergent existing content; never overwrite, replace, or delete\n'
printf 'PLAN: download all five objects to a fresh directory and compare each SHA-256\n'
printf 'PLAN: recheck SHA sidecar, Minisign, pack-manifest values, and exact five-object listing\n'
printf 'PLAN: r1/r2 are read only for before/after existence and SHA verification; never written, modified, or deleted\n'

if [[ "$execute" != "yes" ]]; then
  echo "DRY-RUN: no remote read or mutating command executed; prerequisite approval is required."
  exit 0
fi

verify_dir="$(mktemp -d)"
mkdir "${verify_dir}/existing" "${verify_dir}/final"

for name in "${files[@]}"; do
  remote="${target}/${name}"
  if gcloud storage objects describe "$remote" >/dev/null 2>&1; then
    gcloud storage cp "$remote" "${verify_dir}/existing/${name}"
    remote_sha="$(sha256sum "${verify_dir}/existing/${name}" | awk '{print $1}')"
    [[ "$remote_sha" == "${local_sha256[$name]}" ]] ||
      fail "existing remote object diverges: ${name}"
    printf 'Already uploaded and byte-identical: %s\n' "$name"
  else
    gcloud storage cp --if-generation-match=0 "${release_dir}/${name}" "$remote"
    printf 'Uploaded missing immutable object: %s\n' "$name"
  fi
done

for name in "${files[@]}"; do
  gcloud storage cp "${target}/${name}" "${verify_dir}/final/${name}"
  downloaded_sha="$(sha256sum "${verify_dir}/final/${name}" | awk '{print $1}')"
  [[ "$downloaded_sha" == "${local_sha256[$name]}" ]] ||
    fail "post-upload SHA-256 mismatch: ${name}"
done
verify_release_set "${verify_dir}/final"

mapfile -t remote_objects < <(
  gcloud storage ls "${target}/" |
    sed '/^[[:space:]]*$/d' |
    sed 's#/$##' |
    sort
)
expected_objects=()
for name in "${files[@]}"; do
  expected_objects+=("${target}/${name}")
done
mapfile -t expected_objects < <(printf '%s\n' "${expected_objects[@]}" | sort)
[[ "${#remote_objects[@]}" -eq "${#expected_objects[@]}" ]] ||
  fail "remote prefix does not contain exactly five objects"
for index in "${!expected_objects[@]}"; do
  [[ "${remote_objects[$index]}" == "${expected_objects[$index]}" ]] ||
    fail "unexpected object under immutable r4 prefix"
done

echo "Release upload verification completed: all five immutable objects are byte-identical."
