from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import SELECT_COLUMNS
from app.keyboards.factory import PremiumButtonFactory
from app.keyboards.language_keyboard import language_rows
from app.keyboards.pagination_keyboard import pagination_row
from app.models.emoji import EmojiItem
from app.premium_emojis import PremiumEmoji
from app.services.code_generator_service import CodeLanguage, GeneratedCode
from app.services.session_service import Session
from app.utils.callback_data import (
    NOOP,
    RESTART,
    CodeFileCb,
    EmojiCb,
    ListCreateCb,
    PacksCb,
    PageCb,
    PreviewCb,
    TableFileCb,
)
from app.utils.pagination import PageInfo, chunked
from app.utils.telegram_limits import COPY_TEXT_MAX_CHARS


def table_row(factory: PremiumButtonFactory, sid: str, k: int, index: int, page: int) -> list[InlineKeyboardButton]:
    """[ Ro'yxat yaratish ] [ Jadvalga qaytish ]"""
    return [
        factory.list_create(ListCreateCb(s=sid, k=k, i=index, p=page).pack()),
        factory.table(PageCb(s=sid, k=k, p=page).pack()),
    ]


def _select_rows(
    factory: PremiumButtonFactory, sid: str, k: int, indices: list[int], page: int
) -> list[list[InlineKeyboardButton]]:
    buttons = [factory.plain(str(i), EmojiCb(s=sid, k=k, i=i, p=page).pack()) for i in indices]
    return chunked(buttons, SELECT_COLUMNS)


def explorer_keyboard(
    factory: PremiumButtonFactory, session: Session, k: int, info: PageInfo, admin_url: str | None = None
) -> InlineKeyboardMarkup:
    """Sahifadagi 25 ta emoji (5 qator x 5) + [Oldingi] [p / P] [Keyingi] + yuborilgan emoji nusxasi
    + [Ro'yxat yaratish] [Jadval] + [Admin] (admin profili)."""
    sid = session.sid
    rows = _select_rows(factory, sid, k, info.indices, info.page)
    if info.total_pages > 1:
        rows.append(pagination_row(factory, info, sid, k))
    sent_ids = [item.custom_emoji_id for _, item in session.sent_in_pack(k)]
    copy_value = "\n".join(sent_ids)
    if sent_ids and len(copy_value) <= COPY_TEXT_MAX_CHARS:
        label = "Yuborilgan emojni nusxalash" if len(sent_ids) == 1 else "Yuborilgan emojilarni nusxalash"
        rows.append([factory.copy(label, copy_value)])
    # [ Ro'yxat yaratish ] [ Jadval ] — explorer'da tanlangan emoji yo'q (i=0).
    rows.append(
        [
            factory.list_create(ListCreateCb(s=sid, k=k, i=0, p=info.page).pack()),
            factory.table_file(TableFileCb(s=sid, k=k, p=info.page).pack()),
        ]
    )
    if admin_url:
        rows.append([factory.admin(admin_url)])
    if len(session.packs) > 1:
        rows.append([factory.button("Packlar ro'yxati", role=PremiumEmoji.LIST, callback_data=PacksCb(s=sid).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _short(title: str, limit: int = 40) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"


def pack_list_keyboard(factory: PremiumButtonFactory, session: Session) -> InlineKeyboardMarkup:
    rows = [
        [
            factory.button(
                f"{_short(pack.title)} — {pack.total}",
                role=PremiumEmoji.PACK,
                callback_data=PageCb(s=session.sid, k=k, p=1).pack(),
            )
        ]
        for k, pack in enumerate(session.packs)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def detail_keyboard(
    factory: PremiumButtonFactory, sid: str, k: int, item: EmojiItem, index: int, page: int
) -> InlineKeyboardMarkup:
    rows = language_rows(factory, sid, k, index, page)
    rows.append([factory.copy("ID'ni nusxalash", item.custom_emoji_id)])
    rows.append(
        [
            factory.button(
                "Button Preview",
                role=PremiumEmoji.PREVIEW,
                callback_data=PreviewCb(s=sid, k=k, i=index, p=page).pack(),
            )
        ]
    )
    rows.append(table_row(factory, sid, k, index, page))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def code_keyboard(
    factory: PremiumButtonFactory,
    sid: str,
    k: int,
    index: int,
    page: int,
    generated: GeneratedCode,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if generated.copy_supported:
        rows.append([factory.copy("Kodni nusxalash", generated.code)])
    else:
        # CopyTextButton 256 belgidan oshmaydi: to'liq kod fayl sifatida, tugma qismi — nusxalash.
        if generated.snippet_copy_supported:
            rows.append([factory.copy("Button kodini nusxalash", generated.snippet)])
        rows.append(
            [
                factory.file(
                    "Kodni fayl sifatida olish",
                    CodeFileCb(s=sid, k=k, i=index, l=generated.language.value).pack(),
                )
            ]
        )
    rows += language_rows(factory, sid, k, index, page, exclude=CodeLanguage(generated.language), columns=3)
    rows.append([factory.back(EmojiCb(s=sid, k=k, i=index, p=page).pack(), "Emoji ma'lumotlari")])
    rows.append(table_row(factory, sid, k, index, page))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def preview_keyboard(
    factory: PremiumButtonFactory, sid: str, k: int, item: EmojiItem, index: int, page: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # Haqiqiy tugma: foydalanuvchi tanlagan emoji ikonka sifatida.
            [factory.button("Test button", callback_data=NOOP, icon_custom_emoji_id=item.custom_emoji_id)],
            [factory.back(EmojiCb(s=sid, k=k, i=index, p=page).pack(), "Emoji ma'lumotlari")],
            table_row(factory, sid, k, index, page),
        ]
    )


def table_file_keyboard(factory: PremiumButtonFactory, sid: str, k: int, page: int) -> InlineKeyboardMarkup:
    """Jadval fayli ostida: [ Jadvalga qaytish ] — o'sha sahifaga."""
    return InlineKeyboardMarkup(inline_keyboard=[[factory.table(PageCb(s=sid, k=k, p=page).pack())]])


def restart_keyboard(factory: PremiumButtonFactory) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[factory.refresh(RESTART)]])
