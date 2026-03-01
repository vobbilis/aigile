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
import re
import subprocess
import sys
from pathlib import Path

# Required sections in specs/*.md plan files
SPEC_REQUIRED_SECTIONS = [
    "## Task Description",
    "## Objective",
    "## Relevant Files",
    "## Step by Step Tasks",
    "## Acceptance Criteria",
    "## Team Orchestration",
    "### Team Members",
]

# Required sections in bugs/*/report.md bug reports
BUG_REPORT_REQUIRED_SECTIONS = [
    "## Summary",
    "## Steps to Reproduce",
    "## Expected Behavior",
    "## Actual Behavior",
    "## Environment",
    "## Severity",
    "## Module/Area",
    "## Evidence",
]

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

    # ── Spec file written to specs/ → validate required sections ─────────────
    if changed_file and re.search(r"(^|/)specs/.*\.md$", changed_file):
        spec_path = cwd / changed_file if not Path(changed_file).is_absolute() else Path(changed_file)
        if spec_path.exists():
            content = spec_path.read_text(encoding="utf-8")
            missing = [s for s in SPEC_REQUIRED_SECTIONS if s not in content]
            if missing:
                block(
                    reason="Spec file missing required sections",
                    context=(
                        f"🛑 Plan file {changed_file} is missing required sections:\n\n"
                        + "\n".join(f"  - {s}" for s in missing)
                        + "\n\nAll plan files in specs/ must contain these sections:\n"
                        + "\n".join(f"  - {s}" for s in SPEC_REQUIRED_SECTIONS)
                        + "\n\nAdd the missing sections before continuing."
                    ),
                )

            # ── Validator frequency check ────────────────────────────────────
            builder_count = len(re.findall(
                r"^-\s+\*\*Role\*\*:\s*builder\s*$", content, re.MULTILINE
            ))
            validator_count = len(re.findall(
                r"^-\s+\*\*Role\*\*:\s*validator\s*$", content, re.MULTILINE
            ))
            if builder_count > 5:
                # Require at least 1 intermediate validator + 1 final = 2
                # For 11+, require 1 per 5 builders + 1 final
                required_validators = (builder_count // 5) + 1
                if validator_count < required_validators:
                    block(
                        reason="Spec file has insufficient intermediate validators",
                        context=(
                            f"🛑 Plan file {changed_file} has {builder_count} builder tasks "
                            f"but only {validator_count} validator task(s).\n\n"
                            f"Rule: Plans with >5 builder tasks need intermediate validators.\n"
                            f"  - {builder_count} builders → need ≥{required_validators} "
                            f"validator tasks ({required_validators - 1} intermediate + 1 final).\n"
                            f"  - Currently have: {validator_count}.\n\n"
                            f"Add intermediate validator tasks (e.g., 'validate-phase-1') "
                            f"after every ~5 builder tasks. These should run all tests, lint, "
                            f"and typecheck to catch regressions early."
                        ),
                    )

    # ── Bug report written to bugs/*/report.md → validate required sections ──
    if changed_file and re.search(r"bugs/.+/report\.md$", changed_file):
        report_path = (
            cwd / changed_file
            if not Path(changed_file).is_absolute()
            else Path(changed_file)
        )
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")
            missing = [s for s in BUG_REPORT_REQUIRED_SECTIONS if s not in content]
            if missing:
                block(
                    reason="Bug report missing required sections",
                    context=(
                        f"🛑 Bug report {changed_file} is missing required sections:\n\n"
                        + "\n".join(f"  - {s}" for s in missing)
                        + "\n\nAll bug reports must contain these 8 sections:\n"
                        + "\n".join(f"  - {s}" for s in BUG_REPORT_REQUIRED_SECTIONS)
                        + "\n\nAdd the missing sections before continuing."
                    ),
                )

    allow()


if __name__ == "__main__":
    main()
