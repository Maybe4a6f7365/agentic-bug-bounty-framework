"""
checkers/builtin/rss.py — order-independent RSS/Atom snapshot checker.

Every poll canonicalizes the complete feed into an identifier-keyed snapshot.
Entry order never affects change detection. A later snapshot reports every
added, removed, or content-edited entry in ``CheckResult.change_items``.
"""

import hashlib
import json
import urllib.error
import xml.etree.ElementTree as ET


class _Err:
    STORAGE_MOVED = "STORAGE_MOVED"
    FEED_GONE = "FEED_GONE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"
    PARSE_ERROR = "PARSE_ERROR"
    UNKNOWN = "UNKNOWN"
    BOT_WALL = "BOT_WALL"


NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
}
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_ENTRIES = 2000


def _element(node, namespaced_path, plain_path):
    element = node.find(namespaced_path, NS)
    if element is None:
        element = node.find(plain_path)
    return element


def _element_text(element):
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _element_canonical(element):
    if element is None:
        return ""
    serialized = ET.tostring(element, encoding="unicode")
    try:
        return ET.canonicalize(serialized)
    except (ET.ParseError, ValueError):
        return serialized


def _entry(identifier, link, title, published_at, canonical_body,
           observation_body=None):
    title = title or ""
    canonical_body = canonical_body or ""
    observation_body = canonical_body if observation_body is None else observation_body
    identifier = identifier or link or hashlib.sha256(
        (title + observation_body).encode()
    ).hexdigest()[:16]
    identifier = str(identifier)
    if len(identifier) > 1000:
        identifier = "sha256:" + hashlib.sha256(identifier.encode()).hexdigest()
    link = str(link)[:1000] if link else None
    published_at = str(published_at)[:200] if published_at else None
    canonical = {
        "item_identifier": identifier,
        "title": title[:500],
        "link": link,
        "published_at": published_at,
        "content_hash": hashlib.sha256(
            json.dumps(
                {
                    "title": title,
                    "body": canonical_body,
                    "link": link,
                    "published_at": published_at,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "observation_hash": hashlib.sha256(
            f"{title} {observation_body}".encode()
        ).hexdigest(),
    }
    return canonical


def _snapshot_hash(entries_by_id):
    return hashlib.sha256(
        json.dumps(entries_by_id, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _previous_entries(config):
    metadata = config.get("_last_raw_metadata") or {}
    entries = metadata.get("entries")
    if isinstance(entries, dict):
        return entries, "modern"

    # Upgrade observations written by the former newest-first checker. Hashes
    # are unknown, so retained identifiers must not be reported as edits. The
    # old checker capped all_guids at 20; entry_count tells us whether the list
    # represented the full feed or only a prefix.
    legacy_ids = metadata.get("all_guids")
    if isinstance(legacy_ids, list):
        previous = {
            str(identifier): {
                "item_identifier": str(identifier),
                "content_hash": None,
            }
            for identifier in legacy_ids
        }
        complete = metadata.get("entry_count") == len(previous)
        return previous, "legacy_complete" if complete else "legacy_partial"
    return None, "none"


def _diff(previous, current):
    changes = []
    previous_ids = set(previous)
    current_ids = set(current)

    for identifier in sorted(current_ids - previous_ids):
        changes.append({
            "item_identifier": identifier,
            "change_type": "changelog_entry_added",
            "old": None,
            "new": current[identifier],
        })

    for identifier in sorted(previous_ids & current_ids):
        old_hash = previous[identifier].get("content_hash")
        if old_hash is not None and old_hash != current[identifier]["content_hash"]:
            changes.append({
                "item_identifier": identifier,
                "change_type": "content_changed",
                "old": previous[identifier],
                "new": current[identifier],
            })

    for identifier in sorted(previous_ids - current_ids):
        changes.append({
            "item_identifier": identifier,
            "change_type": "source_disappeared",
            "old": previous[identifier],
            "new": None,
        })
    return changes


def check(config: dict):
    feed_url = config.get("feed_url", "")
    last_immutable_id = config.get("_last_immutable_id")
    if not feed_url:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'feed_url' in config")

    try:
        raw = http_cache.fetch(
            feed_url,
            identity.research_headers(),
            timeout=30,
            max_bytes=MAX_FEED_BYTES,
            # RSS feeds live behind redirect-to-canonical at the protocol
            # level (e.g., Location: /feed.xml, /rss). 2026-08-06 audit:
            # explicitly opt in so the new default (no-follow) does not
            # surface every RSS endpoint as STORAGE_MOVED.
            follow_redirects=True,
        )
        if raw is None:
            return None
        if len(raw) > MAX_FEED_BYTES:
            raise CheckerError(
                _Err.PARSE_ERROR,
                f"Feed exceeds {MAX_FEED_BYTES} byte safety limit: {feed_url}",
            )
    except http_cache.ResponseTooLargeError as exc:
        raise CheckerError(_Err.PARSE_ERROR, str(exc))
    except urllib.error.HTTPError as exc:
        code_map = {
            404: _Err.FEED_GONE,
            410: _Err.FEED_GONE,
            301: _Err.STORAGE_MOVED,
            302: _Err.STORAGE_MOVED,
            401: _Err.AUTH_REQUIRED,
            403: _Err.BOT_WALL,
        }
        raise CheckerError(code_map.get(exc.code, _Err.UNKNOWN), f"HTTP {exc.code}: {feed_url}")
    except urllib.error.URLError as exc:
        if "timed out" in str(exc).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {feed_url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {exc}")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise CheckerError(
            _Err.FEED_GONE,
            f"XML parse error — feed may no longer be valid: {feed_url}",
        )

    tag = root.tag.lower()
    is_atom = "atom" in tag or "feed" in tag
    is_rss = "rss" in tag
    if not (is_atom or is_rss):
        raise CheckerError(_Err.FEED_GONE, f"Unknown feed format: {tag}")

    entries = []
    if is_atom:
        for node in root.findall("atom:entry", NS) or root.findall("entry"):
            identifier = (
                node.findtext("atom:id", default=None, namespaces=NS)
                or node.findtext("id")
            )
            alternate = node.find("atom:link[@rel='alternate']", NS)
            link_node = alternate if alternate is not None else node.find("atom:link", NS)
            if link_node is None:
                link_node = node.find("link")
            link = link_node.get("href") if link_node is not None else None
            title_element = _element(node, "atom:title", "title")
            title = _element_text(title_element)
            published = (
                node.findtext("atom:updated", default=None, namespaces=NS)
                or node.findtext("updated")
            )
            summary_element = _element(node, "atom:summary", "summary")
            content_element = _element(node, "atom:content", "content")
            summary_text = _element_text(summary_element)
            content_text = _element_text(content_element)
            canonical_body = json.dumps(
                {
                    "summary": _element_canonical(summary_element),
                    "content": _element_canonical(content_element),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            observation_body = (
                f"{summary_text}\n{content_text}" if content_text else summary_text
            )
            entries.append(_entry(
                identifier,
                link,
                title,
                published,
                canonical_body,
                observation_body,
            ))
    else:
        channel = root.find("channel")
        if channel is None:
            raise CheckerError(_Err.PARSE_ERROR, "No <channel> in RSS feed")
        for node in channel.findall("item"):
            description_element = node.find("description")
            encoded_element = _element(node, "content:encoded", "encoded")
            description_text = _element_text(description_element)
            encoded_text = _element_text(encoded_element)
            canonical_body = json.dumps(
                {
                    "description": _element_canonical(description_element),
                    "content_encoded": _element_canonical(encoded_element),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            observation_body = (
                f"{description_text}\n{encoded_text}"
                if encoded_text else description_text
            )
            entries.append(_entry(
                node.findtext("guid", default=None),
                node.findtext("link"),
                _element_text(node.find("title")),
                node.findtext("pubDate"),
                canonical_body,
                observation_body,
            ))

    if not entries:
        raise CheckerError(_Err.PARSE_ERROR, f"No entries found in feed: {feed_url}")
    if len(entries) > MAX_ENTRIES:
        raise CheckerError(
            _Err.PARSE_ERROR,
            f"Feed has {len(entries)} entries; safety limit is {MAX_ENTRIES}",
        )

    current = {}
    for entry in entries:
        identifier = entry["item_identifier"]
        if identifier in current and current[identifier] != entry:
            raise CheckerError(
                _Err.PARSE_ERROR,
                f"Conflicting duplicate entry identifier: {identifier[:200]}",
            )
        current[identifier] = entry
    snapshot_hash = _snapshot_hash(current)
    previous, snapshot_state = _previous_entries(config)
    baseline_only = False

    if snapshot_state == "modern":
        changes = _diff(previous, current)
        if not changes:
            return None
    elif snapshot_state == "legacy_complete":
        changes = _diff(previous, current)
        # Even an unchanged complete legacy snapshot must be rewritten once so
        # future polls can detect same-ID content edits.
        baseline_only = not changes
    elif snapshot_state == "legacy_partial":
        # The old checker stored only 20 GUIDs. Treating every other current ID
        # as newly added would create a false event storm, so establish one
        # complete modern baseline without emitting events.
        changes = []
        baseline_only = True
    else:
        # Backward-compatible comparison for callers that only pass the old
        # newest-entry identifier. New runner observations always pass metadata.
        first_identifier = entries[0]["item_identifier"]
        if last_immutable_id and first_identifier == last_immutable_id:
            return None
        changes = None

    # Preserve the historical display fields for compatibility. Entry order
    # is used only for display; all comparison and diff logic above is based on
    # the unordered identifier map.
    representative = entries[0]
    metadata = {
        "feed_url": feed_url,
        "feed_type": "atom" if is_atom else "rss",
        "entry_count": len(current),
        "entries": current,
        "snapshot_hash": snapshot_hash,
        "latest_link": representative["link"],
        # Retained for compatibility with reports and pre-migration readers.
        "all_guids": [entry["item_identifier"] for entry in entries],
        "legacy_snapshot_upgraded": snapshot_state.startswith("legacy_"),
    }
    return CheckResult(
        changed=not baseline_only,
        version_value=representative["title"][:200],
        immutable_identifier=representative["item_identifier"],
        published_at=representative["published_at"],
        content_hash=representative["observation_hash"],
        raw_metadata=metadata,
        change_type="content_changed" if changes else "changelog_entry_added",
        change_items=changes,
        baseline_only=baseline_only,
    )
