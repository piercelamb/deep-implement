#!/usr/bin/env python3
"""Capture session_id and expose it via Claude's context.

This hook runs when Claude Code starts a session. It reads session_id from
the JSON payload on stdin and:
1. Outputs it to stdout as additionalContext (Claude sees this directly)
2. Optionally writes to CLAUDE_ENV_FILE if available (for bash commands)

The stdout approach works even when CLAUDE_ENV_FILE is unavailable (after /clear).

Usage:
    This script is called automatically by Claude Code when configured
    as a SessionStart hook in hooks/hooks.json (for plugins):

    {
      "hooks": {
        "SessionStart": [
          {
            "hooks": [
              {
                "type": "command",
                "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/hooks/capture-session-id.py"
              }
            ]
          }
        ]
      }
    }
"""

import json
import os
import sys


def main() -> int:
    """Capture session_id, output to Claude's context and optionally CLAUDE_ENV_FILE.

    Returns:
        0 always (hooks should not fail the session start)
    """
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    except Exception:
        return 0

    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")

    if not session_id:
        return 0

    # PRIMARY: Output to Claude's context via additionalContext
    # This works even when CLAUDE_ENV_FILE is unavailable
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"DEEP_IMPLEMENT_SESSION_ID={session_id}",
        }
    }
    print(json.dumps(output))

    # SECONDARY: Also try CLAUDE_ENV_FILE for bash commands (may not work)
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file:
        try:
            existing_content = ""
            try:
                with open(env_file) as f:
                    existing_content = f.read()
            except FileNotFoundError:
                pass

            lines_to_write = []
            if f"CLAUDE_SESSION_ID={session_id}" not in existing_content:
                lines_to_write.append(f"export CLAUDE_SESSION_ID={session_id}\n")
            if (
                transcript_path
                and f"CLAUDE_TRANSCRIPT_PATH={transcript_path}" not in existing_content
            ):
                lines_to_write.append(
                    f"export CLAUDE_TRANSCRIPT_PATH={transcript_path}\n"
                )

            if lines_to_write:
                with open(env_file, "a") as f:
                    f.writelines(lines_to_write)
        except OSError:
            pass  # CLAUDE_ENV_FILE failed, but we already output to context

    return 0


if __name__ == "__main__":
    sys.exit(main())
