# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Telegram bot wrapping the Claude Code CLI (`claude -p`) to provide full assistant access from mobile. Supports MCP tools, local knowledge base, custom skills, scheduled jobs, and agent routing.

## Running

```bash
# Install dependencies
venv/bin/pip install -r requirements.txt

# Run the bot
venv/bin/python bot.py

# Managed via systemd in production
sudo systemctl restart tg-assistant
journalctl -u tg-assistant -f   # view logs
```

No test suite exists. Validate changes by running the bot and sending test messages.

## Environment

Configured via `.env` (see `.env.example`). Key vars: `BOT_TOKEN`, `ALLOWED_USER_ID`, `WORK_DIR` (claude working dir, default `~/assistant`), `CLAUDE_BIN`. MCP tokens must also be in `.env` since the claude subprocess inherits them.

## Architecture

Single-process async Python bot using `python-telegram-bot` (PTB). All times are Europe/Warsaw.

**Request flow**: Telegram message → `bot.py` handler → `claude_runner.run_claude()` (subprocess `claude -p ... --output-format json`) → parse JSON → `chunker.send_response()` → reply.

- **bot.py** — PTB Application, all handlers, owner-only auth filter, command-to-skill mapping (`COMMAND_MAP`), agent routing, quick-log pattern matching
- **claude_runner.py** — Async subprocess wrapper with `asyncio.Lock` (one request at a time), 300s timeout, daily session continuity via `--resume`. Scheduled jobs run sessionless (`use_session=False`)
- **chunker.py** — Splits replies at 4000 chars on newline boundaries; sends as `.md` file if >3 chunks
- **scheduler.py** — Declarative job definitions (`SIMPLE_REMINDERS`, `SKILL_JOBS`, `MONTHLY_JOBS`, `BIRTHDAY_CHECK`) registered on PTB's job queue. Simple reminders send plain text; skill jobs invoke `run_claude`

## Key design decisions

- **Single lock**: Only one claude subprocess runs at a time. Concurrent requests get a "please wait" reply rather than queueing.
- **Session per day**: Interactive messages share a daily session ID (`--resume`). Scheduled jobs are isolated (no session resume) to avoid cross-contamination.
- **Telegram command mapping**: Hyphens are forbidden in Telegram commands, so `COMMAND_MAP` in `bot.py` translates underscored commands to hyphenated Claude skill names.
- **Agent routing**: `/agent <name> <prompt>` routes to Claude agents defined in `~/.claude/agents/`. Valid agent names are in `AVAILABLE_AGENTS`.
