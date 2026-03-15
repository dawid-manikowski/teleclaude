# tg-assistant

A Telegram bot that wraps the [Claude Code CLI](https://github.com/anthropics/claude-code) (`claude -p`) to provide full assistant access from mobile — including MCP tools (Calendar, Gmail, Jira), a local knowledge base, and custom skills.

## Why

- SSH on mobile is clunky
- Direct Claude API bots lack MCP context, local files, and custom skills
- Wrapping the CLI gives full assistant power through a clean Telegram chat interface

## Architecture

```
bot.py            # PTB Application, handler registration, main()
claude_runner.py  # asyncio subprocess, lock, timeout
chunker.py        # 4096-char splitting, file fallback
systemd/          # systemd service unit
requirements.txt
.env.example
```

**Core flow**: Telegram message → `claude -p <prompt> --dangerously-skip-permissions` in your assistant working directory → reply

## Setup

### 1. Clone and create virtualenv

```bash
git clone <repo> /opt/tg-assistant
cd /opt/tg-assistant
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
chmod 600 .env
# Edit .env with your values
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `ALLOWED_USER_ID` | Your Telegram numeric user ID |
| `WORK_DIR` | Working directory for `claude` (default: `~/assistant`) |
| `CLAUDE_BIN` | Path to the `claude` binary (default: `claude`) |

All MCP environment variables (Google, Atlassian tokens, etc.) must also be present in `.env` so the subprocess inherits them.

### 3. Systemd service

```bash
cp systemd/tg-assistant.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tg-assistant
```

## Slash commands

Telegram forbids hyphens in commands, so these aliases are mapped:

| Telegram | Claude prompt |
|---|---|
| `/morning_briefing` | `/morning-briefing` |
| `/weekly_review` | `/weekly-review` |
| `/schedule_sync` | `/schedule-sync` |
| `/memory_update` | `/memory-update` |

Any other message or command is passed through to Claude as-is.

## Security

- Auth: only messages from `ALLOWED_USER_ID` are processed — all others are silently dropped
- Concurrency: single `asyncio.Lock` — if busy, replies "processing, please wait"
- Long output: chunked at 4000 chars; sent as `response.md` file if >3 chunks

## Requirements

- Python 3.11+
- [Claude Code CLI](https://github.com/anthropics/claude-code) installed and authenticated
