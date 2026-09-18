from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="start")

START_TEXT = (
    "👋 <b>Telegram Custom Emoji ID Bot</b>\n\n"
    "Menga istalgan Telegram Premium / Custom Emoji yuboring.\n\n"
    "Men:\n"
    "• emoji'ning <b>ID</b> sini aniqlayman;\n"
    "• u tegishli bo'lgan <b>pack/set</b>ni topaman;\n"
    "• set ichidagi <b>barcha Custom Emoji ID</b> larini chiqaraman.\n\n"
    "Bir xabarda bir nechta emoji yuborish ham mumkin — "
    "turli packlardagilar alohida guruhlanadi.\n\n"
    "👇 Premium emoji yuboring."
)


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT)
