import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from chunker import send_response
from claude_runner import run_claude

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])

COMMAND_MAP = {
    "morning_briefing": "/morning-briefing",
    "weekly_review": "/weekly-review",
    "schedule_sync": "/schedule-sync",
    "memory_update": "/memory-update",
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
    await _handle(update, update.message.text)


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmd = update.message.text.lstrip("/").split()[0]
    claude_prompt = COMMAND_MAP.get(cmd, f"/{cmd}")
    await _handle(update, claude_prompt)


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    for cmd in COMMAND_MAP:
        app.add_handler(CommandHandler(cmd, handle_command, filters=owner_filter))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & owner_filter, handle_message))

    log.info("Bot starting, allowed user: %d", ALLOWED_USER_ID)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
