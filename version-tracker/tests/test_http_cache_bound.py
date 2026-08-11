import sqlite3
import urllib.error
from email.message import Message

import pytest

from checkers import http_cache


class _OversizedResponse:
    status = 200
    headers = {}

    def __init__(self):
        self.read_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        self.read_calls.append(size)
        return b"x" * size


class _RedirectingOpener:
    def __init__(self, location=None, code=302):
        self.location = location
        self.code = code
        self.requests = []

    def open(self, req, timeout=30):
        self.requests.append(req.full_url)
        headers = Message()
        if self.location:
            headers["Location"] = self.location
        raise urllib.error.HTTPError(
            req.full_url,
            self.code,
            "Found" if self.code == 302 else "Not Modified",
            headers,
            None,
        )


def test_fetch_enforces_bound_during_network_read(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.row_factory = sqlite3.Row
    response = _OversizedResponse()
    monkeypatch.setattr(http_cache, "_conn", conn)
    monkeypatch.setattr(http_cache, "_ensured", False)
    # After 2026-08-06 audit fix: default follow_redirects=False routes via
    # build_opener(_NoRedirectHandler()).open, NOT urllib.request.urlopen.
    # We patch both for safety: any future rebind stays covered.
    monkeypatch.setattr(http_cache.urllib.request, "urlopen", lambda *args, **kwargs: response)
    monkeypatch.setattr(http_cache.urllib.request, "build_opener", lambda *args, **kwargs: type("Fake", (), {"open": staticmethod(lambda *a, **k: response)})())

    with pytest.raises(http_cache.ResponseTooLargeError):
        # Default follow_redirects=False (2026-08-06 audit fix): explicitly
        # pin the default so the bound-method signature is preserved.
        http_cache.fetch("https://feed.example/rss", max_bytes=100, follow_redirects=False)

    assert response.read_calls == [101]
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_fetch_can_block_redirect_without_requesting_destination(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.row_factory = sqlite3.Row
    opener = _RedirectingOpener("https://other.example/script.js")
    monkeypatch.setattr(http_cache, "_conn", conn)
    monkeypatch.setattr(http_cache, "_ensured", False)
    monkeypatch.setattr(http_cache.urllib.request, "build_opener", lambda *args: opener)

    with pytest.raises(http_cache.RedirectBlockedError) as exc_info:
        http_cache.fetch(
            "https://example.com/script.js",
            follow_redirects=False,
        )

    assert exc_info.value.location == "https://other.example/script.js"
    assert opener.requests == ["https://example.com/script.js"]
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_no_redirect_mode_preserves_304_cache_semantics(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.row_factory = sqlite3.Row
    opener = _RedirectingOpener(code=304)
    monkeypatch.setattr(http_cache, "_conn", conn)
    monkeypatch.setattr(http_cache, "_ensured", False)
    monkeypatch.setattr(http_cache.urllib.request, "build_opener", lambda *args: opener)

    result = http_cache.fetch(
        "https://example.com/script.js",
        follow_redirects=False,
    )

    assert result is None
    assert opener.requests == ["https://example.com/script.js"]


# --- Audit-driven contract (2026-08-06): "stay on domain" is the default. ---


def test_fetch_blocks_redirects_by_default(tmp_path, monkeypatch):
    """Audit fix: the default for `follow_redirects` is False so a configured
    URL that 302-redirects is surfaced as `RedirectBlockedError` rather than
    silently followed."""
    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.row_factory = sqlite3.Row
    opener = _RedirectingOpener(
        location="https://other.example/page",
        code=302,
    )
    monkeypatch.setattr(http_cache, "_conn", conn)
    monkeypatch.setattr(http_cache, "_ensured", False)
    monkeypatch.setattr(http_cache.urllib.request, "build_opener", lambda *args: opener)

    with pytest.raises(http_cache.RedirectBlockedError) as exc_info:
        http_cache.fetch("https://example.com/page")

    assert exc_info.value.location == "https://other.example/page"
    assert opener.requests == ["https://example.com/page"]


def test_fetch_follows_redirects_when_opted_in(tmp_path, monkeypatch):
    """Audit fix (2026-08-06): when a caller passes follow_redirects=True, the
    production path uses urllib.request.urlopen (the default opener), NOT the
    build_opener(_NoRedirectHandler()).open path. The follow_redirects=True
    branch is reached by passing through to urllib's default redirect handler.

    This test pins the contract via the recorded Location: with the default
    (False), the configured URL must surface its Location header; with True,
    urllib is given the latitude to follow.

    Specifically, we verify:

      1. follow_redirects=False surfaces RedirectBlockedError.
      2. follow_redirects=True does not (any urllib-based handling).

    We do not simulate urllib's internal redirect chain end-to-end here;
    that exercise belongs to the integration suite under tests/checkers.
    """

    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.row_factory = sqlite3.Row
    captured = {"mode": None}

    class _BoundOpener:
        def __init__(self, mode):
            self.mode = mode

        def open(self, req, timeout=30):
            captured["mode"] = self.mode
            if self.mode == "no_redirect":
                headers = Message()
                headers["Location"] = "https://other.example/page"
                raise urllib.error.HTTPError(
                    req.full_url if isinstance(req, urllib.request.Request) else req,
                    302,
                    "Found",
                    headers,
                    None,
                )
            # follow_redirects=True: simulate urllib following a redirect and
            # returning the destination body.
            resp = _OversizedResponse()
            resp.status = 200
            resp.read_calls = []
            return resp

    # In follow_redirects=False the production uses build_opener(...).open.
    monkeypatch.setattr(
        http_cache.urllib.request,
        "build_opener",
        lambda *args, **kwargs: _BoundOpener("no_redirect"),
    )
    with pytest.raises(http_cache.RedirectBlockedError):
        http_cache.fetch("https://example.com/start", follow_redirects=False)

    # In follow_redirects=True the production uses urllib.request.urlopen.
    # urlopen is patched via the bound method on the same mock.
    monkeypatch.setattr(
        http_cache.urllib.request,
        "urlopen",
        lambda req, timeout=30: _BoundOpener("follow").open(req, timeout=timeout),
    )
    body = http_cache.fetch("https://example.com/start", follow_redirects=True)
    assert body is not None
    assert captured["mode"] == "follow"


def test_follow_redirects_false_records_intermediate_location_url(tmp_path, monkeypatch):
    """Audit fix: when `follow_redirects=False` raises RedirectBlockedError,
    the `location` attribute carries the redirect target. Callers use this
    to record an STORAGE_MOVED-style redirect-history note on the version_source.
    """
    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.row_factory = sqlite3.Row
    opener = _RedirectingOpener(
        location="https://other.example/redirect-target",
        code=302,
    )
    monkeypatch.setattr(http_cache, "_conn", conn)
    monkeypatch.setattr(http_cache, "_ensured", False)
    monkeypatch.setattr(http_cache.urllib.request, "build_opener", lambda *args: opener)

    with pytest.raises(http_cache.RedirectBlockedError) as exc_info:
        http_cache.fetch("https://example.com/page")

    assert exc_info.value.location == "https://other.example/redirect-target"
