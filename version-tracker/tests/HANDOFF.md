# Handoff — Version-Tracker Test Migration

**Session:** 2026-07-27
**Status:** Phase 0 complete, Phase 1 complete, Phase 2 complete. Phases 3–4 pending.
**Plan:** `/tmp/pytest-test-plan.md` §5 (version-tracker migration, lines 427–468)

---

## What was done

### Phase 0 — Baseline
- Installed pytest + pytest-cov in `.venv`
- Ran existing 316 unittest tests through pytest: **305 pass, 3 fail, 8 skip**
- Wrote `tests/BASELINE.txt` capturing the baseline
- Added `tests/pytest.ini` with markers (`slow`, `integration`, `bash`)

### Phase 1 — Resolved 3 BOT_WALL failures
The 3 failing tests asserted `AUTH_REQUIRED` for HTTP 403, but checkers now
reclassify 403 as `BOT_WALL` (product decision — see §5, Q5 of the plan).

Files changed:
| File | Change |
|------|--------|
| `tests/test_checker_api_json.py` | `test_http_403_auth_required` → `test_http_403_classified_as_bot_wall` (asserts BOT_WALL) + new `test_http_401_still_auth_required` |
| `tests/test_checker_css_selector.py` | Same rename + new 401 guard |
| `tests/test_checker_rss.py` | Same rename + new 401 guard |

**Result: 319 tests, 0 failures, 8 skipped** (VT_INTEGRATION gated)

GitHub checker was NOT affected — its 403 test never failed; it handles
the status code differently.

### New test count: 319 (up from 316)
- +3: `test_http_401_still_auth_required` guards — ensures 401 is still
  classified as AUTH_REQUIRED and BOT_WALL hasn't crept into that path

### Phase 2 — Support modules → conftest fixtures

Created `tests/conftest.py` with pytest fixtures mirroring the support modules:

| Fixture | Scope | Source | Notes |
|---------|-------|--------|-------|
| `db_schema` | session | dbutil.schema_sql() | Cached schema SQL text |
| `db` | function | dbutil.fresh_memory_db() | File-based (tmp_path), WAL-safe |
| `seeded_db` | function | db + sql/seeds/*.sql | Seeds loaded in sorted order |
| `fake_http` | function | fakes.FakeHTTPCache | Fresh per-test, no shared state |
| `fake_gps` | function | fakes.FakeGPSModule | Fresh per-test |

- `support/dbutil.py` and `support/fakes.py` are unchanged — existing
  unittest-based tests continue to import them directly.
- Smoke-tested: schema loads, 19 tables created, FakeHTTPCache functional.
- Gate: **319/319 upheld** (311 passed, 0 failed, 8 skipped).

---

## What's next — Phases 2–4

Per `/tmp/pytest-test-plan.md` §5:

### Phase 2 — Support modules → fixtures (no test-body changes yet)
- `support/dbutil.py` → `conftest.py` fixtures: `db` (function-scoped,
  `tmp_path` sqlite), `seeded_db`, `db_schema` (session-scoped)
- `support/fakes.py` → `fake_http`, `fake_clock`, `fake_registry` fixtures
- Keep `dbutil`/`fakes` as thin shims delegating to fixtures so unmigrated
  files keep working — this enables incremental migration
- Run after each: must still be 319/319

### Phase 3 — File-by-file conversion (14 files)
Mechanically convert each:
- `class TestX(unittest.TestCase)` → plain `class TestX` (or module-level)
- `setUp`/`tearDown` → fixtures; `setUpClass` → class-scoped fixture
- `self.assertEqual(a,b)` → `assert a == b`; `assertRaises` → `pytest.raises`
- Loop-based subtests / `subTest` → `@pytest.mark.parametrize` (biggest value add)
- Delete corresponding `dbutil`/`fakes` shim usage

Suggested order: smallest/most-isolated first → DB-heavy → HTTP-classification last

Gate: test count must not drop. Parametrize usually raises it — that's fine.

### Phase 4 — Consolidation
- Remove `dbutil`/`fakes` shims once no file imports them
- Delete `if __name__ == '__main__': unittest.main()` blocks
- Add `--strict-markers`, coverage gate at Phase-0 measured level
- Wire into same CI job as pipeline suite

Rollback rule: each phase is a separate commit; any phase failing to
reproduce the baseline is reverted, not patched forward.

---

## How to run

```bash
cd /home/hermes/research/version-tracker

# Full suite (319 tests, <1s):
.venv/bin/python -m pytest tests/ -v

# Skip integration tests (default, via pytest.ini):
.venv/bin/python -m pytest tests/ -v

# Integration tests require VT_INTEGRATION=1:
VT_INTEGRATION=1 .venv/bin/python -m pytest tests/ -v -m integration

# Coverage (pytest-cov installed):
.venv/bin/python -m pytest tests/ --cov=. --cov-report=term
```

---

## Key files

| File | Purpose |
|------|---------|
| `tests/BASELINE.txt` | Phase 0/1 baseline — 319 tests, 0 failures |
| `tests/conftest.py` | Phase 2 — pytest fixtures (db, db_schema, seeded_db, fake_http, fake_gps) |
| `tests/pytest.ini` | Pytest config with markers |
| `/tmp/pytest-test-plan.md` | Full plan (Phases 0–4 at lines 427–468) |
| `tests/support/dbutil.py` | DB utility — to become conftest fixtures |
| `tests/support/fakes.py` | FakeHTTPCache etc — to become fixtures |
| `checkers/builtin/api_json.py` | 403→BOT_WALL at line 44 |
| `checkers/builtin/css_selector.py` | 403→BOT_WALL in error path |
| `checkers/builtin/rss.py` | 403→BOT_WALL in error path |

---

## Sync note


---

## Phase 5 — Engagement envelope + health + notify (2026-07-30)

| Target | Mechanisms / sources | Health | Notify | Boundary |
|---|---|---|---|---|
| synthetic `sandbox` (target_id=1) | JS bundle integrity `version_source_id=40`; security headers `41`; robots/sitemap `42`, `43` | `status.py --short` and reports completed; 4 sandbox sources present | `VT_WEBHOOK_URL` not set; `notify.py --dry-run --scope-only --limit 1` returned `No new changes.` | All fetches loopback `127.0.0.1:1810x`; no enumeration, probing, or payload submission |

---

## Phase 7 — Handoff + PR (2026-07-30)

| Todo | Phase state | Mechanics / sources wired | Tests | Boundary |
|---|---|---|---|---|
| `faf0c682` — RSS feeds / website version-changes of a target | Phases 0–7 complete (Phase 6 PARTIAL — runtime OSINT-DYNAMIC cert completed for JS bundle only; OSINT-CODEREVIEW-1/2/3 invariants proven at unit level for all three mechanisms) | 3 mechanisms wired against synthetic `sandbox` target (target_id=1): `js_bundle` (40, asset_id=2), `api/header_diff` (41, asset_id=3), `xml_diff` ×2 (42, 43 on asset_id=4) | 317 passed, 8 skipped, 0 failed (`tests/`); OSINT-CODEREVIEW-1/2/3 unit-test invariants PASS; OSINT-CODEREVIEW-1 also PASS at runtime via Phase 6 Setup A access log | Every fetch is to a URL the synthetic sandbox target publishes locally on loopback `127.0.0.1:1810x`; no enumeration, no probing, no payload submission. Plan §0 + §1 OSINT boundary upheld end-to-end |

### Phase 7 deliverables (this commit)

- New file: `sql/seeds/sandbox-js-bundle.sql` — Phase 2 JS-bundle wiring seed, generated from live DB state (Phase 2 itself did not commit a seed file).
- This handoff entry.
- `tests/HANDOFF.md` append only — no source-code modifications.

### Master handoff pointer

- `/opt/data/.hermes/plans/2026-07-30_<hhmm>-master-handoff.md` — single file that lists every phase, every §11 test-ID with file location, the full DB state dump, the commit chain, and the outstanding-items list. Pin this when handing off to a reviewer.

### Outstanding items (carry-forward)

1. `AGENTS.md` shows +15 uncommitted lines (sibling-session edit, not part of this phase).
2. 13 leftover Phase-1 probe `version_source` rows on `asset_id=1` / `https://example/` (Phase 1 enumeration-coverage fixtures; belong to a separate cleanup phase).
3. Synthetic `target_id=1` ('sandbox') lives in the live DB; do not delete without coordinating Phase 2/3/4/5 mechanism cleanup.
4. `VT_WEBHOOK_URL` env var is unset on this host — notify pipeline wiring was verified at dry-run only (`notify.py --dry-run --scope-only --limit 1` → "No new changes.").
5. **Phase 6 leftover**: `version_source_id=44` (asset_id=5, `source_url='http://127.0.0.1:18104/'`) is in the live DB. The Phase 6 partial handoff §5 claimed this row had been purged before exit; DB audit on 2026-07-30 confirms it is still present. Per the Phase 7 prompt, this does not block Phase 7 (unit-test OSINT invariants are sufficient), but it should be deleted in a follow-up:
   ```sql
   DELETE FROM check_run WHERE version_source_id = 44;
   DELETE FROM version_source WHERE version_source_id = 44;
   DELETE FROM asset WHERE asset_id = 5;
   ```
   (Sequence matters: dependent rows in `check_run` first, then the `version_source`, then the now-orphaned `asset`.)
6. Phase 6 OSINT-DYNAMIC-2 / -3 / -botwall runtime certification outstanding — see `/opt/data/.hermes/plans/2026-07-30_2138-phase6-partial-handoff.md` §4 for the recipe (subagent shape, port assignments 18105–18107, ~30–45 min).

### DB path caveat (do NOT forget)

The runner reads `VERSION_TRACKER_DB` from env, defaulting to `~/.hermes/version-tracker/version_tracker.db`. On this host `$HOME=/opt/data/home`, so the default resolves to `/opt/data/home/.hermes/version-tracker/version_tracker.db` — **NOT** `/opt/data/.hermes/...`. **Every DB-touching command must export `VERSION_TRACKER_DB=/opt/data/.hermes/version-tracker/version_tracker.db` explicitly.** Documented in Phase 4 handoff §9.
