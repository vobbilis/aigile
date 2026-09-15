import asyncio
import importlib
import importlib.util
import os
import signal
import socket
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest


def test_checker_api_exists() -> None:
    assert importlib.util.find_spec("codex_v4.checks") is not None


@pytest.fixture
def checker():
    return importlib.import_module("codex_v4.checks")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    root = tmp_path / "project"
    tests = root / "tests"
    tests.mkdir(parents=True)
    (tests / "test_sample.py").write_text(
        "import pytest\n"
        "def test_named1():\n    assert True\n"
        "def test_omitted():\n    assert True\n"
        "@pytest.mark.skip(reason='not implemented')\n"
        "def test_skipped():\n    pass\n"
        "def test_failed():\n    assert False\n"
        "@pytest.fixture\n"
        "def broken():\n    raise RuntimeError('fixture failed')\n"
        "def test_error(broken):\n    pass\n"
        "class TestGroup:\n"
        "    @pytest.mark.parametrize('value', ['a.b::c', 'simple'])\n"
        "    def test_param(self, value):\n        assert value\n",
        encoding="utf-8",
    )
    return root


def command(argv: list[str], **overrides) -> dict:
    return {
        "id": "check",
        "argv": argv,
        "cwd": ".",
        "timeout_seconds": 10,
        "adapter": "command",
        **overrides,
    }


def promise(identity: str, **overrides) -> dict:
    return {
        "id": "promise",
        "identity": identity,
        "command_id": "check",
        "covers_failure_ids": ["failure-1"],
        **overrides,
    }


def run(checker, root: Path, commands: list[dict], promises: list[dict]) -> dict:
    return asyncio.run(
        checker.run_checks(commands, promises, root, root.parent / "evidence", sys.executable)
    )


def write_junit(path: Path, cases: list[dict]) -> Path:
    suite = ElementTree.Element("testsuite")
    for case in cases:
        attributes = {key: value for key, value in case.items() if key != "outcome"}
        testcase = ElementTree.SubElement(suite, "testcase", attributes)
        if case.get("outcome"):
            ElementTree.SubElement(testcase, case["outcome"])
    ElementTree.ElementTree(suite).write(path, encoding="utf-8")
    return path


def test_real_pytest_named_promise_and_evidence(checker, project: Path) -> None:
    identity = "tests/test_sample.py::test_named1"
    original = command(["{python}", "-m", "pytest", "-q", identity], adapter="pytest-junit")
    report = run(checker, project, [original], [promise(identity)])
    assert set(report) == {"passed", "commands", "promises"}
    assert report["passed"] is True
    assert report["promises"] == [
        {"id": "promise", "identity": identity, "passed": True, "reason": "passed"}
    ]
    result = report["commands"][0]
    assert result["returncode"] == 0
    assert result["timed_out"] is False
    assert result["output_overflow"] is False
    assert result["argv"][0] == sys.executable
    assert result["argv"][-3:] == [
        f"--junitxml={project.parent / 'evidence' / 'check.xml'}",
        "-o",
        "junit_family=xunit1",
    ]
    assert result["cwd"] == str(project.resolve())
    assert "1 passed" in Path(result["stdout_path"]).read_text()
    assert Path(result["stderr_path"]).exists()
    assert Path(result["junit_path"]).is_absolute()
    assert original["argv"][0] == "{python}"
    assert len(original["argv"]) == 5


@pytest.mark.parametrize(
    ("selected", "promised", "reason", "returncode"),
    [
        ("test_named1", "test_omitted", "missing", 0),
        ("test_skipped", "test_skipped", "skipped", 0),
        ("test_failed", "test_failed", "failure", 1),
        ("test_error", "test_error", "error", 1),
    ],
)
def test_real_pytest_unsatisfied_promises(
    checker, project: Path, selected: str, promised: str, reason: str, returncode: int
) -> None:
    report = run(
        checker,
        project,
        [command(
            ["{python}", "-m", "pytest", "-q", f"tests/test_sample.py::{selected}"],
            adapter="pytest-junit",
        )],
        [promise(f"tests/test_sample.py::{promised}")],
    )
    assert report["passed"] is False
    assert report["commands"][0]["returncode"] == returncode
    assert report["promises"][0]["passed"] is False
    assert report["promises"][0]["reason"] == reason


def test_real_pytest_class_and_parameter_identity(checker, project: Path) -> None:
    identity = "tests/test_sample.py::TestGroup::test_param[a.b::c]"
    report = run(
        checker,
        project,
        [command(["{python}", "-m", "pytest", "-q", identity], adapter="pytest-junit")],
        [promise(identity)],
    )
    assert report["passed"] is True


@pytest.mark.parametrize("returncode", [0, 7])
def test_command_adapter_exit_status_and_literal_argv(
    checker, project: Path, returncode: int
) -> None:
    script = project / "check.py"
    script.write_text(
        "import sys\nprint(sys.argv[1])\nprint('stderr evidence', file=sys.stderr)\n"
        f"sys.exit({returncode})\n"
    )
    literal = "; touch should-not-exist $(echo expanded)"
    report = run(
        checker, project, [command(["{python}", "check.py", literal])], [promise("check")]
    )
    assert report["passed"] is (returncode == 0)
    assert report["promises"][0]["passed"] is (returncode == 0)
    result = report["commands"][0]
    assert result["returncode"] == returncode
    assert Path(result["stdout_path"]).read_text() == literal + "\n"
    assert Path(result["stderr_path"]).read_text() == "stderr evidence\n"
    assert not (project / "should-not-exist").exists()


@pytest.mark.parametrize(
    ("file", "classname", "identity"),
    [
        ("tests/test_x.py", "tests.test_x", "tests/test_x.py::test_name[param]"),
        ("tests/test_x.py", "test_x.TestOuter.TestInner",
         "tests/test_x.py::TestOuter::TestInner::test_name[param]"),
        ("tests/test_x.py", "tests.test_x.TestGroup",
         "tests/test_x.py::TestGroup::test_name[param]"),
        ("tests/test_x.py", "package.tests.test_x.TestGroup",
         "tests/test_x.py::TestGroup::test_name[param]"),
        (None, "tests.test_x.TestGroup", "tests/test_x.py::TestGroup::test_name[param]"),
        ("tests/test_x.y.py", "tests.test_x.y", "tests/test_x.y.py::test_name[param]"),
    ],
)
def test_reconcile_file_and_class_suffix(
    checker, tmp_path: Path, file: str | None, classname: str, identity: str
) -> None:
    case = {"classname": classname, "name": "test_name[param]"}
    if file is not None:
        case["file"] = file
    path = write_junit(tmp_path / "results.xml", [case])
    assert checker.reconcile_junit(path, [identity]) == {identity: "passed"}


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_reconcile_nonpassing_case(checker, tmp_path: Path, outcome: str) -> None:
    identity = "tests/test_x.py::test_name"
    path = write_junit(tmp_path / "results.xml", [{
        "file": "tests/test_x.py", "classname": "tests.test_x",
        "name": "test_name", "outcome": outcome,
    }])
    assert checker.reconcile_junit(path, [identity]) == {identity: outcome}


def test_reconcile_duplicates_are_not_success(checker, tmp_path: Path) -> None:
    identity = "tests/test_x.py::test_name"
    case = {"file": "tests/test_x.py", "classname": "tests.test_x", "name": "test_name"}
    path = write_junit(tmp_path / "results.xml", [case, case])
    assert checker.reconcile_junit(path, [identity]) == {identity: "duplicate"}


def test_reconcile_file_is_authoritative(checker, tmp_path: Path) -> None:
    identity = "tests/test_x.py::test_name"
    path = write_junit(tmp_path / "results.xml", [{
        "file": "other/test_x.py", "classname": "tests.test_x", "name": "test_name",
    }])
    assert checker.reconcile_junit(path, [identity]) == {identity: "missing"}


@pytest.mark.parametrize("payload", [
    b"", b"<broken", b"x" * (2 * 1024 * 1024 + 1),
    b'<!DOCTYPE testsuite [<!ENTITY secret "value">]><testsuite/>',
    '<!DOCTYPE testsuite [<!ENTITY secret "value">]><testsuite/>'.encode("utf-16"),
])
def test_reconcile_rejects_invalid_or_unsafe_xml(checker, tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "results.xml"
    path.write_bytes(payload)
    result = checker.reconcile_junit(path, ["tests/test_x.py::test_name"])
    assert set(result.values()) <= {"invalid_junit", "unsafe_junit", "junit_too_large"}


def test_reconcile_missing_file_and_empty_identities(checker, tmp_path: Path) -> None:
    assert checker.reconcile_junit(tmp_path / "absent.xml", ["test_x.py::test_name"]) == {
        "test_x.py::test_name": "missing_junit"
    }
    assert checker.reconcile_junit(tmp_path / "absent.xml", []) == {}


@pytest.mark.parametrize("command_id", ["../escape", "/absolute", "a/b", "..", "a\\b", "x\n"])
def test_unsafe_command_ids_rejected_before_execution(
    checker, project: Path, command_id: str
) -> None:
    with pytest.raises(ValueError, match="command ID"):
        run(checker, project, [command(["{python}", "--version"], id=command_id)], [])
    assert not (project.parent / "evidence").exists()


@pytest.mark.parametrize("cwd", ["..", "escape"])
def test_cwd_cannot_escape_root(checker, project: Path, cwd: str) -> None:
    (project / "escape").symlink_to(project.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="cwd"):
        run(checker, project, [command(["{python}", "--version"], cwd=cwd)], [])


def test_duplicate_ids_rejected_before_any_execution(checker, project: Path) -> None:
    check = command(["{python}", "--version"])
    with pytest.raises(ValueError, match="command ID"):
        run(checker, project, [check, check], [])
    assert not (project.parent / "evidence").exists()


def test_existing_evidence_symlink_rejected(checker, project: Path) -> None:
    evidence = project.parent / "evidence"
    evidence.mkdir()
    outside = project.parent / "private"
    outside.write_text("untouched")
    (evidence / "check.stdout.log").symlink_to(outside)
    with pytest.raises(ValueError, match="evidence"):
        run(checker, project, [command(["{python}", "--version"])], [])
    assert outside.read_text() == "untouched"


def test_stale_junit_cannot_satisfy_promise(checker, project: Path) -> None:
    evidence = project.parent / "evidence"
    evidence.mkdir()
    write_junit(evidence / "check.xml", [{
        "file": "test_x.py", "classname": "test_x", "name": "test_name",
    }])
    report = run(checker, project, [command(
        ["{python}", "--version"], adapter="pytest-junit"
    )], [promise("test_x.py::test_name")])
    assert report["passed"] is False
    assert report["promises"][0]["passed"] is False


def test_spawn_error_is_sanitized(checker, project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = []
    monkeypatch.setattr(checker.sentry_sdk, "capture_exception", captured.append)
    report = run(checker, project, [command(["/missing/SECRET-executable"])], [promise("check")])
    assert report["passed"] is False
    assert report["commands"][0]["returncode"] is None
    assert report["commands"][0]["reason"] == "execution_error"
    assert captured
    assert all("SECRET" not in str(error) and error.__traceback__ is None for error in captured)
    assert all(error.__context__ is None and error.__cause__ is None for error in captured)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")
@pytest.mark.parametrize("mode", ["timeout", "overflow", "exit"])
def test_process_group_cleanup_and_bounded_logs(checker, project: Path, mode: str) -> None:
    child = project / "child.py"
    child.write_text(
        "import pathlib, signal, socket, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "sock = socket.socket()\nsock.bind(('127.0.0.1', 0))\n"
        "sock.listen()\npathlib.Path('port').write_text(str(sock.getsockname()[1]))\n"
        "while True: time.sleep(0.1)\n"
    )
    parent = project / "parent.py"
    parent.write_text(
        "import os, pathlib, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, 'child.py'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "pathlib.Path('child-pid').write_text(str(child.pid))\n"
        "while not pathlib.Path('port').exists(): time.sleep(0.01)\n"
        "print('ready', flush=True)\n"
        + {
            "timeout": "while True: time.sleep(0.1)\n",
            "overflow": "while True: os.write(2, b'x' * 65536)\n",
            "exit": "sys.exit(0)\n",
        }[mode]
    )
    try:
        report = run(checker, project, [command(
            ["{python}", "parent.py"], timeout_seconds=1
        )], [promise("check")])
        result = report["commands"][0]
        assert report["passed"] is (mode == "exit")
        assert result["timed_out"] is (mode == "timeout")
        assert result["output_overflow"] is (mode == "overflow")
        assert result["returncode"] is not None
        assert sum(Path(result[key]).stat().st_size for key in (
            "stdout_path", "stderr_path"
        )) <= 2 * 1024 * 1024
        port = int((project / "port").read_text())
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", port)) != 0
    finally:
        pid_path = project / "child-pid"
        if pid_path.exists():
            pid = int(pid_path.read_text())
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_empty_checks_pass(checker, project: Path) -> None:
    assert run(checker, project, [], []) == {"passed": True, "commands": [], "promises": []}