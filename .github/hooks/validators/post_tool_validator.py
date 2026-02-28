#!/usr/bin/env python3
"""
PostToolUse validator for metrics-dashboard — Copilot format.

Input schema (Copilot):
  {
    "timestamp":  int,
    "cwd":        "/path/to/workspace",
    "toolName":   "editFiles" | "createFile" | "runCommand" | ...,
    "toolArgs":   "{...json string...}",
    "toolResult": "...",
    "sessionId":  "..."
  }

Output schema (Copilot):
  { "continue": true }
  OR
  {
    "decision":   "block",
    "reason":     "short reason",
    "hookSpecificOutput": {
      "hookEventName":   "postToolUse",
      "additionalContext": "message injected into agent context"
    }
  }

NOTE: Copilot hooks use "toolName" (not "tool_name") and
      "toolArgs" (not "tool_input"). The event name is
      "postToolUse" (camelCase), not "PostToolUse".
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Copilot tool names that write/modify files
FILE_WRITE_TOOLS = {
    "editFiles",
    "createFile",
    "writeFile",
    "edit",
    "write",
    "str_replace",
    "insert",
}


def read_input() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def is_file_write(tool_name: str) -> bool:
    # If tool name is empty/unknown, be conservative and run validation
    if not tool_name:
        return True
    return tool_name in FILE_WRITE_TOOLS


def get_changed_file(tool_args_str: str) -> str | None:
    """Extract file path from toolArgs JSON string if present."""
    try:
        args = json.loads(tool_args_str) if tool_args_str else {}
        return (
            args.get("path")
            or args.get("file_path")
            or args.get("filename")
            # editFiles passes a list; take first entry
            or (args.get("files", [None])[0] if isinstance(args.get("files"), list) else None)
        )
    except Exception:
        return None


def run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def block(reason: str, context: str) -> None:
    print(json.dumps({
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "postToolUse",
            "additionalContext": context,
        }
    }))
    sys.exit(1)


def allow() -> None:
    print(json.dumps({"continue": True}))


def main() -> None:
    data = read_input()
    cwd = Path(data.get("cwd", os.getcwd()))

    tool_name = data.get("toolName", "")
    tool_args = data.get("toolArgs", "")

    if not is_file_write(tool_name):
        allow()
        return

    changed_file = get_changed_file(tool_args)

    # ── Python file changed → ruff lint ──────────────────────────────────────
    if changed_file and changed_file.endswith(".py"):
        backend_dir = cwd / "backend"
        if backend_dir.exists():
            ok, out = run(["ruff", "check", changed_file], backend_dir)
            if not ok:
                block(
                    reason="Python lint failed (ruff)",
                    context=(
                        f"🛑 ruff check failed on {changed_file}:\n\n{out}\n\n"
                        "Fix the lint errors before continuing."
                    )
                )

    # ── TypeScript / TSX file changed → tsc --noEmit ─────────────────────────
    elif changed_file and (changed_file.endswith(".ts") or changed_file.endswith(".tsx")):
        frontend_dir = cwd / "frontend"
        if frontend_dir.exists():
            ok, out = run(["npm", "run", "typecheck"], frontend_dir)
            if not ok:
                block(
                    reason="TypeScript typecheck failed",
                    context=(
                        f"🛑 tsc --noEmit failed after editing {changed_file}:\n\n{out}\n\n"
                        "Fix the type errors before continuing."
                    )
                )

    allow()


if __name__ == "__main__":
    main()
