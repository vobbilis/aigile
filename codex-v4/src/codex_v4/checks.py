"""Execute trusted project commands, not a sandbox.

The caller must validate contracts and obtain explicit --trust-checks consent.
Commands can access the host as the caller; cwd containment is not isolation.
POSIX cleanup covers descendants in the command's process group, not processes
that deliberately escape it. Output logs share a 2 MiB cap per command.
"""

import asyncio
import os
import re
import signal
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from xml.etree import ElementTree

import sentry_sdk

_LIMIT = 2 * 1024 * 1024
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _capture(reason: str) -> None:
    sentry_sdk.capture_exception(RuntimeError(f"Check runner: {reason}"))


def _class_suffix(file: str, classname: str) -> str | None:
    if not classname:
        return ""
    module = file.removesuffix(".py").replace("/", ".")
    parts = module.split(".")
    for offset in range(len(parts)):
        candidate = ".".join(parts[offset:])
        position = ("." + classname + ".").find("." + candidate + ".")
        if position >= 0:
            return classname[position + len(candidate) :].lstrip(".")
    return None


def _matches_without_file(case: ElementTree.Element, identity: str) -> bool:
    base, bracket, parameter = identity.partition("[")
    parts = base.split("::")
    if len(parts) < 2:
        return False
    classname = ".".join([parts[0].removesuffix(".py").replace("/", "."), *parts[1:-1]])
    return (
        case.get("classname") == classname
        and case.get("name") == parts[-1] + bracket + parameter
    )


def reconcile_junit(path: Path, identities: list[str]) -> dict[str, str]:
    """Return 'passed' or a failure reason for each exact pytest nodeid.

File attributes take precedence over classname module paths. Without a file,
match the full expected module/class name rather than guessing path boundaries.
Duplicate testcase results fail closed, including pass plus teardown error.
"""
    if not identities:
        return {}
    try:
        with path.open("rb") as source:
            data = source.read(_LIMIT + 1)
    except FileNotFoundError:
        _capture("missing_junit")
        return dict.fromkeys(identities, "missing_junit")
    except OSError:
        _capture("junit_read_error")
        return dict.fromkeys(identities, "invalid_junit")
    if len(data) > _LIMIT:
        return dict.fromkeys(identities, "junit_too_large")
    if b"\x00" in data or any(token in data.upper() for token in (b"<!DOCTYPE", b"<!ENTITY")):
        return dict.fromkeys(identities, "unsafe_junit")
    try:
        document = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        _capture("invalid_junit")
        return dict.fromkeys(identities, "invalid_junit")
    if document.tag not in {"testsuite", "testsuites"}:
        return dict.fromkeys(identities, "invalid_junit")
    results: dict[str, list[str]] = {identity: [] for identity in identities}
    for case in document.iter("testcase"):
        outcome = next(
            (tag for tag in ("error", "failure", "skipped") if case.find(tag) is not None),
            "passed",
        )
        if file := case.get("file"):
            file = str(PurePosixPath(file))
            suffix = _class_suffix(file, case.get("classname", ""))
            if suffix is None or not case.get("name"):
                continue
            classes = suffix.split(".") if suffix else []
            identity = "::".join([file, *classes, case.attrib["name"]])
            if identity in results:
                results[identity].append(outcome)
        else:
            for identity in results:
                if _matches_without_file(case, identity):
                    results[identity].append(outcome)
    return {
        identity: "missing" if not outcomes else "duplicate" if len(outcomes) > 1 else outcomes[0]
        for identity, outcomes in results.items()
    }


def _kill_group(process: asyncio.subprocess.Process) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        elif process.returncode is None:
            process.kill()
    except ProcessLookupError:
        _capture("process_already_exited")


async def _execute(result: dict, timeout: float) -> None:
    process = None
    readers: list[asyncio.Task] = []
    total = 0

    async def drain(stream: asyncio.StreamReader, target: BinaryIO) -> None:
        nonlocal total
        while chunk := await stream.read(64 * 1024):
            remaining = _LIMIT - total
            kept = chunk[:remaining]
            target.write(kept)
            total += len(kept)
            if len(chunk) > remaining and not result["output_overflow"]:
                result["output_overflow"] = True
                assert process is not None
                _kill_group(process)

    with (
        Path(result["stdout_path"]).open("wb") as stdout,
        Path(result["stderr_path"]).open("wb") as stderr,
    ):
        try:
            process = await asyncio.create_subprocess_exec(
                *result["argv"],
                cwd=result["cwd"],
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name == "posix",
            )
            assert process.stdout is not None and process.stderr is not None
            readers = [
                asyncio.create_task(drain(process.stdout, stdout)),
                asyncio.create_task(drain(process.stderr, stderr)),
            ]
            async with asyncio.timeout(timeout):
                await asyncio.gather(process.wait(), *readers)
        except TimeoutError:
            _capture("timeout")
            result["timed_out"] = True
            result["reason"] = "timeout"
        except asyncio.CancelledError:
            _capture("cancelled")
            raise
        except (OSError, ValueError):
            _capture("execution_error")
            result["reason"] = "execution_error"
        finally:
            if process is not None:
                _kill_group(process)
                for reader in readers:
                    reader.cancel()
                await asyncio.gather(*readers, return_exceptions=True)
                await process.communicate()
                result["returncode"] = process.returncode
    if result["output_overflow"]:
        result["reason"] = "output_limit"
    elif result["reason"] == "pending":
        result["reason"] = "passed" if result["returncode"] == 0 else "command_failed"
    result["passed"] = result["reason"] == "passed"


async def run_checks(
    commands: list[dict], promises: list[dict], root: Path, evidence: Path, python: str
) -> dict:
    """Run caller-trusted, contract-validated commands and reconcile promises.

The result contains passed, commands, and promises. Commands retain resolved
argv/cwd, returncode, timed_out, output_overflow, passed/reason, and absolute
stdout_path/stderr_path/junit_path evidence locations. Promise results contain
id, identity, passed, and reason. Invalid IDs or escaping paths raise ValueError
before executing any command. Execution and XML errors fail closed.
"""
    root = root.resolve(strict=True)
    evidence = evidence.resolve()
    prepared: list[dict] = []
    seen: set[str] = set()
    for command in commands:
        command_id = command["id"]
        if not isinstance(command_id, str) or not _SLUG.fullmatch(command_id) or command_id in seen:
            raise ValueError("Unsafe or duplicate command ID")
        seen.add(command_id)
        cwd = (root / command["cwd"]).resolve()
        if not cwd.is_relative_to(root) or not cwd.is_dir():
            raise ValueError("Command cwd must be a directory within root")
        paths = {
            "stdout_path": evidence / f"{command_id}.stdout.log",
            "stderr_path": evidence / f"{command_id}.stderr.log",
            "junit_path": evidence / f"{command_id}.xml",
        }
        if any(path.is_symlink() or not path.resolve().is_relative_to(evidence)
               for path in paths.values()):
            raise ValueError("Unsafe evidence path")
        argv = [argument.replace("{python}", python) for argument in command["argv"]]
        if command["adapter"] == "pytest-junit":
            argv.extend([f"--junitxml={paths['junit_path']}", "-o", "junit_family=xunit1"])
        prepared.append({
            "id": command_id,
            "adapter": command["adapter"],
            "argv": argv,
            "cwd": str(cwd),
            "timeout_seconds": command["timeout_seconds"],
            **{key: str(path) for key, path in paths.items()},
            "returncode": None,
            "timed_out": False,
            "output_overflow": False,
            "passed": False,
            "reason": "pending",
        })
    if prepared:
        evidence.mkdir(parents=True, exist_ok=True)
    command_results = {}
    junit_results = {}
    for result in prepared:
        if result["adapter"] == "pytest-junit":
            Path(result["junit_path"]).unlink(missing_ok=True)
        await _execute(result, result["timeout_seconds"])
        command_results[result["id"]] = result
        if result["adapter"] == "pytest-junit":
            identities = [item["identity"] for item in promises if item["command_id"] == result["id"]]
            junit_results[result["id"]] = reconcile_junit(Path(result["junit_path"]), identities)
    promise_results = []
    for item in promises:
        result = command_results.get(item["command_id"])
        identity = item["identity"]
        if result is None:
            reason = "missing_command"
        elif result["adapter"] == "command":
            reason = result["reason"] if identity == result["id"] else "identity_mismatch"
        else:
            reason = junit_results[item["command_id"]][identity]
            if reason == "passed" and not result["passed"]:
                reason = result["reason"]
        promise_results.append({
            "id": item["id"], "identity": identity, "passed": reason == "passed", "reason": reason
        })
    return {
        "passed": all(result["passed"] for result in prepared)
        and all(result["passed"] for result in promise_results),
        "commands": prepared,
        "promises": promise_results,
    }