import asyncio
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest


def client_module():
    assert importlib.util.find_spec("codex_v4") is not None, "Phase 0 client is not implemented"
    return importlib.import_module("codex_v4.app_server")


def command(mode: str = "normal") -> list[str]:
    return [sys.executable, str(Path(__file__).parents[1] / "fixtures/server.py"), mode]


def test_handshake_notifications_and_model_list() -> None:
    module = client_module()

    async def scenario() -> None:
        async with module.AppServer(command(), timeout=2) as server:
            result = await server.request("model/list", {})
            assert result == {"data": [{"id": "local-model"}], "nextCursor": None}
            assert server.notification_methods == {"notice"}
            assert server.server_info == {"userAgent": "fixture/1"}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "method",
    [
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "item/permissions/requestApproval",
        "item/tool/requestUserInput",
        "mcpServer/elicitation/request",
        "unknown/request",
    ],
)
def test_server_requests_are_rejected(method: str) -> None:
    module = client_module()

    async def scenario() -> None:
        async with module.AppServer(command(method), timeout=2) as server:
            assert await server.request("model/list", {}) == {"rejected": True}
            assert server.rejected_requests == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["eof", "malformed", "remote-error", "wrong-id"])
def test_invalid_transport_fails_without_leaking_server_text(mode: str) -> None:
    module = client_module()

    async def scenario() -> None:
        async with module.AppServer(command(mode), timeout=2) as server:
            with pytest.raises(module.ProtocolError) as caught:
                await server.request("model/list", {})
            assert "secret-fixture-value" not in str(caught.value)

    asyncio.run(scenario())


def test_deadline_terminates_owned_child() -> None:
    module = client_module()

    async def scenario() -> None:
        server = module.AppServer(command("hang"), timeout=0.2)
        async with server:
            with pytest.raises(TimeoutError):
                await server.request("model/list", {})
        assert server.process.returncode is not None

    asyncio.run(scenario())


def test_concurrent_responses_correlate_by_id() -> None:
    module = client_module()

    async def scenario() -> None:
        async with module.AppServer(command("reorder"), timeout=2) as server:
            results = await asyncio.gather(
                server.request("first", {}), server.request("second", {})
            )
            assert results == [{"method": "first"}, {"method": "second"}]

    asyncio.run(scenario())


def test_turn_collects_final_message_even_before_start_response() -> None:
    module = client_module()

    async def scenario() -> None:
        async with module.AppServer(command("turn-completed"), timeout=2) as server:
            assert hasattr(server, "run_turn"), "Client cannot execute model turns"
            result = await server.run_turn({"threadId": "thread-1", "input": []}, timeout=2)
            assert result == {"turn_id": "turn-1", "text": '{"result":"ok"}'}

    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_non_successful_turn_cannot_return_an_answer(status: str) -> None:
    module = client_module()

    async def scenario() -> None:
        async with module.AppServer(command(f"turn-{status}"), timeout=2) as server:
            assert hasattr(server, "run_turn"), "Client cannot execute model turns"
            with pytest.raises(module.ProtocolError, match=status):
                await server.run_turn({"threadId": "thread-1", "input": []}, timeout=2)

    asyncio.run(scenario())
