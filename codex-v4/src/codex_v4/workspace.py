import hashlib
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path, PureWindowsPath

_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".claude",
        ".codex",
        ".codex-v4",
        "codex-v4",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "logs",
        "dist",
        "build",
    }
)
_MAX_FILE_BYTES = 1024 * 1024
_BINARY_CONTROLS = bytes(value for value in range(32) if value not in (9, 10, 13)) + b"\x7f"


def _credential(name: str) -> bool:
    return name in {".env", "auth.json"} or name.startswith(".env.")


def _root_directory(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("Workspace root must not be a symlink")
    if not stat.S_ISDIR(root.stat().st_mode):
        raise ValueError("Workspace root must be a directory")
    return root.resolve()


def _entries(root: Path, *, reject_symlinks: bool) -> Iterator[tuple[Path, bool]]:
    with os.scandir(root) as iterator:
        entries = sorted(iterator, key=lambda entry: entry.name)
    for entry in entries:
        if entry.is_symlink():
            if reject_symlinks:
                raise ValueError("Workspace contains a symlink")
            continue
        if _credential(entry.name):
            continue
        is_directory = entry.is_dir(follow_symlinks=False)
        if is_directory and entry.name in _EXCLUDED_DIRS:
            continue
        path = Path(entry.path)
        if is_directory:
            yield path, True
            yield from _entries(path, reject_symlinks=reject_symlinks)
        elif entry.is_file(follow_symlinks=False):
            yield path, False


def _text_bytes(path: Path) -> bytes | None:
    if path.stat().st_size > _MAX_FILE_BYTES:
        return None
    with path.open("rb") as stream:
        content = stream.read(_MAX_FILE_BYTES + 1)
    if len(content) > _MAX_FILE_BYTES or any(value in content for value in _BINARY_CONTROLS):
        return None
    if content.decode("utf-8", errors="replace").encode("utf-8") != content:
        return None
    return content


def snapshot(source: Path, destination: Path) -> dict[str, str]:
    source = _root_directory(source)
    if destination.is_symlink() or destination.exists():
        raise FileExistsError("Snapshot destination already exists")
    if destination.resolve().is_relative_to(source):
        raise ValueError("Snapshot destination must be outside the source")
    destination.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    for path, is_directory in _entries(source, reject_symlinks=False):
        relative = path.relative_to(source)
        target = destination / relative
        if is_directory:
            target.mkdir()
            continue
        content = _text_bytes(path)
        if content is not None:
            shutil.copy2(path, target, follow_symlinks=False)
            hashes[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    return dict(sorted(hashes.items()))


def file_hashes(root: Path) -> dict[str, str]:
    root = _root_directory(root)
    hashes: dict[str, str] = {}
    for path, is_directory in _entries(root, reject_symlinks=True):
        if not is_directory:
            content = _text_bytes(path)
            if content is not None:
                hashes[path.relative_to(root).as_posix()] = hashlib.sha256(content).hexdigest()
    return dict(sorted(hashes.items()))


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for name, file_digest in sorted(file_hashes(root).items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _safe_parts(path: object) -> tuple[str, ...]:
    if not isinstance(path, str) or not path or "\\" in path or "\0" in path:
        raise ValueError("Change path must be a safe relative path")
    parts = tuple(path.split("/"))
    if PureWindowsPath(path).drive or any(
        part in {"", ".", ".."} or part in _EXCLUDED_DIRS or _credential(part) for part in parts
    ):
        raise ValueError("Change path is unsafe or protected")
    return parts


def _validate_target(root: Path, parts: tuple[str, ...]) -> os.stat_result | None:
    target = root
    for index, part in enumerate(parts):
        target = target / part
        if target.is_symlink():
            raise ValueError("Change path contains a symlink")
        if not target.exists():
            return None
        metadata = target.lstat()
        if index < len(parts) - 1:
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("Change parent must be a directory")
        else:
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink > 1:
                raise ValueError("Change target must be a regular file with a single link")
            return metadata
    return None


def _replace_file(target: Path, content: bytes, mode: int | None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=".workspace-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def apply_changes(root: Path, changes: list[dict[str, object]], scope: list[str]) -> list[str]:
    root = _root_directory(root)
    if not isinstance(changes, list) or not isinstance(scope, list):
        raise ValueError("Changes and scope must be lists")
    for path in scope:
        _safe_parts(path)
    allowed = set(scope)
    prepared: dict[str, tuple[tuple[str, ...], bytes | None, int | None]] = {}
    for change in changes:
        if not isinstance(change, dict) or "path" not in change or "content" not in change:
            raise ValueError("Each change must contain path and content")
        path = change["path"]
        parts = _safe_parts(path)
        if not isinstance(path, str) or path not in allowed or path in prepared:
            raise ValueError("Change must be unique and exactly in scope")
        content = change["content"]
        if content is not None and not isinstance(content, str):
            raise ValueError("Change content must be text or null")
        encoded = content.encode("utf-8") if content is not None else None
        metadata = _validate_target(root, parts)
        if content is None and metadata is None:
            raise FileNotFoundError("Deletion target does not exist")
        mode = stat.S_IMODE(metadata.st_mode) if metadata is not None else None
        prepared[path] = parts, encoded, mode
    for parts, _, _ in prepared.values():
        if any("/".join(parts[:index]) in prepared for index in range(1, len(parts))):
            raise ValueError("Changes contain conflicting parent paths")
    for path in sorted(prepared):
        parts, content, mode = prepared[path]
        _validate_target(root, parts)
        target = root.joinpath(*parts)
        if content is None:
            target.unlink()
        else:
            _replace_file(target, content, mode)
    return sorted(prepared)


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(
        path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
    )
