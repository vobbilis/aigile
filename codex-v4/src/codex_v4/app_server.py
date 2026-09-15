import asyncio
import json
from types import TracebackType
from typing import Self

import sentry_sdk


class ProtocolError(RuntimeError):
    pass


class AppServer:
    def __init__(
        self,
        command: list[str],
        *,
        timeout: float = 10,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.command = command
        self.timeout = timeout
        self.cwd = cwd
        self.env = env
        self.process: asyncio.subprocess.Process | None = None
        self.server_info: dict = {}
        self.notification_methods: set[str] = set()
        self.rejected_requests = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._sequence = 0
        self._reader: asyncio.Task | None = None
        self._failure: ProtocolError | None = None
        self._turn_events: dict[str, asyncio.Queue] = {}

    async def __aenter__(self) -> Self:
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=self.cwd,
            env=self.env,
            limit=4 * 1024 * 1024,
        )
        self._reader = asyncio.create_task(self._read_messages())
        initialized = False
        try:
            self.server_info = await self.request(
                "initialize",
                {
                    "clientInfo": {"name": "codex_v4_probe", "version": "0.0.1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            await self._send({"method": "initialized"})
            initialized = True
        finally:
            if not initialized:
                await self.close()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def _send(self, message: dict) -> None:
        if self.process is None or self.process.stdin is None:
            raise ProtocolError("App Server is not running")
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        await self.process.stdin.drain()

    async def request(self, method: str, params: dict) -> dict:
        if self._failure is not None:
            raise self._failure
        self._sequence += 1
        request_id = self._sequence
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            async with asyncio.timeout(self.timeout):
                await self._send({"id": request_id, "method": method, "params": params})
                return await future
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()

    async def _read_messages(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            while raw := await self.process.stdout.readline():
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ProtocolError("Invalid protocol envelope")
                if "method" in message:
                    if not isinstance(message["method"], str):
                        raise ProtocolError("Invalid protocol method")
                    if "id" in message:
                        self.rejected_requests += 1
                        await self._send(
                            {
                                "id": message["id"],
                                "error": {"code": -32601, "message": "Unattended probe denied"},
                            }
                        )
                    else:
                        self.notification_methods.add(message["method"])
                        params = message.get("params", {})
                        queue = self._turn_events.get(params.get("threadId"))
                        if queue is not None and message["method"] in {
                            "item/completed",
                            "turn/completed",
                        }:
                            queue.put_nowait(message)
                    continue
                request_id = message.get("id")
                if type(request_id) is not int or request_id not in self._pending:
                    raise ProtocolError("Uncorrelated App Server response")
                future = self._pending[request_id]
                if future.done():
                    raise ProtocolError("Duplicate or late App Server response")
                if "error" in message:
                    future.set_exception(ProtocolError("App Server rejected request"))
                elif isinstance(message.get("result"), dict):
                    future.set_result(message["result"])
                else:
                    raise ProtocolError("Invalid App Server result")
            self._fail_pending(ProtocolError("App Server closed its output"))
        except Exception:
            failure = ProtocolError("App Server protocol or transport failure")
            sentry_sdk.capture_exception(failure)
            self._fail_pending(failure)

    def _fail_pending(self, failure: ProtocolError) -> None:
        self._failure = failure
        for queue in self._turn_events.values():
            if not queue.full():
                queue.put_nowait(failure)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(failure)

    async def run_turn(self, params: dict, *, timeout: float) -> dict:
        thread_id = params["threadId"]
        if thread_id in self._turn_events:
            raise ProtocolError("A turn is already active on this thread")
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._turn_events[thread_id] = queue
        try:
            async with asyncio.timeout(timeout):
                started = await self.request("turn/start", params)
                turn_id = started["turn"]["id"]
                final_text = None
                while True:
                    event = await queue.get()
                    if isinstance(event, ProtocolError):
                        raise event
                    payload = event["params"]
                    if event["method"] == "item/completed":
                        if payload.get("turnId") != turn_id:
                            continue
                        item = payload["item"]
                        if item.get("type") == "agentMessage" and item.get("phase") in {
                            None,
                            "final_answer",
                        }:
                            final_text = item.get("text")
                    elif payload["turn"]["id"] == turn_id:
                        status = payload["turn"]["status"]
                        if status != "completed":
                            raise ProtocolError(f"Model turn {status}")
                        if not isinstance(final_text, str) or not final_text.strip():
                            raise ProtocolError("Model turn completed without a final answer")
                        return {"turn_id": turn_id, "text": final_text}
        finally:
            self._turn_events.pop(thread_id, None)

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
        self._fail_pending(ProtocolError("App Server client closed"))
        if self.process is not None and self.process.returncode is None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            waiter = asyncio.create_task(self.process.wait())
            done, _ = await asyncio.wait({waiter}, timeout=1)
            if not done and self.process.returncode is None:
                self.process.terminate()
                done, _ = await asyncio.wait({waiter}, timeout=1)
            if not done and self.process.returncode is None:
                self.process.kill()
            await waiter
