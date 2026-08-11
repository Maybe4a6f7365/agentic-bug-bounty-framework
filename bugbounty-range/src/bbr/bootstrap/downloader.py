"""Authenticated GCS artifact download with isolated test modes."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse

from .errors import BootstrapError


def pull_artifact(gcs_uri: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / "artifact.tar.zst"
    test_mode = os.environ.get("BBR_TEST_MODE")

    if test_mode == "1":
        parsed = urlparse(gcs_uri)
        if parsed.scheme != "file":
            raise BootstrapError(30, "TEST_MODE_REQUIRES_FILE_URI", "DOWNLOAD", gcs_uri)
        source = Path(parsed.path)
        if not source.is_file():
            raise BootstrapError(30, "HTTP_404", "DOWNLOAD", gcs_uri)
        shutil.copyfile(source, destination)
        return destination

    if test_mode == "2":
        fixture = os.environ.get("BBR_TEST_ARTIFACT")
        if not fixture or not Path(fixture).is_file():
            raise BootstrapError(30, "HTTP_404", "DOWNLOAD", gcs_uri)
        shutil.copyfile(fixture, destination)
        return destination

    if not gcs_uri.startswith("gs://"):
        raise BootstrapError(30, "INVALID_GCS_URI", "DOWNLOAD", gcs_uri)
    bucket_object = gcs_uri[5:].split("/", 1)
    if len(bucket_object) != 2:
        raise BootstrapError(30, "INVALID_GCS_URI", "DOWNLOAD", gcs_uri)
    token = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True, text=True, check=False,
    )
    if token.returncode != 0 or not token.stdout.strip():
        raise BootstrapError(30, "SERVICE_ACCOUNT_TOKEN_FAILED", "DOWNLOAD", gcs_uri)
    url = (
        "https://storage.googleapis.com/storage/v1/b/"
        f"{quote(bucket_object[0], safe='')}/o/{quote(bucket_object[1], safe='')}?alt=media"
    )
    result = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location",
         "-H", f"Authorization: Bearer {token.stdout.strip()}",
         "--output", str(destination), url],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        raise BootstrapError(30, f"HTTP_FAIL_{result.returncode}", "DOWNLOAD", gcs_uri)
    return destination

