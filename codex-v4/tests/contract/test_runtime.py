import importlib

import pytest


def runtime_module():
    assert importlib.util.find_spec("codex_v4.runtime") is not None, "Runtime launcher missing"
    return importlib.import_module("codex_v4.runtime")


def profile() -> dict:
    return {
        "model": "local-model",
        "model_provider": "local",
        "model_catalog_json": "/tmp/catalog.json",
        "model_providers": {
            "local": {
                "name": "Local",
                "base_url": "http://127.0.0.1:4113/v1",
                "wire_api": "responses",
            }
        },
    }


def test_launcher_uses_explicit_overrides_and_disables_mcp() -> None:
    command = runtime_module().launch_command(profile(), ["node_repl", "chrome-devtools"])
    assert command[:3] == ["codex", "app-server", "--stdio"]
    assert "-p" not in command
    assert "mcp_servers.node_repl.enabled=false" in command
    assert "mcp_servers.chrome-devtools.enabled=false" in command
    assert 'model_provider="local"' in command
    assert "features.multi_agent=false" in command
    assert "features.plugins=false" in command


@pytest.mark.parametrize("field", ["api_key", "http_headers", "env_key"])
def test_launcher_rejects_credential_configuration(field: str) -> None:
    config = profile()
    config["model_providers"]["local"][field] = "secret-fixture-value"
    with pytest.raises(ValueError) as caught:
        runtime_module().launch_command(config, [])
    assert "secret-fixture-value" not in str(caught.value)


@pytest.mark.parametrize(
    "endpoint", ["https://remote.example/v1", "http://user:secret@127.0.0.1/v1"]
)
def test_launcher_requires_local_secret_free_bridge(endpoint: str) -> None:
    config = profile()
    config["model_providers"]["local"]["base_url"] = endpoint
    with pytest.raises(ValueError):
        runtime_module().launch_command(config, [])


def test_launcher_rejects_invalid_config_identifiers() -> None:
    with pytest.raises(ValueError):
        runtime_module().launch_command(profile(), ['unsafe"=true'])


def test_missing_models_are_not_certified() -> None:
    result = runtime_module().assess_models(["local"], ["local", "frontier"])
    assert result["missing_models"] == ["frontier"]
    assert result["discovery"] == "FAILED"
    assert result["certified"] is False


def test_catalog_discovery_is_not_runtime_certification() -> None:
    result = runtime_module().assess_models(["local", "frontier"], ["local", "frontier"])
    assert result["discovery"] == "PASSED"
    assert result["certified"] is False
