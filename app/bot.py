"""Bot va Dispatcher yig'ish, logging sozlash, polling."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent

from app.config import Settings
from app.handlers import emoji, start
from app.services.emoji_service import EmojiService

logger = logging.getLogger(__name__)

GENERIC_ERROR_TEXT = "⚠️ Kutilmagan xatolik yuz berdi. Keyinroq qayta urinib ko'ring."


class _RedactSecretFilter(logging.Filter):
    """Token tasodifan log yozuviga tushsa ham uni yashiradi."""

    def __init__(self, secret: str) -> None:
        super().__init__()
        self._secret = secret

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if self._secret in message:
            record.msg = message.replace(self._secret, "***")
            record.args = None
        return True


def setup_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    handler.addFilter(_RedactSecretFilter(settings.bot_token))
    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)
    # aiogram har bir update'ni INFO da yozadi — shovqinni kamaytiramiz.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


errors_router = Router(name="errors")


@errors_router.errors()
async def on_error(event: ErrorEvent) -> bool:
    # To'liq traceback faqat server logida; foydalanuvchiga umumiy matn.
    logger.exception("Unhandled error while processing update %s", event.update.update_id, exc_info=event.exception)
    update = event.update
    try:
        if update.message is not None:
            await update.message.answer(GENERIC_ERROR_TEXT)
        elif update.callback_query is not None:
            await update.callback_query.answer(GENERIC_ERROR_TEXT, show_alert=True)
    except Exception:  # noqa: BLE001 — xatolik handler'i o'zi yiqilmasligi kerak
        logger.warning("Could not notify user about error")
    return True


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


def create_dispatcher(bot: Bot, settings: Settings) -> Dispatcher:
    dp = Dispatcher()
    dp["emoji_service"] = EmojiService(bot, set_cache_ttl=settings.set_cache_ttl)
    dp.include_routers(errors_router, start.router, emoji.router)
    return dp


async def run_polling(settings: Settings) -> None:
    bot = create_bot(settings)
    dp = create_dispatcher(bot, settings)
    try:
        me = await bot.get_me()
        logger.info("Starting bot @%s (id=%s)", me.username, me.id)
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Botni ishga tushirish"),
                BotCommand(command="help", description="Qo'llanma"),
            ]
        )
        # Polling ishlashi uchun webhook o'chirilgan bo'lishi kerak.
        await bot.delete_webhook(drop_pending_updates=False)
        # start_polling SIGINT/SIGTERM da o'zi to'xtaydi (graceful shutdown).
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped")
