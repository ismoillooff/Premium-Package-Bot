from __future__ import annotations

from aiogram.types import InlineKeyboardButton

from app.keyboards.factory import PremiumButtonFactory
from app.services.code_generator_service import LANGUAGES, CodeLanguage
from app.utils.callback_data import CodeCb
from app.utils.pagination import chunked


def language_rows(
    factory: PremiumButtonFactory,
    sid: str,
    k: int,
    index: int,
    page: int,
    *,
    exclude: CodeLanguage | None = None,
    columns: int = 2,
) -> list[list[InlineKeyboardButton]]:
    buttons = [
        factory.language(spec.label, spec.icon, CodeCb(s=sid, k=k, i=index, l=lang.value, p=page).pack())
        for lang, spec in LANGUAGES.items()
        if lang != exclude
    ]
    return chunked(buttons, columns)
