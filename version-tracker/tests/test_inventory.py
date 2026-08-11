import json
import sqlite3
import stat
from pathlib import Path

import pytest

import scripts.inventory as inventory
from scripts.inventory import check_inventory, main, refresh_inventory


OBSERVED_AT = "2026-08-05T12:00:00Z"


def _seed_target(db, name="Zulu", *, status="active"):
    cursor = db.execute(
        "INSERT INTO target (canonical_name, target_status) VALUES (?, ?)",
        (name, status),
    )
    db.commit()
    return cursor.lastrowid


def test_refresh_writes_json_and_markdown_from_one_snapshot(db, tmp_path):
    _seed_target(db)
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"

    snapshot = refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=json_path,
        markdown_path=markdown_path,
        observed_at=OBSERVED_AT,
    )

    payload = json.loads(json_path.read_text())
    markdown = markdown_path.read_text()
    assert snapshot["observed_at"] == payload["observed_at"] == OBSERVED_AT
    assert snapshot["summary"]["targets_total"] == 1
    assert payload["summary"]["targets_total"] == 1
    assert "Targets total | 1" in markdown
    assert OBSERVED_AT in markdown


def test_snapshot_reads_all_sections_from_one_database_transaction(
    db, tmp_path, monkeypatch
):
    original_target_id = _seed_target(db, "Original")
    original_asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "original.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (original_target_id, original_asset_id),
    )
    db.commit()
    db.execute("PRAGMA journal_mode=WAL")
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]
    writer = sqlite3.connect(db_path)
    real_connect = sqlite3.connect

    class CommitBetweenSelects:
        def __init__(self, connection):
            self.connection = connection
            self.selects = 0

        @property
        def row_factory(self):
            return self.connection.row_factory

        @row_factory.setter
        def row_factory(self, value):
            self.connection.row_factory = value

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, statement, *args):
            if statement.lstrip().upper().startswith("SELECT"):
                if self.selects == 1:
                    concurrent_target_id = writer.execute(
                        "INSERT INTO target (canonical_name, target_status) VALUES (?, ?)",
                        ("Concurrent", "active"),
                    ).lastrowid
                    concurrent_asset_id = writer.execute(
                        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
                        ("api", "concurrent.example"),
                    ).lastrowid
                    writer.execute(
                        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
                        (concurrent_target_id, concurrent_asset_id),
                    )
                    writer.commit()
                self.selects += 1
            return self.connection.execute(statement, *args)

    monkeypatch.setattr(
        inventory.sqlite3,
        "connect",
        lambda *args, **kwargs: CommitBetweenSelects(real_connect(*args, **kwargs)),
    )
    try:
        snapshot = refresh_inventory(
            db_path=db_path,
            json_path=tmp_path / "inventory.json",
            markdown_path=tmp_path / "inventory.md",
            observed_at=OBSERVED_AT,
        )
    finally:
        writer.close()

    assert [target["canonical_name"] for target in snapshot["targets"]] == ["Original"]
    assert [asset["canonical_identifier"] for asset in snapshot["assets"]] == [
        "original.example"
    ]


def test_snapshot_order_is_stable_regardless_of_insert_order(db, tmp_path):
    zulu_target = _seed_target(db, "Zulu")
    alpha_target = _seed_target(db, "Alpha")
    zulu_asset = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("website", "zulu.example"),
    ).lastrowid
    alpha_asset = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "alpha.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (zulu_target, zulu_asset),
    )
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (alpha_target, alpha_asset),
    )
    db.commit()

    snapshot = refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    assert [target["canonical_name"] for target in snapshot["targets"]] == [
        "Alpha",
        "Zulu",
    ]
    assert [asset["canonical_identifier"] for asset in snapshot["assets"]] == [
        "alpha.example",
        "zulu.example",
    ]


def test_snapshot_redacts_credentials_urls_and_raw_source_config(db, tmp_path):
    target_id = _seed_target(db, "Secret Target")
    asset_id = db.execute(
        """INSERT INTO asset
           (vector_type, canonical_identifier, discovery_source_url)
           VALUES (?, ?, ?)""",
        ("api", "secret.example", "https://user:pass@example.test/discover?token=raw#frag"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, source_url, config)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            asset_id,
            "api",
            "private-api",
            "json_path",
            "https://name:password@example.test/version?api_key=source-secret",
            json.dumps(
                {
                    "api_url": "https://example.test/data?token=config-secret",
                    "headers": {"Authorization": "Bearer super-secret"},
                    "nested": {"password": "database-secret", "path": "$.version"},
                    "auth": "opaque-auth-secret",
                    "access_key": "access-key-secret",
                    "private_key": "private-key-secret",
                    "session": "session-secret",
                }
            ),
        ),
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    combined = (tmp_path / "inventory.json").read_text() + (tmp_path / "inventory.md").read_text()
    for secret in (
        "user:pass@",
        "source-secret",
        "config-secret",
        "super-secret",
        "database-secret",
        "opaque-auth-secret",
        "access-key-secret",
        "private-key-secret",
        "session-secret",
    ):
        assert secret not in combined
    payload = json.loads((tmp_path / "inventory.json").read_text())
    source = payload["version_sources"][0]
    assert source["source_url"] == "https://example.test/[REDACTED]?[REDACTED]"
    assert source["config"]["headers"] == "[REDACTED]"
    assert source["config"]["nested"]["password"] == "[REDACTED]"


def test_source_identifier_redacts_url_credentials_and_capabilities(db, tmp_path):
    target_id = _seed_target(db, "Identifier URL")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "identifier-url.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.executemany(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        [
            (
                asset_id,
                "api",
                "https://identifier-user:identifier-password@example.test/"
                "identifier-capability?token=identifier-query#identifier-fragment",
                "json_path",
            ),
            (
                asset_id,
                "api",
                "https://inventory-private-capability.example/",
                "json_path",
            ),
            (asset_id, "api", "latest_release", "json_path"),
        ],
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    json_text = (tmp_path / "inventory.json").read_text()
    markdown = (tmp_path / "inventory.md").read_text()
    for leaked_value in (
        "identifier-user",
        "identifier-password",
        "identifier-capability",
        "identifier-query",
        "identifier-fragment",
        "inventory-private-capability",
    ):
        assert leaked_value not in json_text
        assert leaked_value not in markdown
    payload = json.loads(json_text)
    assert [source["source_identifier"] for source in payload["version_sources"]] == [
        "[REDACTED]",
        "[REDACTED]",
        "[REDACTED]",
    ]


def test_source_identifier_redacts_username_value(db, tmp_path):
    target_id = _seed_target(db, "Identifier Username")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "identifier-username.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        (asset_id, "api", "username=inventory-private-user", "json_path"),
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    json_text = (tmp_path / "inventory.json").read_text()
    markdown = (tmp_path / "inventory.md").read_text()
    assert "inventory-private-user" not in json_text
    assert "inventory-private-user" not in markdown
    assert json.loads(json_text)["version_sources"][0]["source_identifier"] == (
        "[REDACTED]"
    )


def test_source_identifier_redacts_path_capability(db, tmp_path):
    target_id = _seed_target(db, "Identifier Path")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "identifier-path.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        (asset_id, "api", "/hooks/inventory-private-capability", "json_path"),
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    json_text = (tmp_path / "inventory.json").read_text()
    markdown = (tmp_path / "inventory.md").read_text()
    assert "inventory-private-capability" not in json_text
    assert "inventory-private-capability" not in markdown
    assert json.loads(json_text)["version_sources"][0]["source_identifier"] == (
        "[REDACTED]"
    )


def test_source_identifier_redacts_token_like_values(db, tmp_path):
    target_id = _seed_target(db, "Identifier Tokens")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "identifier-token.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    token_identifiers = [
        "ghp_0123456789abcdefghijklmnopqrstuv",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJpbnZlbnRvcnkifQ.inventory-signature",
    ]
    db.executemany(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        [(asset_id, "api", identifier, "json_path") for identifier in token_identifiers],
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    json_text = (tmp_path / "inventory.json").read_text()
    markdown = (tmp_path / "inventory.md").read_text()
    for identifier in token_identifiers:
        assert identifier not in json_text
        assert identifier not in markdown
    payload = json.loads(json_text)
    assert {
        source["source_identifier"] for source in payload["version_sources"]
    } == {"[REDACTED]"}


def test_source_identifier_fails_closed_for_unclassified_sensitive_text(db, tmp_path):
    target_id = _seed_target(db, "Identifier Fail Closed")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "identifier-fail-closed.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    sensitive_identifiers = [
        "user:password@example.test/hooks/capability",
        "https:/user:password@example.test/hooks/capability",
        "hooks/private-capability",
        "latest?opaque-capability",
        "latest#access_token=fragment-secret",
        "?unknown=raw-query-capability",
        "client_secret=assignment-secret",
        "accessToken=alias-secret",
        "Bearer embedded-bearer-secret",
        r"relative\backslash-capability",
        "https%3A%2F%2Fencoded-user%3Aencoded-pass%40example.test%2Fcapability",
        "[service](https://markdown-user:markdown-pass@example.test/capability)",
        "AKIAIOSFODNN7EXAMPLE",
        "0123456789abcdef0123456789abcdef",
        "sk-proj-abcdefghijklmnopqrstuvwxyz",
    ]
    db.executemany(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, enabled)
           VALUES (?, ?, ?, ?, 1)""",
        [
            (asset_id, "api", identifier, "json_path")
            for identifier in sensitive_identifiers
        ],
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    json_text = (tmp_path / "inventory.json").read_text()
    markdown = (tmp_path / "inventory.md").read_text()
    for identifier in sensitive_identifiers:
        assert identifier not in json_text
        assert identifier not in markdown
    payload = json.loads(json_text)
    assert {
        source["source_identifier"] for source in payload["version_sources"]
    } == {"[REDACTED]"}
    assert {
        source["source_identifier"]
        for source in payload["scheduled_version_sources"]
    } == {"[REDACTED]"}


def test_source_identifier_secret_changes_do_not_affect_output_order(db):
    target_id = _seed_target(db, "Identifier Noninterference")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "identifier-noninterference.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    first_id = db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        (asset_id, "api", "zulu?secret=first", "json_path"),
    ).lastrowid
    second_id = db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        (asset_id, "api", "alpha?secret=second", "json_path"),
    ).lastrowid
    db.commit()
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]

    before = inventory.build_inventory_snapshot(db_path, OBSERVED_AT)
    db.execute(
        "UPDATE version_source SET source_identifier = ? WHERE version_source_id = ?",
        ("aardvark?secret=changed-first", first_id),
    )
    db.execute(
        "UPDATE version_source SET source_identifier = ? WHERE version_source_id = ?",
        ("zebra?secret=changed-second", second_id),
    )
    db.commit()
    after = inventory.build_inventory_snapshot(db_path, OBSERVED_AT)

    assert inventory.render_json(after) == inventory.render_json(before)
    assert inventory.render_markdown(after) == inventory.render_markdown(before)


def test_source_identifier_preserves_classified_public_forms(db, tmp_path):
    target_id = _seed_target(db, "Identifier Public Forms")
    public_sources = [
        ("github_repository", "Shopify/cli", "github_release", "latest_release", "Shopify/cli-releases"),
        ("api", "api.example.com", "api", "json_path", "api.example.com/version"),
        ("android_app", "org.mozilla.firefox", "android_store", "google_play_scrape", "org.mozilla.firefox-playstore"),
        ("package", "npm:public-package", "package_registry", "registry_api", "npm:public-package"),
        ("github_repository", "Public/repo", "github", "latest_tag", "Public/repo-tags"),
        ("website", "example.com/feed", "rss", "feed_parse", "example.com/feed-rss"),
        ("ios_app", "123456789", "ios_store", "app_store", "123456789-appstore"),
        ("docker_image", "public/image", "package_registry", "registry_api", "docker-public/image"),
    ]
    for vector_type, canonical, source_type, check_method, identifier in public_sources:
        asset_id = db.execute(
            "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
            (vector_type, canonical),
        ).lastrowid
        db.execute(
            "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
            (target_id, asset_id),
        )
        db.execute(
            """INSERT INTO version_source
               (asset_id, source_type, source_identifier, check_method)
               VALUES (?, ?, ?, ?)""",
            (asset_id, source_type, identifier, check_method),
        )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    payload = json.loads((tmp_path / "inventory.json").read_text())
    expected = {source[-1] for source in public_sources}
    assert {
        source["source_identifier"] for source in payload["version_sources"]
    } == expected
    markdown = (tmp_path / "inventory.md").read_text()
    for identifier in expected:
        assert identifier in markdown


def test_source_identifier_redacts_public_shaped_values_in_wrong_context(db, tmp_path):
    target_id = _seed_target(db, "Identifier Context Binding")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "public-api.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    shaped_secrets = [
        "github:tags:Public/repo",
        "npm:public-package",
        "org.mozilla.firefox-playstore",
        "Shopify/cli-releases",
        "rss:rss:example.com/feed",
        "api:json_path:other-api.example/v",
        "latest_release",
    ]
    db.executemany(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, 'api', ?, 'json_path')""",
        [(asset_id, identifier) for identifier in shaped_secrets],
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    json_text = (tmp_path / "inventory.json").read_text()
    markdown = (tmp_path / "inventory.md").read_text()
    for identifier in shaped_secrets:
        assert identifier not in json_text
        assert identifier not in markdown
    assert {
        source["source_identifier"]
        for source in json.loads(json_text)["version_sources"]
    } == {"[REDACTED]"}


def test_snapshot_redacts_secrets_embedded_in_url_paths(db, tmp_path):
    target_id = _seed_target(db, "Path Secret")
    asset_id = db.execute(
        """INSERT INTO asset
           (vector_type, canonical_identifier, discovery_source_url)
           VALUES (?, ?, ?)""",
        ("api", "path-secret.example", "https://example.test/hooks/path-capability-secret"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )
    combined = (tmp_path / "inventory.json").read_text() + (
        tmp_path / "inventory.md"
    ).read_text()

    assert "path-capability-secret" not in combined
    assert "https://example.test/[REDACTED]" in combined


def test_check_compares_json_semantics_not_formatting(db, tmp_path):
    _seed_target(db, "Semantic")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]
    refresh_inventory(
        db_path=db_path,
        json_path=json_path,
        markdown_path=markdown_path,
        observed_at=OBSERVED_AT,
    )
    payload = json.loads(json_path.read_text())
    json_path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=False))

    assert check_inventory(
        db_path=db_path,
        json_path=json_path,
        markdown_path=markdown_path,
    ) == []


def test_check_reports_exactly_the_stale_artifact(db, tmp_path):
    _seed_target(db, "Exact")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]
    refresh_inventory(
        db_path=db_path,
        json_path=json_path,
        markdown_path=markdown_path,
        observed_at=OBSERVED_AT,
    )
    json_path.write_text("not json")

    assert check_inventory(
        db_path=db_path,
        json_path=json_path,
        markdown_path=markdown_path,
    ) == [str(json_path)]


def test_check_uses_markdown_timestamp_when_json_lacks_observed_at(db, tmp_path):
    _seed_target(db, "Missing Timestamp")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]
    refresh_inventory(
        db_path=db_path,
        json_path=json_path,
        markdown_path=markdown_path,
        observed_at=OBSERVED_AT,
    )
    payload = json.loads(json_path.read_text())
    payload.pop("observed_at")
    json_path.write_text(json.dumps(payload))

    assert check_inventory(
        db_path=db_path,
        json_path=json_path,
        markdown_path=markdown_path,
    ) == [str(json_path)]


def test_refresh_atomically_rewrites_private_artifacts(db, tmp_path):
    _seed_target(db, "Private")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json")
    markdown_path.write_text("old markdown")
    json_path.chmod(0o644)
    markdown_path.chmod(0o644)

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=json_path,
        markdown_path=markdown_path,
        observed_at=OBSERVED_AT,
    )

    assert stat.S_IMODE(json_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(markdown_path.stat().st_mode) == 0o600
    assert list(tmp_path.glob(".inventory.*.tmp")) == []


def test_refresh_is_byte_idempotent_with_controlled_observation_time(db, tmp_path):
    _seed_target(db, "Idempotent")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    arguments = {
        "db_path": db.execute("PRAGMA database_list").fetchone()["file"],
        "json_path": json_path,
        "markdown_path": markdown_path,
        "observed_at": OBSERVED_AT,
    }

    refresh_inventory(**arguments)
    first = (json_path.read_bytes(), markdown_path.read_bytes())
    refresh_inventory(**arguments)

    assert (json_path.read_bytes(), markdown_path.read_bytes()) == first


def test_snapshot_includes_scope_and_scheduled_source_summary(db, tmp_path):
    target_id = _seed_target(db, "Complete")
    platform_id = db.execute(
        "INSERT INTO bug_bounty_platform (name, slug) VALUES (?, ?)",
        ("Platform", "platform"),
    ).lastrowid
    program_id = db.execute(
        """INSERT INTO bug_bounty_program
           (platform_id, external_handle, name, program_url, policy_url)
           VALUES (?, ?, ?, ?, ?)""",
        (
            platform_id,
            "complete",
            "Complete Program",
            "https://platform.test/complete?session=private",
            "https://platform.test/complete/policy#private",
        ),
    ).lastrowid
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "complete.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, enabled)
           VALUES (?, ?, ?, ?, 1)""",
        (asset_id, "api", "complete-source", "json_path"),
    )
    db.execute(
        """INSERT INTO scope_record
           (program_id, asset_id, asset_identifier, asset_type, scope_status)
           VALUES (?, ?, ?, ?, ?)""",
        (program_id, asset_id, "complete.example", "URL", "in_scope"),
    )
    db.commit()

    snapshot = refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    assert snapshot["summary"]["version_sources_total"] == 1
    assert snapshot["summary"]["scheduled_sources"] == 1
    assert snapshot["summary"]["scheduled_by_type"] == {"api": 1}
    assert snapshot["summary"]["current_scope_records"] == 1
    assert snapshot["scheduled_version_sources"] == snapshot["version_sources"]
    assert snapshot["scope_records"][0]["program_url"] == (
        "https://platform.test/[REDACTED]?[REDACTED]"
    )


def test_shared_asset_does_not_duplicate_version_sources_or_summary(db, tmp_path):
    alpha_id = _seed_target(db, "Alpha")
    beta_id = _seed_target(db, "Beta")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "shared.example"),
    ).lastrowid
    db.executemany(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        [(alpha_id, asset_id), (beta_id, asset_id)],
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, enabled)
           VALUES (?, ?, ?, ?, 1)""",
        (asset_id, "api", "shared-source", "json_path"),
    )
    db.commit()

    snapshot = refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    assert snapshot["summary"]["version_sources_total"] == 1
    assert snapshot["summary"]["scheduled_sources"] == 1
    assert len(snapshot["version_sources"]) == 1
    assert [target["canonical_name"] for target in snapshot["version_sources"][0]["targets"]] == [
        "Alpha",
        "Beta",
    ]


def test_markdown_is_a_complete_view_of_the_same_snapshot(db, tmp_path):
    target_id = _seed_target(db, "Markdown Target")
    asset_id = db.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ("api", "markdown.example"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method)
           VALUES (?, ?, ?, ?)""",
        (asset_id, "api", "markdown.example/version", "json_path"),
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    markdown = (tmp_path / "inventory.md").read_text()
    assert "| Version sources total | 1 |" in markdown
    assert "## Targets" in markdown and "Markdown Target" in markdown
    assert "## Assets" in markdown and "markdown.example" in markdown
    assert "## Version sources" in markdown and "markdown.example/version" in markdown
    assert "## Current scope" in markdown


def test_cli_write_then_check_reports_fresh_artifacts(db, tmp_path, capsys):
    _seed_target(db, "CLI")
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    common = [
        "--db",
        db_path,
        "--json",
        str(json_path),
        "--markdown",
        str(markdown_path),
    ]

    assert main([*common, "--write", "--observed-at", OBSERVED_AT]) == 0
    assert main([*common, "--check"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"wrote {json_path}",
        f"wrote {markdown_path}",
        "inventory is fresh",
    ]


def test_cli_requires_exactly_one_mode(db, tmp_path):
    db_path = db.execute("PRAGMA database_list").fetchone()["file"]
    common = [
        "--db",
        db_path,
        "--json",
        str(tmp_path / "inventory.json"),
        "--markdown",
        str(tmp_path / "inventory.md"),
    ]

    with pytest.raises(SystemExit, match="2"):
        main(common)
    with pytest.raises(SystemExit, match="2"):
        main([*common, "--write", "--check", "--observed-at", OBSERVED_AT])


def test_database_path_with_uri_special_characters_is_opened_read_only(db, tmp_path):
    _seed_target(db, "Special Path")
    special_path = tmp_path / "inventory ?#%.db"
    copied = sqlite3.connect(special_path)
    db.backup(copied)
    copied.close()

    snapshot = refresh_inventory(
        db_path=special_path,
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )

    assert snapshot["targets"][0]["canonical_name"] == "Special Path"


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "missing ?#%.db"

    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        refresh_inventory(
            db_path=missing,
            json_path=tmp_path / "inventory.json",
            markdown_path=tmp_path / "inventory.md",
            observed_at=OBSERVED_AT,
        )

    assert not missing.exists()


def test_refresh_rolls_back_both_artifacts_when_second_replace_fails(
    db, tmp_path, monkeypatch
):
    _seed_target(db, "Rollback")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json")
    markdown_path.write_text("old markdown")
    json_path.chmod(0o640)
    markdown_path.chmod(0o644)
    real_replace = inventory.os.replace
    failed = False

    def fail_markdown_once(source, destination):
        nonlocal failed
        if Path(destination) == markdown_path and not failed:
            failed = True
            raise OSError("simulated second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(inventory.os, "replace", fail_markdown_once)

    with pytest.raises(OSError, match="simulated second replace failure"):
        refresh_inventory(
            db_path=db.execute("PRAGMA database_list").fetchone()["file"],
            json_path=json_path,
            markdown_path=markdown_path,
            observed_at=OBSERVED_AT,
        )

    assert json_path.read_text() == "old json"
    assert markdown_path.read_text() == "old markdown"
    assert stat.S_IMODE(json_path.stat().st_mode) == 0o640
    assert stat.S_IMODE(markdown_path.stat().st_mode) == 0o644
    assert list(tmp_path.glob(".inventory.*")) == []


def test_refresh_rejects_output_paths_that_resolve_to_the_same_file(db, tmp_path):
    _seed_target(db, "Aliased Outputs")
    output_path = tmp_path / "inventory.json"
    output_path.write_text("original")
    alias_path = tmp_path / "inventory-alias.md"
    alias_path.symlink_to(output_path)

    with pytest.raises(ValueError, match="output paths must be distinct"):
        refresh_inventory(
            db_path=db.execute("PRAGMA database_list").fetchone()["file"],
            json_path=output_path,
            markdown_path=alias_path,
            observed_at=OBSERVED_AT,
        )

    assert output_path.read_text() == "original"
    assert alias_path.is_symlink()


def test_refresh_preserves_backup_when_rollback_restore_fails(db, tmp_path, monkeypatch):
    _seed_target(db, "Failed Restore")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json")
    markdown_path.write_text("old markdown")
    real_replace = inventory.os.replace
    markdown_failed = False

    def fail_write_then_restore(source, destination):
        nonlocal markdown_failed
        source = Path(source)
        destination = Path(destination)
        if destination == markdown_path and not markdown_failed:
            markdown_failed = True
            raise OSError("simulated second replace failure")
        if destination == json_path and source.name.startswith(".inventory.backup."):
            raise OSError("simulated rollback restore failure")
        real_replace(source, destination)

    monkeypatch.setattr(inventory.os, "replace", fail_write_then_restore)

    with pytest.raises(OSError, match="simulated rollback restore failure"):
        refresh_inventory(
            db_path=db.execute("PRAGMA database_list").fetchone()["file"],
            json_path=json_path,
            markdown_path=markdown_path,
            observed_at=OBSERVED_AT,
        )

    backups = list(tmp_path.glob(".inventory.backup.*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "old json"
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    assert markdown_path.read_text() == "old markdown"


def test_markdown_contains_every_canonical_snapshot_section_and_field(db, tmp_path):
    target_id = _seed_target(db, "Parity")
    asset_id = db.execute(
        """INSERT INTO asset
           (vector_type, canonical_identifier, display_name)
           VALUES (?, ?, ?)""",
        ("api", "parity.example", "Parity Display"),
    ).lastrowid
    db.execute(
        "INSERT INTO target_asset (target_id, asset_id) VALUES (?, ?)",
        (target_id, asset_id),
    )
    db.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, source_url,
            config, enabled, on_error_policy)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            asset_id,
            "api",
            "parity.example/version",
            "json_path",
            "https://parity.example/version?secret=value",
            json.dumps({"path": "$.release.version"}),
            "retry_aggressive",
        ),
    )
    db.commit()

    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=tmp_path / "inventory.json",
        markdown_path=tmp_path / "inventory.md",
        observed_at=OBSERVED_AT,
    )
    markdown = (tmp_path / "inventory.md").read_text()

    assert "Parity Display" in markdown
    assert "https://parity.example/[REDACTED]?[REDACTED]" in markdown
    assert "$.release.version" in markdown
    assert "retry_aggressive" in markdown
    assert "## Scheduled version sources" in markdown
    assert "parity.example/version" in markdown.split("## Scheduled version sources", 1)[1]


def test_temporary_and_backup_files_remain_private_during_failed_refresh(
    db, tmp_path, monkeypatch
):
    _seed_target(db, "Private Failure")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json")
    markdown_path.write_text("old markdown")
    json_path.chmod(0o644)
    markdown_path.chmod(0o644)
    real_replace = inventory.os.replace
    inspected = False

    def inspect_then_fail(source, destination):
        nonlocal inspected
        if Path(destination) == markdown_path and not inspected:
            inspected = True
            temporary_modes = {
                stat.S_IMODE(path.stat().st_mode)
                for path in tmp_path.glob(".inventory.*")
            }
            assert temporary_modes == {0o600}
            raise OSError("simulated failure after permission inspection")
        real_replace(source, destination)

    monkeypatch.setattr(inventory.os, "replace", inspect_then_fail)
    with pytest.raises(OSError, match="simulated failure"):
        refresh_inventory(
            db_path=db.execute("PRAGMA database_list").fetchone()["file"],
            json_path=json_path,
            markdown_path=markdown_path,
            observed_at=OBSERVED_AT,
        )


def test_backup_never_inherits_public_destination_mode(db, tmp_path, monkeypatch):
    _seed_target(db, "Private Backup Copy")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json")
    markdown_path.write_text("old markdown")
    json_path.chmod(0o644)
    markdown_path.chmod(0o644)
    real_chmod = Path.chmod

    def assert_private_before_chmod(path, mode, *args, **kwargs):
        if path.name.startswith(".inventory.backup."):
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", assert_private_before_chmod)
    refresh_inventory(
        db_path=db.execute("PRAGMA database_list").fetchone()["file"],
        json_path=json_path,
        markdown_path=markdown_path,
        observed_at=OBSERVED_AT,
    )


def test_partial_backup_is_removed_when_copy_fails(db, tmp_path, monkeypatch):
    _seed_target(db, "Failed Backup Copy")
    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json")
    markdown_path.write_text("old markdown")

    def fail_after_partial_copy(source, destination, *args, **kwargs):
        Path(destination).write_text("partial private inventory")
        raise OSError("simulated backup copy failure")

    monkeypatch.setattr(inventory.shutil, "copyfile", fail_after_partial_copy)
    with pytest.raises(OSError, match="simulated backup copy failure"):
        refresh_inventory(
            db_path=db.execute("PRAGMA database_list").fetchone()["file"],
            json_path=json_path,
            markdown_path=markdown_path,
            observed_at=OBSERVED_AT,
        )

    assert list(tmp_path.glob(".inventory.*")) == []
