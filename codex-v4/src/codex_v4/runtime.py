import json
import re
from urllib.parse import urlsplit

EXPECTED_MODELS = (
    "openai.gpt-5.6-sol",
    "openai.gpt-5.6-terra",
    "openai.gpt-5.6-luna",
    "deepseek-v4-flash",
    "glm-5.3-flash",
)
PROFILE_FIELDS = {
    "model",
    "model_provider",
    "model_catalog_json",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "web_search",
}
PROVIDER_FIELDS = {
    "name",
    "base_url",
    "wire_api",
    "supports_websockets",
    "request_max_retries",
    "stream_max_retries",
    "stream_idle_timeout_ms",
}


def launch_command(profile: dict, mcp_names: list[str]) -> list[str]:
    provider_name = profile["model_provider"]
    identifiers = [provider_name, *mcp_names]
    if not all(isinstance(name, str) and re.fullmatch(r"[\w-]+", name) for name in identifiers):
        raise ValueError("Invalid configuration identifier")
    provider = profile["model_providers"][provider_name]
    if set(provider) - PROVIDER_FIELDS:
        raise ValueError("Unsupported provider configuration; credentials cannot enter argv")
    endpoint = urlsplit(provider["base_url"])
    if (
        endpoint.scheme != "http"
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
        or provider.get("wire_api") != "responses"
    ):
        raise ValueError("Certification requires a local, secret-free Responses bridge")
    command = ["codex", "app-server", "--stdio"]
    overrides = {key: value for key, value in profile.items() if key in PROFILE_FIELDS}
    overrides.update(
        {f"model_providers.{provider_name}.{key}": value for key, value in provider.items()}
    )
    overrides.update({f"mcp_servers.{name}.enabled": False for name in mcp_names})
    overrides.update(
        {
            "features.plugins": False,
            "features.multi_agent": False,
            "approval_policy": "never",
            "sandbox_mode": "read-only",
        }
    )
    for key, value in sorted(overrides.items()):
        if not isinstance(value, str | bool | int):
            raise ValueError("Unsupported configuration value")
        command.extend(["-c", f"{key}={json.dumps(value)}"])
    return command


def assess_models(observed: list[str], expected: list[str]) -> dict:
    missing = sorted(set(expected) - set(observed))
    return {
        "discovery": "FAILED" if missing else "PASSED",
        "observed_models": sorted(set(observed)),
        "missing_models": missing,
        "certified": False,
        "pending": [
            "restricted sandbox enforcement",
            "exact-output and function-tool canaries",
            "per-request physical-route attestation",
            "mixed and single-backend execution",
            "failure and lifecycle certification",
        ],
    }
