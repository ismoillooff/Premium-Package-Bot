"""Bot va Dispatcher yig'ish, logging sozlash, polling."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import BotCommand, ErrorEvent

from app.config import Settings
from app.handlers import code_generator, emoji_input, emoji_select, pagination, start
from app.premium_emojis import PremiumEmojiRegistry
from app.services.code_generator_service import CodeGeneratorService
from app.services.emoji_service import EmojiService
from app.services.presenter import Presenter
from app.services.session_service import SessionStore
from app.services.sticker_set_service import StickerSetService
from app.views import Views

logger = logging.getLogger(__name__)


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


def _errors_router(views: Views, presenter: Presenter) -> Router:
    router = Router(name="errors")

    @router.errors()
    async def on_error(event: ErrorEvent) -> bool:
        exc = event.exception
        # To'liq traceback faqat server logida; foydalanuvchiga umumiy matn.
        if isinstance(exc, (TelegramNetworkError, TelegramRetryAfter)):
            logger.warning("Telegram unavailable while processing update %s: %s", event.update.update_id, exc)
            text = "Telegram bilan aloqa vaqtincha uzildi. Birozdan keyin qayta urinib ko'ring."
        else:
            logger.exception("Unhandled error while processing update %s", event.update.update_id, exc_info=exc)
            text = "Kutilmagan xatolik yuz berdi. Keyinroq qayta urinib ko'ring."
        update = event.update
        try:
            if update.message is not None and update.message.bot is not None:
                await presenter.send(update.message.bot, update.message.chat.id, lambda: views.warning(text))
            elif update.callback_query is not None:
                await update.callback_query.answer(text, show_alert=True)
        except Exception:  # noqa: BLE001 — xatolik handler'i o'zi yiqilmasligi kerak
            logger.warning("Could not notify user about error")
        return True

    return router


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


def create_dispatcher(bot: Bot, settings: Settings, registry: PremiumEmojiRegistry | None = None) -> Dispatcher:
    registry = registry or PremiumEmojiRegistry.from_sources()
    views = Views(registry)
    presenter = Presenter(registry)
    sets = StickerSetService(bot, cache_ttl=settings.cache_ttl)

    dp = Dispatcher()
    dp["registry"] = registry
    dp["views"] = views
    dp["presenter"] = presenter
    dp["sessions"] = SessionStore()
    dp["emoji_service"] = EmojiService(bot, sets)
    dp["code_generator"] = CodeGeneratorService()
    dp.include_routers(
        _errors_router(views, presenter),
        start.router,
        pagination.router,
        emoji_select.router,
        code_generator.router,
        emoji_input.router,  # catch-all message handler oxirida
    )
    return dp


async def resolve_admin_url(bot: Bot, admin_id: int | None) -> str | None:
    """ADMIN_ID bo'yicha profil havolasi: username bo'lsa https://t.me/<username>, aks holda tg://user?id=.

    tg://user?id= havolasi foydalanuvchi maxfiylik sozlamasi ruxsat bersagina ishlaydi (aks holda Telegram
    tugmani rad etadi) — bunday holatda tugma ko'rsatilmaydi.
    """
    if admin_id is None:
        return None
    try:
        chat = await bot.get_chat(admin_id)
    except TelegramAPIError as exc:
        logger.warning("Admin chat unavailable (admin must /start the bot first): %s", exc)
        return None
    if chat.username:
        return f"https://t.me/{chat.username}"
    if chat.has_private_forwards:
        logger.warning("Admin has no username and restricts links by ID — Admin button hidden")
        return None
    return f"tg://user?id={admin_id}"


async def run_polling(settings: Settings) -> None:
    bot = create_bot(settings)
    dp = create_dispatcher(bot, settings)
    try:
        me = await bot.get_me()
        logger.info("Starting bot @%s (id=%s)", me.username, me.id)
        await dp["registry"].verify(bot)
        dp["views"].admin_url = await resolve_admin_url(bot, settings.admin_id)
        logger.info("Admin button: %s", "enabled" if dp["views"].admin_url else "disabled")
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Bosh sahifa"),
                BotCommand(command="help", description="Qo'llanma"),
                BotCommand(command="cancel", description="Sessiyani tozalash"),
            ]
        )
        # Polling ishlashi uchun webhook o'chirilgan bo'lishi kerak.
        await bot.delete_webhook(drop_pending_updates=False)
        # start_polling SIGINT/SIGTERM da o'zi to'xtaydi (graceful shutdown).
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped")
