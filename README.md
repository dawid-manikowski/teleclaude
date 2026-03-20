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
scheduler.py      # Proactive scheduled jobs (reminders, skills)
systemd/          # systemd service unit
requirements.txt
.env.example
```

**Core flow**: Telegram message -> `claude -p <prompt> --dangerously-skip-permissions` in your assistant working directory -> reply

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
sudo cp systemd/tg-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tg-assistant
```

## Slash commands

Telegram forbids hyphens in commands, so these aliases are mapped:

| Telegram | Claude prompt |
|---|---|
| `/start_day` | `/start-day` (morning-briefing + schedule-sync) |
| `/end_week` | `/end-week` (memory-update + weekly-review) |
| `/morning_briefing` | `/morning-briefing` |
| `/weekly_review` | `/weekly-review` |
| `/monthly_review` | `/monthly-review` |
| `/quarterly_review` | `/quarterly-review` |
| `/schedule_sync` | `/schedule-sync` |
| `/memory_update` | `/memory-update` |
| `/meeting_prep` | `/meeting-prep` |
| `/fitness_log` | `/fitness-log` |
| `/habit_log` | `/habit-log` |
| `/decide` | `/decide` |
| `/jobs` | List all scheduled jobs and next run times |

Any other message or command is passed through to Claude as-is.

## Quick-log messages

These are recognized as single-message habit logs (no slash command needed):

| Message | Action |
|---|---|
| `meds done` / `took meds` | Log medication in HABITS.md |
| `roza exercises done` / `exercises done` | Log Roza exercises in HABITS.md |
| `sleep 3/5` / `sleep 4` | Log sleep quality in HABITS.md |
| `pushups 30` | Log pushups in FITNESS.md |

## Scheduled jobs

The bot automatically sends proactive reminders and runs skills:

| Time (Warsaw) | Job | Type |
|---|---|---|
| 07:30 daily | Birthday check (7-day lookahead) | Claude skill |
| 07:45 daily | Morning briefing (`/start-day`) | Claude skill |
| 08:15 daily | "Meds after breakfast?" | Simple reminder |
| 12:00 daily | "Roza oral exercises" | Simple reminder |
| 09:00 Wednesday | "Maczfit -- pick meals" | Simple reminder |
| 09:00 Thursday | "Prep Nathan 1:1 notes" | Simple reminder |
| 13:45 Tuesday | "Scan tech designs Slack" | Simple reminder |
| 14:00 Friday | End-of-week review (`/end-week`) | Claude skill |
| 20:00 Sunday | Memory sync (`/memory-update`) | Claude skill |
| 08:00 1st of month | Monthly review | Claude skill |

Use `/jobs` in Telegram to see all scheduled jobs and their next run times.

## Security

- Auth: only messages from `ALLOWED_USER_ID` are processed — all others are silently dropped
- Concurrency: single `asyncio.Lock` — if busy, replies "processing, please wait"
- Long output: chunked at 4000 chars; sent as `response.md` file if >3 chunks

## Requirements

- Python 3.11+
- [Claude Code CLI](https://github.com/anthropics/claude-code) installed and authenticated
