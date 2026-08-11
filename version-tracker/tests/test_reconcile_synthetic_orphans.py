import json
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
COMMAND = ROOT / "scripts/reconcile_synthetic_orphans.py"


def _insert_asset(conn, asset_id, identifier, *, discovery_method="manual_synthetic", status="active"):
    conn.execute(
        """INSERT INTO asset
           (asset_id, vector_type, canonical_identifier, status, discovery_method)
           VALUES (?, 'website', ?, ?, ?)""",
        (asset_id, identifier, status, discovery_method),
    )


def _seed_stale_db(conn, *, phase1_id=41, phase6_id=87):
    _insert_asset(conn, phase1_id, "phase1-test.example")
    _insert_asset(conn, phase6_id, "phase6-js-bundle")
    conn.executemany(
        """INSERT INTO version_source
           (version_source_id, asset_id, source_type, source_identifier, check_method, enabled)
           VALUES (?, ?, 'manual', ?, 'manual', 1)""",
        [(1000 + index, phase1_id, f"phase1-{index}") for index in range(13)],
    )
    conn.commit()


def _run(db_path):
    return subprocess.run(
        [sys.executable, str(COMMAND), "--db", str(db_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_reconciles_stale_synthetic_orphans_without_using_historical_ids(db, tmp_path):
    _seed_stale_db(db)
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "ok": True,
        "phase1_sources_disabled": 13,
        "assets_deprecated": 2,
    }
    with sqlite3.connect(db_path) as check:
        statuses = dict(check.execute(
            "SELECT canonical_identifier, status FROM asset "
            "WHERE canonical_identifier IN ('phase1-test.example', 'phase6-js-bundle')"
        ))
        assert statuses == {
            "phase1-test.example": "deprecated",
            "phase6-js-bundle": "deprecated",
        }
        assert check.execute(
            "SELECT COUNT(*) FROM version_source WHERE asset_id=41 AND enabled=0"
        ).fetchone()[0] == 13
        assert check.execute("SELECT COUNT(*) FROM asset").fetchone()[0] == 2
        assert check.execute("SELECT COUNT(*) FROM version_source").fetchone()[0] == 13
        assert check.execute("SELECT COUNT(*) FROM target_asset").fetchone()[0] == 0


def test_refuses_unexpected_phase1_source_count_and_rolls_back(db, tmp_path):
    _seed_stale_db(db)
    db.execute("DELETE FROM version_source WHERE source_identifier='phase1-12'")
    db.commit()
    db_path = tmp_path / "test.db"
    before = [tuple(row) for row in db.execute(
        "SELECT canonical_identifier, status FROM asset ORDER BY canonical_identifier"
    )]
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "unexpected phase1 source state" in result.stderr
    with sqlite3.connect(db_path) as check:
        assert check.execute(
            "SELECT canonical_identifier, status FROM asset ORDER BY canonical_identifier"
        ).fetchall() == before
        assert check.execute(
            "SELECT COUNT(*) FROM version_source WHERE enabled=1"
        ).fetchone()[0] == 12


def test_refuses_linked_or_wrong_phase6_state_and_rolls_back(db, tmp_path):
    _seed_stale_db(db)
    phase1_id = db.execute(
        "SELECT asset_id FROM asset WHERE canonical_identifier='phase1-test.example'"
    ).fetchone()[0]
    db.execute("INSERT INTO target (canonical_name) VALUES ('decoy')")
    target_id = db.execute("SELECT target_id FROM target").fetchone()[0]
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id, is_current) VALUES (?, ?, 1)",
        (target_id, phase1_id),
    )
    db.execute(
        "UPDATE asset SET discovery_method='manual' "
        "WHERE canonical_identifier='phase6-js-bundle'"
    )
    db.commit()
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "unexpected synthetic orphan state" in result.stderr
    with sqlite3.connect(db_path) as check:
        assert check.execute(
            "SELECT COUNT(*) FROM version_source WHERE enabled=1"
        ).fetchone()[0] == 13
        assert check.execute(
            "SELECT COUNT(*) FROM asset WHERE status='active'"
        ).fetchone()[0] == 2


def test_refuses_phase6_sources(db, tmp_path):
    _seed_stale_db(db)
    phase6_id = db.execute(
        "SELECT asset_id FROM asset WHERE canonical_identifier='phase6-js-bundle'"
    ).fetchone()[0]
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, enabled)
           VALUES (?, 'manual', 'unexpected', 'manual', 0)""",
        (phase6_id,),
    )
    db.commit()
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "unexpected synthetic orphan state" in result.stderr


def test_second_run_is_a_logical_noop(db, tmp_path):
    _seed_stale_db(db)
    db_path = tmp_path / "test.db"
    db.close()

    first = _run(db_path)
    with sqlite3.connect(db_path) as check:
        after_first = check.iterdump()
        first_dump = "\n".join(after_first)
    second = _run(db_path)
    with sqlite3.connect(db_path) as check:
        second_dump = "\n".join(check.iterdump())

    assert first.returncode == second.returncode == 0
    assert json.loads(second.stdout) == {
        "ok": True,
        "phase1_sources_disabled": 0,
        "assets_deprecated": 0,
    }
    assert second_dump == first_dump


def test_missing_database_is_rejected_without_creation(tmp_path):
    db_path = tmp_path / "typo.db"

    result = _run(db_path)

    assert result.returncode != 0
    assert "database does not exist" in result.stderr
    assert not db_path.exists()


def test_rolls_back_if_mutation_has_an_unexpected_side_effect(db, tmp_path):
    _seed_stale_db(db)
    phase6_id = db.execute(
        "SELECT asset_id FROM asset WHERE canonical_identifier='phase6-js-bundle'"
    ).fetchone()[0]
    db.executescript(f"""
        CREATE TRIGGER inject_unexpected_source
        AFTER UPDATE OF enabled ON version_source
        WHEN OLD.enabled=1 AND NEW.enabled=0
        BEGIN
          INSERT OR IGNORE INTO version_source
            (asset_id, source_type, source_identifier, check_method, enabled)
          VALUES ({phase6_id}, 'manual', 'injected', 'manual', 0);
        END;
    """)
    db.commit()
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "unexpected database changes" in result.stderr
    with sqlite3.connect(db_path) as check:
        assert check.execute(
            "SELECT COUNT(*) FROM version_source WHERE enabled=1"
        ).fetchone()[0] == 13
        assert check.execute(
            "SELECT COUNT(*) FROM asset WHERE status='active'"
        ).fetchone()[0] == 2


def test_refuses_missing_asset(db, tmp_path):
    _seed_stale_db(db)
    db.execute("DELETE FROM asset WHERE canonical_identifier='phase6-js-bundle'")
    db.commit()
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "missing or duplicated" in result.stderr


def test_refuses_duplicate_canonical_asset(tmp_path):
    db_path = tmp_path / "duplicates.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE asset (
                asset_id INTEGER PRIMARY KEY,
                vector_type TEXT NOT NULL,
                canonical_identifier TEXT NOT NULL,
                status TEXT NOT NULL,
                discovery_method TEXT,
                updated_at TEXT
            );
            CREATE TABLE version_source (
                version_source_id INTEGER PRIMARY KEY,
                asset_id INTEGER NOT NULL REFERENCES asset(asset_id),
                enabled INTEGER NOT NULL
            );
            CREATE TABLE target_asset (
                target_asset_id INTEGER PRIMARY KEY,
                asset_id INTEGER NOT NULL REFERENCES asset(asset_id),
                is_current INTEGER NOT NULL
            );
            INSERT INTO asset VALUES
                (41, 'website', 'phase1-test.example', 'active', 'manual_synthetic', NULL),
                (42, 'website', 'phase1-test.example', 'active', 'manual_synthetic', NULL),
                (87, 'website', 'phase6-js-bundle', 'active', 'manual_synthetic', NULL);
        """)
        conn.executemany(
            "INSERT INTO version_source VALUES (?, 41, 1)",
            [(1000 + index,) for index in range(13)],
        )

    result = _run(db_path)

    assert result.returncode != 0
    assert "missing or duplicated" in result.stderr


def test_rolls_back_if_trigger_mutates_retained_observation(db, tmp_path):
    _seed_stale_db(db)
    phase1_id = db.execute(
        "SELECT asset_id FROM asset WHERE canonical_identifier='phase1-test.example'"
    ).fetchone()[0]
    db.execute(
        """INSERT INTO version_observation
           (version_source_id, asset_id, immutable_identifier, raw_metadata)
           VALUES (1000, ?, 'retained-observation', 'original')""",
        (phase1_id,),
    )
    observation_id = db.execute(
        "SELECT version_observation_id FROM version_observation"
    ).fetchone()[0]
    db.executescript(f"""
        CREATE TRIGGER mutate_retained_observation
        AFTER UPDATE OF enabled ON version_source
        WHEN OLD.version_source_id=1000
        BEGIN
          UPDATE version_observation SET raw_metadata='mutated'
          WHERE version_observation_id={observation_id};
        END;
    """)
    db.commit()
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "unexpected database changes" in result.stderr
    with sqlite3.connect(db_path) as check:
        assert check.execute(
            "SELECT raw_metadata FROM version_observation"
        ).fetchone()[0] == "original"
        assert check.execute(
            "SELECT COUNT(*) FROM version_source WHERE enabled=1"
        ).fetchone()[0] == 13


def test_refuses_database_with_foreign_key_violation_before_mutation(db, tmp_path):
    _seed_stale_db(db)
    db.execute("PRAGMA foreign_keys=OFF")
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, enabled)
           VALUES (999999, 'manual', 'orphan', 'manual', 0)"""
    )
    db.commit()
    db_path = tmp_path / "test.db"
    db.close()

    result = _run(db_path)

    assert result.returncode != 0
    assert "pre-reconciliation integrity checks" in result.stderr
    with sqlite3.connect(db_path) as check:
        assert check.execute(
            "SELECT COUNT(*) FROM version_source WHERE enabled=1"
        ).fetchone()[0] == 13
        assert check.execute(
            "SELECT COUNT(*) FROM asset WHERE status='active'"
        ).fetchone()[0] == 2
