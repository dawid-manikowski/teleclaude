import asyncio
import json
import logging
import os
from datetime import date

log = logging.getLogger(__name__)

WORK_DIR = os.path.expanduser(os.environ.get("WORK_DIR", "~/assistant"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
TIMEOUT = 300

_lock = asyncio.Lock()

# Session tracking: one session per day for conversational continuity.
# Scheduled jobs get their own sessions (no cross-contamination).
_session_id: str | None = None
_session_date: date | None = None


def _get_session_args(use_session: bool) -> list[str]:
    """Return --resume args if we have an active session for today."""
    global _session_id, _session_date
    if not use_session:
        return []
    today = date.today()
    if _session_date == today and _session_id:
        return ["--resume", _session_id]
    return []


def _update_session(session_id: str | None) -> None:
    """Store the session ID for today's conversation."""
    global _session_id, _session_date
    if session_id:
        _session_id = session_id
        _session_date = date.today()


async def run_claude(prompt: str, *, use_session: bool = True) -> str:
    """Run claude -p with optional session continuity.

    Args:
        prompt: The prompt to send to Claude.
        use_session: If True, maintain a daily conversation session.
                     Set to False for scheduled jobs (they get isolated runs).
    """
    if _lock.locked():
        return "Processing previous request, please wait."

    async with _lock:
        session_args = _get_session_args(use_session)
        mode = "resume" if session_args else "new"
        log.info("Running claude (%s): %r", mode, prompt[:80])

        cmd = [
            CLAUDE_BIN,
            "-p", prompt,
            "--dangerously-skip-permissions",
            "--output-format", "json",
            *session_args,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=WORK_DIR,
                env={**os.environ},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            log.warning("Claude timed out after %ss", TIMEOUT)
            return f"Timed out after {TIMEOUT}s."
        except Exception as e:
            log.exception("Failed to invoke claude")
            return f"Error invoking claude: {e}"

        raw = stdout.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0 and not raw:
            err = stderr.decode("utf-8", errors="replace").strip()
            log.error("Claude rc=%s stderr=%r", proc.returncode, err[:200])
            return f"Claude error (rc={proc.returncode}):\n{err}"

        # Parse JSON output to extract result and session_id
        try:
            data = json.loads(raw)
            output = data.get("result", "")
            session_id = data.get("session_id")
            if use_session and session_id:
                _update_session(session_id)
                log.info("Session: %s", session_id)
        except (json.JSONDecodeError, TypeError):
            # Fallback: treat as plain text (shouldn't happen with --output-format json)
            output = raw
            log.warning("Failed to parse JSON output, using raw text")

        log.info("Claude returned %d chars", len(output))
        return output or "[No output]"
