"""Scheduled jobs for proactive assistant pushes.

All times are Europe/Warsaw. Jobs respect quiet hours (22:00-07:00).
Simple reminders are sent as plain text. Skill jobs invoke Claude CLI.
"""

import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

from claude_runner import run_claude
from chunker import send_response_to_chat

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Warsaw")

# ---- Simple text reminders (no Claude call) --------------------------------

SIMPLE_REMINDERS = [
    {
        "name": "meds",
        "time": time(8, 15, tzinfo=TZ),
        "text": "Meds after breakfast?",
        "days": (0, 1, 2, 3, 4, 5, 6),
    },
    {
        "name": "roza_exercises",
        "time": time(12, 0, tzinfo=TZ),
        "text": "Roza oral exercises",
        "days": (0, 1, 2, 3, 4, 5, 6),
    },
    {
        "name": "tech_designs",
        "time": time(13, 45, tzinfo=TZ),
        "text": "Scan tech designs Slack channel (20 min max)",
        "days": (1,),  # Tuesday
    },
    {
        "name": "maczfit",
        "time": time(9, 0, tzinfo=TZ),
        "text": "Maczfit -- pick meals for next week",
        "days": (2,),  # Wednesday
    },
    {
        "name": "nathan_prep",
        "time": time(9, 0, tzinfo=TZ),
        "text": "Prep Nathan 1:1 notes (meeting later today)",
        "days": (3,),  # Thursday
    },
]

# ---- Claude skill invocations ----------------------------------------------

SKILL_JOBS = [
    {
        "name": "morning_briefing",
        "time": time(7, 45, tzinfo=TZ),
        "prompt": "/start-day",
        "days": (0, 1, 2, 3, 4, 5, 6),
    },
    {
        "name": "end_week",
        "time": time(14, 0, tzinfo=TZ),
        "prompt": "/end-week",
        "days": (4,),  # Friday
    },
    {
        "name": "memory_sync",
        "time": time(20, 0, tzinfo=TZ),
        "prompt": "/memory-update",
        "days": (6,),  # Sunday
    },
]

# ---- Monthly / special jobs -------------------------------------------------

MONTHLY_JOBS = [
    {
        "name": "monthly_review",
        "day": 1,
        "time": time(8, 0, tzinfo=TZ),
        "prompt": "It's the 1st of the month. Run /monthly-review",
    },
]

BIRTHDAY_CHECK = {
    "name": "birthday_check",
    "time": time(7, 30, tzinfo=TZ),
    "prompt": (
        "Check knowledge-base/reference/birthdays.md for any birthdays or occasions "
        "in the next 7 days from today. If found, send a gift reminder with concrete "
        "suggestions. If nothing upcoming, reply with just 'No upcoming birthdays.'"
    ),
}


# ---- Job callbacks ----------------------------------------------------------

async def _send_simple(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a plain text reminder."""
    text = context.job.data["text"]
    chat_id = context.job.data["chat_id"]
    log.info("Sending reminder: %s", text)
    await context.bot.send_message(chat_id=chat_id, text=text)


async def _run_skill(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run a Claude skill and send the output. Scheduled jobs are sessionless."""
    prompt = context.job.data["prompt"]
    chat_id = context.job.data["chat_id"]
    log.info("Running scheduled skill: %s", prompt)
    result = await run_claude(prompt, use_session=False)
    await send_response_to_chat(context.bot, chat_id, result)


# ---- Registration -----------------------------------------------------------

def register_jobs(app: Application, chat_id: int) -> None:
    """Register all scheduled jobs with the application's job queue."""
    jq = app.job_queue

    # Simple daily/weekly reminders
    for reminder in SIMPLE_REMINDERS:
        jq.run_daily(
            _send_simple,
            time=reminder["time"],
            days=reminder["days"],
            name=reminder["name"],
            data={"text": reminder["text"], "chat_id": chat_id},
        )
        log.info("Registered reminder: %s at %s", reminder["name"], reminder["time"])

    # Claude skill jobs
    for skill in SKILL_JOBS:
        jq.run_daily(
            _run_skill,
            time=skill["time"],
            days=skill["days"],
            name=skill["name"],
            data={"prompt": skill["prompt"], "chat_id": chat_id},
        )
        log.info("Registered skill job: %s at %s", skill["name"], skill["time"])

    # Monthly jobs
    for monthly in MONTHLY_JOBS:
        jq.run_monthly(
            _run_skill,
            when=monthly["time"],
            day=monthly["day"],
            name=monthly["name"],
            data={"prompt": monthly["prompt"], "chat_id": chat_id},
        )
        log.info("Registered monthly job: %s on day %d", monthly["name"], monthly["day"])

    # Daily birthday check (runs early, before morning briefing)
    jq.run_daily(
        _run_skill,
        time=BIRTHDAY_CHECK["time"],
        days=(0, 1, 2, 3, 4, 5, 6),
        name=BIRTHDAY_CHECK["name"],
        data={"prompt": BIRTHDAY_CHECK["prompt"], "chat_id": chat_id},
    )
    log.info("Registered birthday check at %s", BIRTHDAY_CHECK["time"])

    log.info("All %d scheduled jobs registered", len(SIMPLE_REMINDERS) + len(SKILL_JOBS) + len(MONTHLY_JOBS) + 1)
