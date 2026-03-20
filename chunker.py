import io

CHUNK_SIZE = 4000


def split_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    while text:
        if len(text) <= CHUNK_SIZE:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, CHUNK_SIZE)
        if split_at == -1:
            split_at = CHUNK_SIZE
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def send_response(message, text: str) -> None:
    chunks = split_text(text)
    if len(chunks) > 3:
        bio = io.BytesIO(text.encode("utf-8"))
        bio.name = "response.md"
        await message.reply_document(bio)
        return
    for chunk in chunks:
        await message.reply_text(chunk)


async def send_response_to_chat(bot, chat_id: int, text: str) -> None:
    """Send a response to a chat_id (for scheduled jobs, not replies)."""
    chunks = split_text(text)
    if len(chunks) > 3:
        bio = io.BytesIO(text.encode("utf-8"))
        bio.name = "response.md"
        await bot.send_document(chat_id=chat_id, document=bio)
        return
    for chunk in chunks:
        await bot.send_message(chat_id=chat_id, text=chunk)
