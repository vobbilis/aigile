import asyncio
import json
import sys
from collections.abc import Callable
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Protocol

import sentry_sdk
from jsonschema import Draft202012Validator

from codex_v4.checks import run_checks
from codex_v4.contracts import SPEC_SCHEMA, render_spec, validate_spec
from codex_v4.workspace import apply_changes, changed_paths, file_hashes, snapshot, tree_digest


class Model(Protocol):
    async def ask(self, role: str, prompt: str, schema: dict, worker: str) -> dict: ...


EDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "summary", "changes"],
    "properties": {
        "status": {"enum": ["ready", "escalate"]},
        "summary": {"type": "string"},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "content"],
                "properties": {"path": {"type": "string"}, "content": {"type": ["string", "null"]}},
            },
        },
    },
}
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["passed", "findings"],
    "properties": {
        "passed": {"type": "boolean"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
}


def save_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    temporary.replace(path)


def context(root: Path, paths: list[str]) -> str:
    hashes = file_hashes(root)
    files = {}
    for name in dict.fromkeys(paths):
        if name not in hashes:
            continue
        files[name] = (root / name).read_text()
    payload = json.dumps({"files": files, "available_paths": list(hashes)}, ensure_ascii=True)
    if len(payload) > 250_000:
        raise ValueError("Context exceeds 250000 characters; select fewer context files")
    return payload


def _prepare(source: Path, output: Path) -> Path:
    source = source.resolve(strict=True)
    if output.is_symlink() or output.exists() or output.resolve().is_relative_to(source):
        raise ValueError("Run directory must be new and outside the source repository")
    output.mkdir(parents=True)
    root = output / "workspace"
    snapshot(source, root)
    return root


async def _ask(model: Model, role: str, payload: dict, schema: dict, worker: str) -> dict:
    answer = await model.ask(role, json.dumps(payload, ensure_ascii=True), schema, worker)
    Draft202012Validator(schema).validate(answer)
    return answer


async def plan(
    requirements: str,
    source: Path,
    output: Path,
    model: Model,
    *,
    panel: str = "auto",
    context_files: list[str] | None = None,
    progress: Callable[[str], None] = print,
) -> dict:
    if not requirements.strip() or panel not in {"auto", "on", "off"}:
        raise ValueError("Requirements and a valid panel policy are required")
    root = _prepare(source, output)
    hashes = file_hashes(root)
    selected = context_files if context_files is not None else ["README.md"]
    pins = [{"path": name, "sha256": hashes[name]} for name in selected if name in hashes]
    digest = tree_digest(root)
    payload = {
        "instruction": "Create a repository-grounded implementation spec. Do not change files. "
        "Use exact file write scopes and test identities. Use lowercase hyphenated command IDs. "
        "Every material failure must map to a test promise. No test-count quota. "
        "Separate locked constraints, private implementation discretion, and escalation. "
        "Use {python} for Python commands. Return only the requested JSON object.",
        "requirements": requirements,
        "repo_digest": digest,
        "context_files": pins,
        "panel": panel,
        "repository": context(root, selected),
    }
    result = {"status": "PLANNING", "workspace": str(root), "reviews": []}
    save_json(output / "result.json", result)
    try:
        progress("Planning: reading supplied repository context")
        spec = await _ask(model, "planner", payload, SPEC_SCHEMA, "planner")
        spec.update(requirements=requirements, repo_digest=digest, context_files=pins)
        spec["planning"]["panel"] = panel
        validate_spec(spec)
        if not spec["tasks"]:
            raise ValueError("Plan must contain at least one task")
        if panel == "on" or panel == "auto" and spec["planning"]["complexity"] != "simple":
            progress("Planning: independent critic review")
            for lens in ("failure-coverage", "grounding", "missing-work", "routing"):
                review = await _ask(
                    model,
                    "critic",
                    {
                        "instruction": f"Review this spec for {lens}. Return actionable findings.",
                        "spec": spec,
                        "repository": context(root, selected),
                    },
                    REVIEW_SCHEMA,
                    f"critic-{lens}",
                )
                result["reviews"].append({"lens": lens, **review})
            if any(not review["passed"] or review["findings"] for review in result["reviews"]):
                spec = await _ask(
                    model,
                    "planner",
                    {
                        **payload,
                        "previous_spec": spec,
                        "critic_findings": result["reviews"],
                        "instruction": "Revise the spec to address the critic findings, retaining "
                        "requirements and locked constraints. Return the complete spec JSON.",
                    },
                    SPEC_SCHEMA,
                    "planner",
                )
                spec.update(requirements=requirements, repo_digest=digest, context_files=pins)
                spec["planning"]["panel"] = panel
                validate_spec(spec)
        if tree_digest(root) != digest:
            raise ValueError("Planner changed its read-only repository snapshot")
        spec_path = output / "spec.md"
        spec_path.write_text(render_spec(spec))
        result.update(status="PLANNED", spec=str(spec_path))
        save_json(output / "result.json", result)
        return result
    except Exception:
        sentry_sdk.capture_exception(RuntimeError("Planning failed"))
        result["status"] = "ERROR"
        save_json(output / "result.json", result)
        raise


async def build(
    spec: dict,
    source: Path,
    output: Path,
    model: Model,
    *,
    python: str = sys.executable,
    trust_checks: bool = False,
    progress: Callable[[str], None] = print,
) -> dict:
    if not trust_checks:
        raise ValueError("Explicit trust_checks consent is required for host project commands")
    validate_spec(spec)
    if not spec["tasks"] or not spec["validation_commands"]:
        raise ValueError("Build requires tasks and validation commands")
    if tree_digest(source) != spec["repo_digest"]:
        raise ValueError("Repository changed since planning; generate a new plan")
    hashes = file_hashes(source)
    if any(hashes.get(pin["path"]) != pin["sha256"] for pin in spec["context_files"]):
        raise ValueError("Pinned context changed")
    root = _prepare(source, output)
    original = file_hashes(root)
    result: dict = {
        "status": "RUNNING",
        "workspace": str(root),
        "tasks": {},
        "mode": "trusted-checks",
    }
    commands = {command["id"]: command for command in spec["validation_commands"]}
    tasks = {task["id"]: task for task in spec["tasks"]}
    pins = [pin["path"] for pin in spec["context_files"]]
    save_json(output / "result.json", result)

    def checkpoint(message: str) -> None:
        save_json(output / "result.json", result)
        with (output / "events.jsonl").open("a") as stream:
            stream.write(json.dumps({"event": message, "status": result["status"]}) + "\n")
        progress(message)

    async def checks(selected: list[dict], promises: list[dict], name: str) -> dict:
        before = file_hashes(root)
        checked = await run_checks(selected, promises, root, output / "checks" / name, python)
        checked["changed_source_paths"] = changed_paths(before, file_hashes(root))
        checked["passed"] = checked["passed"] and not checked["changed_source_paths"]
        return checked

    def finish(status: str) -> dict:
        result["status"] = status
        result["changed_paths"] = changed_paths(original, file_hashes(root))
        result["tree_digest"] = tree_digest(root)
        checkpoint(f"Build {status}: {output}")
        (output / "build-evidence.md").write_text(
            f"# {spec['title']}\n\nResult: **{status}**\n\n"
            f"Workspace: {root}\n\nSource repository was not modified by the controller.\n\n"
            "Project checks ran as trusted host commands, not sandboxed commands.\n\n"
            "See result.json for check results, attempts, and review findings.\n"
        )
        (output / "spec.md").write_text(render_spec(spec) + f"\nBuild result: {status}\n")
        return result

    try:
        for index, task_id in enumerate(
            TopologicalSorter(
                {name: task["depends_on"] for name, task in tasks.items()}
            ).static_order()
        ):
            task = tasks[task_id]
            entry: dict = {"status": "RUNNING", "attempts": []}
            result["tasks"][task_id] = entry
            selected_ids = {promise["command_id"] for promise in task["test_promises"]}
            selected = [command for name, command in commands.items() if name in selected_ids]
            for attempt in range(3):
                checkpoint(f"Task {task_id}: attempt {attempt + 1}/3")
                answer = await _ask(
                    model,
                    "builder",
                    {
                        "instruction": (
                            "Implement only this task's exact write_scope. Return full "
                            "file contents (null deletes). Do not execute commands or edit "
                            "files yourself. Respect locked constraints; use discretion only "
                            "within the contract. If the contract conflicts with the repository, "
                            "return status escalate with the conflict, evidence, affected task, "
                            "and proposed resolution. Do not weaken tests."
                        ),
                        "task": task,
                        "design": spec["design"],
                        "requirements": spec["requirements"],
                        "repository": context(root, pins + task["write_scope"]),
                        "previous_attempts": entry["attempts"],
                    },
                    EDIT_SCHEMA,
                    task["assigned_agent"],
                )
                record: dict = {"summary": answer["summary"], "attempt": attempt + 1}
                entry["attempts"].append(record)
                if answer["status"] == "escalate":
                    entry["status"] = "NEEDS_DECISION"
                    return finish("NEEDS_DECISION")
                record["changed_paths"] = apply_changes(
                    root, answer["changes"], task["write_scope"]
                )
                record["checks"] = await checks(
                    selected, task["test_promises"], f"task-{index}-{attempt}"
                )
                if record["checks"]["passed"]:
                    record["review"] = await _ask(
                        model,
                        "reviewer",
                        {
                            "instruction": (
                                "Independently review code and tests against acceptance, "
                                "locked constraints and failure coverage. Detect weakened "
                                "assertions. Do not edit files. Passing commands alone "
                                "do not imply approval."
                            ),
                            "task": task,
                            "design": spec["design"],
                            "repository": context(root, pins + task["write_scope"]),
                            "checks": record["checks"],
                        },
                        REVIEW_SCHEMA,
                        f"review-{index}-{attempt}",
                    )
                    if record["review"]["passed"] and not record["review"]["findings"]:
                        entry["status"] = "PASSED"
                        break
                checkpoint(f"Task {task_id}: validation failed")
            if entry["status"] != "PASSED":
                entry["status"] = "FAILED"
                return finish("FAILED")
            checkpoint(f"Task {task_id}: PASSED")
        promises = [promise for task in tasks.values() for promise in task["test_promises"]]
        scope = [path for task in tasks.values() for path in task["write_scope"]]
        result["final_checks"] = await checks(list(commands.values()), promises, "final")
        if not result["final_checks"]["passed"]:
            return finish("FAILED")
        checkpoint("Final independent review")
        result["final_review"] = await _ask(
            model,
            "reviewer",
            {
                "instruction": "Review the complete build against the spec, including cross-task "
                "compatibility, failure cases, and test adequacy. Do not edit files.",
                "spec": spec,
                "repository": context(root, pins + scope),
                "checks": result["final_checks"],
            },
            REVIEW_SCHEMA,
            "final-review",
        )
        if not result["final_review"]["passed"] or result["final_review"]["findings"]:
            return finish("FAILED")
        checkpoint("Second verification pass")
        result["second_pass"] = await checks(list(commands.values()), promises, "second-pass")
        return finish("PASSED" if result["second_pass"]["passed"] else "FAILED")
    except (Exception, asyncio.CancelledError):
        sentry_sdk.capture_exception(RuntimeError("Build workflow failed"))
        result["status"] = "ERROR"
        checkpoint("Build stopped on error; workspace retained")
        raise
