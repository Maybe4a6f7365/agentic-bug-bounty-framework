"""
checkers/http_cache.py — HTTP cache with ETag/Last-Modified support.

Reduces bandwidth and rate-limit pressure for the daily version sweep.
On a cache hit with 304 Not Modified, returns None (signal: unchanged).
On cache miss or content change (200), returns bytes body.

Uses a single cached connection per process with a busy timeout, so
concurrent writer contention never gets an immediate SQLITE_BUSY.

Usage (in checkers):
    try:
        body = http_cache.fetch(url, headers, timeout=30)
        if body is None:
            return None  # Content unchanged — skip version extraction
    except urllib.error.HTTPError as e:
        ...  # Same error handling as before

Table: http_cache(url, etag, last_modified, body_hash, status_code,
                  cached_at, last_hit_at, hit_count)
"""

import hashlib
import os
import sqlite3
import threading
import urllib.request
import urllib.error


class BotWallError(Exception):
    """Raised when a bot wall is detected during HTTP fetch.

    Mirrors the CheckerError interface from runner.py so the runner's
    except block can catch it without a circular import (runner imports
    http_cache, so http_cache cannot import from runner).
    """
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ResponseTooLargeError(Exception):
    """Raised before an HTTP response can exceed a caller's memory bound."""

    def __init__(self, url: str, max_bytes: int):
        self.url = url
        self.max_bytes = max_bytes
        super().__init__(f"response from {url} exceeds {max_bytes} bytes")


class RedirectBlockedError(Exception):
    """Raised when a caller opts out of redirects and receives one."""

    def __init__(self, url: str, location: str | None):
        self.url = url
        self.location = location or ""
        super().__init__(f"redirect blocked: {url} -> {self.location or '[missing Location]'}")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Make urllib surface 3xx responses instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Shared DB path — same as runner.py
_DB_PATH = os.environ.get(
    "VERSION_TRACKER_DB",
    os.path.expanduser("~/.hermes/version-tracker/version_tracker.db"),
)

_CACHE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS http_cache (
    url             TEXT PRIMARY KEY,
    etag            TEXT,
    last_modified   TEXT,
    body_hash       TEXT NOT NULL,
    status_code     INTEGER NOT NULL DEFAULT 200,
    cached_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_hit_at     TEXT NOT NULL DEFAULT (datetime('now')),
    hit_count       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_http_cache_last_hit ON http_cache(last_hit_at);
"""

_ensured = False

# ── Cached connection (one per process, with busy timeout) ──
_conn = None
_conn_lock = threading.Lock()


def _get_conn():
    """One cached connection per process, with a busy timeout."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.execute("PRAGMA busy_timeout = 30000")
        _conn.row_factory = sqlite3.Row
    return _conn


def _ensure_table():
    """Create the cache table if it doesn't exist (idempotent, once per process)."""
    global _ensured
    if _ensured:
        return
    conn = _get_conn()
    conn.executescript(_CACHE_TABLE_DDL)
    conn.commit()
    _ensured = True


def fetch(url: str, headers: dict | None = None, timeout: int = 30,
          max_bytes: int | None = None,
          follow_redirects: bool = False) -> bytes | None:
    """Fetch a URL with ETag/Last-Modified conditional request support.

    Args:
        url: The URL to fetch.
        headers: Dict of request headers (User-Agent, Authorization, etc.).
        timeout: Request timeout in seconds.
        max_bytes: Optional hard response-body bound enforced during read.
        follow_redirects: Follow HTTP redirects when True. **Default False**: a
            configured URL that 3xx-redirects is treated as an *observable
            change* (raises `RedirectBlockedError` and exposes the Location),
            so silent migrations surface post-hoc. Operators must opt in to
            redirect-following on a per-call basis where redirect-to-canonical
            is part of the protocol (e.g., RSS feed readers following
            `Location: /feed.xml` to a CDN).

    Returns:
        bytes  — response body (new or changed content).
        None   — content unchanged (304 Not Modified from cache).

    Raises:
        urllib.error.HTTPError  — on non-304 HTTP errors (404, 403, 429, ...).
        urllib.error.URLError   — on connection/timeout/DNS errors.
        ResponseTooLargeError   — before reading beyond max_bytes.
        RedirectBlockedError    — on 3xx when follow_redirects is False.
    """
    _ensure_table()

    conn = _get_conn()
    row = conn.execute(
        "SELECT etag, last_modified FROM http_cache WHERE url = ?", [url]
    ).fetchone()

    req_headers = dict(headers) if headers else {}
    if row:
        if row["etag"]:
            req_headers["If-None-Match"] = row["etag"]
        if row["last_modified"]:
            req_headers["If-Modified-Since"] = row["last_modified"]

    req = urllib.request.Request(url, headers=req_headers)

    open_request = urllib.request.urlopen
    if not follow_redirects:
        open_request = urllib.request.build_opener(_NoRedirectHandler()).open

    try:
        with open_request(req, timeout=timeout) as resp:
            # 304 Not Modified — use cached data
            if getattr(resp, "status", 200) == 304:
                with _conn_lock:
                    conn.execute(
                        "UPDATE http_cache SET last_hit_at = datetime('now'), "
                        "hit_count = hit_count + 1 WHERE url = ?",
                        [url],
                    )
                    conn.commit()
                return None

            if max_bytes is not None:
                if max_bytes < 0:
                    raise ValueError("max_bytes must be non-negative")
                content_length = resp.headers.get("Content-Length")
                try:
                    declared_length = int(content_length) if content_length else None
                except (TypeError, ValueError):
                    declared_length = None
                if declared_length is not None and declared_length > max_bytes:
                    raise ResponseTooLargeError(url, max_bytes)
                body = resp.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ResponseTooLargeError(url, max_bytes)
            else:
                body = resp.read()
            etag = resp.headers.get("ETag", "")
            last_modified = resp.headers.get("Last-Modified", "")
            body_hash = hashlib.sha256(body).hexdigest()

            with _conn_lock:
                conn.execute(
                    """INSERT OR REPLACE INTO http_cache
                       (url, etag, last_modified, body_hash, status_code,
                        cached_at, last_hit_at, hit_count)
                       VALUES (?, ?, ?, ?, 200,
                               COALESCE((SELECT cached_at FROM http_cache WHERE url = ?),
                                        datetime('now')),
                               datetime('now'),
                               COALESCE((SELECT hit_count FROM http_cache WHERE url = ?), 0) + 1)""",
                    [url, etag, last_modified, body_hash, url, url],
                )
                conn.commit()
            return body

    except urllib.error.HTTPError as e:
        if not follow_redirects and e.code != 304 and 300 <= e.code < 400:
            raise RedirectBlockedError(url, e.headers.get("Location")) from e

        # 304 from a server that raises instead of returning the response
        if e.code == 304:
            with _conn_lock:
                conn.execute(
                    "UPDATE http_cache SET last_hit_at = datetime('now'), "
                    "hit_count = hit_count + 1 WHERE url = ?",
                    [url],
                )
                conn.commit()
            return None

        # Bot wall detection: on 403, read the body to classify before propagating
        if e.code == 403:
            try:
                body_preview = e.read(500).decode(errors='replace')
                wall_sigs = ['access denied', 'challenges.cloudflare.com',
                             'hcaptcha.com', 'recaptcha']
                if any(sig in body_preview.lower() for sig in wall_sigs):
                    raise BotWallError(
                        "BOT_WALL",
                        f"Bot wall at {url}: {body_preview[:200]}"
                    )
            except BotWallError:
                raise  # Re-raise our own BotWallError
            except Exception:
                pass  # Can't read body — fall through to normal raise

        raise  # All other HTTP errors propagate to checker's error handler


def stats() -> dict:
    """Return cache hit/miss statistics for diagnostics."""
    _ensure_table()
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) AS n FROM http_cache").fetchone()["n"]
    total_hits = conn.execute(
        "SELECT COALESCE(SUM(hit_count), 0) AS n FROM http_cache"
    ).fetchone()["n"]
    recent = conn.execute(
        "SELECT COUNT(*) AS n FROM http_cache "
        "WHERE last_hit_at > datetime('now', '-7 days')"
    ).fetchone()["n"]
    return {
        "entries": total,
        "total_hits": total_hits,
        "active_7d": recent,
        "db_path": _DB_PATH,
    }


def clear_expired(max_age_days: int = 90):
    """Remove cache entries not hit in max_age_days."""
    _ensure_table()
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM http_cache WHERE last_hit_at < datetime('now', ?)",
        [f"-{max_age_days} days"],
    )
    deleted = cur.rowcount
    conn.commit()
    return deleted
