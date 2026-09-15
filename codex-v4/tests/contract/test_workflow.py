import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest

from codex_v4.contracts import render_spec
from codex_v4.workspace import tree_digest


def example(root: Path) -> dict:
    return {
        "schema": "codex-v4/spec/2",
        "spec_id": "add-double",
        "title": "Add double",
        "requirements": "Double an integer, including negatives.",
        "repo_digest": tree_digest(root),
        "planning": {"complexity": "simple", "panel": "auto"},
        "design": {
            "summary": "Add a pure function.",
            "locked": ["double(value) returns value * 2"],
            "discretion": ["Internal implementation"],
            "escalate": ["Public API changes"],
        },
        "context_files": [],
        "agents": [{"id": "builder", "model_class": "STANDARD", "tasks": ["double"]}],
        "tasks": [
            {
                "id": "double",
                "title": "Implement double",
                "instructions": "Add code and tests.",
                "assigned_agent": "builder",
                "model_class": "STANDARD",
                "depends_on": [],
                "write_scope": ["double.py", "test_double.py"],
                "acceptance": ["Positive and negative inputs work."],
                "failure_surface": [{"id": "negative", "condition": "Negative input"}],
                "test_promises": [
                    {
                        "id": "test-double",
                        "identity": "test_double.py::test_double",
                        "command_id": "unit",
                        "covers_failure_ids": ["negative"],
                    }
                ],
            }
        ],
        "validation_commands": [
            {
                "id": "unit",
                "argv": ["{python}", "-m", "pytest", "test_double.py", "-q"],
                "cwd": ".",
                "timeout_seconds": 30,
                "adapter": "pytest-junit",
            }
        ],
    }


def edits(correct: bool = True) -> dict:
    return {
        "status": "ready",
        "summary": "Implemented double.",
        "changes": [
            {
                "path": "double.py",
                "content": f"def double(value):\n    return value * {2 if correct else 3}\n",
            },
            {
                "path": "test_double.py",
                "content": (
                    "from double import double\n\ndef test_double():\n"
                    "    assert double(2) == 4\n    assert double(-2) == -4\n"
                ),
            },
        ],
    }


class Model:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def ask(self, role: str, prompt: str, schema: dict, worker: str) -> dict:
        self.calls.append({"role": role, "prompt": prompt, "worker": worker})
        return self.responses.pop(0)


def run_build(tmp_path: Path, responses: list[dict], *, trust: bool = True):
    api = importlib.import_module("codex_v4.workflow")
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("Sandbox project\n")
    spec = example(source)
    model = Model(responses)
    result = asyncio.run(
        api.build(
            spec,
            source,
            tmp_path / "run",
            model,
            python=sys.executable,
            trust_checks=trust,
        )
    )
    return result, model, source


def test_build_runs_real_checks_and_independent_review(tmp_path):
    result, model, source = run_build(
        tmp_path,
        [
            edits(),
            {"passed": True, "findings": []},
            {"passed": True, "findings": []},
        ],
    )
    assert result["status"] == "PASSED"
    assert result["final_checks"]["promises"][0]["passed"] is True
    assert result["second_pass"]["passed"] is True
    assert not (source / "double.py").exists()
    assert (Path(result["workspace"]) / "double.py").exists()
    assert [call["role"] for call in model.calls] == ["builder", "reviewer", "reviewer"]
    assert model.calls[0]["worker"] != model.calls[1]["worker"]
    saved = json.loads((tmp_path / "run" / "result.json").read_text())
    assert saved["status"] == "PASSED"
    assert "PASSED" in (tmp_path / "run" / "build-evidence.md").read_text()


def test_failed_check_repairs_original_task(tmp_path):
    result, model, _ = run_build(
        tmp_path,
        [
            edits(False),
            edits(),
            {"passed": True, "findings": []},
            {"passed": True, "findings": []},
        ],
    )
    assert result["status"] == "PASSED"
    attempts = result["tasks"]["double"]["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["checks"]["passed"] is False
    assert model.calls[0]["worker"] == model.calls[1]["worker"]
    assert "command_failed" in model.calls[1]["prompt"]


def test_exhausted_repairs_do_not_release_final_gate(tmp_path):
    result, model, _ = run_build(tmp_path, [edits(False)] * 3)
    assert result["status"] == "FAILED"
    assert len(result["tasks"]["double"]["attempts"]) == 3
    assert all(call["role"] == "builder" for call in model.calls)
    assert "final_checks" not in result


def test_escalation_stops_without_applying_changes(tmp_path):
    result, _, _ = run_build(
        tmp_path,
        [
            {
                "status": "escalate",
                "summary": "Acceptance conflicts with requirement.",
                "changes": [],
            }
        ],
    )
    assert result["status"] == "NEEDS_DECISION"
    assert not (Path(result["workspace"]) / "double.py").exists()


def test_checks_require_explicit_trust(tmp_path):
    with pytest.raises(ValueError, match="trust"):
        run_build(tmp_path, [], trust=False)


def test_plan_publishes_validated_manifest(tmp_path):
    api = importlib.import_module("codex_v4.workflow")
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("Sandbox project\n")
    spec = example(source)
    model = Model([spec])
    result = asyncio.run(
        api.plan(spec["requirements"], source, tmp_path / "plan", model, panel="auto")
    )
    assert result["status"] == "PLANNED"
    assert Path(result["spec"]).read_text() == render_spec(spec)
    assert [call["role"] for call in model.calls] == ["planner"]
