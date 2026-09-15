from pathlib import Path


def sandbox_blockers(schema: dict) -> list[str]:
    profile_type = schema.get("properties", {}).get("permissionProfile", {}).get("type", [])
    if profile_type == "string" or isinstance(profile_type, list) and "string" in profile_type:
        return []
    variants = schema.get("definitions", {}).get("SandboxPolicy", {}).get("oneOf", [])
    if not variants:
        return ["SandboxPolicy schema unavailable"]
    policies = {
        name: variant.get("properties", {})
        for variant in variants
        for name in variant.get("properties", {}).get("type", {}).get("enum", [])
    }
    return [
        f"{policy}.{field} unsupported"
        for policy, field in [("readOnly", "access"), ("workspaceWrite", "readOnlyAccess")]
        if field not in policies.get(policy, {})
    ]


def read_profile_args() -> list[str]:
    return [
        "-c",
        'permissions.codex-v4-read-probe.filesystem={ ":root" = "deny", '
        '":minimal" = "read", ":workspace_roots" = "read" }',
        "-c",
        "permissions.codex-v4-read-probe.network.enabled=false",
    ]


def read_probe_params(root: Path, sentinel: Path) -> dict:
    return {
        "command": ["/bin/cat", str(sentinel)],
        "cwd": str(root),
        "timeoutMs": 3000,
        "outputBytesCap": 256,
        "permissionProfile": "codex-v4-read-probe",
    }
