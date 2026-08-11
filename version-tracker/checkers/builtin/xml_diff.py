"""
checkers/builtin/xml_diff.py — Canonicalised XML / text file diff checker.

Config shape:
  {"feed_url": "https://example.com/robots.txt",
   "content_type_hint": "text/plain"}
  {"feed_url": "https://example.com/sitemap.xml",
   "content_type_hint": "application/xml"}

The checker fetches exactly one URL — the one in `feed_url` — and
canonicalises the body so cosmetic edits (whitespace, comments, blank-line
runs) don't fire change events.

Canonicalisation rules:
  For XML-ish content (anything not flagged as `text/plain`):
    - Drop XML comments (<!-- … -->).
    - Collapse runs of whitespace inside tags to a single space.
    - Trim leading/trailing whitespace on each tag and on the document.
  For text/plain content (robots.txt):
    - Drop lines starting with `#` (robots.txt comments).
    - Strip trailing whitespace on each line.
    - Collapse runs of blank lines to a single blank line.
  Either way the output is bytes-stable: the same source body always
  canonicalises to the same canonical bytes.

OSINT boundary:
  Only one URL is fetched per check — the `feed_url` from config. There is
  no discovery, no link following, no parsing of <loc>, <url>, <sitemap>,
  or any other element. No probing of `Disallow:` paths. Every fetch
  carries identity.research_headers() so the program can attribute the
  traffic.

Returns CheckResult when the canonical body changes, None when
http_cache returns 304 Not Modified.

Mirrors checkers/builtin/rss.py's return shape.
"""

import hashlib
import json
import re
import urllib.error


class _Err:
    STORAGE_MOVED = "STORAGE_MOVED"
    FEED_GONE = "FEED_GONE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PARSE_ERROR = "PARSE_ERROR"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    UNKNOWN = "UNKNOWN"
    BOT_WALL = "BOT_WALL"


def _fetch(url: str, req_headers: dict, timeout: int = 30):
    try:
        raw = http_cache.fetch(url, req_headers, timeout=timeout)
        # follow_redirects=False: 2026-08-06 audit. The module-level docstring
        # above already states "no link following" for OSINT reasons; the
        # new default in http_cache.fetch keeps this contract.
        if raw is None:
            return None  # 304 Not Modified
        return raw
    except urllib.error.HTTPError as e:
        code_map = {
            404: _Err.STORAGE_MOVED,
            410: _Err.STORAGE_MOVED,
            401: _Err.AUTH_REQUIRED,
            403: _Err.BOT_WALL,
            429: _Err.RATE_LIMITED,
        }
        raise CheckerError(code_map.get(e.code, _Err.UNKNOWN), f"HTTP {e.code}: {url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")


def _canonicalise_xml(body: str) -> str:
    """Drop XML comments, collapse whitespace, trim tags.

    Deliberately not a full XML parse — we never descend into <loc>,
    <url>, or <sitemap>, and there is no XML walker that could be
    tricked into following them.
    """
    # Strip <!-- … --> comments (non-greedy, may span lines).
    no_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # Collapse runs of whitespace inside tags/text to a single space.
    collapsed = re.sub(r"\s+", " ", no_comments)
    # Trim the document and recover a structural shape by re-inserting
    # newlines before each opening tag (purely cosmetic; the hash is the
    # same either way, but it keeps diffs human-readable).
    spaced = re.sub(r"\s*<\s*", "\n<", collapsed)
    # Drop empty lines and trailing whitespace on each remaining line.
    lines = [line.rstrip() for line in spaced.split("\n") if line.strip()]
    return "\n".join(lines)


def _canonicalise_text(body: str) -> str:
    """robots.txt-style canonicalisation: drop comments, normalise blanks."""
    lines = []
    for line in body.splitlines():
        # Drop comment lines (robots.txt convention).
        if line.lstrip().startswith("#"):
            continue
        lines.append(line.rstrip())
    # Collapse runs of blank lines to a single blank line.
    deduped = []
    prev_blank = False
    for line in lines:
        is_blank = (line.strip() == "")
        if is_blank and prev_blank:
            continue
        deduped.append(line)
        prev_blank = is_blank
    # Strip leading/trailing blank lines.
    while deduped and deduped[0].strip() == "":
        deduped.pop(0)
    while deduped and deduped[-1].strip() == "":
        deduped.pop()
    return "\n".join(deduped)


def check(config: dict):
    feed_url = config.get("feed_url", "")
    content_type_hint = (config.get("content_type_hint") or "").lower()
    last_immutable_id = config.get("_last_immutable_id")

    if not feed_url:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'feed_url' in config")

    req_headers = identity.research_headers()

    raw = _fetch(feed_url, req_headers)
    if raw is None:
        return None  # 304 — content unchanged
    if not raw.strip():
        raise CheckerError(_Err.EMPTY_RESPONSE, f"Empty response from {feed_url}")

    try:
        text = raw.decode("utf-8", "replace")
    except Exception:
        raise CheckerError(_Err.PARSE_ERROR, f"Could not decode response from {feed_url}")

    # Choose canonicaliser from the explicit hint; default to XML-style
    # because most use-cases (sitemap.xml, atom.xml reused here) are XML.
    if content_type_hint == "text/plain":
        canonical = _canonicalise_text(text)
    else:
        canonical = _canonicalise_xml(text)

    canonical_bytes = canonical.encode("utf-8")
    immutable_id = hashlib.sha256(canonical_bytes).hexdigest()
    content_hash = hashlib.sha256(canonical_bytes).hexdigest()

    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    # Wrap the canonical body in a stable JSON envelope so the runner has
    # a uniform version_value shape (string vs dict) — same convention as
    # the api_json checker, which uses str(value) when the JSONPath
    # returned a string.
    version_value = json.dumps(
        {"canonical_body": canonical, "content_type_hint": content_type_hint or "xml"},
        sort_keys=True,
        separators=(",", ":"),
    )

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        content_hash=content_hash,
        raw_metadata={
            "feed_url": feed_url,
            "content_type_hint": content_type_hint or "xml",
            "canonical_bytes": len(canonical_bytes),
        },
        change_type="xml_diff_changed",
    )
