import hashlib
import os
from pathlib import Path

import pytest

from codex_v4 import workspace

EXCLUDED_DIRS = (
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
)
SECRETS = (".env", ".env.local", ".env.production", "auth.json")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_snapshot_copies_dirty_untracked_text_without_touching_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    script = source / "run.sh"
    script.write_bytes(b"#!/bin/sh\necho dirty\n")
    script.chmod(0o751)
    (source / "untracked.txt").write_text("new text", encoding="utf-8")
    (source / "empty").mkdir()
    original_stat = script.stat()
    destination = tmp_path / "snapshot"

    hashes = workspace.snapshot(source, destination)

    assert hashes == {
        "run.sh": sha256(b"#!/bin/sh\necho dirty\n"),
        "untracked.txt": sha256(b"new text"),
    }
    assert workspace.file_hashes(destination) == hashes
    assert (destination / "empty").is_dir()
    assert (destination / "run.sh").stat().st_mode == original_stat.st_mode
    assert (destination / "run.sh").stat().st_mtime_ns == original_stat.st_mtime_ns
    assert script.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert (destination / "run.sh").stat().st_ino != original_stat.st_ino
    (destination / "run.sh").write_text("changed copy", encoding="utf-8")
    assert script.read_bytes() == b"#!/bin/sh\necho dirty\n"
    assert sorted(path.name for path in source.iterdir()) == ["empty", "run.sh", "untracked.txt"]


@pytest.mark.parametrize("excluded", EXCLUDED_DIRS + SECRETS)
def test_snapshot_and_hashes_share_nested_exclusions(tmp_path: Path, excluded: str) -> None:
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (nested / "keep.txt").write_bytes(b"keep")
    if excluded in EXCLUDED_DIRS:
        (nested / excluded).mkdir()
        (nested / excluded / "hidden.txt").write_bytes(b"excluded")
    else:
        (nested / excluded).write_bytes(b"secret")
    expected = {"nested/keep.txt": sha256(b"keep")}
    destination = tmp_path / "snapshot"
    assert workspace.snapshot(source, destination) == expected
    assert workspace.file_hashes(source) == expected
    assert not (destination / "nested" / excluded).exists()


@pytest.mark.parametrize("content", [b"a\x00b", b"\xff\xfe", b"\x01\x02", b"x" * (1048576 + 1)])
def test_snapshot_and_hashes_skip_binary_non_utf8_and_large_files(
    tmp_path: Path, content: bytes
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "skip.bin").write_bytes(content)
    assert workspace.snapshot(source, tmp_path / "snapshot") == {}
    assert workspace.file_hashes(source) == {}
    assert not (tmp_path / "snapshot" / "skip.bin").exists()


def test_empty_unicode_and_size_boundary_files_are_included(tmp_path: Path) -> None:
    files = {"empty": b"", "unicode": "caf\u00e9 \ufffd\n".encode(), "limit": b"x" * 1048576}
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    assert workspace.file_hashes(tmp_path) == {
        name: sha256(content) for name, content in files.items()
    }


@pytest.mark.parametrize("kind", ["file", "directory", "dangling"])
def test_snapshot_skips_symlinks_but_hashes_reject_them(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    if kind == "directory":
        outside.mkdir()
        (outside / "secret").write_bytes(b"private")
    elif kind == "file":
        outside.write_bytes(b"private")
    (source / "link").symlink_to(outside, target_is_directory=kind == "directory")
    assert workspace.snapshot(source, tmp_path / "snapshot") == {}
    assert not (tmp_path / "snapshot" / "link").is_symlink()
    with pytest.raises(ValueError):
        workspace.file_hashes(source)


@pytest.mark.parametrize("destination_kind", ["existing", "same", "nested", "dangling"])
def test_snapshot_refuses_unsafe_destinations(tmp_path: Path, destination_kind: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "destination"
    if destination_kind == "existing":
        destination.mkdir()
    elif destination_kind == "same":
        destination = source
    elif destination_kind == "nested":
        destination = source / "new" / "snapshot"
    else:
        destination.symlink_to(tmp_path / "missing")
    with pytest.raises((ValueError, FileExistsError)):
        workspace.snapshot(source, destination)
    assert list(source.iterdir()) == []


def test_snapshot_rejects_destination_inside_source_via_alias(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError):
        workspace.snapshot(source, alias / "snapshot")
    assert list(source.iterdir()) == []


def test_apply_replaces_creates_and_deletes_in_sorted_order(tmp_path: Path) -> None:
    (tmp_path / "replace").write_bytes(b"old")
    (tmp_path / "replace").chmod(0o751)
    (tmp_path / "delete").write_bytes(b"gone")
    changes = [
        {"path": "replace", "content": "caf\u00e9\n"},
        {"path": "new/deep/empty", "content": ""},
        {"path": "delete", "content": None},
    ]
    assert workspace.apply_changes(tmp_path, changes, [item["path"] for item in changes]) == [
        "delete",
        "new/deep/empty",
        "replace",
    ]
    assert (tmp_path / "replace").read_text(encoding="utf-8") == "caf\u00e9\n"
    assert (tmp_path / "replace").stat().st_mode & 0o777 == 0o751
    assert (tmp_path / "new/deep/empty").read_bytes() == b""
    assert not (tmp_path / "delete").exists()


@pytest.mark.parametrize("scope", [[], ["other"], ["nested"], ["nested/*"]])
def test_scope_is_exact_and_entire_batch_is_validated(tmp_path: Path, scope: list[str]) -> None:
    (tmp_path / "first").write_bytes(b"unchanged")
    with pytest.raises(ValueError):
        workspace.apply_changes(
            tmp_path,
            [
                {"path": "first", "content": "must not write"},
                {"path": "nested/file", "content": "forbidden"},
            ],
            ["first", *scope],
        )
    assert (tmp_path / "first").read_bytes() == b"unchanged"
    assert not (tmp_path / "nested").exists()


@pytest.mark.parametrize(
    "path",
    [
        "",
        ".",
        "..",
        "../escape",
        "/absolute",
        "a/../escape",
        "a\\escape",
        "a//b",
        "a/./b",
        "a/",
        "bad\x00name",
        "C:/escape",
        *EXCLUDED_DIRS,
        *SECRETS,
        *[f"nested/{name}/file" for name in EXCLUDED_DIRS + SECRETS],
    ],
)
def test_apply_rejects_unsafe_and_protected_paths_before_writing(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        workspace.apply_changes(
            tmp_path,
            [{"path": "first", "content": "not written"}, {"path": path, "content": "bad"}],
            ["first", path],
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "invalid",
    [
        {"path": "second"},
        {"content": "text"},
        {"path": 42, "content": "text"},
        {"path": "second", "content": 42},
        {"path": "second", "content": "\ud800"},
        "bad",
    ],
)
def test_malformed_entries_are_rejected_before_writing(tmp_path: Path, invalid: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        workspace.apply_changes(
            tmp_path, [{"path": "first", "content": "not written"}, invalid], ["first", "second"]
        )
    assert list(tmp_path.iterdir()) == []


def test_duplicate_changes_are_rejected_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        workspace.apply_changes(
            tmp_path,
            [{"path": "new", "content": "first"}, {"path": "new", "content": "second"}],
            ["new"],
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_new_parent_paths_are_rejected_before_writing(
    tmp_path: Path, reverse: bool
) -> None:
    changes = [{"path": "new", "content": "file"}, {"path": "new/child", "content": "child"}]
    with pytest.raises(ValueError):
        workspace.apply_changes(
            tmp_path, changes[::-1] if reverse else changes, ["new", "new/child"]
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("content", [None, "replacement"])
@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "parent", "dangling"])
def test_apply_rejects_link_escapes_and_directories(
    tmp_path: Path, content: str | None, kind: str
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"private")
    target = root / "target"
    path = "target"
    if kind == "symlink":
        target.symlink_to(sentinel)
    elif kind == "hardlink":
        os.link(sentinel, target)
    elif kind == "directory":
        target.mkdir()
    elif kind == "parent":
        target.symlink_to(outside, target_is_directory=True)
        path = "target/sentinel"
    else:
        target.symlink_to(outside / "missing")
    with pytest.raises(ValueError):
        workspace.apply_changes(
            root,
            [{"path": "first", "content": "not written"}, {"path": path, "content": content}],
            ["first", path],
        )
    assert not (root / "first").exists()
    assert sentinel.read_bytes() == b"private"
    assert not (outside / "missing").exists()


def test_missing_deletion_validates_before_writing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        workspace.apply_changes(
            tmp_path,
            [{"path": "first", "content": "not written"}, {"path": "missing", "content": None}],
            ["first", "missing"],
        )
    assert list(tmp_path.iterdir()) == []


def test_existing_file_parent_rejects_entire_batch(tmp_path: Path) -> None:
    (tmp_path / "parent").write_bytes(b"file")
    with pytest.raises(ValueError):
        workspace.apply_changes(
            tmp_path,
            [
                {"path": "first", "content": "not written"},
                {"path": "parent/child", "content": "bad"},
            ],
            ["first", "parent/child"],
        )
    assert not (tmp_path / "first").exists()
    assert (tmp_path / "parent").read_bytes() == b"file"


def test_apply_uses_same_directory_atomic_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    original_replace = os.replace
    observed = []
    target = tmp_path / "nested" / "file"
    target.parent.mkdir()
    target.write_bytes(b"old")

    def inspect_replace(source: str | Path, destination: str | Path) -> None:
        assert Path(source).parent == target.parent
        assert Path(destination) == target
        assert target.read_bytes() == b"old"
        assert Path(source).read_bytes() == b"new"
        observed.append(True)
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", inspect_replace)
    workspace.apply_changes(tmp_path, [{"path": "nested/file", "content": "new"}], ["nested/file"])
    assert observed == [True]
    assert list(target.parent.iterdir()) == [target]


def test_failed_atomic_replace_leaves_original_and_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "file").write_bytes(b"old")

    def fail_replace(*args: object, **kwargs: object) -> None:
        raise OSError("replacement failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError):
        workspace.apply_changes(tmp_path, [{"path": "file", "content": "new"}], ["file"])
    assert (tmp_path / "file").read_bytes() == b"old"
    assert [path.name for path in tmp_path.iterdir()] == ["file"]


def test_digest_stability_content_names_and_cache_exclusions(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root, names in [(left, ["z", "a"]), (right, ["a", "z"])]:
        for name in names:
            (root / name).write_bytes(name.encode())
    assert list(workspace.file_hashes(left)) == ["a", "z"]
    baseline = workspace.tree_digest(left)
    assert len(baseline) == 64
    assert workspace.tree_digest(right) == baseline
    (left / "logs").mkdir()
    (left / "logs" / "cache").write_bytes(b"ignored")
    assert workspace.tree_digest(left) == baseline
    (left / "a").write_bytes(b"changed")
    assert workspace.tree_digest(left) != baseline
    (right / "a").rename(right / "renamed")
    assert workspace.tree_digest(right) != baseline


def test_changed_paths_is_sorted_union_of_added_removed_and_modified() -> None:
    before = {"removed": "old", "same": "same", "modified": "old"}
    after = {"added": "new", "same": "same", "modified": "new"}
    assert workspace.changed_paths(before, after) == ["added", "modified", "removed"]
    assert before == {"removed": "old", "same": "same", "modified": "old"}
    assert after == {"added": "new", "same": "same", "modified": "new"}


def test_empty_workspace_and_changes(tmp_path: Path) -> None:
    assert workspace.file_hashes(tmp_path) == {}
    assert workspace.tree_digest(tmp_path) == sha256(b"")
    assert workspace.apply_changes(tmp_path, [], []) == []
    assert workspace.changed_paths({}, {}) == []
