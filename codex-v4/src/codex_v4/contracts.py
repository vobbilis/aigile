import html
import json
import re
from graphlib import TopologicalSorter
from pathlib import PurePosixPath

from jsonschema import Draft202012Validator

_START = "<!-- codex-v4-manifest:start -->"
_END = "<!-- codex-v4-manifest:end -->"
_TEXT = {"type": "string"}
_NONEMPTY = {"type": "string", "minLength": 1}
_CLASS = {"enum": ["MECHANICAL", "STANDARD", "REASONING"]}
_SHA256 = {
    "type": "string",
    "minLength": 64,
    "maxLength": 64,
    "pattern": "^[a-fA-F0-9]{64}$",
}
_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_PROTECTED = {".git", ".claude", ".codex", ".codex-v4"}
_PYTHON = {"python", "python3", "{python}"}
_PROGRAMS = _PYTHON | {"pytest", "ruff", "npm", "npx", "yarn", "cargo", "go"}


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _array(items: dict, minimum: int = 0) -> dict:
    return {"type": "array", "items": items, "minItems": minimum}


SPEC_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **_object(
        {
            "schema": {"const": "codex-v4/spec/2"},
            "spec_id": {"type": "string", "pattern": f"^{_SLUG}$"},
            "title": _NONEMPTY,
            "requirements": _TEXT,
            "repo_digest": _SHA256,
            "planning": _object(
                {
                    "complexity": {"enum": ["simple", "medium", "complex"]},
                    "panel": {"enum": ["auto", "on", "off"]},
                }
            ),
            "design": _object(
                {
                    "summary": _TEXT,
                    "locked": _array(_NONEMPTY, 1),
                    "discretion": _array(_TEXT),
                    "escalate": _array(_TEXT),
                }
            ),
            "context_files": _array(_object({"path": _NONEMPTY, "sha256": _SHA256})),
            "agents": _array(
                _object({"id": _NONEMPTY, "model_class": _CLASS, "tasks": _array(_NONEMPTY)})
            ),
            "tasks": _array(
                _object(
                    {
                        "id": _NONEMPTY,
                        "title": _NONEMPTY,
                        "instructions": _TEXT,
                        "assigned_agent": _NONEMPTY,
                        "model_class": _CLASS,
                        "depends_on": _array(_NONEMPTY),
                        "write_scope": _array(_NONEMPTY, 1),
                        "acceptance": _array(_NONEMPTY, 1),
                        "failure_surface": _array(_object({"id": _NONEMPTY, "condition": _TEXT})),
                        "test_promises": _array(
                            _object(
                                {
                                    "id": _NONEMPTY,
                                    "identity": _NONEMPTY,
                                    "command_id": _NONEMPTY,
                                    "covers_failure_ids": _array(_NONEMPTY),
                                }
                            ),
                            1,
                        ),
                    }
                )
            ),
            "validation_commands": _array(
                _object(
                    {
                        "id": _NONEMPTY,
                        "argv": _array(_NONEMPTY, 1),
                        "cwd": _NONEMPTY,
                        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 900},
                        "adapter": {"enum": ["pytest-junit", "command"]},
                    }
                ),
                1,
            ),
        }
    ),
}

_VALIDATOR = Draft202012Validator(SPEC_SCHEMA)


def _unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"Duplicate {label}: {value!r}")
        seen.add(value)
    return seen


def _index(entries: list[dict], label: str) -> dict[str, dict]:
    _unique([entry["id"] for entry in entries], f"{label} ID")
    return {entry["id"]: entry for entry in entries}


def _validate_path(path: str, *, cwd: bool = False, write: bool = False) -> None:
    if cwd and path == ".":
        return
    parts = path.split("/")
    if (
        not path
        or path.startswith(("/", "~"))
        or re.match(r"^[A-Za-z]:", path)
        or any(character in path for character in "\\*?[]{}")
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
        or any(part in {"", ".", ".."} for part in parts)
        or any(
            part.casefold() in _PROTECTED
            or part.casefold() == ".env"
            or part.casefold().startswith(".env.")
            for part in parts
        )
    ):
        raise ValueError(f"Unsafe relative path: {path!r}")
    if write and parts[0].casefold() == "codex-v4":
        raise ValueError(f"Controller paths are not writable: {path!r}")


def _python_module(argv: list[str]) -> str | None:
    position = 1
    while position < len(argv):
        argument = argv[position]
        if not argument.startswith("-") or argument in {"-", "--"}:
            return None
        if argument.startswith("--"):
            position += 2 if argument == "--check-hash-based-pycs" else 1
            continue
        for offset, option in enumerate(argument[1:], start=1):
            if option == "c":
                raise ValueError("Interpreter -c commands are forbidden")
            if option == "m":
                module = argument[offset + 1 :]
                if not module and position + 1 < len(argv):
                    module = argv[position + 1]
                if not module:
                    raise ValueError("Python -m requires a module")
                return module
            if option in {"W", "X"}:
                if not argument[offset + 1 :]:
                    position += 1
                break
        position += 1
    return None


def _validate_command(command: dict) -> None:
    _validate_path(command["cwd"], cwd=True)
    argv = command["argv"]
    if any("\x00" in argument for argument in argv):
        raise ValueError("Command arguments cannot contain NUL")
    program = PurePosixPath(argv[0]).name
    if program not in _PROGRAMS or "\\" in argv[0]:
        raise ValueError(f"Command program is not allowed: {argv[0]!r}")
    module = _python_module(argv) if program in _PYTHON else None
    if program in {"npm", "npx", "yarn"} and any(
        argument.startswith(("-c", "--call=")) or argument == "--call" for argument in argv[1:]
    ):
        raise ValueError("Shell -c/--call commands are forbidden")
    if command["adapter"] == "pytest-junit" and not (
        program == "pytest" or program in _PYTHON and module == "pytest"
    ):
        raise ValueError("pytest-junit requires a pytest invocation or python -m pytest")


def _validate_assignments(tasks: dict[str, dict], agents: dict[str, dict]) -> None:
    assigned: dict[str, set[str]] = {agent_id: set() for agent_id in agents}
    for task_id, task in tasks.items():
        agent_id = task["assigned_agent"]
        if agent_id not in agents:
            raise ValueError(f"Task {task_id!r} references unknown agent {agent_id!r}")
        if task["model_class"] != agents[agent_id]["model_class"]:
            raise ValueError(f"Task {task_id!r} and agent {agent_id!r} model classes must match")
        assigned[agent_id].add(task_id)
    for agent_id, agent in agents.items():
        claimed = _unique(agent["tasks"], f"task assignment for {agent_id}")
        if claimed != assigned[agent_id]:
            raise ValueError(f"Agent {agent_id!r} task assignments must match exactly")


def _validate_promises(task: dict, commands: dict[str, dict]) -> None:
    failures = {failure["id"] for failure in task["failure_surface"]}
    covered: set[str] = set()
    for promise in task["test_promises"]:
        command_id = promise["command_id"]
        if command_id not in commands:
            raise ValueError(f"Promise {promise['id']!r} references unknown command {command_id!r}")
        identity = promise["identity"]
        if commands[command_id]["adapter"] == "command":
            if identity != command_id:
                raise ValueError("Command adapter promise identity must equal command ID")
        elif not identity.strip():
            raise ValueError("pytest-junit promise identity requires a nonempty nodeid")
        promised = _unique(promise["covers_failure_ids"], f"failure reference in {promise['id']}")
        if not promised <= failures:
            raise ValueError(f"Promise {promise['id']!r} references unknown same-task failure IDs")
        covered.update(promised)
    if covered != failures:
        raise ValueError(
            f"Task {task['id']!r} has uncovered failures: {sorted(failures - covered)}"
        )


def _validate_graph(tasks: dict[str, dict]) -> None:
    dependencies = {}
    writers: dict[str, list[str]] = {}
    for task_id, task in tasks.items():
        dependencies[task_id] = _unique(task["depends_on"], f"dependency in {task_id}")
        unknown = dependencies[task_id] - tasks.keys()
        if unknown:
            raise ValueError(f"Task {task_id!r} has unknown dependencies: {sorted(unknown)}")
        for path in _unique(task["write_scope"], f"write path in {task_id}"):
            _validate_path(path, write=True)
            writers.setdefault(path, []).append(task_id)
    ancestors: dict[str, set[str]] = {}
    for task_id in TopologicalSorter(dependencies).static_order():
        ancestors[task_id] = set(dependencies[task_id])
        for dependency in dependencies[task_id]:
            ancestors[task_id].update(ancestors[dependency])
    for path, owners in writers.items():
        for position, first in enumerate(owners):
            for second in owners[position + 1 :]:
                if first not in ancestors[second] and second not in ancestors[first]:
                    raise ValueError(f"Unordered write overlap for {path!r}: {first!r}, {second!r}")


def validate_spec(spec: dict) -> None:
    _VALIDATOR.validate(spec)
    if not re.fullmatch(_SLUG, spec["spec_id"]):
        raise ValueError("spec_id must be a lowercase hyphen-separated slug")
    tasks = _index(spec["tasks"], "task")
    agents = _index(spec["agents"], "agent")
    commands = _index(spec["validation_commands"], "command")
    for field in ("failure_surface", "test_promises"):
        _index([entry for task in tasks.values() for entry in task[field]], field)
    for context in spec["context_files"]:
        _validate_path(context["path"])
    for command in commands.values():
        _validate_command(command)
    _validate_assignments(tasks, agents)
    for task in tasks.values():
        _validate_promises(task, commands)
    _validate_graph(tasks)


def _narrative(text: str) -> str:
    return html.escape(text, quote=False).replace("`", "&#96;")


def render_spec(spec: dict) -> str:
    validate_spec(spec)
    design = spec["design"]
    lines = [
        f"# {_narrative(spec['title'])}",
        "",
        "## Summary",
        _narrative(design["summary"]),
        "",
        "## Requirements",
        _narrative(spec["requirements"]),
        "",
        "## Constraints",
    ]
    for label, field in (
        ("Locked", "locked"),
        ("Discretion", "discretion"),
        ("Escalate", "escalate"),
    ):
        lines.extend(f"- {label}: {_narrative(constraint)}" for constraint in design[field])
    payload = json.dumps(spec, indent=2, ensure_ascii=True, allow_nan=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("`", "\\u0060")
    lines.extend(["", "## Build Evidence", "", _START, "```json", payload, "```", _END, ""])
    return "\n".join(lines)


def _json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON property: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def parse_spec(text: str) -> dict:
    if not isinstance(text, str) or text.count(_START) != 1 or text.count(_END) != 1:
        raise ValueError("Expected exactly one codex-v4 manifest block")
    start = text.index(_START) + len(_START)
    end = text.index(_END)
    if end < start:
        raise ValueError("Manifest end marker precedes start marker")
    match = re.fullmatch(r"\s*```json[ \t]*\r?\n(.*?)\r?\n```[ \t]*\s*", text[start:end], re.DOTALL)
    if match is None:
        raise ValueError("Manifest must contain exactly one fenced json block")
    spec = json.loads(
        match.group(1), object_pairs_hook=_json_object, parse_constant=_invalid_constant
    )
    validate_spec(spec)
    return spec
