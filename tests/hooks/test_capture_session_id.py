"""Tests for capture-session-id.py hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "hooks"
    / "capture-session-id.py"
)


def run_hook(stdin_data: str, env: dict | None = None) -> tuple[int, str, str]:
    """Run the hook script with given stdin and environment.

    Returns:
        (return_code, stdout, stderr)
    """
    import os

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=run_env,
    )
    return result.returncode, result.stdout, result.stderr


class TestAdditionalContextOutput:
    """Test the primary mechanism: outputting to Claude's context."""

    def test_outputs_session_id_as_additional_context(self):
        """Valid session_id should output hookSpecificOutput with additionalContext."""
        payload = {"session_id": "test-session-123"}
        returncode, stdout, _ = run_hook(json.dumps(payload))

        assert returncode == 0
        output = json.loads(stdout)
        assert output == {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "DEEP_SESSION_ID=test-session-123",
            }
        }

    def test_outputs_correct_format_for_uuid_session_id(self):
        """Should work with UUID-style session IDs."""
        payload = {"session_id": "51f3d992-1234-5678-9abc-def012345678"}
        returncode, stdout, _ = run_hook(json.dumps(payload))

        assert returncode == 0
        output = json.loads(stdout)
        assert (
            output["hookSpecificOutput"]["additionalContext"]
            == "DEEP_SESSION_ID=51f3d992-1234-5678-9abc-def012345678"
        )


class TestMissingOrInvalidInput:
    """Test handling of missing or invalid input."""

    def test_no_output_when_session_id_missing(self):
        """Missing session_id should produce no output."""
        payload = {"transcript_path": "/some/path"}
        returncode, stdout, _ = run_hook(json.dumps(payload))

        assert returncode == 0
        assert stdout == ""

    def test_no_output_when_session_id_empty(self):
        """Empty session_id should produce no output."""
        payload = {"session_id": ""}
        returncode, stdout, _ = run_hook(json.dumps(payload))

        assert returncode == 0
        assert stdout == ""

    def test_no_output_on_invalid_json(self):
        """Invalid JSON should produce no output and succeed."""
        returncode, stdout, _ = run_hook("not valid json")

        assert returncode == 0
        assert stdout == ""

    def test_no_output_on_empty_stdin(self):
        """Empty stdin should produce no output and succeed."""
        returncode, stdout, _ = run_hook("")

        assert returncode == 0
        assert stdout == ""


class TestClaudeEnvFileFallback:
    """Test the secondary mechanism: writing to CLAUDE_ENV_FILE."""

    def test_writes_to_claude_env_file_when_available(self, tmp_path):
        """Should write session_id to CLAUDE_ENV_FILE when available."""
        env_file = tmp_path / "env_file.sh"
        env_file.touch()

        payload = {"session_id": "test-session-456"}
        returncode, stdout, _ = run_hook(
            json.dumps(payload), env={"CLAUDE_ENV_FILE": str(env_file)}
        )

        assert returncode == 0
        # Should still output to context
        assert "DEEP_SESSION_ID=test-session-456" in stdout

        # Should also write to env file
        content = env_file.read_text()
        assert "export DEEP_SESSION_ID=test-session-456" in content

    def test_writes_transcript_path_to_env_file(self, tmp_path):
        """Should write transcript_path to CLAUDE_ENV_FILE."""
        env_file = tmp_path / "env_file.sh"
        env_file.touch()

        payload = {
            "session_id": "test-session-789",
            "transcript_path": "/path/to/transcript.jsonl",
        }
        returncode, _, _ = run_hook(
            json.dumps(payload), env={"CLAUDE_ENV_FILE": str(env_file)}
        )

        assert returncode == 0
        content = env_file.read_text()
        assert "export DEEP_SESSION_ID=test-session-789" in content
        assert "export CLAUDE_TRANSCRIPT_PATH=/path/to/transcript.jsonl" in content

    def test_does_not_duplicate_existing_entries(self, tmp_path):
        """Should not duplicate entries already in CLAUDE_ENV_FILE."""
        env_file = tmp_path / "env_file.sh"
        env_file.write_text("export DEEP_SESSION_ID=test-session-111\n")

        payload = {"session_id": "test-session-111"}
        returncode, _, _ = run_hook(
            json.dumps(payload), env={"CLAUDE_ENV_FILE": str(env_file)}
        )

        assert returncode == 0
        content = env_file.read_text()
        # Should only appear once
        assert content.count("DEEP_SESSION_ID=test-session-111") == 1

    def test_succeeds_when_claude_env_file_not_set(self):
        """Should succeed even when CLAUDE_ENV_FILE is not set."""
        payload = {"session_id": "test-session-222"}
        # Explicitly remove CLAUDE_ENV_FILE from environment
        returncode, stdout, _ = run_hook(
            json.dumps(payload), env={"CLAUDE_ENV_FILE": ""}
        )

        assert returncode == 0
        # Should still output to context
        assert "DEEP_SESSION_ID=test-session-222" in stdout

    def test_succeeds_when_claude_env_file_write_fails(self, tmp_path):
        """Should succeed even when CLAUDE_ENV_FILE write fails."""
        # Point to a directory (can't write to it as a file)
        payload = {"session_id": "test-session-333"}
        returncode, stdout, _ = run_hook(
            json.dumps(payload), env={"CLAUDE_ENV_FILE": str(tmp_path)}
        )

        assert returncode == 0
        # Should still output to context
        assert "DEEP_SESSION_ID=test-session-333" in stdout


class TestAlwaysReturnsZero:
    """Verify hook never fails (returns 0 always)."""

    def test_returns_zero_on_success(self):
        """Normal operation returns 0."""
        payload = {"session_id": "test"}
        returncode, _, _ = run_hook(json.dumps(payload))
        assert returncode == 0

    def test_returns_zero_on_invalid_json(self):
        """Invalid JSON returns 0."""
        returncode, _, _ = run_hook("{{{{")
        assert returncode == 0

    def test_returns_zero_on_empty_input(self):
        """Empty input returns 0."""
        returncode, _, _ = run_hook("")
        assert returncode == 0

    def test_returns_zero_on_missing_session_id(self):
        """Missing session_id returns 0."""
        payload = {}
        returncode, _, _ = run_hook(json.dumps(payload))
        assert returncode == 0


class TestDeepSessionIdConditional:
    """Test conditional output based on DEEP_SESSION_ID environment variable."""

    def test_skips_output_when_deep_session_id_matches(self):
        """Should not output when DEEP_SESSION_ID already matches session_id."""
        payload = {"session_id": "test-session-123"}
        returncode, stdout, _ = run_hook(
            json.dumps(payload), env={"DEEP_SESSION_ID": "test-session-123"}
        )

        assert returncode == 0
        # Should NOT output additionalContext since it already matches
        assert stdout == ""

    def test_outputs_when_deep_session_id_differs(self):
        """Should output when DEEP_SESSION_ID exists but doesn't match."""
        payload = {"session_id": "new-session-456"}
        returncode, stdout, _ = run_hook(
            json.dumps(payload), env={"DEEP_SESSION_ID": "old-session-123"}
        )

        assert returncode == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["additionalContext"] == "DEEP_SESSION_ID=new-session-456"

    def test_outputs_when_deep_session_id_not_set(self):
        """Should output when DEEP_SESSION_ID is not set."""
        payload = {"session_id": "test-session-789"}
        # Don't pass DEEP_SESSION_ID in env
        returncode, stdout, _ = run_hook(json.dumps(payload), env={})

        assert returncode == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["additionalContext"] == "DEEP_SESSION_ID=test-session-789"
