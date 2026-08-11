"""
checkers/builtin/android_store.py — Google Play Store version checker.

Uses google-play-scraper to fetch app metadata from the Play Store.
No API key required — public Play Store data.

Config shapes (from enrich.py classification):
  {"package_name": "com.example.app", "store_url": "https://play.google.com/..."}
  {"app_id": "com.example.app"}

Accepts either `app_id` or `package_name` as the Play Store package ID.
If neither is provided, parses `store_url` for `?id=<package_name>`.

Error codes:
  APP_UNLISTED — app not found (404)
  PARSE_ERROR — version could not be extracted
  UNKNOWN — scraper error or network failure
"""

import hashlib, json
from urllib.parse import urlparse, parse_qs


def _dict_hash(d: dict) -> str:
    """Stable hash of a dict's relevant fields for change detection."""
    fields = ["version", "versionCode", "updated", "androidVersionText",
              "androidVersion", "size", "installs"]
    payload = {k: d.get(k) for k in fields}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


class _Err:
    APP_UNLISTED   = "APP_UNLISTED"
    PARSE_ERROR    = "PARSE_ERROR"
    UNKNOWN        = "UNKNOWN"


def _resolve_app_id(config: dict) -> str:
    """Extract the Play Store app ID from config."""
    app_id = config.get("app_id") or config.get("package_name")
    if app_id:
        return str(app_id).strip()

    # Try parsing from store_url
    store_url = config.get("store_url", "")
    if store_url:
        parsed = urlparse(store_url)
        qs = parse_qs(parsed.query)
        if "id" in qs:
            return qs["id"][0]
        # Some URLs have the ID in the path: /store/apps/details?id=...
        # urlparse may put it in query; if not, try the path
        if "details" in parsed.path and "id=" in parsed.path:
            return parsed.path.split("id=")[-1]

    return ""


def check(config: dict):
    app_id = _resolve_app_id(config)
    lang = config.get("lang", "en")
    country = config.get("country", "us")
    last_immutable_id = config.get("_last_immutable_id")

    if not app_id:
        raise CheckerError(_Err.PARSE_ERROR,
                           "Missing app_id / package_name in config — got keys: " +
                           ", ".join(sorted(config.keys())))

    try:
        import google_play_scraper as gps
    except ImportError:
        raise CheckerError(_Err.UNKNOWN,
                           "google-play-scraper not installed. Run: uv pip install google-play-scraper")

    try:
        result = gps.app(app_id, lang=lang, country=country)
    except gps.exceptions.NotFoundError:
        raise CheckerError(_Err.APP_UNLISTED, f"App not found on Play Store: {app_id}")
    except Exception as e:
        msg = str(e)
        if "not found" in msg.lower() or "404" in msg:
            raise CheckerError(_Err.APP_UNLISTED, f"App not found on Play Store: {app_id}")
        raise CheckerError(_Err.UNKNOWN, f"Play Store scraper error for {app_id}: {msg}")

    raw_version = str(result.get("version", "")).strip()
    version_code = result.get("versionCode")
    android_version = result.get("androidVersionText") or result.get("androidVersion")
    updated_ts = result.get("updated")

    # Build version value — prefer real version numbers over "Varies with device"
    if raw_version and raw_version not in ("Varies with device", "None", ""):
        version_value = raw_version
    elif version_code is not None:
        version_value = str(version_code)
    elif updated_ts:
        version_value = f"updated:{updated_ts}"
    else:
        # App uses "Varies with device" with no versionCode or timestamp.
        # Use a content hash so we still detect listing changes.
        listing_hash = _dict_hash(result)
        version_value = f"varies:{listing_hash}"

    # Immutable identifier: hash the app's full state for change detection
    immutable_id = _dict_hash(result)

    # Change detection
    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    # Convert updated (epoch seconds) to ISO if available
    published_at = None
    if updated_ts:
        from datetime import datetime, timezone
        published_at = datetime.fromtimestamp(updated_ts, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        build_number=str(version_code) if version_code is not None else None,
        published_at=published_at,
        content_hash=hashlib.sha256(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest(),
        raw_metadata={
            "app_id": app_id,
            "title": result.get("title"),
            "developer": result.get("developer"),
            "installs": result.get("installs"),
            "score": result.get("score"),
            "android_version_required": android_version,
            "version_raw": raw_version,
            "version_code": version_code,
            "play_store_url": result.get("url") or config.get("store_url"),
        },
        change_type="release_published",
    )
