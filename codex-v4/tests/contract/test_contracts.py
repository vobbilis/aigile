import importlib
import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

START = "<!-- codex-v4-manifest:start -->"
END = "<!-- codex-v4-manifest:end -->"
INVALID = (ValueError, ValidationError)


def sample_spec() -> dict:
    return {
        "schema": "codex-v4/spec/2",
        "spec_id": "contract-example",
        "title": "Contract example",
        "requirements": "Implement a validated contract.",
        "repo_digest": "a" * 64,
        "planning": {"complexity": "simple", "panel": "auto"},
        "design": {
            "summary": "Validate before executing.",
            "locked": ["Keep the public API stable."],
            "discretion": ["Choose internal helpers."],
            "escalate": ["Changes to the public API."],
        },
        "context_files": [{"path": "README.md", "sha256": "b" * 64}],
        "agents": [{"id": "agent-1", "model_class": "STANDARD", "tasks": ["task-1"]}],
        "tasks": [
            {
                "id": "task-1",
                "title": "Implement contracts",
                "instructions": "Validate the specification.",
                "assigned_agent": "agent-1",
                "model_class": "STANDARD",
                "depends_on": [],
                "write_scope": ["src/contracts.py"],
                "acceptance": ["Invalid specifications fail."],
                "failure_surface": [{"id": "failure-1", "condition": "Invalid input accepted"}],
                "test_promises": [
                    {
                        "id": "promise-1",
                        "identity": "tests/test_contracts.py::test_invalid",
                        "command_id": "unit-tests",
                        "covers_failure_ids": ["failure-1"],
                    }
                ],
            }
        ],
        "validation_commands": [
            {
                "id": "unit-tests",
                "argv": ["{python}", "-m", "pytest", "tests/test_contracts.py"],
                "cwd": ".",
                "timeout_seconds": 120,
                "adapter": "pytest-junit",
            }
        ],
    }


def _api():
    return importlib.import_module("codex_v4.contracts")


def _manifest(spec: dict) -> str:
    return f"{START}\n```json\n{json.dumps(spec)}\n```\n{END}"


def _task_pair() -> dict:
    spec = sample_spec()
    second = deepcopy(spec["tasks"][0])
    second.update(id="task-2", write_scope=["src/second.py"])
    second["failure_surface"][0]["id"] = "failure-2"
    second["test_promises"][0].update(id="promise-2", covers_failure_ids=["failure-2"])
    spec["tasks"].append(second)
    spec["agents"][0]["tasks"].append("task-2")
    return spec


def test_roundtrip_and_public_schema():
    api = _api()
    spec = sample_spec()
    original = deepcopy(spec)
    assert isinstance(api.SPEC_SCHEMA, dict)
    Draft202012Validator.check_schema(api.SPEC_SCHEMA)
    assert api.validate_spec(spec) is None
    rendered = api.render_spec(spec)
    assert rendered.count(START) == rendered.count(END) == 1
    assert "```json\n" in rendered
    assert "## Build Evidence" in rendered
    narrative = rendered.split(START)[0]
    for text in [spec["design"]["summary"], *spec["design"]["locked"]]:
        assert text in narrative
    assert api.parse_spec(rendered) == spec
    assert spec == original


def test_sample_spec_is_independent():
    first = sample_spec()
    first["tasks"][0]["id"] = "changed"
    assert sample_spec()["tasks"][0]["id"] == "task-1"


OBJECT_PATHS = [
    (),
    ("planning",),
    ("design",),
    ("context_files", 0),
    ("agents", 0),
    ("tasks", 0),
    ("tasks", 0, "failure_surface", 0),
    ("tasks", 0, "test_promises", 0),
    ("validation_commands", 0),
]


def _at(spec, path):
    for key in path:
        spec = spec[key]
    return spec


@pytest.mark.parametrize("path", OBJECT_PATHS)
def test_every_property_is_required_and_extra_properties_fail(path):
    api = _api()
    original = sample_spec()
    for key in _at(original, path):
        spec = deepcopy(original)
        del _at(spec, path)[key]
        with pytest.raises(ValidationError):
            api.validate_spec(spec)
    spec = deepcopy(original)
    _at(spec, path)["unexpected"] = True
    with pytest.raises(ValidationError):
        api.validate_spec(spec)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), "codex-v4/spec/1"),
        (("spec_id",), "Not a Slug"),
        (("spec_id",), "slug\n"),
        (("repo_digest",), "not-a-digest"),
        (("repo_digest",), "g" * 64),
        (("repo_digest",), "a" * 64 + "\n"),
        (("context_files", 0, "sha256"), "a" * 63),
        (("planning", "complexity"), "huge"),
        (("planning", "panel"), True),
        (("design", "locked"), []),
        (("design", "discretion"), [5]),
        (("tasks", 0, "write_scope"), []),
        (("tasks", 0, "acceptance"), []),
        (("tasks", 0, "test_promises"), []),
        (("tasks", 0, "model_class"), "SMALL"),
        (("agents", 0, "model_class"), "SMALL"),
        (("validation_commands",), []),
        (("validation_commands", 0, "argv"), []),
        (("validation_commands", 0, "argv"), [12]),
        (("validation_commands", 0, "timeout_seconds"), 0),
        (("validation_commands", 0, "timeout_seconds"), 901),
        (("validation_commands", 0, "timeout_seconds"), True),
        (("validation_commands", 0, "timeout_seconds"), 1.5),
        (("validation_commands", 0, "adapter"), "shell"),
    ],
)
def test_invalid_schema_values(path, value):
    api = _api()
    spec = sample_spec()
    _at(spec, path[:-1])[path[-1]] = value
    with pytest.raises(INVALID):
        api.validate_spec(spec)


@pytest.mark.parametrize("value", [None, [], "spec", 42])
def test_invalid_root(value):
    with pytest.raises(INVALID):
        _api().validate_spec(value)


@pytest.mark.parametrize("path", [("agents",), ("tasks",), ("validation_commands",)])
def test_duplicate_top_level_ids(path):
    api = _api()
    spec = sample_spec()
    entries = _at(spec, path)
    entries.append(deepcopy(entries[0]))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        api.validate_spec(spec)


@pytest.mark.parametrize("field", ["failure_surface", "test_promises"])
@pytest.mark.parametrize("cross_task", [False, True])
def test_duplicate_nested_ids(field, cross_task):
    api = _api()
    spec = _task_pair()
    first = spec["tasks"][0][field]
    if cross_task:
        spec["tasks"][1][field][0]["id"] = first[0]["id"]
    else:
        first.append(deepcopy(first[0]))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        api.validate_spec(spec)


@pytest.mark.parametrize("dependencies", [["missing"], ["task-1"], ["task-2", "task-2"]])
def test_invalid_dependencies(dependencies):
    api = _api()
    spec = _task_pair()
    spec["tasks"][0]["depends_on"] = dependencies
    with pytest.raises(ValueError):
        api.validate_spec(spec)


def test_dependency_cycle():
    api = _api()
    spec = _task_pair()
    spec["tasks"][0]["depends_on"] = ["task-2"]
    spec["tasks"][1]["depends_on"] = ["task-1"]
    with pytest.raises(ValueError, match="[Cc]ycle"):
        api.validate_spec(spec)


@pytest.mark.parametrize("claimed_tasks", [[], ["missing"], ["task-1", "task-1"]])
def test_agent_task_list_must_match_exactly(claimed_tasks):
    api = _api()
    spec = sample_spec()
    spec["agents"][0]["tasks"] = claimed_tasks
    with pytest.raises(ValueError):
        api.validate_spec(spec)


def test_unknown_assigned_agent():
    api = _api()
    spec = sample_spec()
    spec["tasks"][0]["assigned_agent"] = "missing"
    with pytest.raises(ValueError):
        api.validate_spec(spec)


def test_multiple_agents_cannot_claim_task():
    api = _api()
    spec = sample_spec()
    second = deepcopy(spec["agents"][0])
    second["id"] = "agent-2"
    spec["agents"].append(second)
    with pytest.raises(ValueError):
        api.validate_spec(spec)


def test_agent_class_must_be_homogeneous_and_match_tasks():
    api = _api()
    spec = _task_pair()
    spec["tasks"][1]["model_class"] = "REASONING"
    with pytest.raises(ValueError):
        api.validate_spec(spec)


@pytest.mark.parametrize("model_class", ["MECHANICAL", "STANDARD", "REASONING"])
def test_all_model_classes_and_no_reasoning_quota(model_class):
    api = _api()
    spec = sample_spec()
    spec["agents"][0]["model_class"] = model_class
    spec["tasks"][0]["model_class"] = model_class
    assert api.validate_spec(spec) is None


@pytest.mark.parametrize("covered", [[], ["unknown"], ["failure-2"]])
def test_failures_require_same_task_coverage(covered):
    api = _api()
    spec = _task_pair()
    spec["tasks"][0]["test_promises"][0]["covers_failure_ids"] = covered
    with pytest.raises(ValueError):
        api.validate_spec(spec)


def test_no_failures_needs_no_coverage_quota():
    api = _api()
    spec = sample_spec()
    spec["tasks"][0]["failure_surface"] = []
    spec["tasks"][0]["test_promises"][0]["covers_failure_ids"] = []
    assert api.validate_spec(spec) is None


def test_unknown_command_reference():
    api = _api()
    spec = sample_spec()
    spec["tasks"][0]["test_promises"][0]["command_id"] = "missing"
    with pytest.raises(ValueError):
        api.validate_spec(spec)


@pytest.mark.parametrize("ordered", [False, True])
def test_exact_path_overlap_requires_dependency_order(ordered):
    api = _api()
    spec = _task_pair()
    spec["tasks"][1]["write_scope"] = spec["tasks"][0]["write_scope"][:]
    if ordered:
        spec["tasks"][0]["depends_on"] = ["task-2"]
        assert api.validate_spec(spec) is None
    else:
        with pytest.raises(ValueError, match="[Oo]verlap"):
            api.validate_spec(spec)


def test_transitive_overlap_is_ordered():
    api = _api()
    spec = _task_pair()
    third = deepcopy(spec["tasks"][0])
    third.update(id="task-3", depends_on=["task-2"], failure_surface=[])
    third["test_promises"][0].update(id="promise-3", covers_failure_ids=[])
    spec["tasks"][1]["depends_on"] = ["task-1"]
    spec["tasks"].append(third)
    spec["agents"][0]["tasks"].append("task-3")
    assert api.validate_spec(spec) is None


UNSAFE_PATHS = [
    "/tmp/file.py",
    "../file.py",
    "src/../file.py",
    "src\\file.py",
    "C:/file.py",
    "//host/file.py",
    "src/.git/config",
    ".claude/settings.json",
    ".codex/config.toml",
    ".codex-v4/state.json",
    ".env",
    "config/.env.production",
    "src/*.py",
    "src/file?.py",
    "src/[ab].py",
    "src/{first,second}.py",
    "src/\x00file.py",
    "~/file.py",
    "",
]


@pytest.mark.parametrize("path", UNSAFE_PATHS)
@pytest.mark.parametrize("surface", ["write", "context", "cwd"])
def test_unsafe_paths(surface, path):
    api = _api()
    spec = sample_spec()
    if surface == "write":
        spec["tasks"][0]["write_scope"] = [path]
    elif surface == "context":
        spec["context_files"][0]["path"] = path
    else:
        spec["validation_commands"][0]["cwd"] = path
    with pytest.raises(INVALID):
        api.validate_spec(spec)


@pytest.mark.parametrize(
    "path", [".", "src/", "src//file.py", "./src/file.py", "codex-v4/src/codex_v4/cli.py"]
)
def test_writes_are_exact_canonical_non_controller_files(path):
    api = _api()
    spec = sample_spec()
    spec["tasks"][0]["write_scope"] = [path]
    with pytest.raises(ValueError):
        api.validate_spec(spec)


def test_controller_context_is_readable_and_cwd_can_be_relative():
    api = _api()
    spec = sample_spec()
    spec["context_files"][0]["path"] = "codex-v4/src/codex_v4/cli.py"
    spec["validation_commands"][0]["cwd"] = "packages/example"
    assert api.validate_spec(spec) is None


@pytest.mark.parametrize(
    "program",
    ["python", "python3", "pytest", "ruff", "npm", "npx", "yarn", "cargo", "go", "{python}"],
)
def test_allowlisted_command_programs(program):
    api = _api()
    spec = sample_spec()
    spec["validation_commands"][0].update(adapter="command", argv=[program, "--version"])
    spec["tasks"][0]["test_promises"][0]["identity"] = "unit-tests"
    assert api.validate_spec(spec) is None


@pytest.mark.parametrize(
    "argv",
    [
        ["bash", "-c", "true"],
        ["sh", "-c", "true"],
        ["env", "pytest"],
        ["node", "-e", "true"],
        ["python", "-c", "print(1)"],
        ["python3", "-cprint(1)"],
        ["{python}", "-Ic", "print(1)"],
        ["/usr/bin/python3", "-u", "-c", "print(1)"],
        ["npx", "-c", "echo hello"],
        ["npm", "exec", "--call=echo hello"],
    ],
)
def test_unsafe_commands(argv):
    api = _api()
    spec = sample_spec()
    spec["validation_commands"][0].update(adapter="command", argv=argv)
    spec["tasks"][0]["test_promises"][0]["identity"] = "unit-tests"
    with pytest.raises(ValueError):
        api.validate_spec(spec)


@pytest.mark.parametrize(
    "argv",
    [
        ["pytest"],
        ["/repo/venv/bin/pytest", "-q"],
        ["python", "-m", "pytest"],
        ["/repo/venv/bin/python3", "-I", "-m", "pytest", "-c", "pytest.ini"],
        ["{python}", "-m", "pytest"],
    ],
)
def test_pytest_adapter_accepts_pytest_invocations(argv):
    api = _api()
    spec = sample_spec()
    spec["validation_commands"][0]["argv"] = argv
    assert api.validate_spec(spec) is None


@pytest.mark.parametrize(
    "argv", [["ruff", "check"], ["python", "script.py", "-m", "pytest"], ["python", "-m", "other"]]
)
def test_pytest_adapter_rejects_other_invocations(argv):
    api = _api()
    spec = sample_spec()
    spec["validation_commands"][0]["argv"] = argv
    with pytest.raises(ValueError):
        api.validate_spec(spec)


@pytest.mark.parametrize("identity", ["", " ", "\n"])
def test_pytest_identity_cannot_be_blank(identity):
    api = _api()
    spec = sample_spec()
    spec["tasks"][0]["test_promises"][0]["identity"] = identity
    with pytest.raises(INVALID):
        api.validate_spec(spec)


def test_command_identity_must_equal_command_id():
    api = _api()
    spec = sample_spec()
    spec["validation_commands"][0].update(adapter="command", argv=["ruff", "check", "."])
    with pytest.raises(ValueError):
        api.validate_spec(spec)


@pytest.mark.parametrize("timeout", [1, 900])
def test_timeout_boundaries(timeout):
    api = _api()
    spec = sample_spec()
    spec["validation_commands"][0]["timeout_seconds"] = timeout
    assert api.validate_spec(spec) is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "```json\n{}\n```",
        START,
        END,
        END + START,
        START + "\n{}\n" + END,
        START + "\n```python\n{}\n```\n" + END,
        START + "\n```json\n{bad}\n```\n" + END,
        START + "\n```json\n[]\n```\n" + END,
        START + "\n```json\n{}\n```\n```json\n{}\n```\n" + END,
        START + "\n```json\n{}\n```\n" + END,
    ],
)
def test_malformed_manifest(text):
    with pytest.raises(INVALID):
        _api().parse_spec(text)


@pytest.mark.parametrize("extra", [START, END, "both"])
def test_extra_manifest_markers_fail(extra):
    api = _api()
    text = _manifest(sample_spec())
    text += text if extra == "both" else extra
    with pytest.raises(ValueError):
        api.parse_spec(text)


def test_duplicate_json_keys_fail():
    api = _api()
    text = _manifest(sample_spec()).replace('"title":', '"title": "first", "title":')
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        api.parse_spec(text)


def test_parse_validates_semantics_and_render_rejects_invalid_specs():
    api = _api()
    spec = sample_spec()
    spec["tasks"][0]["depends_on"] = ["missing"]
    with pytest.raises(ValueError):
        api.parse_spec(_manifest(spec))
    with pytest.raises(ValueError):
        api.render_spec(spec)


def test_unicode_and_marker_strings_roundtrip_without_extra_blocks():
    api = _api()
    spec = sample_spec()
    spec["title"] = "Contract \u65e5\u672c\u8a9e"
    spec["design"]["summary"] = f"Literal {START}\n```json\n{{}}\n```\n{END}"
    spec["design"]["locked"] = [START, END]
    rendered = api.render_spec(spec)
    assert rendered.count(START) == rendered.count(END) == 1
    assert api.parse_spec(rendered) == spec


def test_manifest_accepts_surrounding_narrative_and_crlf():
    api = _api()
    text = "# Reviewed specification\n\n" + _manifest(sample_spec()) + "\nEvidence follows."
    assert api.parse_spec(text.replace("\n", "\r\n")) == sample_spec()
