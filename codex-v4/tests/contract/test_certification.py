import hashlib
import importlib
import json
from pathlib import Path


def certification_module():
    assert (
        importlib.util.find_spec("codex_v4.certification") is not None
    ), "Certification gate missing"
    return importlib.import_module("codex_v4.certification")


def sandbox_schema() -> dict:
    return {
        "definitions": {
            "SandboxPolicy": {
                "oneOf": [
                    {"properties": {"type": {"enum": ["readOnly"]}, "networkAccess": {}}},
                    {"properties": {"type": {"enum": ["workspaceWrite"]}, "writableRoots": {}}},
                ]
            }
        }
    }


def test_missing_restricted_reads_block_certification() -> None:
    blockers = certification_module().sandbox_blockers(sandbox_schema())
    assert blockers == ["readOnly.access unsupported", "workspaceWrite.readOnlyAccess unsupported"]


def test_named_permission_profile_is_supported_without_legacy_fields() -> None:
    schema = sandbox_schema()
    schema["properties"] = {"permissionProfile": {"type": ["string", "null"]}}
    assert certification_module().sandbox_blockers(schema) == []


def test_unknown_schema_shape_fails_closed() -> None:
    assert certification_module().sandbox_blockers({}) == ["SandboxPolicy schema unavailable"]


def test_probe_only_reads_synthetic_paths_with_network_disabled(tmp_path) -> None:
    params = certification_module().read_probe_params(tmp_path, tmp_path.parent / "sentinel")
    assert params["command"] == ["/bin/cat", str(tmp_path.parent / "sentinel")]
    assert params["timeoutMs"] == 3000
    assert params["permissionProfile"] == "codex-v4-read-probe"
    assert "sandboxPolicy" not in params


def test_installed_01441_schema_supports_named_permissions() -> None:
    path = Path(__file__).parents[1] / "fixtures/CommandExecParams-0.144.1.json"
    assert path.is_file(), "Generated installed-binary schema fixture missing"
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == (
        "d67efca42dd7671c3102b6bb67ca2cd28aad2767538e182a1d7014d1d4fdcc65"
    )
    assert certification_module().sandbox_blockers(json.loads(data)) == []


def test_probe_profile_has_no_global_read_or_write_grants() -> None:
    args = certification_module().read_profile_args()
    assert 'permissions.codex-v4-read-probe.filesystem={ ":root" = "deny", ' in args[1]
    assert '":minimal" = "read"' in args[1]
    assert '":workspace_roots" = "read"' in args[1]
    assert "permissions.codex-v4-read-probe.network.enabled=false" in args
    assert "write" not in " ".join(args)
