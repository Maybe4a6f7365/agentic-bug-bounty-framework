"""
tests/test_checker_android_store.py — Google Play Store checker unit tests.

Phase 3.  Verifies app_id resolution, version extraction, "Varies with device"
fallback, APP_UNLISTED, and error handling — all with FakeGPSModule injected
as google-play-scraper.  No real Play Store calls.
"""

import sys

import pytest

from tests.support.fakes import (
    FakeGPSModule,
    load_checker,
    FIREFOX_APP,
    FIREFOX_APP_V2,
    VARIES_APP,
)

# ── Module-level imports (replaces setUpClass) ────────────────────

from checkers import runner  # noqa: E402
CheckerError = runner.CheckerError


# ── Autouse fixture: inject fake_gps into sys.modules ─────────────

@pytest.fixture(autouse=True)
def _inject_fake_gps(fake_gps, monkeypatch):
    """Inject fake_gps as google_play_scraper before each test;
    monkeypatch cleans up on teardown."""
    monkeypatch.setitem(sys.modules, "google_play_scraper", fake_gps)


# ── App ID resolution ─────────────────────────────────────────────

def test_resolves_app_id_direct(fake_gps) -> None:
    """Config with app_id='org.mozilla.firefox' → resolves to that ID."""
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({"app_id": "org.mozilla.firefox"})

    assert result is not None
    assert result.version_value == "152.0.6"
    assert fake_gps.app.calls[0][0] == "org.mozilla.firefox"


def test_resolves_package_name(fake_gps) -> None:
    """Config with package_name → same resolution path."""
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({"package_name": "org.mozilla.firefox"})

    assert result is not None
    assert result.version_value == "152.0.6"


def test_resolves_from_store_url_query(fake_gps) -> None:
    """Config with store_url containing ?id=... → extracts app_id."""
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({
        "store_url": "https://play.google.com/store/apps/details?id=org.mozilla.firefox",
    })

    assert result is not None
    assert result.version_value == "152.0.6"


def test_resolves_from_store_url_path(fake_gps) -> None:
    """store_url with id= in path (no query string) → extracts app_id."""
    fake_gps.app.set("com.example.app", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({
        "store_url": "https://play.google.com/store/apps/details?id=com.example.app&hl=en",
    })

    assert result is not None
    assert result.version_value is not None


# ── Happy path ────────────────────────────────────────────────────

def test_version_extracted(fake_gps) -> None:
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({"app_id": "org.mozilla.firefox"})

    assert result is not None
    assert result.changed
    assert result.version_value == "152.0.6"
    assert result.raw_metadata["app_id"] == "org.mozilla.firefox"
    assert result.raw_metadata["title"] == "Firefox Fast & Private Browser"
    assert result.raw_metadata["developer"] == "Mozilla"
    assert result.change_type == "release_published"


def test_version_change_detected(fake_gps) -> None:
    """New version → different immutable_id → CheckResult."""
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP_V2)
    mod = load_checker("android_store")

    result = mod.check({
        "app_id": "org.mozilla.firefox",
        "_last_immutable_id": "stale_hash_dead",
    })

    assert result is not None
    assert result.version_value == "153.0.0"


def test_no_change_same_immutable_id(fake_gps) -> None:
    """Same version → same immutable_id → check() returns None."""
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result1 = mod.check({"app_id": "org.mozilla.firefox"})
    assert result1 is not None

    # Second call with same immutable_id — fresh module for isolation
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod2 = load_checker("android_store")

    result2 = mod2.check({
        "app_id": "org.mozilla.firefox",
        "_last_immutable_id": result1.immutable_identifier,
    })
    assert result2 is None


# ── "Varies with device" fallback ─────────────────────────────────

def test_varies_with_device_falls_back_to_version_code(fake_gps) -> None:
    """version='Varies with device' → uses versionCode instead."""
    fake_gps.app.set("com.example.varies", VARIES_APP)
    mod = load_checker("android_store")

    result = mod.check({"app_id": "com.example.varies"})

    assert result is not None
    assert result.version_value == "500"


# ── Parsed metadata ───────────────────────────────────────────────

def test_published_at_converted_to_iso(fake_gps) -> None:
    """updated epoch seconds → ISO-8601 published_at."""
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({"app_id": "org.mozilla.firefox"})

    assert result is not None
    assert result.published_at is not None
    assert "T" in result.published_at
    assert "Z" in result.published_at


def test_raw_metadata_has_play_store_url(fake_gps) -> None:
    fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)
    mod = load_checker("android_store")

    result = mod.check({"app_id": "org.mozilla.firefox"})

    assert result is not None
    assert result.raw_metadata.get("play_store_url") is not None


# ── Error branches ────────────────────────────────────────────────

def test_app_not_found_raises_app_unlisted(fake_gps) -> None:
    """Play Store returns NotFoundError → APP_UNLISTED."""
    fake_gps.app.set_not_found("com.nonexistent.app")
    mod = load_checker("android_store")

    with pytest.raises(CheckerError) as exc_info:
        mod.check({"app_id": "com.nonexistent.app"})
    assert "APP_UNLISTED" in str(exc_info.value)


def test_missing_app_id_raises_parse_error(fake_gps) -> None:
    """No app_id, package_name, or store_url → PARSE_ERROR."""
    mod = load_checker("android_store")

    with pytest.raises(CheckerError) as exc_info:
        mod.check({"some_other_key": "value"})
    assert "PARSE_ERROR" in str(exc_info.value)
    assert "Missing app_id" in str(exc_info.value)


def test_empty_app_id_raises_parse_error(fake_gps) -> None:
    """app_id='' (falsy) → no fallback → PARSE_ERROR."""
    mod = load_checker("android_store")

    with pytest.raises(CheckerError) as exc_info:
        mod.check({"app_id": ""})
    assert "PARSE_ERROR" in str(exc_info.value)


def test_missing_version_and_version_code_falls_back_to_dict_hash(fake_gps) -> None:
    """App has no version, no versionCode, no updated → falls back to
    'varies:{listing_hash}' instead of raising PARSE_ERROR (Phase D.5
    content-hash fallback)."""
    fake_gps.app.set("com.empty.app", {
        "title": "Empty App",
        "version": None,
        "versionCode": None,
        "updated": None,
    })
    mod = load_checker("android_store")

    result = mod.check({"app_id": "com.empty.app"})
    assert result is not None
    assert result.version_value.startswith("varies:")


def test_scraper_generic_error_raises_unknown(fake_gps) -> None:
    """Non-NotFound scraper exception → UNKNOWN."""
    fake_gps.app.set_error("com.crash.app", RuntimeError("Something broke"))
    mod = load_checker("android_store")

    with pytest.raises(CheckerError) as exc_info:
        mod.check({"app_id": "com.crash.app"})
    assert "UNKNOWN" in str(exc_info.value)


def test_scraper_not_found_message_raises_app_unlisted(fake_gps) -> None:
    """Generic exception with 'not found' in message → APP_UNLISTED."""
    fake_gps.app.set_error("com.removed.app", Exception("App not found on store"))
    mod = load_checker("android_store")

    with pytest.raises(CheckerError) as exc_info:
        mod.check({"app_id": "com.removed.app"})
    assert "APP_UNLISTED" in str(exc_info.value)


def test_store_url_without_app_id_raises_parse_error(fake_gps) -> None:
    """store_url without id= anywhere → empty app_id → PARSE_ERROR."""
    mod = load_checker("android_store")

    with pytest.raises(CheckerError) as exc_info:
        mod.check({"store_url": "https://play.google.com/store/apps"})
    assert "PARSE_ERROR" in str(exc_info.value)


def test_no_version_but_has_updated_fallback(fake_gps) -> None:
    """App with updated timestamp but no version/versionCode
    → version_value = 'updated:<epoch>'."""
    fake_gps.app.set("com.updated.only", {
        "title": "Update Only App",
        "version": "Varies with device",
        "versionCode": None,
        "updated": 1740000000,
    })
    mod = load_checker("android_store")

    result = mod.check({"app_id": "com.updated.only"})

    assert result is not None
    assert "updated:" in result.version_value
