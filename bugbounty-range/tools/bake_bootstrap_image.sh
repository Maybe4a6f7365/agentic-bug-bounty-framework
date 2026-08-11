#!/usr/bin/env bash
set -euo pipefail

project="your-lab-name-your-researcher-handle"
zone="europe-west3-a"
network="bbr-shared-vpc"
subnet="bbr-bastion-subnet"
network_tag="ssh-iap"
target_image="bbr-debian-12-bootstrap-tools-20260727-v2"
target_self_link="projects/${project}/global/images/${target_image}"
source_image_project="debian-cloud"
source_image_name="debian-12-bookworm-v20260721"
source_image_self_link="projects/${source_image_project}/global/images/${source_image_name}"
boot_disk_type="pd-standard"
boot_disk_size_gb=20
machine_type="e2-micro"
run_id="${BBR_BAKE_RUN_ID:-$(date -u +%Y%m%d%H%M%S)-$$}"
temp_vm="bbr-image-bake-${run_id}"
temp_disk="${temp_vm}-boot"
execute="${BBR_IMAGE_BAKE_EXECUTE:-no}"
iap_readiness_timeout_seconds="${BBR_IAP_READINESS_TIMEOUT_SECONDS:-300}"
iap_readiness_interval_seconds="${BBR_IAP_READINESS_INTERVAL_SECONDS:-10}"
scp_max_attempts="${BBR_SCP_MAX_ATTEMPTS:-3}"
scp_retry_interval_seconds="${BBR_SCP_RETRY_INTERVAL_SECONDS:-5}"
input_dir="${BBR_BOOTSTRAP_IMAGE_INPUT_DIR:-/home/admin/.bbr-build/bootstrap-image-inputs-20260727-v2}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input_spec="${script_dir}/../packs/wordpress-smoke/bootstrap-image-inputs.json"
minisign_archive="minisign-0.12-linux.tar.gz"
minisign_sha256="9a599b48ba6eb7b1e80f12f36b94ceca7c00b7a5173c95c3efc88d9822957e73"
stage_dir=""
vm_created="no"
disk_created="no"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

# Fresh VMs can transiently return IAP 4047/4003 until IAP and SSH are ready.
wait_for_iap_ssh_readiness() {
  local attempt=1
  local started_at=$SECONDS
  local elapsed=0
  local max_attempts=$((iap_readiness_timeout_seconds / iap_readiness_interval_seconds + 1))

  while true; do
    elapsed=$((SECONDS - started_at))
    printf 'Waiting for IAP/SSH readiness: attempt %s/%s (%ss elapsed)\n' \
      "$attempt" "$max_attempts" "$elapsed"
    if gcloud compute ssh "$temp_vm" \
      --project="$project" --zone="$zone" --tunnel-through-iap \
      --command=true >/dev/null 2>&1; then
      return 0
    fi

    elapsed=$((SECONDS - started_at))
    if (( elapsed >= iap_readiness_timeout_seconds )); then
      fail "IAP/SSH readiness timeout after ${iap_readiness_timeout_seconds}s for ${temp_vm}"
    fi
    sleep "$iap_readiness_interval_seconds"
    attempt=$((attempt + 1))
  done
}

copy_bootstrap_inputs() {
  local attempt

  for ((attempt = 1; attempt <= scp_max_attempts; attempt++)); do
    printf 'Transferring bootstrap inputs over IAP-SCP: attempt %s/%s\n' \
      "$attempt" "$scp_max_attempts"
    if gcloud compute scp --recurse "$stage_dir" "$temp_vm:/tmp/bbr-bootstrap-inputs" \
      --project="$project" --zone="$zone" --tunnel-through-iap; then
      return 0
    fi
    if (( attempt < scp_max_attempts )); then
      sleep "$scp_retry_interval_seconds"
    fi
  done

  fail "IAP-SCP failed after ${scp_max_attempts} attempts for ${temp_vm}"
}

spec_value() {
  jq -er "$1" "$input_spec"
}

verify_local_inputs() {
  [[ -f "$input_spec" ]] || fail "missing tracked input spec: ${input_spec}"
  [[ "$(spec_value '.source_image_self_link')" == "$source_image_self_link" ]] ||
    fail "source image differs from tracked input spec"
  [[ "$(spec_value '.boot_disk.type')" == "$boot_disk_type" ]] ||
    fail "boot disk type differs from tracked input spec"
  [[ "$(spec_value '.boot_disk.size_gb')" == "$boot_disk_size_gb" ]] ||
    fail "boot disk size differs from tracked input spec"
  [[ "$(spec_value '.minisign.archive')" == "$minisign_archive" ]] ||
    fail "Minisign archive differs from tracked input spec"
  [[ "$(spec_value '.minisign.sha256')" == "$minisign_sha256" ]] ||
    fail "Minisign SHA-256 differs from pinned value"

  local name expected actual
  while IFS=$'\t' read -r name expected; do
    [[ -f "${input_dir}/${name}" ]] || fail "missing bootstrap input: ${input_dir}/${name}"
    actual="$(sha256sum "${input_dir}/${name}" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]] || fail "SHA-256 mismatch for ${name}"
  done < <(jq -r '.packages[] | [.file, .sha256] | @tsv' "$input_spec")

  [[ -f "${input_dir}/${minisign_archive}" ]] ||
    fail "missing Minisign archive: ${input_dir}/${minisign_archive}"
  actual="$(sha256sum "${input_dir}/${minisign_archive}" | awk '{print $1}')"
  [[ "$actual" == "$minisign_sha256" ]] || fail "Minisign archive SHA-256 mismatch"
}

print_plan() {
  printf 'PLAN: target project: %s\n' "$project"
  printf 'PLAN: zone: %s\n' "$zone"
  printf 'PLAN: network: %s\n' "$network"
  printf 'PLAN: subnet: %s\n' "$subnet"
  printf 'PLAN: network tag: %s\n' "$network_tag"
  printf 'PLAN: external IP: NONE\n'
  printf 'PLAN: service account: NONE; OAuth scopes: NONE\n'
  printf 'PLAN: OS Login enabled; project-wide SSH keys blocked\n'
  printf 'PLAN: source image project: %s\n' "$source_image_project"
  printf 'PLAN: source image name: %s\n' "$source_image_name"
  printf 'PLAN: source image: %s\n' "$source_image_self_link"
  printf 'PLAN: temporary boot disk size: %sGB\n' "$boot_disk_size_gb"
  printf 'PLAN: bake VM machine type: %s\n' "$machine_type"
  printf 'PLAN: temporary VM: %s\n' "$temp_vm"
  printf 'PLAN: create temporary boot disk %s from pinned source image %s using %s at %sGB\n' \
    "$temp_disk" "$source_image_self_link" "$boot_disk_type" "$boot_disk_size_gb"
  printf 'PLAN: attach existing disk %s as the VM boot disk (boot=yes; auto-delete=no; device-name=%s)\n' \
    "$temp_disk" "$temp_disk"
  printf 'PLAN: local input directory: %s\n' "$input_dir"
  jq -r '.packages[] | "PLAN: bootstrap .deb: \(.file) sha256=\(.sha256)"' "$input_spec"
  printf 'PLAN: Minisign archive: %s sha256=%s\n' "$minisign_archive" "$minisign_sha256"
  printf 'PLAN: wait for IAP/SSH readiness before IAP-SCP transfer\n'
  printf 'PLAN: transfer tracked spec, hash manifest, local .deb files, and Minisign archive over IAP-SCP\n'
  printf 'PLAN: recheck every transferred SHA-256 on the bake VM\n'
  printf 'PLAN: install offline with dpkg --unpack <local bootstrap packages>; dpkg --configure -a\n'
  printf 'PLAN: install verified Minisign 0.12 archive; no repository or network downloads\n'
  printf 'PLAN: verify bash curl sha256sum minisign jq tar unzstd and exact Minisign version 0.12\n'
  printf 'PLAN: sanitize inputs, caches, logs, credentials, SSH host keys, and machine-id\n'
  printf 'PLAN: stop VM and create image %s from %s\n' "$target_self_link" "$temp_disk"
  printf 'PLAN: require exact name/self-link, READY status, and UEFI_COMPATIBLE guest feature\n'
  printf 'PLAN: cleanup temporary VM and disk on success or failure\n'
  printf 'PLAN: no firewall, route, Foundation, or Lab resource changes\n'
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ "$execute" == "yes" ]]; then
    if [[ "$vm_created" == "yes" ]]; then
      gcloud compute instances delete "$temp_vm" \
        --project="$project" --zone="$zone" --quiet >/dev/null 2>&1 || true
    fi
    if [[ "$disk_created" == "yes" ]]; then
      gcloud compute disks delete "$temp_disk" \
        --project="$project" --zone="$zone" --quiet >/dev/null 2>&1 || true
    fi
  fi
  if [[ -n "$stage_dir" && -d "$stage_dir" ]]; then
    rm -rf -- "$stage_dir"
  fi
  exit "$status"
}

verify_local_inputs
print_plan

if [[ "$execute" != "yes" ]]; then
  echo "DRY-RUN: no mutating command executed; prerequisite approval is required."
  exit 0
fi

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -n "$(gcloud compute images list --project="$project" \
  --filter="name=${target_image}" --format='value(name)')" ]]; then
  fail "refusing to overwrite or delete existing target image"
fi
if [[ -n "$(gcloud compute instances list --project="$project" \
  --zones="$zone" --filter="name=${temp_vm}" --format='value(name)')" ]]; then
  fail "temporary VM name already exists: ${temp_vm}"
fi
if [[ -n "$(gcloud compute disks list --project="$project" \
  --zones="$zone" --filter="name=${temp_disk}" --format='value(name)')" ]]; then
  fail "temporary disk name already exists: ${temp_disk}"
fi

stage_dir="$(mktemp -d)"
cp "$input_spec" "${stage_dir}/bootstrap-image-inputs.json"
cp "${input_dir}/${minisign_archive}" "${stage_dir}/${minisign_archive}"
while IFS= read -r name; do
  cp "${input_dir}/${name}" "${stage_dir}/${name}"
done < <(jq -r '.packages[].file' "$input_spec")
(
  cd "$stage_dir"
  jq -r '.packages[] | "\(.sha256)  \(.file)"' bootstrap-image-inputs.json \
    > bootstrap-inputs.sha256
  printf '%s  %s\n' "$minisign_sha256" "$minisign_archive" >> bootstrap-inputs.sha256
)

gcloud compute disks create "$temp_disk" \
  --project="$project" \
  --zone="$zone" \
  --image="$source_image_name" \
  --image-project="$source_image_project" \
  --type=pd-standard \
  --size=20GB
disk_created="yes"

gcloud compute instances create "$temp_vm" \
  --project="$project" \
  --zone="$zone" \
  --machine-type="$machine_type" \
  --network="$network" \
  --subnet="$subnet" \
  --tags="$network_tag" \
  --no-address \
  --no-service-account \
  --no-scopes \
  --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE \
  --disk="name=${temp_disk},boot=yes,auto-delete=no,device-name=${temp_disk}" \
  --shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring
vm_created="yes"

wait_for_iap_ssh_readiness
copy_bootstrap_inputs

remote_command="$(cat <<'REMOTE'
set -euo pipefail
cd /tmp/bbr-bootstrap-inputs
sha256sum -c bootstrap-inputs.sha256
sudo dpkg --unpack ./*.deb
sudo dpkg --configure -a
tar -xzf minisign-0.12-linux.tar.gz minisign-linux/x86_64/minisign
sudo install -o root -g root -m 0755 minisign-linux/x86_64/minisign /usr/local/bin/minisign
for tool in bash curl sha256sum minisign jq tar unzstd; do
  command -v "$tool"
done
[[ "$(minisign -v 2>&1)" == "minisign 0.12" ]]
jq -e \
  --arg bash "$(bash --version | head -1)" \
  --arg curl "$(curl --version | head -1)" \
  --arg sha256sum "$(sha256sum --version | head -1)" \
  --arg jq_version "$(jq --version)" \
  --arg tar_version "$(tar --version | head -1)" \
  --arg unzstd "$(zstd --version | head -1)" \
  '(.expected_tools.bash as $v | $bash | contains($v)) and
   (.expected_tools.curl as $v | $curl | contains($v)) and
   (.expected_tools.sha256sum as $v | $sha256sum | contains($v)) and
   (.expected_tools.jq as $v | $jq_version | contains($v)) and
   (.expected_tools.tar as $v | $tar_version | contains($v)) and
   (.expected_tools.unzstd as $v | $unzstd | contains($v))' \
  bootstrap-image-inputs.json
sudo rm -rf -- /tmp/bbr-bootstrap-inputs
sudo rm -f /var/cache/apt/archives/*.deb
sudo find /var/log -type f -exec sh -c ': > "$1"' _ {} \;
sudo rm -f /root/.bash_history /home/*/.bash_history
sudo rm -f /etc/ssh/ssh_host_*
sudo truncate -s 0 /etc/machine-id
sudo rm -f /var/lib/dbus/machine-id
sudo rm -rf -- /root/.ssh /home/*/.ssh
REMOTE
)"
gcloud compute ssh "$temp_vm" \
  --project="$project" --zone="$zone" --tunnel-through-iap \
  --command="$remote_command"

gcloud compute instances stop "$temp_vm" --project="$project" --zone="$zone"
gcloud compute images create "$target_image" \
  --project="$project" \
  --source-disk="$temp_disk" \
  --source-disk-zone="$zone" \
  --architecture=X86_64 \
  --guest-os-features=UEFI_COMPATIBLE

image_json="$(gcloud compute images describe "$target_image" --project="$project" --format=json)"
[[ "$(jq -r '.name' <<<"$image_json")" == "$target_image" ]] ||
  fail "created image name mismatch"
[[ "$(jq -r '.selfLink | sub("^https://www.googleapis.com/compute/v1/"; "")' <<<"$image_json")" == "$target_self_link" ]] ||
  fail "created image self-link mismatch"
[[ "$(jq -r '.status' <<<"$image_json")" == "READY" ]] ||
  fail "created image is not READY"
jq -e '[.guestOsFeatures[]?.type] | index("UEFI_COMPATIBLE") != null' \
  >/dev/null <<<"$image_json" || fail "created image lacks UEFI_COMPATIBLE guest feature"

gcloud compute instances delete "$temp_vm" --project="$project" --zone="$zone" --quiet
vm_created="no"
gcloud compute disks delete "$temp_disk" --project="$project" --zone="$zone" --quiet
disk_created="no"
echo "Image bake completed and temporary resources were removed."
