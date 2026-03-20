import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from chunker import send_response
from claude_runner import run_claude
from scheduler import register_jobs

load_dotenv(override=False)  # only fill env vars not already set by systemd EnvironmentFile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])

# Telegram forbids hyphens in commands — map underscored versions to Claude prompts
COMMAND_MAP = {
    "morning_briefing": "/morning-briefing",
    "weekly_review": "/weekly-review",
    "schedule_sync": "/schedule-sync",
    "memory_update": "/memory-update",
    "start_day": "/start-day",
    "end_week": "/end-week",
    "monthly_review": "/monthly-review",
    "quarterly_review": "/quarterly-review",
    "meeting_prep": "/meeting-prep",
    "fitness_log": "/fitness-log",
    "habit_log": "/habit-log",
    "decide": "/decide",
}

# Quick-log patterns: single-message habit tracking without invoking a full skill
QUICK_LOG_TRIGGERS = {
    "meds done": "Log in HABITS.md: medication taken today. Confirm with streak count.",
    "took meds": "Log in HABITS.md: medication taken today. Confirm with streak count.",
    "medication done": "Log in HABITS.md: medication taken today. Confirm with streak count.",
    "roza exercises done": "Log in HABITS.md: Roza exercises done today. Confirm with streak count.",
    "roza done": "Log in HABITS.md: Roza exercises done today. Confirm with streak count.",
    "exercises done": "Log in HABITS.md: Roza exercises done today. Confirm with streak count.",
}


class OwnerFilter(filters.MessageFilter):
    def filter(self, message):
        return bool(message.from_user and message.from_user.id == ALLOWED_USER_ID)


owner_filter = OwnerFilter()


async def _typing_loop(chat_id: int, bot, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.wait_for(stop.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            break


async def _handle(update: Update, prompt: str) -> None:
    stop = asyncio.Event()
    typing = asyncio.create_task(_typing_loop(update.effective_chat.id, update.get_bot(), stop))
    try:
        result = await run_claude(prompt)
    finally:
        stop.set()
        await typing
    await send_response(update.message, result)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    text_lower = text.lower()

    # Check for quick-log triggers
    for trigger, prompt in QUICK_LOG_TRIGGERS.items():
        if text_lower == trigger:
            await _handle(update, prompt)
            return

    # Check for sleep quality pattern: "sleep N/5" or "sleep N"
    if text_lower.startswith("sleep "):
        await _handle(update, f"Log in HABITS.md: {text}. Confirm with streak count.")
        return

    # Check for pushup pattern: "pushups N"
    if text_lower.startswith("pushups "):
        await _handle(update, text)
        return

    # Pass everything else to Claude as-is
    await _handle(update, text)


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmd = update.message.text.lstrip("/").split()[0]
    claude_prompt = COMMAND_MAP.get(cmd, f"/{cmd}")
    # Append any arguments after the command
    parts = update.message.text.split(maxsplit=1)
    if len(parts) > 1:
        claude_prompt += " " + parts[1]
    await _handle(update, claude_prompt)


async def handle_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all scheduled jobs and their next run times."""
    jobs = context.job_queue.jobs()
    if not jobs:
        await update.message.reply_text("No scheduled jobs.")
        return
    lines = ["**Scheduled Jobs**\n"]
    for job in sorted(jobs, key=lambda j: str(j.next_t or "")):
        next_run = job.next_t.strftime("%a %H:%M %Z") if job.next_t else "unknown"
        lines.append(f"- `{job.name}` -- next: {next_run}")
    await update.message.reply_text("\n".join(lines))


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Slash commands
    for cmd in COMMAND_MAP:
        app.add_handler(CommandHandler(cmd, handle_command, filters=owner_filter))
    app.add_handler(CommandHandler("jobs", handle_jobs, filters=owner_filter))

    # Free-text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & owner_filter, handle_message))

    # Register scheduled jobs
    register_jobs(app, ALLOWED_USER_ID)

    log.info("Bot starting, allowed user: %d", ALLOWED_USER_ID)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
