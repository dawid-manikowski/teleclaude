import asyncio
import logging
import os

log = logging.getLogger(__name__)

WORK_DIR = os.path.expanduser(os.environ.get("WORK_DIR", "~/assistant"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
TIMEOUT = 300

_lock = asyncio.Lock()


async def run_claude(prompt: str) -> str:
    if _lock.locked():
        return "Processing previous request, please wait."

    async with _lock:
        log.info("Running claude: %r", prompt[:80])
        try:
            proc = await asyncio.create_subprocess_exec(
                CLAUDE_BIN,
                "-p", prompt,
                "--dangerously-skip-permissions",
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

        output = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and not output:
            err = stderr.decode("utf-8", errors="replace").strip()
            log.error("Claude rc=%s stderr=%r", proc.returncode, err[:200])
            return f"Claude error (rc={proc.returncode}):\n{err}"

        log.info("Claude returned %d chars", len(output))
        return output or "[No output]"
