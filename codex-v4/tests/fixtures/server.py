import json
import sys


def receive() -> dict:
    return json.loads(sys.stdin.readline())


def emit(message: dict) -> None:
    print(json.dumps(message), flush=True)


initialize = receive()
assert initialize["method"] == "initialize"
assert "jsonrpc" not in initialize
emit({"id": initialize["id"], "result": {"userAgent": "fixture/1"}})
assert receive() == {"method": "initialized"}
request = receive()
mode = sys.argv[1]

if mode == "eof":
    sys.exit(0)
elif mode.startswith("turn-"):
    emit(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "item": {
                    "type": "agentMessage",
                    "phase": "final_answer",
                    "text": '{"result":"ok"}',
                },
            },
        }
    )
    emit({"id": request["id"], "result": {"turn": {"id": "turn-1"}}})
    emit(
        {
            "method": "turn/completed",
            "params": {"threadId": "thread-1", "turn": {"id": "turn-1", "status": mode[5:]}},
        }
    )
elif mode == "malformed":
    print("secret-fixture-value", flush=True)
elif mode == "remote-error":
    emit({"id": request["id"], "error": {"code": -1, "message": "secret-fixture-value"}})
elif mode == "wrong-id":
    emit({"id": 999, "result": {}})
elif mode == "hang":
    sys.stdin.read()
elif mode == "reorder":
    second = receive()
    emit({"id": second["id"], "result": {"method": second["method"]}})
    emit({"id": request["id"], "result": {"method": request["method"]}})
elif mode == "reject-probe":
    emit({"id": request["id"], "result": {"data": [{"id": "local-model"}], "nextCursor": None}})
    probe = receive()
    emit({"id": probe["id"], "error": {"code": -32602, "message": "secret-fixture-value"}})
elif mode != "normal":
    emit({"id": "approval-1", "method": mode, "params": {}})
    rejection = receive()
    assert rejection["id"] == "approval-1"
    assert rejection["error"]["code"] == -32601
    emit({"id": request["id"], "result": {"rejected": True}})
else:
    emit({"method": "notice", "params": {"secret": "secret-fixture-value"}})
    emit({"id": request["id"], "result": {"data": [{"id": "local-model"}], "nextCursor": None}})

sys.stdin.read()
