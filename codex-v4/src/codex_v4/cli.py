import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import jsonschema
import sentry_sdk

from codex_v4.app_server import AppServer, ProtocolError
from codex_v4.certification import read_probe_params, read_profile_args, sandbox_blockers
from codex_v4.contracts import parse_spec
from codex_v4.native import NativeModel, worker_permission_args
from codex_v4.runtime import EXPECTED_MODELS, assess_models, launch_command
from codex_v4.workflow import build, plan, save_json


async def discover(command: list[str], environment: dict[str, str], probe: bool) -> dict:
    if probe:
        command = [*command, *read_profile_args()]
    with tempfile.TemporaryDirectory(prefix="codex-v4-discovery-") as directory:
        async with AppServer(command, cwd=directory, env=environment, timeout=20) as server:
            observed: list[str] = []
            cursor = None
            seen_cursors: set[str] = set()
            for _ in range(20):
                page = await server.request("model/list", {"includeHidden": True, "cursor": cursor})
                observed.extend(item["id"] for item in page["data"])
                cursor = page.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or cursor in seen_cursors:
                    raise ProtocolError("Invalid model pagination")
                seen_cursors.add(cursor)
            else:
                raise ProtocolError("Model pagination limit exceeded")
            report = assess_models(observed, list(EXPECTED_MODELS))
            report["handshake"] = "PASSED"
            if probe:
                with tempfile.TemporaryDirectory(
                    prefix=".codex-v4-boundary-", dir=Path.home()
                ) as boundary:
                    parent = Path(boundary).resolve()
                    root = parent / "allowed"
                    root.mkdir()
                    inside = root / "control"
                    outside = parent / "sentinel"
                    marker = "codex-v4-synthetic-boundary-marker"
                    inside.write_text(marker)
                    outside.write_text(marker)
                    try:
                        control = await server.request(
                            "command/exec", read_probe_params(root, inside)
                        )
                        attack = await server.request(
                            "command/exec", read_probe_params(root, outside)
                        )
                    except (ProtocolError, TimeoutError):
                        sentry_sdk.capture_exception(RuntimeError("Synthetic read probe failed"))
                        report["read_boundary_probe"] = {
                            "result": "UNVERIFIED",
                            "error": "COMMAND_REJECTED_OR_UNAVAILABLE",
                        }
                    else:
                        control_passed = control.get("exitCode") == 0 and marker in control.get(
                            "stdout", ""
                        )
                        escaped = marker in attack.get("stdout", "")
                        report["read_boundary_probe"] = {
                            "control_read_succeeded": control_passed,
                            "outside_sentinel_readable": escaped,
                            "result": "FAILED" if escaped else "UNVERIFIED",
                        }
                        if control_passed and not escaped and attack.get("exitCode") != 0:
                            report["read_boundary_probe"]["result"] = "PASSED"
            report["rejected_requests"] = server.rejected_requests
            return report


def doctor(home: Path, probe: bool) -> dict:
    with (home / "codex-multi.config.toml").open("rb") as stream:
        profile = tomllib.load(stream)
    with (home / "config.toml").open("rb") as stream:
        base = tomllib.load(stream)
    command = launch_command(profile, list(base.get("mcp_servers", {})))
    environment = {
        key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "LANG"}
    }
    environment["CODEX_HOME"] = str(home.resolve())
    version = subprocess.run(
        ["codex", "--version"], capture_output=True, text=True, timeout=10, check=True
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="codex-v4-schema-") as directory:
        subprocess.run(
            ["codex", "app-server", "generate-json-schema", "--experimental", "--out", directory],
            capture_output=True,
            timeout=30,
            check=True,
            env=environment,
            cwd=directory,
        )
        schema_bytes = (Path(directory) / "v2/CommandExecParams.json").read_bytes()
        schema = json.loads(schema_bytes)
        jsonschema.Draft7Validator.check_schema(schema)
        blockers = sandbox_blockers(schema)
        report = asyncio.run(discover(command, environment, probe))
        report.update(
            {
                "codex_version": version,
                "command_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
                "blockers": blockers,
                "phase0": "BLOCKED" if blockers else "INCOMPLETE",
                "inference_executed": False,
            }
        )
        if report.get("read_boundary_probe", {}).get("result") == "FAILED":
            report["blockers"].append("Restricted read policy did not isolate the synthetic file")
            report["phase0"] = "BLOCKED"
        return report


async def execute_workflow(args: argparse.Namespace) -> dict:
    with (args.codex_home / "codex-multi.config.toml").open("rb") as stream:
        profile = tomllib.load(stream)
    with (args.codex_home / "config.toml").open("rb") as stream:
        base = tomllib.load(stream)
    command = launch_command(profile, list(base.get("mcp_servers", {})))
    command.extend(worker_permission_args())
    bindings = dict.fromkeys(
        ["MECHANICAL", "STANDARD", "REASONING"], args.model or profile["model"]
    )
    if args.bindings:
        bindings = json.loads(args.bindings.read_text())
    environment = {
        key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "LANG"}
    }
    environment["CODEX_HOME"] = str(args.codex_home.resolve())
    output = args.output.resolve()
    source = args.repo.resolve(strict=True)
    if output.exists() or output.is_relative_to(source):
        raise ValueError("Output must be a new directory outside the source repository")
    requirements = args.requirements.read_text() if args.command == "plan" else None
    spec = parse_spec(args.spec.read_text()) if args.command == "build" else None
    with tempfile.TemporaryDirectory(prefix="codex-v4-worker-") as temporary:
        async with AppServer(command, cwd=temporary, env=environment, timeout=30) as server:
            model = NativeModel(server, Path(temporary), bindings, timeout=args.turn_timeout)

            def progress(message: str) -> None:
                print(message, file=sys.stderr, flush=True)
                if output.exists():
                    save_json(output / "routes.json", {"turns": model.events})

            try:
                if args.command == "plan":
                    return await plan(
                        requirements,
                        source,
                        output,
                        model,
                        panel=args.panel,
                        context_files=args.context,
                        progress=progress,
                    )
                return await build(
                    spec,
                    source,
                    output,
                    model,
                    python=args.python,
                    trust_checks=args.trust_checks,
                    progress=progress,
                )
            finally:
                if output.exists():
                    save_json(output / "routes.json", {"turns": model.events})


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex v4 sandbox workflows")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="Check runtime without inference")
    doctor_parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    doctor_parser.add_argument("--probe-read-boundary", action="store_true")
    plan_parser = subparsers.add_parser("plan", help="Generate a validated implementation spec")
    plan_parser.add_argument("requirements", type=Path, help="Requirements text file")
    plan_parser.add_argument("--panel", choices=["auto", "on", "off"], default="auto")
    plan_parser.add_argument("--context", action="append", help="Repository-relative context file")
    build_parser = subparsers.add_parser("build", help="Build and validate in a separate snapshot")
    build_parser.add_argument("spec", type=Path)
    build_parser.add_argument(
        "--trust-checks",
        action="store_true",
        help="Allow spec commands to execute on this host, without a sandbox",
    )
    build_parser.add_argument("--python", default=sys.executable, help="Python for project checks")
    for workflow_parser in (plan_parser, build_parser):
        workflow_parser.add_argument("--repo", type=Path, required=True)
        workflow_parser.add_argument("--output", type=Path, required=True)
        workflow_parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
        workflow_parser.add_argument("--model", help="Use one model for all classes")
        workflow_parser.add_argument("--bindings", type=Path, help="JSON class-to-model mapping")
        workflow_parser.add_argument("--turn-timeout", type=int, default=300)
    status_parser = subparsers.add_parser("status", help="Read persisted run status")
    status_parser.add_argument("run", type=Path)
    args = parser.parse_args()
    if args.command == "build" and not args.trust_checks:
        parser.error("build requires --trust-checks: project commands execute on the host")
    if args.command != "doctor":
        try:
            if args.command == "status":
                report = json.loads((args.run / "result.json").read_text())
            else:
                if args.turn_timeout <= 0:
                    parser.error("--turn-timeout must be positive")
                report = asyncio.run(execute_workflow(args))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            ProtocolError,
            TimeoutError,
            jsonschema.ValidationError,
        ):
            sentry_sdk.capture_exception(RuntimeError("Codex workflow command failed"))
            print(
                "Workflow failed; inspect the retained run directory. No automatic retry.",
                file=sys.stderr,
            )
            return 2
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] in {"PASSED", "PLANNED"} else 2
    try:
        report = doctor(args.codex_home, args.probe_read_boundary)
    except (OSError, ValueError, KeyError, TypeError):
        sentry_sdk.capture_exception(RuntimeError("Codex v4 configuration check failed"))
        report = {"phase0": "BLOCKED", "certified": False, "error": "CONFIGURATION"}
    except (ProtocolError, TimeoutError, subprocess.SubprocessError, jsonschema.SchemaError):
        sentry_sdk.capture_exception(RuntimeError("Codex v4 runtime check failed"))
        report = {"phase0": "BLOCKED", "certified": False, "error": "RUNTIME"}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2
