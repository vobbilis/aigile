import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3] / "codex-v4" / "native"
ROLES = (
    "v4-builder",
    "v4-validator",
    "v4-reviewer",
    "v4-spec-updater",
    "v4-design-updater",
    "v4-auditor",
    "v4-plan-critic",
)


@pytest.mark.parametrize("name", ["plan-to-build-v4", "build-v4"])
def test_native_skill_is_discoverable_and_does_not_require_controller(name):
    text = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text()
    assert text.startswith(f"---\nname: {name}\n")
    assert "description:" in text.split("---", 2)[1]
    assert len(text.splitlines()) < 500
    assert "codex_v4" not in text
    assert "app-server" not in text


@pytest.mark.parametrize("role", ROLES)
def test_native_roles_use_supported_standalone_config(role):
    config = tomllib.loads((ROOT / ".codex" / "agents" / f"{role}.toml").read_text())
    assert config["name"] == role
    assert config["description"]
    assert config["developer_instructions"]
    assert "model" not in config
    assert "model_reasoning_effort" not in config
    if role in {"v4-validator", "v4-reviewer", "v4-auditor", "v4-plan-critic"}:
        assert config["sandbox_mode"] == "read-only"


def test_build_keeps_two_reviews_and_post_build_roles_explicit():
    text = (ROOT / ".agents/skills/build-v4/SKILL.md").read_text()
    for step in (
        "reviewer-alpha",
        "reviewer-beta",
        "v4-validator",
        "v4-spec-updater",
        "v4-design-updater",
        "v4-auditor",
        "send_input",
        "wait",
    ):
        assert step in text
    assert "two repair cycles" in text
    assert "NEEDS_DECISION" in text


def test_plan_retains_four_critics_and_failure_coverage():
    text = (ROOT / ".agents/skills/plan-to-build-v4/SKILL.md").read_text()
    for term in (
        "failure-surface",
        "grounding",
        "omissions",
        "routing",
        "Test Promises",
        "Design Grounding",
        "Model Routing",
        "Build Evidence",
    ):
        assert term in text


def test_native_roles_are_explicitly_registered_for_codex_0144():
    config_path = ROOT / ".codex" / "config.toml"
    config = tomllib.loads(config_path.read_text())
    assert config["features"]["multi_agent"] is True
    assert config["features"]["multi_agent_v2"] is False
    for role in ROLES:
        registration = config["agents"][role]
        role_path = config_path.parent / registration["config_file"]
        assert role_path == ROOT / ".codex" / "agents" / f"{role}.toml"
        assert registration["description"]


@pytest.mark.parametrize("name", ["plan-to-build-v4", "build-v4"])
def test_custom_roles_require_fresh_context_and_no_silent_substitution(name):
    text = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text()
    assert "fork_context=false" in text
    assert "Do not substitute default agents" in text


def test_build_releases_finished_agents_before_final_audit():
    text = (ROOT / ".agents/skills/build-v4/SKILL.md").read_text()
    assert "Before spawning the auditor, close finished" in text


@pytest.mark.parametrize("name", ["plan-to-build-v4", "build-v4"])
def test_empty_invocation_returns_usage_before_any_work(name):
    text = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text()
    help_section = text.split("## Invocation And Help", 1)[1].split("\n## ", 1)[0]
    for required in ("no arguments", "help", "-h", "--help", "STOP", "Do not use tools"):
        assert required in help_section
    assert f"${name}" in help_section
    assert text.index("## Invocation And Help") < text.index(
        "## Preflight" if name == "build-v4" else "## Inputs And Boundaries"
    )
