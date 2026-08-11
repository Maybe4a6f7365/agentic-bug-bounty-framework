#!/usr/bin/env bash
# tools/validate-skills.sh
#
# Validates the skills/ library so the skill router can actually load it.
#
# Skills are loaded by the agent harness from a discoverable skills root via the
# YAML frontmatter of each skills/<name>/SKILL.md. The `name` and `description`
# fields are the only routing signal — a skill that is not registered, or whose
# description does not describe when to load it, is dead weight. This validator
# enforces the invariants that keep the library loadable as it grows.
#
# Run before every commit that touches skills/. Non-zero exit on any error.
#
# Dependency requirements:
#   - bash >= 4
#   - coreutils (find, sort, readlink)
#
# Checks:
#   1. .claude/skills is a symlink resolving to the repo's skills/ directory
#      (this is what makes the library discoverable at all)
#   2. Every skills/<dir>/ contains a SKILL.md
#   3. Every SKILL.md opens with a YAML frontmatter block
#   4. Frontmatter declares `name` and `description`
#   5. `name` matches the containing directory name
#   6. `description` is within sane bounds (60..1400 chars) and says when to load
#   7. No skill still carries the inert legacy `trigger:` field
#   8. No root-level skills/<name>.md legacy skill files remain
#   9. Every skill directory is listed in skills/README.md
#
# Usage:
#   ./tools/validate-skills.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

ERRORS=0
CHECKED=0

err() {
  echo "ERROR: $*" >&2
  ERRORS=$((ERRORS + 1))
}

# Directories under skills/ that are references, not loadable skills.
is_excluded_dir() {
  case "$1" in
    references) return 0 ;;
    *) return 1 ;;
  esac
}

# --- Check 1: registration symlink -------------------------------------------
if [[ ! -L .claude/skills ]]; then
  err ".claude/skills is missing or not a symlink — the skills library is not registered and nothing will load. Create it with: ln -s ../skills .claude/skills"
else
  resolved="$(readlink -f .claude/skills)"
  if [[ "$resolved" != "$REPO_ROOT/skills" ]]; then
    err ".claude/skills resolves to '$resolved', expected '$REPO_ROOT/skills'"
  fi
fi

# --- Check 8: no legacy root-level skill files -------------------------------
while IFS= read -r legacy; do
  [[ -z "$legacy" ]] && continue
  base="$(basename "$legacy")"
  [[ "$base" == "README.md" || "$base" == "ROADMAP.md" ]] && continue
  err "legacy root-level skill file '$legacy' — folder skills only; move it to skills/<name>/SKILL.md so it carries frontmatter and can load"
done < <(find skills -maxdepth 1 -name "*.md" -type f 2>/dev/null | sort)

# --- Per-skill checks --------------------------------------------------------
while IFS= read -r dir; do
  [[ -z "$dir" ]] && continue
  name="$(basename "$dir")"
  is_excluded_dir "$name" && continue

  skill_file="$dir/SKILL.md"

  # Check 2
  if [[ ! -f "$skill_file" ]]; then
    err "$dir/ has no SKILL.md"
    continue
  fi
  CHECKED=$((CHECKED + 1))

  # Check 3
  if [[ "$(head -n 1 "$skill_file")" != "---" ]]; then
    err "$skill_file does not open with a YAML frontmatter block"
    continue
  fi

  # Extract the frontmatter block (between the first two --- lines).
  frontmatter="$(awk 'NR==1 && $0=="---" {inside=1; next} inside && $0=="---" {exit} inside' "$skill_file")"

  # Check 4 + 5
  fm_name="$(printf '%s\n' "$frontmatter" | sed -n 's/^name:[[:space:]]*//p' | head -n 1)"
  if [[ -z "$fm_name" ]]; then
    err "$skill_file frontmatter has no 'name' field"
  elif [[ "$fm_name" != "$name" ]]; then
    err "$skill_file declares name '$fm_name' but lives in directory '$name' — they must match"
  fi

  fm_desc="$(printf '%s\n' "$frontmatter" | sed -n 's/^description:[[:space:]]*//p' | head -n 1)"
  if [[ -z "$fm_desc" ]]; then
    err "$skill_file frontmatter has no 'description' field — this is the only routing signal"
    continue
  fi

  # Check 6
  desc_len=${#fm_desc}
  if (( desc_len < 60 )); then
    err "$skill_file description is only $desc_len chars — too thin to route on (min 60)"
  fi
  if (( desc_len > 1400 )); then
    err "$skill_file description is $desc_len chars — too long (max 1400); every description is carried in context for the whole session"
  fi
  if [[ "$fm_desc" != *"Load "* && "$fm_desc" != *"load "* ]]; then
    err "$skill_file description never says when to load it — add a 'Load when ...' clause"
  fi

  # Check 7
  if printf '%s\n' "$frontmatter" | grep -q '^trigger:'; then
    err "$skill_file still declares the legacy 'trigger:' field — it is not read by the router; fold that vocabulary into 'description'"
  fi

  # Check 9
  if [[ -f skills/README.md ]] && ! grep -q "$name" skills/README.md; then
    err "skill '$name' is not listed in skills/README.md — the index has drifted"
  fi
done < <(find skills -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

# --- Summary -----------------------------------------------------------------
echo
if (( ERRORS == 0 )); then
  echo "✓ skills library valid — $CHECKED skills registered, frontmatter and index in sync"
  exit 0
fi
echo "✗ $ERRORS error(s) across $CHECKED skills"
exit 1
