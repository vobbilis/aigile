import asyncio
import importlib
import json

import pytest


class Server:
    def __init__(self, *, wrong_model: bool = False) -> None:
        self.requests: list[dict] = []
        self.turns: list[dict] = []
        self.wrong_model = wrong_model

    async def request(self, method: str, params: dict) -> dict:
        self.requests.append({"method": method, **params})
        return {
            "thread": {"id": f"thread-{len(self.requests)}"},
            "model": "wrong" if self.wrong_model else params["model"],
        }

    async def run_turn(self, params: dict, *, timeout: float) -> dict:
        self.turns.append(params)
        return {"turn_id": f"turn-{len(self.turns)}", "text": json.dumps({"passed": True})}


def test_native_reuses_builder_thread_but_separates_reviewers(tmp_path):
    api = importlib.import_module("codex_v4.native")
    server = Server()
    model = api.NativeModel(
        server,
        tmp_path,
        {"MECHANICAL": "small", "STANDARD": "medium", "REASONING": "large"},
        timeout=30,
    )

    async def scenario():
        schema = {"type": "object"}
        await model.ask("builder", '{"task":{"model_class":"STANDARD"}}', schema, "builder")
        await model.ask("builder", '{"task":{"model_class":"STANDARD"}}', schema, "builder")
        await model.ask("reviewer", "{}", schema, "review-1")

    asyncio.run(scenario())
    assert len(server.requests) == 2
    assert server.turns[0]["threadId"] == server.turns[1]["threadId"]
    assert server.turns[2]["threadId"] != server.turns[0]["threadId"]
    assert server.requests[0]["model"] == "medium"
    assert server.requests[1]["model"] == "large"
    assert all(item["permissions"] == "codex-v4-worker" for item in server.requests)
    assert all(item["allowProviderModelFallback"] is False for item in server.requests)
    assert all("sandbox" not in item for item in server.requests)
    assert all("outputSchema" in item for item in server.turns)
    assert len(model.events) == 3


def test_native_rejects_wrong_reported_model(tmp_path):
    api = importlib.import_module("codex_v4.native")
    model = api.NativeModel(
        Server(wrong_model=True),
        tmp_path,
        {"MECHANICAL": "small", "STANDARD": "medium", "REASONING": "large"},
        timeout=30,
    )
    with pytest.raises(ValueError, match="model"):
        asyncio.run(model.ask("planner", "{}", {}, "planner"))
