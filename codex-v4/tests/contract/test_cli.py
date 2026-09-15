import asyncio
import json
import subprocess
import sys
from pathlib import Path

from codex_v4.cli import discover


def test_help_exposes_workflow_commands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "codex_v4", "--help"], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, "Doctor CLI is missing"
    assert "doctor" in result.stdout
    assert "build" in result.stdout
    assert "plan" in result.stdout
    assert "status" in result.stdout


def test_build_requires_trust_before_starting_runtime(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "codex_v4",
            "build",
            "missing.md",
            "--repo",
            str(tmp_path),
            "--output",
            str(tmp_path / "run"),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert "trust-checks" in result.stderr
    assert not (tmp_path / "run").exists()


def test_missing_profile_reports_sanitized_configuration_failure(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "codex_v4", "doctor", "--codex-home", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["certified"] is False
    assert report["error"] == "CONFIGURATION"
    assert str(tmp_path) not in result.stdout
    assert "Traceback" not in result.stderr


def test_rejected_boundary_probe_preserves_discovery() -> None:
    command = [
        sys.executable,
        str(Path(__file__).parents[1] / "fixtures/server.py"),
        "reject-probe",
    ]
    report = asyncio.run(discover(command, {}, True))
    assert report["handshake"] == "PASSED"
    assert report["observed_models"] == ["local-model"]
    assert report["read_boundary_probe"]["result"] == "UNVERIFIED"
    assert report["read_boundary_probe"]["error"] == "COMMAND_REJECTED_OR_UNAVAILABLE"
    assert "secret-fixture-value" not in json.dumps(report)
