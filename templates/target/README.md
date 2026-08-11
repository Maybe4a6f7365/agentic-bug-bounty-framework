# Target Template

Use this directory as a starting point for new HackerOne targets.

## Quick start

From the repository root, replace `<your-target>` with the stable target ID:

```bash
mkdir -p targets/<your-target>
cp templates/target/README.template.md targets/<your-target>/README.md
cp templates/target/contract.template.yaml targets/<your-target>/contract.yaml
cp templates/target/findings-manifest.template.json targets/<your-target>/findings-manifest.json
cp templates/target/pre_scan.template.yaml targets/<your-target>/pre_scan.yaml
cp -R templates/target/findings templates/target/evidence templates/target/repro \
  templates/target/runs templates/target/submit templates/target/notes \
  templates/target/generated targets/<your-target>/
```

Fill every placeholder before treating the target as live. Remove `.gitkeep` from
a directory after adding real files.

## Files

- `README.template.md` — copy to `targets/<your-target>/README.md` and fill in.
- `contract.template.yaml` — copy to `targets/<your-target>/contract.yaml`.
- `findings-manifest.template.json` — copy to
  `targets/<your-target>/findings-manifest.json`.
- `pre_scan.template.yaml` — copy to `targets/<your-target>/pre_scan.yaml`.

The `.template.*` names prevent recursive discovery from treating these files as
a live target.

## Subdirectories

Each empty subdirectory represents a category of material that lives under a
target. Use them per the canonical layout:

- `findings/` — finalized finding reports (`F01.md`, `F02.md`, …); use
  `findings/legacy/` for date-stamped pre-template reports.
- `evidence/` — redacted screenshots and request/response traces, organized by
  finding (`F01/`, `F02/`) or under `shared/` for cross-cutting material.
- `repro/` — minimal reproducible PoCs, organized by finding.
- `runs/` — operational snapshots (`standing_knowns.yaml`,
  `translation-log.yaml`) and append-only ledgers under `handoffs/`.
- `submit/` — attachments bundled for HackerOne submission.
- `notes/` — research-time material not yet promoted to a finding; use
  `audit/`, `lessons/`, and `next-steps.md` as appropriate.
- `generated/` — view-only outputs from regenerators (`OUTCOMES.md`,
  `REPLICATION_INDEX.md`). Do not hand-edit them.

## Validation

After copying and filling the templates, run from the repository root:

```bash
./tools/validate-manifests.sh
./tools/regenerate_target_outcomes.sh <your-target>
```
