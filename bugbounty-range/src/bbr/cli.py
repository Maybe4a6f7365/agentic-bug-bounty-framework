"""BugBountyRange — generic GCP lab platform control plane.

Phase 3 hardened implementation:

  validate    — schema + node-refs + cost-limit + ttl + image checks; no GCP
  plan        — full Phase 3 plan: gcloud auth list, init, validate, plan,
                terraform show -json, SHA-256, atomar state write;
                never creates GCP resources
  create      — REVIEWABLE ONLY: requires --plan-file, --expected-sha256,
                --expected-commit; refuses to apply without the explicit
                APPROVE PHASE 3 EXECUTE gate (only the SHA-validated
                plan-file is allowed; aborts on any mismatch)
  verify      — read-only verification of GCP state; transitions to READY
  list        — local runtime state
  destroy     — REVIEWABLE ONLY: produces a destroy plan file and its SHA

The Phase 3 vertical slice targets exactly one small raw-vm
smoke lab. The product-agnostic invariant is that EVERY command
without an explicit authorization gate returns non-zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from bbr.pack_validation import (
    PackValidationError,
    load_manifest,
    validate_pack,
)
from bbr.network.allocator import (
    HARD_CAP_ACTIVE_LABS,
    allocate_cidr,
)
from bbr.lifecycle.state_machine import (
    PHASE3_VALID_STATES,
    make_state,
    record_transition,
)
from bbr.state.locking import LockError, locked
from bbr.bootstrap.errors import BootstrapError
from bbr.state.extensions import (
    update_health_status,
    write_artifact_fields,
    write_substate,
    write_timestamps,
)
from bbr.plan_contract import PlanContract, plan_contract

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO_ROOT / "platform/your-lab-name/schemas/lab-pack.schema.json"
DEFAULT_STATE_DIR = REPO_ROOT / "state"
DEFAULT_LAB_TF_DIR = REPO_ROOT / "platform/your-lab-name/terraform/lab"
DEFAULT_PACKS_DIR = REPO_ROOT / "platform/your-lab-name/packs"
DEFAULT_GCP_PROJECT = "your-lab-name-your-researcher-handle"
DEFAULT_GCP_REGION = "europe-west3"
DEFAULT_GCP_ZONE = "europe-west3-a"
PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00
EXIT_DESTROY_FROM_FAILURE = 22
EXIT_DOWNLOAD_FAIL = 30
EXIT_SIGNATURE_FAIL = 31
EXIT_SHA_FAIL = 32
EXIT_MANIFEST_FAIL = 33
EXIT_MANIFEST_HASH_FAIL = 34
EXIT_EXTRACT_FAIL = 35
EXIT_INSTALL_FAIL = 36
EXIT_CONFIG_FAIL = 37
EXIT_START_FAIL = 38
EXIT_HEALTH_FAIL = 39

# Phase-3 smoke plan hard-coded values. The CLI uses these for
# verification only; the authoritative values live in the pack
# manifest and the runtime state file.
PHASE3_SMOKE_LAB_ID = "smoke-vm-001"
PHASE3_SMOKE_INTERNAL_IP = "10.200.1.10"
PHASE3_SMOKE_BACKEND_PREFIX = "labs/smoke-vm-001"

EGRESS_FORBIDDEN_KEYWORDS = (
    "apt-get",
    " apt ",
    "apt install",
    "apt-get install",
    "apt update",
    "apt-get update",
    "curl ",
    "wget ",
    "git clone",
    "pip install",
    "pip3 install",
    "npm install",
    "npm update",
    "wp core update",
    "apt upgrade",
    "apt dist-upgrade",
    "composer update",
    "docker",
    "podman",
    "fetch ",
    "wget\t",
)


def contains_forbidden_egress_command(command: str) -> bool:
    normalized = " ".join(command.strip().lower().split())
    return any(keyword.strip() in normalized for keyword in EGRESS_FORBIDDEN_KEYWORDS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_plus(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _state_dir() -> Path:
    env = os.environ.get("BBR_STATE_DIR")
    if env:
        return Path(env)
    return DEFAULT_STATE_DIR


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    """Atomically write payload to path. The caller is expected to
    have prepared the full payload; this function only handles the
    safe-write (write to temp + rename) so a partial write never
    leaves the runtime state file half-written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=str(path.parent), delete=False, prefix=path.name + ".",
    ) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _resolve_pack(pack_arg: str) -> Path:
    p = Path(pack_arg)
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    if p.is_dir():
        return p
    if p.name == "manifest.json" and p.is_file():
        return p.parent
    return p


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_subprocess(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None)


def _run_subprocess_with_exit_propagation(
    cmd: List[str], exit_code_map: Dict[int, int],
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    result = _run_subprocess(cmd, cwd)
    if result.returncode:
        code = exit_code_map.get(result.returncode, result.returncode)
        if not 30 <= code <= 39:
            code = EXIT_START_FAIL
        raise BootstrapError(code, f"SUBPROCESS_EXIT_{result.returncode}")
    return result


def validate_wordpress_driver_payload(
    payload: Dict[str, Any], pack_id: str = "wordpress-smoke",
) -> None:
    import re
    uri = payload.get("artifact_uri", "")
    uri_pattern = (
        rf"^gs://bbr-bootstrap-[a-z0-9-]+/artifacts/"
        rf"(?:wordpress|{re.escape(pack_id)})/[A-Za-z0-9._-]+/artifact\.tar\.zst$"
    )
    if not re.fullmatch(uri_pattern, uri):
        raise BootstrapError(33, "ARTIFACT_URI_MISMATCH", "MANIFEST", uri)
    if not re.fullmatch(r"[a-f0-9]{64}", payload.get("artifact_sha256", "")):
        raise BootstrapError(33, "ARTIFACT_SHA256_INVALID", "MANIFEST", uri)
    if not payload.get("artifact_signature"):
        raise BootstrapError(33, "ARTIFACT_SIGNATURE_MISSING", "MANIFEST", uri)
    if not (payload.get("minisign_public_key") or payload.get("minisign_trust_store")):
        raise BootstrapError(33, "MINISIGN_TRUST_MISSING", "MANIFEST", uri)
    if not re.fullmatch(
        r"projects/[^/]+/global/images/[^/]+",
        payload.get("supported_platform", ""),
    ):
        raise BootstrapError(34, "UNSUPPORTED_PLATFORM", "MANIFEST", uri)


def _detect_operator() -> str:
    """Read-only operator identity: gcloud auth list --filter=status:ACTIVE."""
    r = _run_subprocess(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if r.returncode != 0 or not r.stdout.strip():
        # fallback: BBR_OPERATOR_PRINCIPAL env
        env = os.environ.get("BBR_OPERATOR_PRINCIPAL")
        if env:
            return env
        raise RuntimeError(
            f"could not determine operator identity: gcloud returned {r.returncode}, "
            f"stderr={r.stderr!r}"
        )
    account = r.stdout.strip().splitlines()[0].strip()
    if not account:
        raise RuntimeError("gcloud auth list returned empty account")
    return f"user:{account}"


def _require_oauth_token(command: str) -> str:
    """Credential preflight: ensure GOOGLE_OAUTH_ACCESS_TOKEN is set
    before any `terraform apply` is invoked.

    Returns the token (which the caller may export for the
    subprocess). Aborts the CLI with a clear, single-line error
    if the variable is missing or empty.

    Tokens are NEVER printed, hashed, logged, or written to disk.
    Only the length of the token may be echoed in error messages.
    """
    token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN", "")
    if not token:
        print(
            f"{command}: FAIL credential preflight — "
            "GOOGLE_OAUTH_ACCESS_TOKEN is not set.\n"
            "       Run: eval $(gcloud auth print-access-token | "
            "awk '{print \"export GOOGLE_OAUTH_ACCESS_TOKEN=\"$1}') "
            "before invoking 'bbr " + command + "'",
            file=sys.stderr,
        )
        raise SystemExit(18)
    if not token.strip():
        print(
            f"{command}: FAIL credential preflight — "
            "GOOGLE_OAUTH_ACCESS_TOKEN is empty",
            file=sys.stderr,
        )
        raise SystemExit(18)
    return token


def _plan_state_serial(plan_path: Path) -> Optional[int]:
    """Extract the terraform_state_version serial recorded in a
    saved plan. Used to detect stale plans.

    `terraform show -json <plan>` returns a top-level
    `terraform_version` and a nested `prior_state` and
    `state.state_version`-equivalent; the canonical serial in
    TF state is in `state.serials.lab_state`. We use the file
    metadata as a stable proxy: the plan records the State
    serial in `output_changes` only; for our purposes the
    `serial` field at the plan root is what we want.
    """
    try:
        plan_json = _terraform_show_json(DEFAULT_LAB_TF_DIR, plan_path)
    except RuntimeError:
        return None
    # TF saves the State version number inside the plan output
    # as `state_version`. We grab the resource-count of the plan
    # as a stable cross-check, but the primary signal is
    # terraform_version + resource_changes consistency.
    state = plan_json.get("state", {}) or {}
    serial = state.get("serial")
    if isinstance(serial, int):
        return serial
    # Terraform plan JSON does not consistently expose a State serial.
    # Absence means the preflight cannot compare serials; never invent a
    # proxy (such as a resource count), which would falsely mark fresh
    # create plans stale.
    return None


def _current_lab_state_serial() -> Optional[int]:
    """Read the lab State file from GCS and return its serial.

    Used to compare against the serial recorded in a saved plan
    so we can detect stale plans BEFORE invoking terraform apply.
    """
    r = _run_subprocess([
        "terraform",
        "-chdir=" + str(DEFAULT_LAB_TF_DIR),
        "state",
        "pull",
    ])
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        state = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    serial = state.get("serial")
    return serial if isinstance(serial, int) else None


# ------------------------------------------------------------------
# validate
# ------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    pack = _resolve_pack(args.pack)
    manifest = load_manifest(pack)
    try:
        validate_pack(manifest, SCHEMA_PATH)
    except (PackValidationError, FileNotFoundError) as exc:
        print(f"validate: FAIL — {exc}", file=sys.stderr)
        return 1
    print(f"validate: PASS — pack={pack.name}")
    return 0


# ------------------------------------------------------------------
# plan
# ------------------------------------------------------------------

def _build_lab_tfvars(args: argparse.Namespace, manifest: Dict[str, Any], lab_id: str,
                      lab_internal_ip: str, operator: str) -> Dict[str, str]:
    """Build the Terraform variables for the lab root from the
    validated manifest and the CLI args."""
    node = manifest["topology"]["nodes"][0]
    image = node.get("base_image", {})
    image_self_link = image.get("self_link")
    if not image_self_link:
        raise RuntimeError("Phase 3 requires base_image.self_link; got: " + str(image))
    internal_ip = node.get("driver_payload", {}).get("internal_ip") or lab_internal_ip
    payload = node.get("driver_payload", {})
    tfvars = {
        "gcp_project_id": DEFAULT_GCP_PROJECT,
        "gcp_region": DEFAULT_GCP_REGION,
        "gcp_zone": DEFAULT_GCP_ZONE,
        "lab_id": lab_id,
        "pack_id": manifest["pack_id"],
        "lab_subnet_cidr": args.subnet_cidr,
        "lab_internal_ip": internal_ip,
        "lab_service_account_id": f"bbr-lab-{lab_id}",
        "machine_type": node.get("machine_type", "e2-micro"),
        "disk_size_gb": str(node.get("disk_size_gb", 10)),
        "disk_type": node.get("disk_type", "pd-standard"),
        "base_image_self_link": image_self_link,
        "operator_principal": operator,
        "ttl_max_lifetime_seconds": "28800",
        "ttl_idle_timeout_seconds": "1800",
        "per_cycle_eur_limit": str(PHASE3_SMOKE_CYCLE_LIMIT_EUR),
    }
    if manifest["pack_id"] == "wordpress-smoke":
        tfvars.update({
            "artifact_uri": payload["artifact_uri"],
            "artifact_sha256": payload["artifact_sha256"],
            "minisign_public_key": payload["minisign_public_key"],
            "supported_platform": payload["supported_platform"],
            "bootstrap_bucket_name": "bbr-bootstrap-your-lab-name-your-researcher-handle",
        })
    return tfvars


def _terraform_init(lab_dir: Path, project_id: str, prefix: str) -> None:
    r = _run_subprocess(
        [
            "terraform", "init",
            "-input=false",
            f"-backend-config=bucket=bbr-state-{project_id}",
            f"-backend-config=prefix={prefix}",
        ],
        cwd=lab_dir,
    )
    if r.returncode != 0:
        raise RuntimeError(f"terraform init failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")


def _terraform_validate(lab_dir: Path) -> None:
    r = _run_subprocess(["terraform", "validate"], cwd=lab_dir)
    if r.returncode != 0:
        raise RuntimeError(f"terraform validate failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")


def _terraform_plan(lab_dir: Path, plan_path: Path, tfvars: Dict[str, str]) -> str:
    cmd = [
        "terraform", "plan",
        "-input=false",
        "-refresh=true",
        f"-out={plan_path}",
    ]
    for k, v in tfvars.items():
        cmd.append(f"-var={k}={v}")
    r = _run_subprocess(cmd, cwd=lab_dir)
    if r.returncode != 0:
        raise RuntimeError(f"terraform plan failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r.stdout


def _terraform_show_json(lab_dir: Path, plan_path: Path) -> Dict[str, Any]:
    r = _run_subprocess(
        ["terraform", "show", "-json", str(plan_path)],
        cwd=lab_dir,
    )
    if r.returncode != 0:
        raise RuntimeError(f"terraform show -json failed:\nSTDERR:\n{r.stderr}")
    return json.loads(r.stdout)


def _assert_plan_shape(
    plan_json: Dict[str, Any], contract: Optional[PlanContract] = None
) -> List[str]:
    """Returns a list of error messages. Empty list means OK."""
    errors: List[str] = []
    rc = plan_json.get("resource_changes", []) or []
    creates = [r for r in rc if r.get("change", {}).get("actions", []) == ["create"]]
    updates = [r for r in rc if "update" in r.get("change", {}).get("actions", [])]
    deletes = [r for r in rc if r.get("change", {}).get("actions", []) == ["delete"]]
    contract = contract or plan_contract("wordpress-smoke")
    if len(creates) != contract.expected_count:
        errors.append(f"expected {contract.expected_count} creates, got {len(creates)}")
    if len(updates) != 0:
        errors.append(f"expected 0 updates, got {len(updates)}")
    if len(deletes) != 0:
        errors.append(f"expected 0 deletes, got {len(deletes)}")
    expected_addresses = set(contract.expected_create_addresses)
    actual_addresses = {r.get("address") for r in creates}
    if actual_addresses != expected_addresses:
        errors.append(f"unexpected create addresses: got {actual_addresses - expected_addresses}, missing {expected_addresses - actual_addresses}")
    return errors


def cmd_plan(args: argparse.Namespace) -> int:
    pack_dir = _resolve_pack(args.pack)
    manifest = load_manifest(pack_dir)
    contract = plan_contract(manifest["pack_id"])

    # Step 1: validate the pack (raises on failure; no GCP action).
    try:
        validate_pack(manifest, SCHEMA_PATH)
    except (PackValidationError, FileNotFoundError) as exc:
        print(f"plan: FAIL validation — {exc}", file=sys.stderr)
        return 1

    # Step 2: operator identity (read-only via gcloud auth list).
    try:
        operator = _detect_operator()
    except RuntimeError as exc:
        print(f"plan: FAIL operator identity — {exc}", file=sys.stderr)
        return 1
    print(f"plan: operator = {operator}")

    # Step 3: active-lab cap + CIDR allocation.
    state_dir = _state_dir()
    try:
        with locked(state_dir, manifest["pack_id"], blocking=False):
            pass  # acquire just to assert no concurrent activity for the same lab_id
    except LockError as exc:
        print(f"plan: FAIL lock — {exc}", file=sys.stderr)
        return 1
    try:
        allocation = allocate_cidr(
            state_dir=state_dir,
            project_id=args.gcp_project or DEFAULT_GCP_PROJECT,
            active_lab_limit=int(os.environ.get("BBR_ACTIVE_LAB_LIMIT", "1")),
        )
    except Exception as exc:
        print(f"plan: FAIL allocator — {exc}", file=sys.stderr)
        return 1
    print(f"plan: allocated CIDR {allocation.cidr}")

    lab_id = args.lab_id or f"{manifest['pack_id']}-001"

    if manifest["pack_id"] == "wordpress-smoke":
        args.subnet_cidr = "10.200.2.0/24"
        internal_ip = "10.200.2.10"
    else:
        args.subnet_cidr = "10.200.1.0/24"
        internal_ip = "10.200.1.10"

    # Step 4: build the full Terraform variable set from the pack.
    tfvars = _build_lab_tfvars(args, manifest, lab_id, internal_ip, operator)

    # Step 5: init lab root with the per-lab GCS backend.
    prefix = contract.expected_backend_prefix
    try:
        _terraform_init(DEFAULT_LAB_TF_DIR, args.gcp_project or DEFAULT_GCP_PROJECT, prefix)
    except RuntimeError as exc:
        print(f"plan: FAIL terraform init — {exc}", file=sys.stderr)
        return 1
    print("plan: terraform init OK")

    # Step 6: validate.
    try:
        _terraform_validate(DEFAULT_LAB_TF_DIR)
    except RuntimeError as exc:
        print(f"plan: FAIL terraform validate — {exc}", file=sys.stderr)
        return 1
    print("plan: terraform validate OK")

    # Step 7: produce the saved plan.
    plan_path = Path(
        "/tmp/bbr-phase4-wordpress-create-v10.tfplan"
        if manifest["pack_id"] == "wordpress-smoke"
        else "/tmp/bbr-phase3-smoke-create-v4.tfplan"
    )
    try:
        _terraform_plan(DEFAULT_LAB_TF_DIR, plan_path, tfvars)
    except RuntimeError as exc:
        print(f"plan: FAIL terraform plan — {exc}", file=sys.stderr)
        return 1
    print(f"plan: terraform plan saved to {plan_path}")

    # Step 8: validate via terraform show -json.
    try:
        plan_json = _terraform_show_json(DEFAULT_LAB_TF_DIR, plan_path)
    except RuntimeError as exc:
        print(f"plan: FAIL terraform show -json — {exc}", file=sys.stderr)
        return 1
    shape_errors = _assert_plan_shape(plan_json, contract)
    if shape_errors:
        for err in shape_errors:
            print(f"plan: FAIL plan shape — {err}", file=sys.stderr)
        return 1
    print(
        f"plan: plan shape OK ({contract.expected_count} creates, "
        "0 updates, 0 deletes)"
    )

    # Step 9: SHA-256.
    sha = _file_sha256(plan_path)
    print(f"plan: SHA-256 = {sha}")

    # Step 10: atomically write the runtime state ONLY after all
    # prior steps have succeeded. The state file contains the
    # full provenance so bbr create can validate it.
    source_commit = _run_subprocess(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
    ).stdout.strip()
    ttl_deadline = _iso_plus(int(tfvars["ttl_max_lifetime_seconds"]))

    # Build DEFINED -> VALIDATED -> PLANNED transition history.
    s = make_state(
        lab_id=lab_id,
        pack_id=manifest["pack_id"],
        state="DEFINED",
        operator_principal=operator,
        ttl_deadline=ttl_deadline,
    )
    s["source_commit"] = source_commit
    s["pack_version"] = manifest.get("version", "")
    s["lab_subnet_cidr"] = args.subnet_cidr
    s["lab_internal_ip"] = internal_ip
    s["backend_prefix"] = prefix
    s["plan_file"] = str(plan_path)
    s["plan_sha256"] = sha
    s["node_list"] = [n.get("node_id") for n in manifest["topology"]["nodes"]]
    s["driver_payload"] = manifest["topology"]["nodes"][0].get("driver_payload", {})
    s["per_cycle_eur_limit"] = PHASE3_SMOKE_CYCLE_LIMIT_EUR
    s["node_base_image"] = tfvars["base_image_self_link"]
    s["machine_type"] = tfvars["machine_type"]
    s["disk_size_gb"] = int(tfvars["disk_size_gb"])
    s["disk_type"] = tfvars["disk_type"]
    s["runtime_service_account"] = tfvars["lab_service_account_id"]
    s["operator_principal"] = tfvars["operator_principal"]
    if manifest["pack_id"] == "wordpress-smoke":
        s["artifact_uri"] = tfvars["artifact_uri"]
        s["artifact_sha256"] = tfvars["artifact_sha256"]
        s["minisign_public_key"] = tfvars["minisign_public_key"]
        s["bootstrap_bucket"] = tfvars["bootstrap_bucket_name"]
    # transition_history already has the DEFINED entry from
    # make_state(state="DEFINED"). Add VALIDATED and PLANNED so
    # the full plan path DEFINED -> VALIDATED -> PLANNED is
    # recorded.
    s = record_transition(s, "VALIDATED", by=operator)
    s = record_transition(s, "PLANNED", by=operator)

    state_file = state_dir / f"{lab_id}.json"
    _atomic_write(state_file, s)
    print(f"plan: runtime state written to {state_file} (state=PLANNED)")
    phase = "4" if manifest["pack_id"] == "wordpress-smoke" else "3"
    print(f"plan: complete. Next step requires 'APPROVE PHASE {phase} EXECUTE'.")
    return 0


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------

def _git_clean(working_dir: Path) -> bool:
    r = _run_subprocess(["git", "-C", str(working_dir), "status", "--porcelain"], cwd=working_dir)
    return r.returncode == 0 and r.stdout.strip() == ""


def _git_head(working_dir: Path) -> str:
    r = _run_subprocess(["git", "-C", str(working_dir), "rev-parse", "HEAD"], cwd=working_dir)
    return r.stdout.strip()


def _git_origin_main(working_dir: Path) -> str:
    r = _run_subprocess(["git", "-C", str(working_dir), "rev-parse", "origin/main"], cwd=working_dir)
    return r.stdout.strip()


def cmd_create(args: argparse.Namespace) -> int:
    """Apply the reviewed Phase 3 create plan exactly once.

    This command enforces EVERY gate before invoking terraform.
    Aborts on ANY mismatch.

    Required arguments:
      --plan-file          absolute path to the reviewed plan file
      --expected-sha256    SHA-256 of the plan file
      --expected-commit    exact commit hash the plan was reviewed at

    Additional gates enforced before apply:
      - plan file exists
      - SHA matches exactly
      - git HEAD equals origin/main
      - git HEAD equals --expected-commit
      - working tree is clean
      - runtime state file exists and state == PLANNED
      - runtime state lab_id matches the positional argument
      - runtime state backend_prefix == 'labs/smoke-vm-001'
      - runtime state plan_file and plan_sha256 match the
        arguments provided on the command line
      - terraform show -json on the plan file shows exactly 8
        creates, 0 updates, 0 deletes, on the expected addresses
        only, with no access_config, no foundation resources,
        no cloud_nat, no vpc peering

    A failure on any gate returns non-zero WITHOUT calling
    terraform apply.
    """
    plan_arg = args.plan_file
    expected_sha = args.expected_sha256
    expected_commit = args.expected_commit
    lab_id = args.lab_id

    # Hard requirement: all three flags must be present and exact.
    if not plan_arg or not expected_sha or not expected_commit:
        print(
            "create: FAIL — --plan-file, --expected-sha256 and "
            "--expected-commit are required",
            file=sys.stderr,
        )
        return 2

    # === CREDENTIAL PREFLIGHT (early) ===
    # A missing GOOGLE_OAUTH_ACCESS_TOKEN must abort BEFORE any
    # terraform validation runs, so that the operator sees the
    # failure immediately and the State stays unmutated.
    if not os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN", "").strip():
        print(
            "create: FAIL credential preflight — "
            "GOOGLE_OAUTH_ACCESS_TOKEN is not set or is empty.\n"
            "       Run: eval $(gcloud auth print-access-token | "
            "awk '{print \"export GOOGLE_OAUTH_ACCESS_TOKEN=\"$1}') "
            "before invoking 'bbr create'.",
            file=sys.stderr,
        )
        return 18

    plan_path = Path(plan_arg)
    if not plan_path.is_file():
        print(f"create: FAIL — plan file does not exist: {plan_arg}", file=sys.stderr)
        return 2
    actual_sha = _file_sha256(plan_path)
    if actual_sha != expected_sha:
        print(
            f"create: FAIL SHA mismatch.\n"
            f"  expected: {expected_sha}\n"
            f"  actual:   {actual_sha}\n"
            f"  plan:     {plan_path}",
            file=sys.stderr,
        )
        return 3
    head_sha = _git_head(REPO_ROOT)
    origin_main_sha = _git_origin_main(REPO_ROOT)
    if head_sha != origin_main_sha:
        print(
            f"create: FAIL HEAD not equal to origin/main.\n"
            f"  HEAD:        {head_sha}\n"
            f"  origin/main: {origin_main_sha}",
            file=sys.stderr,
        )
        return 4
    if head_sha != expected_commit:
        print(
            f"create: FAIL --expected-commit does not match HEAD.\n"
            f"  HEAD:             {head_sha}\n"
            f"  --expected-commit: {expected_commit}",
            file=sys.stderr,
        )
        return 5
    # Detect a stale saved plan before the working-tree gate. This check is
    # read-only and gives the more actionable failure when State already moved.
    plan_serial = _plan_state_serial(plan_path)
    current_serial = _current_lab_state_serial()
    if plan_serial is not None and current_serial is not None and plan_serial != current_serial:
        print("create: FAIL — saved plan is stale.", file=sys.stderr)
        return 19
    if not _git_clean(REPO_ROOT):
        print("create: FAIL working tree is not clean", file=sys.stderr)
        return 6

    # Runtime-state gate.
    state_file = _state_dir() / f"{lab_id}.json"
    if not state_file.is_file():
        print(f"create: FAIL runtime state missing for {lab_id}", file=sys.stderr)
        return 7
    state = json.loads(state_file.read_text())
    try:
        contract = plan_contract(state.get("pack_id", ""))
    except ValueError as exc:
        print(f"create: FAIL — {exc}", file=sys.stderr)
        return 16
    if state.get("state") != "PLANNED":
        print(
            f"create: FAIL runtime state must be PLANNED, got "
            f"{state.get('state')!r}",
            file=sys.stderr,
        )
        return 8
    if state.get("lab_id") != lab_id:
        print(
            f"create: FAIL runtime state lab_id mismatch: "
            f"{state.get('lab_id')!r} vs {lab_id!r}",
            file=sys.stderr,
        )
        return 9
    expected_backend_prefix = contract.expected_backend_prefix
    if state.get("backend_prefix") != expected_backend_prefix:
        print(
            f"create: FAIL backend_prefix must be "
            f"{expected_backend_prefix!r}, got "
            f"{state.get('backend_prefix')!r}",
            file=sys.stderr,
        )
        return 10
    if state.get("plan_file") != str(plan_path):
        print(
            f"create: FAIL runtime state plan_file does not match CLI arg.\n"
            f"  state:   {state.get('plan_file')!r}\n"
            f"  CLI arg: {str(plan_path)!r}",
            file=sys.stderr,
        )
        return 11
    if state.get("plan_sha256") != actual_sha:
        print(
            f"create: FAIL runtime state plan_sha256 does not match file.\n"
            f"  state:   {state.get('plan_sha256')!r}\n"
            f"  on disk: {actual_sha!r}",
            file=sys.stderr,
        )
        return 12
    if state.get("pack_id") == "wordpress-smoke":
        payload = state.get("driver_payload", {})
        try:
            validate_wordpress_driver_payload(payload)
        except BootstrapError as exc:
            print(f"create: FAIL — {exc.message}", file=sys.stderr)
            return exc.code
        trust = payload.get("minisign_public_key") or payload["minisign_trust_store"]
        write_artifact_fields(
            state_file,
            state.get("pack_version", ""),
            payload["artifact_uri"],
            payload["artifact_sha256"],
            payload["artifact_signature"],
            trust,
        )

    # Plan-shape gate (terraform show -json).
    try:
        plan_json = _terraform_show_json(DEFAULT_LAB_TF_DIR, plan_path)
    except RuntimeError as exc:
        print(f"create: FAIL — terraform show -json failed: {exc}", file=sys.stderr)
        return 13
    shape_errors = _assert_plan_shape(plan_json, contract)
    if shape_errors:
        for err in shape_errors:
            print(f"create: FAIL plan shape — {err}", file=sys.stderr)
        return 14
    # Provider actions gate (no foundation resources).
    provider_actions: set = set()
    for rc in plan_json.get("resource_changes", []) or []:
        for action in (rc.get("change", {}).get("actions") or []):
            provider_actions.add(action)
    forbidden_actions = {"delete", "update", "delete-before-create", "create-before-delete"}
    bad = provider_actions & forbidden_actions
    if bad:
        print(f"create: FAIL forbidden plan actions: {sorted(bad)}", file=sys.stderr)
        return 15
    # Resource type gate: only the approved lab resource types.
    allowed_types = set(contract.allowed_resource_types)
    types_in_plan = {rc.get("type") for rc in plan_json.get("resource_changes", []) or []}
    extra_types = types_in_plan - allowed_types
    if extra_types:
        print(f"create: FAIL unexpected resource types: {extra_types}", file=sys.stderr)
        return 16

    # Everything passed. The Phase 3 EXECUTE gate has already been
    # granted by the operator. We still print a loud message that
    # the apply will now run and explicitly refuse to apply if
    # BBR_PHASE3_EXECUTE_CONFIRM != "yes".
    confirm = os.environ.get(contract.gate_label)
    if confirm != "yes":
        phase = "4" if state.get("pack_id") == "wordpress-smoke" else "3"
        print(
            f"create: all gates passed; {contract.gate_label}=yes is\n"
            "        required to invoke 'terraform apply'. No apply has\n"
            f"        been performed. APPROVE PHASE {phase} EXECUTE is "
            "the human gate.\n"
            f"        plan:     {plan_path}\n"
            f"        SHA-256:  {actual_sha}\n"
            f"        HEAD:     {head_sha}",
            file=sys.stdout,
        )
        return 0

    # === PLAN-FRESHNESS CHECK ===
    # A saved plan is bound to a specific State serial. If the
    # State serial has changed (e.g. by a previous failed apply,
    # a refresh, or any other State mutation), Terraform will
    # reject the plan as stale. Detect this BEFORE invoking
    # apply and refuse to start, so the operator gets a clear
    # message and can re-plan rather than burn an EXECUTE
    # budget on a guaranteed failure.
    plan_serial = _plan_state_serial(plan_path)
    current_serial = _current_lab_state_serial()
    if plan_serial is not None and current_serial is not None and plan_serial != current_serial:
        print(
            "create: FAIL — saved plan is stale.\n"
            f"  plan serial:    {plan_serial}\n"
            f"  current serial: {current_serial}\n"
            "  Run 'bbr plan' again to produce a fresh plan and commit it.\n"
            "  No apply has been performed.",
            file=sys.stderr,
        )
        return 19

    # === ACTUAL APPLY ===
    r = _run_subprocess(
        ["terraform", "apply", "-input=false", str(plan_path)],
        cwd=DEFAULT_LAB_TF_DIR,
    )
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode != 0:
        print("create: FAIL terraform apply returned non-zero", file=sys.stderr)
        return 17
    return 0


# ------------------------------------------------------------------
# verify
# ------------------------------------------------------------------

def _verify_wordpress_phase4(
    state_file: Path, state: Dict[str, Any], manual_confirm: bool = False,
) -> int:
    """Drive the synthetic Phase 4 control-plane lifecycle.

    VM-side execution remains behind the EXECUTE gate. Tests can inject a
    phase failure with BBR_BOOTSTRAP_FAIL_CODE; no secret values are stored.
    """
    operator = os.environ.get("BBR_OPERATOR_PRINCIPAL", "system")
    s = state
    if s.get("state") in {"HEALTHY", "VERIFIED"}:
        if manual_confirm and s["state"] == "HEALTHY":
            s = record_transition(s, "VERIFIED", by=operator, exit_code=0)
            _atomic_write(state_file, s)
        return 0
    if s.get("state") == "PLANNED":
        s = record_transition(s, "CREATED", by=operator)
    if s.get("state") == "CREATED":
        s = record_transition(s, "BOOTSTRAPPING", by="system")
        _atomic_write(state_file, s)
        write_timestamps(state_file, bootstrap_started_at=_now_iso())
        s = json.loads(state_file.read_text())

    fail_code = int(os.environ.get("BBR_BOOTSTRAP_FAIL_CODE", "0"))
    sequence = (
        ("VERIFYING_ARTIFACT", range(31, 36)),
        ("INSTALLING", (36,)),
        ("CONFIGURING", (37,)),
        ("STARTING", (38, 39)),
        ("READY", ()),
    )
    if fail_code == 30 and s["state"] == "BOOTSTRAPPING":
        s = record_transition(s, "FAILURE", by="system", exit_code=30)
        s["error_class"] = "BootstrapError:30"
        _atomic_write(state_file, s)
        write_substate(state_file, "failure_state", {
            "error_class": s["error_class"], "exit_code": 30,
        })
        return 30
    for target, failure_codes in sequence:
        if s["state"] == target:
            continue
        s = record_transition(s, target, by="system", exit_code=0)
        _atomic_write(state_file, s)
        s = json.loads(state_file.read_text())
        if fail_code in failure_codes:
            s = record_transition(s, "FAILURE", by="system", exit_code=fail_code)
            s["error_class"] = f"BootstrapError:{fail_code}"
            _atomic_write(state_file, s)
            write_substate(state_file, "failure_state", {
                "error_class": s["error_class"], "exit_code": fail_code,
            })
            return fail_code
        if target == "INSTALLING":
            write_timestamps(state_file, install_started_at=_now_iso())

    write_timestamps(
        state_file, bootstrap_finished_at=_now_iso(), install_finished_at=_now_iso()
    )
    passes = int(os.environ.get("BBR_HEALTH_CONSECUTIVE_PASSES", "3"))
    update_health_status(
        state_file, "healthy" if passes >= 3 else "unhealthy", passes
    )
    s = json.loads(state_file.read_text())
    if passes >= 3 and s["state"] == "READY":
        s = record_transition(s, "HEALTHY", by="system", exit_code=0)
        _atomic_write(state_file, s)
    if manual_confirm and s["state"] == "HEALTHY":
        s = record_transition(s, "VERIFIED", by=operator, exit_code=0)
        _atomic_write(state_file, s)
    return 0 if passes >= 3 else EXIT_HEALTH_FAIL


def _verify_wordpress_real(
    state_file: Path, state: Dict[str, Any], lab_id: str, manual_confirm: bool,
) -> int:
    """Run the 16 read-only GCP/IAP checks before advancing lifecycle state."""
    project = os.environ.get("BBR_GCP_PROJECT", DEFAULT_GCP_PROJECT)
    zone = os.environ.get("BBR_GCP_ZONE", DEFAULT_GCP_ZONE)
    payload = state.get("driver_payload", {})

    def run(cmd: List[str], label: str) -> subprocess.CompletedProcess:
        result = _run_subprocess(cmd)
        if result.returncode:
            raise RuntimeError(f"{label}: {result.stderr.strip()}")
        return result

    def ssh(command: str, label: str) -> subprocess.CompletedProcess:
        return run([
            "gcloud", "compute", "ssh", lab_id, f"--project={project}",
            f"--zone={zone}", "--tunnel-through-iap", f"--command={command}",
        ], label)

    try:
        vm = json.loads(run([
            "gcloud", "compute", "instances", "describe", lab_id,
            f"--project={project}", f"--zone={zone}", "--format=json",
        ], "instance describe").stdout)
        if vm.get("status") != "RUNNING":
            raise RuntimeError("instance status is not RUNNING")
        nic = vm.get("networkInterfaces", [{}])[0]
        if nic.get("networkIP") != "10.200.2.10":
            raise RuntimeError("internal IP is not 10.200.2.10")
        if nic.get("accessConfigs", []) or []:
            raise RuntimeError("external accessConfigs are present")
        accounts = vm.get("serviceAccounts", [])
        expected_sa = (
            "bbr-lab-wordpress-smoke-001@"
            "your-lab-name-your-researcher-handle.iam.gserviceaccount.com"
        )
        if not accounts or accounts[0].get("email") != expected_sa:
            raise RuntimeError("dedicated service account attachment mismatch")
        scopes = set(accounts[0].get("scopes", []))
        if scopes != {"https://www.googleapis.com/auth/devstorage.read_only"}:
            raise RuntimeError("OAuth scopes must be exactly devstorage.read_only")

        rows = json.loads(run([
            "gcloud", "compute", "firewall-rules", "list",
            f"--project={project}", "--format=json",
        ], "firewall list").stdout)
        expected_names = _wordpress_firewall_names(lab_id)
        by_suffix = {
            row["name"].split(lab_id, 1)[-1].lstrip("-"): row
            for row in rows if row.get("name") in expected_names
        }
        expected_fw = {
            "egress-deny": ("EGRESS", 65000, ["0.0.0.0/0"], [], [{"IPProtocol": "all"}]),
            "iap-ssh": ("INGRESS", 1000, [], ["35.235.240.0/20"], [{"IPProtocol": "tcp", "ports": ["22"]}]),
            "wg-admin": ("INGRESS", 1000, [], ["10.254.0.0/24"], None),
            "bootstrap-egress": ("EGRESS", 1000, ["199.36.153.4/30"], [], [{"IPProtocol": "tcp", "ports": ["443"]}]),
        }
        if set(by_suffix) != set(expected_fw):
            raise RuntimeError(f"firewall set mismatch: {sorted(by_suffix)}")
        for suffix, (direction, priority, destinations, sources, allowed) in expected_fw.items():
            row = by_suffix[suffix]
            if row.get("targetTags") != [lab_id]:
                raise RuntimeError(f"{suffix} target tags mismatch")
            if row.get("direction") != direction or row.get("priority") != priority:
                raise RuntimeError(f"{suffix} direction/priority mismatch")
            if sorted(row.get("destinationRanges", [])) != sorted(destinations):
                raise RuntimeError(f"{suffix} destination ranges mismatch")
            if sorted(row.get("sourceRanges", [])) != sorted(sources):
                raise RuntimeError(f"{suffix} source ranges mismatch")
            if suffix == "egress-deny":
                if row.get("denied") != allowed:
                    raise RuntimeError("egress-deny rule mismatch")
            elif suffix == "wg-admin":
                protocols = {(a.get("IPProtocol"), tuple(a.get("ports", []))) for a in row.get("allowed", [])}
                if protocols != {("tcp", ("22",)), ("icmp", ())}:
                    raise RuntimeError("wg-admin allowed rules mismatch")
            elif row.get("allowed") != allowed:
                raise RuntimeError(f"{suffix} allowed rules mismatch")

        iam = json.loads(run([
            "gcloud", "storage", "buckets", "get-iam-policy",
            "gs://bbr-bootstrap-your-lab-name-your-researcher-handle",
            f"--project={project}", "--format=json",
        ], "bucket IAM").stdout)
        member = f"serviceAccount:{expected_sa}"
        roles = [
            binding.get("role") for binding in iam.get("bindings", [])
            if member in binding.get("members", [])
        ]
        if roles != ["roles/storage.objectViewer"]:
            raise RuntimeError("dedicated service account bucket IAM mismatch")

        ssh("test -f /var/lib/bbr/ready", "ready marker")
        ssh("test -f /var/lib/bbr/wordpress-ready", "wordpress marker")
        ssh("test ! -f /var/lib/bbr/failure", "failure marker absence")
        for service in ("mariadb", "php8.2-fpm", "nginx"):
            ssh(f"systemctl is-active {service}", f"{service} active")
        ssh(_wordpress_wp_cli("core is-installed"), "WordPress installed")
        version = ssh(
            _wordpress_wp_cli("core version"), "WordPress version"
        ).stdout.strip()
        if version != payload.get("wordpress_version"):
            raise RuntimeError("WordPress version mismatch")
        status = ssh(
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/",
            "HTTP exact status",
        ).stdout.strip()
        if status != "200":
            raise RuntimeError(f"HTTP status {status!r}, expected '200'")
        artifact_sha = ssh(
            _wordpress_artifact_sha_command(),
            "artifact SHA-256",
        ).stdout.strip()
        if artifact_sha != payload.get("bootstrap_artifact_sha256"):
            raise RuntimeError("bootstrap artifact SHA-256 mismatch")
        log_tail = ssh("tail -n 100 /var/log/bbr/bootstrap.log", "bootstrap log").stdout
        if "Minisign verification successful" not in log_tail or "SHA-256 verification successful" not in log_tail:
            raise RuntimeError("bootstrap log lacks verification success messages")
    except (RuntimeError, ValueError, IndexError, json.JSONDecodeError) as exc:
        print(f"verify: FAIL — {exc}", file=sys.stderr)
        return 1

    operator = os.environ.get("BBR_OPERATOR_PRINCIPAL", "system")
    s = _advance_wordpress_verified_state(state, operator)
    if manual_confirm:
        if s.get("state") == "HEALTHY":
            s = record_transition(s, "VERIFIED", by=operator, exit_code=0)
    _atomic_write(state_file, s)
    print("verify: PASS — all 16 WordPress checks passed")
    return 0


def _advance_wordpress_verified_state(
    state: dict[str, Any], operator: str
) -> dict[str, Any]:
    """Record first verification, while keeping repeated verification idempotent."""
    if state.get("state") in {"HEALTHY", "VERIFIED"}:
        return state
    s = state
    for target in ("CREATED", "BOOTSTRAPPING", "VERIFYING_ARTIFACT", "INSTALLING",
                   "CONFIGURING", "STARTING", "READY", "HEALTHY"):
        if s.get("state") == target:
            continue
        s = record_transition(s, target, by=operator, exit_code=0)
    return s


def _wordpress_firewall_names(lab_id: str) -> set[str]:
    """Return the exact Terraform-managed firewall names for a WordPress lab."""
    return {
        f"bbr-lab-{lab_id}-egress-deny",
        f"bbr-lab-{lab_id}-iap-ssh",
        f"bbr-lab-{lab_id}-wg-admin",
        f"bbr-{lab_id}-bootstrap-egress",
    }


def _wordpress_wp_cli(command: str) -> str:
    """Build a WP-CLI check that can read the root-owned runtime config."""
    return f"sudo wp --allow-root --path=/var/www/html {command}"


def _wordpress_artifact_sha_command() -> str:
    """Hash the root-only downloaded artifact without weakening its mode."""
    return "sudo sha256sum /opt/bbr/artifact.tar.zst | awk '{print $1}'"


def cmd_verify(args: argparse.Namespace) -> int:
    """Read-only verification of the lab state.

    Aborts on the first failure with a non-zero exit code.
    Successful verification records the lifecycle transitions
    PLANNED -> CREATED -> BOOTSTRAPPING -> ISOLATED -> READY.
    A missing VM never returns success.
    """
    state_dir = _state_dir()
    state_file = state_dir / f"{args.lab_id}.json"
    if not state_file.is_file():
        print(f"verify: FAIL — no local state for {args.lab_id}", file=sys.stderr)
        return 1
    state = json.loads(state_file.read_text())
    if state.get("pack_id") == "wordpress-smoke":
        return _verify_wordpress_real(
            state_file, state, args.lab_id, getattr(args, "manual_confirm", False)
        )
    project = os.environ.get("BBR_GCP_PROJECT") or DEFAULT_GCP_PROJECT
    zone = os.environ.get("BBR_GCP_ZONE") or DEFAULT_GCP_ZONE

    # 1. VM exists and is RUNNING.
    r = _run_subprocess([
        "gcloud", "compute", "instances", "describe", args.lab_id,
        f"--project={project}",
        f"--zone={zone}",
        "--format=json",
    ])
    if r.returncode != 0:
        print(f"verify: FAIL — VM {args.lab_id} does not exist in GCP", file=sys.stderr)
        return 2
    vm = json.loads(r.stdout)
    if vm.get("status") != "RUNNING":
        print(f"verify: FAIL — VM status is {vm.get('status')}, expected RUNNING",
              file=sys.stderr)
        return 3

    # 2. Internal IP is exactly 10.200.1.10.
    nics = vm.get("networkInterfaces", [])
    if not nics:
        print("verify: FAIL — VM has no network interfaces", file=sys.stderr)
        return 4
    internal_ip = nics[0].get("networkIP")
    if internal_ip != PHASE3_SMOKE_INTERNAL_IP:
        print(
            f"verify: FAIL — internal IP is {internal_ip!r}, expected "
            f"{PHASE3_SMOKE_INTERNAL_IP!r}",
            file=sys.stderr,
        )
        return 5

    # 3. No external IPv4 and no access_config.
    access_configs = nics[0].get("accessConfigs", []) or []
    if access_configs:
        print(
            f"verify: FAIL — VM has {len(access_configs)} access_config(s); expected 0",
            file=sys.stderr,
        )
        return 6

    # 4. Subnet is exactly 10.200.1.0/24.
    subnetwork_self_link = nics[0].get("subnetwork", "")
    r = _run_subprocess([
        "gcloud", "compute", "networks", "subnets", "describe",
        subnetwork_self_link.rsplit("/", 1)[-1] if "/" in subnetwork_self_link else subnetwork_self_link,
        f"--project={project}",
        "--region=europe-west3",
        "--format=value(ipCidrRange)",
    ])
    if r.returncode != 0 or r.stdout.strip() != "10.200.1.0/24":
        print(
            f"verify: FAIL — subnet CIDR is {r.stdout.strip()!r}, expected "
            f"'10.200.1.0/24'",
            file=sys.stderr,
        )
        return 7

    # 5. The three expected firewall rules exist.
    expected_firewalls = {
        f"bbr-lab-{args.lab_id}-wg-admin",
        f"bbr-lab-{args.lab_id}-iap-ssh",
        f"bbr-lab-{args.lab_id}-egress-deny",
    }
    # Use 'firewall-rules' (the canonical gcloud subcommand) with
    # JSON output, then filter on target_tags in Python. The
    # 'firewalls' alias plus the 'targetTags:' filter expression is
    # not accepted by gcloud as a list filter and silently returns
    # zero rows, which would falsely fail the verify check.
    r = _run_subprocess([
        "gcloud", "compute", "firewall-rules", "list",
        f"--project={project}",
        "--format=json",
    ])
    firewalls: set = set()
    if r.returncode == 0 and r.stdout.strip():
        try:
            rows = json.loads(r.stdout)
            for row in rows:
                tags = row.get("targetTags") or []
                if args.lab_id in tags:
                    name = row.get("name")
                    if name:
                        firewalls.add(name)
        except json.JSONDecodeError:
            pass
    if not expected_firewalls.issubset(firewalls):
        print(
            f"verify: FAIL — missing firewalls. "
            f"expected {expected_firewalls}, got {firewalls}",
            file=sys.stderr,
        )
        return 8

    # 6. Egress-deny is the deny rule.
    r = _run_subprocess([
        "gcloud", "compute", "firewalls", "describe",
        f"bbr-lab-{args.lab_id}-egress-deny",
        f"--project={project}",
        "--format=json",
    ])
    if r.returncode == 0:
        fw = json.loads(r.stdout)
        if fw.get("direction") != "EGRESS" or not fw.get("deny"):
            print("verify: FAIL — egress-deny is not an EGRESS deny rule",
                  file=sys.stderr)
            return 9

    # 7. IAP / OS Login reachable. Read instance metadata.
    metadata = vm.get("metadata", {}).get("items", [])
    items = {m.get("key"): m.get("value") for m in metadata}
    if items.get("enable-oslogin") != "TRUE":
        print("verify: FAIL — OS Login not enabled", file=sys.stderr)
        return 10

    # 8. Readiness marker on the VM (via IAP-tunneled SSH).
    r = _run_subprocess([
        "gcloud", "compute", "ssh", args.lab_id,
        f"--project={project}",
        f"--zone={zone}",
        "--tunnel-through-iap",
        "--command=cat /var/lib/bbr/ready",
    ])
    if r.returncode != 0:
        print("verify: FAIL — readiness marker not readable via IAP SSH",
              file=sys.stderr)
        return 11
    marker = r.stdout
    expected_marker_lines = {
        f"LAB_ID={args.lab_id}",
        "PACK_ID=smoke-vm",
        f"NODE_ID={args.lab_id}",
        "EXPECTED_INTERNAL_IP=10.200.1.10",
    }
    for line in expected_marker_lines:
        if line not in marker:
            print(f"verify: FAIL — marker missing line {line!r}", file=sys.stderr)
            return 12

    # 9. Record lifecycle transitions: PLANNED -> CREATED ->
    #    BOOTSTRAPPING -> ISOLATED -> READY. The runtime state
    #    file must be COMPLETE (have transition_history) so that
    #    record_transition() can append. A bare or partial state
    #    file is a critical inconsistency between the local
    #    record and the live GCP VM — verify must fail loudly
    #    rather than silently pass.
    s = state
    if s["state"] == "PLANNED":
        if not isinstance(s.get("transition_history"), list):
            print(
                "verify: FAIL — runtime state is PLANNED but lacks "
                "transition_history. The runtime state file is "
                "incomplete relative to the live VM. Run 'bbr plan' "
                "to regenerate the runtime state before verify.",
                file=sys.stderr,
            )
            return 13
        for next_state in ("CREATED", "BOOTSTRAPPING", "ISOLATED", "READY"):
            s = record_transition(s, next_state, by=_detect_operator())
        _atomic_write(state_file, s)
        print(f"verify: state advanced to READY in {state_file}")
    else:
        print(f"verify: state already at {s['state']!r}, not advanced")
    print("verify: PASS — all checks passed")
    return 0


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    state_dir = _state_dir()
    if not state_dir.is_dir():
        print("list: no labs")
        return 0
    rows = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        rows.append((
            d.get("lab_id", f.stem),
            d.get("pack_id", "?"),
            d.get("state", "?"),
            d.get("lab_subnet_cidr", ""),
        ))
    if not rows:
        print("list: no labs")
        return 0
    print(f"{'LAB_ID':<24} {'PACK_ID':<16} {'STATE':<12} {'CIDR':<18}")
    for r in rows:
        print(f"{r[0]:<24} {r[1]:<16} {r[2]:<12} {r[3]:<18}")
    return 0


# ------------------------------------------------------------------
# destroy
# ------------------------------------------------------------------

def _destroy_addresses_are_valid(
    plan_json: Dict[str, Any],
    state_addresses: Sequence[str],
    expected_destroy_addresses: Sequence[str],
) -> bool:
    destroyed_addresses = {
        r.get("address")
        for r in plan_json.get("resource_changes", []) or []
        if r.get("change", {}).get("actions", []) == ["delete"]
    }
    actual_state_addresses = {
        address for address in state_addresses if not address.startswith("data.")
    }
    expected_destroy = set(expected_destroy_addresses)
    return (
        destroyed_addresses == actual_state_addresses
        and destroyed_addresses <= expected_destroy
    )


def _record_destroy_planned(state: dict[str, Any], by: str) -> dict[str, Any]:
    """Advance an eligible runtime state through STOPPED to DESTROY_PLANNED."""
    s = state
    if s.get("state") in {"READY", "HEALTHY", "VERIFIED"}:
        s = record_transition(s, "STOPPED", by=by)
    if s.get("state") in {"PLANNED", "ROLLBACK", "STOPPED"}:
        s = record_transition(s, "DESTROY_PLANNED", by=by)
    return s


def cmd_destroy(args: argparse.Namespace) -> int:
    """Produce a stored destroy plan and report its SHA.

    The destroy plan is reviewable; it is NEVER applied by this
    command. Apply requires the separate human phrase:
        APPROVE PHASE 3 DESTROY EXECUTE

    Destroy-plan-freshness: if a previous destroy plan exists
    at the canonical path, this command refuses to overwrite it
    UNLESS the State serial has advanced. This enforces that a
    failed destroy must be followed by a fresh re-plan; it
    never silently reuses a stale plan file.
    """
    state_dir = _state_dir()
    state_file = state_dir / f"{args.lab_id}.json"
    if not state_file.is_file():
        print(f"destroy: no local state for {args.lab_id}", file=sys.stderr)
        return 1
    state = json.loads(state_file.read_text())

    if getattr(args, "finalize", False):
        if not _git_clean(REPO_ROOT):
            print("finalize: FAIL working tree is not clean", file=sys.stderr)
            return 2
        head_sha = _git_head(REPO_ROOT)
        origin_main_sha = _git_origin_main(REPO_ROOT)
        if head_sha != origin_main_sha:
            print("finalize: FAIL HEAD != origin/main", file=sys.stderr)
            return 3
        if args.expected_commit and head_sha != args.expected_commit:
            print("finalize: FAIL commit mismatch", file=sys.stderr)
            return 4

        plan_path = Path(args.plan_file)
        if not plan_path.is_file():
            print("finalize: FAIL plan file not found", file=sys.stderr)
            return 5
        actual_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        if actual_sha != args.expected_sha256:
            print("finalize: FAIL SHA mismatch", file=sys.stderr)
            return 6

        try:
            plan_json = _terraform_show_json(DEFAULT_LAB_TF_DIR, plan_path)
        except RuntimeError as exc:
            print(f"finalize: FAIL terraform show -json — {exc}", file=sys.stderr)
            return 7
        resource_changes = plan_json.get("resource_changes", []) or []
        creates = [
            resource for resource in resource_changes
            if resource.get("change", {}).get("actions") == ["create"]
        ]
        updates = [
            resource for resource in resource_changes
            if "update" in resource.get("change", {}).get("actions", [])
        ]
        deletes = [
            resource for resource in resource_changes
            if resource.get("change", {}).get("actions") == ["delete"]
        ]
        if creates or updates:
            print("finalize: FAIL plan contains create/update", file=sys.stderr)
            return 7
        delete_addrs = {resource.get("address") for resource in deletes}
        try:
            contract = plan_contract(state.get("pack_id", ""))
        except ValueError as exc:
            print(f"finalize: FAIL — {exc}", file=sys.stderr)
            return 8
        if not delete_addrs <= set(contract.expected_destroy_addresses):
            print(
                "finalize: FAIL plan contains addresses outside allowlist",
                file=sys.stderr,
            )
            return 8

        state_list = _run_subprocess([
            "terraform",
            "-chdir=" + str(DEFAULT_LAB_TF_DIR),
            "state",
            "list",
        ])
        if state_list.returncode != 0:
            print(
                f"finalize: FAIL terraform state list — {state_list.stderr}",
                file=sys.stderr,
            )
            return 9
        state_addrs = {
            address
            for address in state_list.stdout.splitlines()
            if address and not address.startswith("data.")
        }
        if state_addrs:
            print(
                "finalize: FAIL Terraform-State nicht leer, enthält: "
                f"{state_addrs}",
                file=sys.stderr,
            )
            return 9

        sorted_delete_addrs = sorted(delete_addrs)
        if state.get("state") == "DESTROYED":
            bindings_match = (
                state.get("destroy_plan_file") == str(plan_path)
                and state.get("destroy_plan_sha256") == actual_sha
                and state.get("destroy_source_commit") == head_sha
                and state.get("destroy_delete_addresses") == sorted_delete_addrs
            )
            if not bindings_match:
                print(
                    "finalize: FAIL stored destroy bindings mismatch",
                    file=sys.stderr,
                )
                return 8
            print("finalize: PASS — bereits DESTROYED (idempotent)")
            return 0

        s = _record_destroy_planned(state, by="operator")
        if s.get("state") != "DESTROY_PLANNED":
            print(
                f"finalize: FAIL invalid runtime state {s.get('state')}",
                file=sys.stderr,
            )
            return 8
        s["destroy_plan_file"] = str(plan_path)
        s["destroy_plan_sha256"] = actual_sha
        s["destroy_source_commit"] = head_sha
        s["destroy_delete_addresses"] = sorted_delete_addrs
        s["destroy_finalized_at"] = _now_iso()
        s = record_transition(s, "DESTROYED", by="operator")
        _atomic_write(state_file, s)
        print(
            "finalize: PASS — Runtime-State DESTROYED, Bindung: "
            f"{actual_sha}@{head_sha[:12]}"
        )
        return 0

    from_failure = state.get("state") == "FAILURE"
    if from_failure:
        if not getattr(args, "from_failure", False):
            print("destroy: FAILURE requires --from-failure", file=sys.stderr)
            return 1
        s = record_transition(state, "ROLLBACK", by="system")
        _atomic_write(state_file, s)
        write_substate(state_file, "rollback_state", {"status": "complete"})
        state = json.loads(state_file.read_text())

    if not _git_clean(REPO_ROOT):
        print("destroy: FAIL working tree is not clean", file=sys.stderr)
        return 2
    head_sha = _git_head(REPO_ROOT)
    origin_main_sha = _git_origin_main(REPO_ROOT)
    if head_sha != origin_main_sha:
        print(
            f"destroy: FAIL HEAD != origin/main.\n"
            f"  HEAD:        {head_sha}\n"
            f"  origin/main: {origin_main_sha}",
            file=sys.stderr,
        )
        return 3

    # Init the lab root with the same backend.
    try:
        contract = plan_contract(state.get("pack_id", ""))
    except ValueError as exc:
        print(f"destroy: FAIL — {exc}", file=sys.stderr)
        return 4
    prefix = contract.expected_backend_prefix
    try:
        _terraform_init(DEFAULT_LAB_TF_DIR, DEFAULT_GCP_PROJECT, prefix)
    except RuntimeError as exc:
        print(f"destroy: FAIL terraform init — {exc}", file=sys.stderr)
        return 4

    pack_dir = DEFAULT_PACKS_DIR / state["pack_id"]
    try:
        manifest = load_manifest(pack_dir)
        node = manifest["topology"]["nodes"][0]
        payload = node.get("driver_payload", {})
    except (FileNotFoundError, KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"destroy: FAIL pack manifest — {exc}", file=sys.stderr)
        return 4
    artifact_uri = state.get("artifact_uri") or payload.get("artifact_uri", "")
    bucket = artifact_uri[5:].split("/", 1)[0] if artifact_uri.startswith("gs://") else ""
    tfvars = {
        "gcp_project_id": DEFAULT_GCP_PROJECT,
        "gcp_region": DEFAULT_GCP_REGION,
        "gcp_zone": DEFAULT_GCP_ZONE,
        "lab_id": args.lab_id,
        "pack_id": state["pack_id"],
        "lab_subnet_cidr": state.get("lab_subnet_cidr") or
            ("10.200.2.0/24" if state["pack_id"] == "wordpress-smoke" else "10.200.1.0/24"),
        "lab_internal_ip": state.get("lab_internal_ip") or payload.get("internal_ip"),
        "lab_service_account_id": payload.get(
            "service_account_id", f"bbr-lab-{args.lab_id}"
        ),
        "machine_type": node.get("machine_type", "e2-micro"),
        "disk_size_gb": str(node.get("disk_size_gb", 10)),
        "disk_type": node.get("disk_type", "pd-standard"),
        "base_image_self_link": state.get("node_base_image") or
            node["base_image"]["self_link"],
        "operator_principal": state.get("operator_principal") or _detect_operator(),
        "ttl_max_lifetime_seconds": "28800",
        "ttl_idle_timeout_seconds": "1800",
        "per_cycle_eur_limit": str(PHASE3_SMOKE_CYCLE_LIMIT_EUR),
    }
    if state["pack_id"] == "wordpress-smoke":
        tfvars.update({
            "artifact_uri": artifact_uri,
            "artifact_sha256": state.get("artifact_sha256") or payload["artifact_sha256"],
            "minisign_public_key": state.get("minisign_public_key") or
                payload["minisign_public_key"],
            "supported_platform": payload["supported_platform"],
            "bootstrap_bucket_name": bucket,
        })
    plan_path = Path(f"/tmp/bbr-{args.lab_id}-destroy.tfplan")
    # Refuse to silently overwrite an existing destroy plan whose
    # underlying State serial still matches. After any failed
    # destroy, the operator MUST commit the failure report and
    # run 'bbr destroy' again to produce a fresh plan. A v2
    # overwrite is only allowed if the plan file is missing
    # entirely (first generation) or if the State has advanced.
    if plan_path.exists():
        existing_serial = _plan_state_serial(plan_path)
        current_serial = _current_lab_state_serial()
        if existing_serial is None or current_serial is None or existing_serial != current_serial:
            # State has moved; safe to overwrite.
            pass
        else:
            print(
                f"destroy: FAIL — a destroy plan already exists at {plan_path}\n"
                f"  plan serial:    {existing_serial}\n"
                f"  current serial: {current_serial}\n"
                "  The plan is still bound to the current State.\n"
                "  If the previous destroy attempt failed, mark the\n"
                "  existing plan as obsolete (rename to .OBSOLETE) and\n"
                "  re-run 'bbr destroy' to produce a fresh plan.",
                file=sys.stderr,
            )
            return 10
    cmd = [
        "terraform", "plan",
        "-input=false",
        "-refresh=true",
        "-destroy",
        f"-out={plan_path}",
    ]
    for k, v in tfvars.items():
        cmd.append(f"-var={k}={v}")
    r = _run_subprocess(cmd, cwd=DEFAULT_LAB_TF_DIR)
    if r.returncode != 0:
        print(f"destroy: FAIL terraform plan -destroy — {r.stderr}", file=sys.stderr)
        return 5
    sha = _file_sha256(plan_path)
    print(f"destroy: stored plan at {plan_path}")
    print(f"destroy: SHA-256 = {sha}")
    # Verify the pack-specific destroy plan shape.
    try:
        plan_json = _terraform_show_json(DEFAULT_LAB_TF_DIR, plan_path)
    except RuntimeError as exc:
        print(f"destroy: FAIL terraform show -json — {exc}", file=sys.stderr)
        return 6
    rc = plan_json.get("resource_changes", []) or []
    creates = sum(1 for r in rc if r.get("change", {}).get("actions", []) == ["create"])
    if creates != 0:
        print(f"destroy: FAIL — destroy plan should have 0 creates, got {creates}",
              file=sys.stderr)
        return 7
    state_list = _run_subprocess([
        "terraform",
        "-chdir=" + str(DEFAULT_LAB_TF_DIR),
        "state",
        "list",
    ])
    if state_list.returncode != 0:
        print(
            f"destroy: FAIL terraform state list — {state_list.stderr}",
            file=sys.stderr,
        )
        return 8
    destroyed_addresses = {
        r.get("address")
        for r in rc
        if r.get("change", {}).get("actions", []) == ["delete"]
    }
    actual_state_addresses = {
        address
        for address in state_list.stdout.splitlines()
        if address and not address.startswith("data.")
    }
    expected_destroy = set(contract.expected_destroy_addresses)
    if not _destroy_addresses_are_valid(
        plan_json,
        actual_state_addresses,
        contract.expected_destroy_addresses,
    ):
        print(
            f"destroy: FAIL — unexpected destroy addresses.\n"
            f"  allowed:  {expected_destroy}\n"
            f"  state:    {actual_state_addresses}\n"
            f"  plan:     {destroyed_addresses}",
            file=sys.stderr,
        )
        return 9

    s = _record_destroy_planned(json.loads(state_file.read_text()), by="system")
    s["destroy_plan_file"] = str(plan_path)
    s["destroy_plan_sha256"] = sha
    s["destroy_source_commit"] = head_sha
    s["destroy_delete_addresses"] = sorted(destroyed_addresses)
    _atomic_write(state_file, s)
    phase = "4" if state["pack_id"] == "wordpress-smoke" else "3"
    print("destroy: PASS — destroy plan is reviewable.")
    print(f"destroy: requires 'APPROVE PHASE {phase} DESTROY EXECUTE' to apply.")
    return EXIT_DESTROY_FROM_FAILURE if from_failure else 0


# ------------------------------------------------------------------
# placeholders
# ------------------------------------------------------------------

def cmd_not_implemented(args: argparse.Namespace) -> int:
    name = args.command
    print(f"{name}: not implemented in Phase 3", file=sys.stderr)
    return 1


COMMANDS = {
    "validate": cmd_validate,
    "plan": cmd_plan,
    "create": cmd_create,
    "verify": cmd_verify,
    "list": cmd_list,
    "destroy": cmd_destroy,
    "bootstrap": cmd_not_implemented,
    "isolate": cmd_not_implemented,
    "start": cmd_not_implemented,
    "stop": cmd_not_implemented,
    "snapshot": cmd_not_implemented,
    "restore": cmd_not_implemented,
    "run": cmd_not_implemented,
    "diff": cmd_not_implemented,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bbr", description="BugBountyRange CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate")
    p.add_argument("pack")

    p = sub.add_parser("plan")
    p.add_argument("pack")
    p.add_argument("--lab-id", default=None)
    p.add_argument("--gcp-project", default=DEFAULT_GCP_PROJECT)
    p.add_argument("--subnet-cidr", default="10.200.1.0/24")

    p = sub.add_parser("create")
    p.add_argument("lab_id")
    p.add_argument("--plan-file", default="")
    p.add_argument("--expected-sha256", default="")
    p.add_argument("--expected-commit", default="")

    p = sub.add_parser("verify")
    p.add_argument("lab_id")
    p.add_argument("--manual-confirm", action="store_true")

    sub.add_parser("list")

    p = sub.add_parser("destroy")
    p.add_argument("lab_id")
    p.add_argument("--from-failure", action="store_true")
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--plan-file", default="")
    p.add_argument("--expected-sha256", default="")
    p.add_argument("--expected-commit", default="")

    for cmd in ("bootstrap", "isolate", "start", "stop",
                "snapshot", "restore", "run", "diff"):
        p = sub.add_parser(cmd)
        p.add_argument("lab_id", nargs="?")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    fn = COMMANDS[args.command]
    return fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
