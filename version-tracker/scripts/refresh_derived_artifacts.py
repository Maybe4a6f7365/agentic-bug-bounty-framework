#!/usr/bin/env python3
"""Durably publish target/asset and inventory views from one SQLite database."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone


class PublicationError(RuntimeError):
    """Unsafe configuration or failed derived-artifact publication."""


def _open_bound_regular(
    path: Path,
    *,
    resolve_symlink: bool = False,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, Path, tuple[int, int]]:
    opened_path = path.resolve(strict=True) if resolve_symlink else path
    try:
        fd = os.open(opened_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise PublicationError(f"cannot securely bind file: {path}") from exc
    info = os.fstat(fd)
    identity = (info.st_dev, info.st_ino)
    if (not stat.S_ISREG(info.st_mode)
            or (expected_identity is not None and identity != expected_identity)):
        os.close(fd)
        raise PublicationError(f"bound path identity changed: {path}")
    return fd, opened_path, identity


def _assert_identity(path: Path, identity: tuple[int, int]) -> None:
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise PublicationError(f"configured path identity changed: {path}") from exc
    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != identity:
        raise PublicationError(f"configured path identity changed: {path}")


def _snapshot_output(path: Path) -> tuple[int, int] | None:
    try:
        info = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise PublicationError(f"derived-artifact output must be regular: {path}")
    return info.st_dev, info.st_ino


def _bind_output(
    path: Path, directory_fd: int
) -> tuple[int, tuple[int, int]] | None:
    try:
        fd = os.open(
            path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PublicationError(f"cannot securely bind derived-artifact output: {path}") from exc
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise PublicationError(f"derived-artifact output must be regular: {path}")
    return fd, (info.st_dev, info.st_ino)


def _bind_staged_artifact(path: Path) -> int:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise PublicationError(
            "generator did not produce a bindable staged artifact"
        ) from exc
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise PublicationError("generator did not produce a regular staged artifact")
    return fd


def _assert_output_unchanged(path: Path, identity: tuple[int, int] | None) -> None:
    if _snapshot_output(path) != identity:
        raise PublicationError(f"derived-artifact output identity changed: {path}")


def _configured_path(name: str, default: Path) -> Path:
    value = os.environ.get(name, str(default))
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise PublicationError(f"invalid {name}")
    return Path(value).expanduser().absolute()


def _configured_identity(name: str) -> tuple[int, int] | None:
    value = os.environ.get(name)
    if value is None:
        return None
    parts = value.split(":")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise PublicationError(f"invalid {name}")
    return int(parts[0]), int(parts[1])


def _database_fds(identity: tuple[int, int]) -> set[int]:
    matches: set[int] = set()
    for entry in Path("/proc/self/fd").iterdir():
        try:
            fd = int(entry.name)
            info = os.fstat(fd)
            if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == identity:
                matches.add(fd)
        except (OSError, ValueError):
            continue
    return matches


def _verify_bound_database_for_generators(
    db_fd: int, identity: tuple[int, int]
) -> None:
    """Verify SQLite opens the retained DB inode, excluding every inherited FD."""
    preexisting_fds = _database_fds(identity)
    uri = Path(f"/proc/self/fd/{db_fd}").absolute().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        if not (_database_fds(identity) - preexisting_fds):
            raise PublicationError("SQLite generator database binding could not be verified")
        connection.execute("PRAGMA schema_version").fetchone()
    finally:
        connection.close()


def _reject_aliases(paths: list[Path]) -> list[Path]:
    resolved = [path.resolve(strict=False) for path in paths]
    if len(set(resolved)) != len(resolved):
        raise PublicationError("derived-artifact paths must be pairwise distinct")
    identities: set[tuple[int, int]] = set()
    for path in resolved:
        try:
            info = path.stat()
        except OSError:
            continue
        identity = (info.st_dev, info.st_ino)
        if identity in identities:
            raise PublicationError("derived-artifact paths must not be hard-link aliases")
        identities.add(identity)
    return resolved


def _reject_output(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PublicationError(f"derived-artifact output must be a regular non-symlink path: {path}")


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_durable_directory(path: Path) -> None:
    """Create missing publication ancestors and persist every new dirent."""
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        if cursor == cursor.parent:
            raise PublicationError(f"cannot create publication directory: {path}")
        missing.append(cursor)
        cursor = cursor.parent
    if cursor.is_symlink() or not cursor.is_dir():
        raise PublicationError(f"unsafe publication directory: {cursor}")
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        _fsync_directory(directory.parent)
    _fsync_directory(path)


def _publish(
    staged_fd: int,
    destination: Path,
    directory_fd: int,
    expected_identity: tuple[int, int] | None,
) -> tuple[str, int, tuple[int, int]]:
    """Copy one retained stage into a retained publication temporary inode."""
    _assert_output_unchanged(destination, expected_identity)
    temporary_name = f".{destination.name}.{uuid.uuid4().hex}"
    fd = os.open(
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        os.fchmod(fd, 0o600)
        os.lseek(staged_fd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(fd), "wb") as handle, os.fdopen(
            os.dup(staged_fd), "rb"
        ) as source:
            shutil.copyfileobj(source, handle)
            handle.flush()
            os.fsync(handle.fileno())
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PublicationError(f"publication temporary is not regular: {destination}")
        return temporary_name, fd, (info.st_dev, info.st_ino)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        raise


def _publish_all(
    staged_fds: list[int],
    outputs: list[Path],
    output_identities: list[tuple[int, int] | None],
    output_fds: list[int | None],
    parent_bindings: dict[Path, tuple[int, tuple[int, int]]],
) -> list[tuple[int, int]]:
    """Install the artifact trio and restore the complete prior trio on failure."""
    prepared: list[tuple[str, int, tuple[int, int]]] = []
    rollback_names: list[str | None] = [None] * len(outputs)
    installed = [False] * len(outputs)
    try:
        for staged_fd, output, expected in zip(
            staged_fds, outputs, output_identities, strict=True
        ):
            prepared.append(
                _publish(staged_fd, output, parent_bindings[output.parent][0], expected)
            )

        # Hard links preserve each exact prior inode until the new trio is fully
        # installed and durable.  They are created from retained output FDs.
        for index, (output, expected, output_fd) in enumerate(
            zip(outputs, output_identities, output_fds, strict=True)
        ):
            if expected is None:
                continue
            assert output_fd is not None
            _assert_output_unchanged(output, expected)
            directory_fd = parent_bindings[output.parent][0]
            rollback_name = f".{output.name}.rollback.{uuid.uuid4().hex}"
            os.link(
                f"/proc/self/fd/{output_fd}", rollback_name,
                dst_dir_fd=directory_fd, follow_symlinks=True,
            )
            rollback_info = os.stat(
                rollback_name, dir_fd=directory_fd, follow_symlinks=False
            )
            if (not stat.S_ISREG(rollback_info.st_mode)
                    or (rollback_info.st_dev, rollback_info.st_ino) != expected):
                raise PublicationError(f"rollback artifact identity changed: {output}")
            rollback_names[index] = rollback_name
        for directory in sorted({output.parent for output in outputs}, key=str):
            os.fsync(parent_bindings[directory][0])

        published_identities: list[tuple[int, int]] = []
        for index, (output, expected, prepared_item) in enumerate(
            zip(outputs, output_identities, prepared, strict=True)
        ):
            temporary_name, _temporary_fd, temporary_identity = prepared_item
            _assert_output_unchanged(output, expected)
            directory_fd = parent_bindings[output.parent][0]
            os.replace(
                temporary_name, output.name,
                src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
            )
            installed[index] = True
            published = os.stat(
                output.name, dir_fd=directory_fd, follow_symlinks=False
            )
            published_identity = (published.st_dev, published.st_ino)
            if (not stat.S_ISREG(published.st_mode)
                    or published_identity != temporary_identity
                    or os.fstat(_temporary_fd).st_ino != published.st_ino
                    or os.fstat(_temporary_fd).st_dev != published.st_dev):
                raise PublicationError(f"published artifact identity changed: {output}")
            published_identities.append(published_identity)

        _fsync_publication(outputs, published_identities, parent_bindings)
    except BaseException as original:
        rollback_error: BaseException | None = None
        for index, output in enumerate(outputs):
            directory_fd = parent_bindings[output.parent][0]
            rollback_name = rollback_names[index]
            try:
                if rollback_name is not None:
                    os.replace(
                        rollback_name, output.name,
                        src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    )
                    rollback_names[index] = None
                elif installed[index]:
                    os.unlink(output.name, dir_fd=directory_fd)
            except BaseException as exc:
                rollback_error = rollback_error or exc
        for directory in sorted({output.parent for output in outputs}, key=str):
            try:
                os.fsync(parent_bindings[directory][0])
            except BaseException as exc:
                rollback_error = rollback_error or exc
        if rollback_error is not None:
            raise PublicationError("derived-artifact publication rollback failed") from rollback_error
        raise original
    else:
        # Publication is already durable. Hidden rollback links are cleanup-only;
        # a cleanup failure leaves the committed trio intact and recoverable.
        for rollback_name, output in zip(rollback_names, outputs, strict=True):
            if rollback_name is not None:
                try:
                    os.unlink(rollback_name, dir_fd=parent_bindings[output.parent][0])
                except OSError:
                    pass
        for directory in sorted({output.parent for output in outputs}, key=str):
            try:
                os.fsync(parent_bindings[directory][0])
            except OSError:
                pass
        return published_identities
    finally:
        for temporary_name, fd, _identity in prepared:
            try:
                os.close(fd)
            except OSError:
                pass
            for output in outputs:
                directory_fd = parent_bindings[output.parent][0]
                try:
                    os.unlink(temporary_name, dir_fd=directory_fd)
                    break
                except FileNotFoundError:
                    continue
                except OSError:
                    break


def _fsync_publication(
    outputs: list[Path],
    identities: list[tuple[int, int]],
    parent_bindings: dict[Path, tuple[int, tuple[int, int]]],
) -> None:
    for output, identity in zip(outputs, identities, strict=True):
        directory_fd, _ = parent_bindings[output.parent]
        fd = os.open(
            output.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd
        )
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != identity:
                raise PublicationError(f"published artifact is not regular: {output}")
            os.fsync(fd)
        finally:
            os.close(fd)
    for directory in sorted({output.parent for output in outputs}, key=str):
        os.fsync(parent_bindings[directory][0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--target-asset-output", required=True, type=Path)
    parser.add_argument("--inventory-json", required=True, type=Path)
    parser.add_argument("--inventory-markdown", required=True, type=Path)
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    python = _configured_path("VERSION_TRACKER_PYTHON", Path(sys.executable))
    python_argv0 = os.environ.get("VERSION_TRACKER_PYTHON_ARGV0", str(python))
    if (not python_argv0
            or any(ord(char) < 32 or ord(char) == 127 for char in python_argv0)):
        raise PublicationError("invalid VERSION_TRACKER_PYTHON_ARGV0")
    current = _configured_path(
        "VERSION_TRACKER_CURRENT_TARGET_ASSETS", script_dir / "current_target_assets.py"
    )
    inventory = _configured_path("VERSION_TRACKER_INVENTORY", script_dir / "inventory.py")
    raw_outputs = [
        args.target_asset_output.expanduser().absolute(),
        args.inventory_json.expanduser().absolute(),
        args.inventory_markdown.expanduser().absolute(),
    ]
    bound_fds: list[int] = []
    try:
        expected_db_identity = _configured_identity(
            "VERSION_TRACKER_EXPECTED_DB_IDENTITY"
        )
        resolved = _reject_aliases(
            [args.db.expanduser().absolute(), python, current, inventory, *raw_outputs]
        )
        db, _resolved_python, current, inventory, *outputs = resolved
        if not db.is_file() or not os.access(python, os.X_OK):
            raise PublicationError("derived-artifact database or interpreter is unavailable")
        if not current.is_file() or not inventory.is_file():
            raise PublicationError("derived-artifact generator is unavailable")
        for output in raw_outputs:
            _reject_output(output)
        for directory in {output.parent for output in outputs}:
            _ensure_durable_directory(directory)

        db_fd, db_bound_path, db_identity = _open_bound_regular(
            db, expected_identity=expected_db_identity
        )
        python_fd, python_bound_path, python_identity = _open_bound_regular(
            python, resolve_symlink=True
        )
        current_fd, current_bound_path, current_identity = _open_bound_regular(current)
        inventory_fd, inventory_bound_path, inventory_identity = _open_bound_regular(inventory)
        bound_fds.extend((db_fd, python_fd, current_fd, inventory_fd))
        _verify_bound_database_for_generators(db_fd, db_identity)
        parent_bindings: dict[Path, tuple[int, tuple[int, int]]] = {}
        for output in outputs:
            if output.parent not in parent_bindings:
                parent_fd = os.open(
                    output.parent,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                )
                parent_info = os.fstat(parent_fd)
                parent_bindings[output.parent] = (
                    parent_fd, (parent_info.st_dev, parent_info.st_ino)
                )
                bound_fds.append(parent_fd)
        output_bindings = [
            _bind_output(output, parent_bindings[output.parent][0]) for output in outputs
        ]
        output_fds = [binding[0] if binding is not None else None for binding in output_bindings]
        output_identities = [
            binding[1] if binding is not None else None for binding in output_bindings
        ]
        bound_fds.extend(fd for fd in output_fds if fd is not None)

        observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with tempfile.TemporaryDirectory(prefix="vt-derived-") as temporary_dir:
            temporary = Path(temporary_dir)
            staged = [temporary / "targets.md", temporary / "inventory.json", temporary / "inventory.md"]
            _assert_identity(db_bound_path, db_identity)
            _assert_identity(python_bound_path, python_identity)
            _assert_identity(current_bound_path, current_identity)
            subprocess.run(
                [python_argv0, f"/proc/self/fd/{current_fd}",
                 "--db", f"/proc/self/fd/{db_fd}",
                 "--output", str(staged[0]), "--write"],
                check=True,
                pass_fds=(python_fd, current_fd, db_fd),
                executable=f"/proc/self/fd/{python_fd}",
            )
            staged_fds = [_bind_staged_artifact(staged[0])]
            bound_fds.append(staged_fds[0])
            _assert_identity(db_bound_path, db_identity)
            _assert_identity(python_bound_path, python_identity)
            _assert_identity(inventory_bound_path, inventory_identity)
            subprocess.run(
                [python_argv0, f"/proc/self/fd/{inventory_fd}",
                 "--db", f"/proc/self/fd/{db_fd}",
                 "--json", str(staged[1]), "--markdown", str(staged[2]),
                 "--observed-at", observed_at, "--write"],
                check=True,
                pass_fds=(python_fd, inventory_fd, db_fd),
                executable=f"/proc/self/fd/{python_fd}",
            )
            for path in staged[1:]:
                staged_fd = _bind_staged_artifact(path)
                staged_fds.append(staged_fd)
                bound_fds.append(staged_fd)
            for output, identity in zip(outputs, output_identities, strict=True):
                _assert_output_unchanged(output, identity)
                _parent_fd, parent_identity = parent_bindings[output.parent]
                parent_info = output.parent.stat(follow_symlinks=False)
                if (parent_info.st_dev, parent_info.st_ino) != parent_identity:
                    raise PublicationError(f"publication directory identity changed: {output.parent}")
            _publish_all(
                staged_fds, outputs, output_identities, output_fds, parent_bindings
            )
    except (OSError, PublicationError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"derived-artifact refresh failed: {exc}", file=sys.stderr)
        return 2
    finally:
        for fd in reversed(bound_fds):
            os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
