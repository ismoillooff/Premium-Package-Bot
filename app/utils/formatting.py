"""Natija matnlarini HTML formatda tayyorlash va xavfsiz bo'laklarga ajratish.

Barcha dinamik qiymatlar (set nomi, title, emoji) escape qilinadi.
Xabarlar faqat qator chegarasida bo'linadi, shuning uchun HTML teglar buzilmaydi.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from html import escape

from app.services.emoji_service import EmojiInfo, EmojiPack, LookupResult

# Telegram limiti 4096 belgi (entity'lar parse qilingandan keyin, UTF-16 da).
# Xom HTML uzunligi har doim natijaviy matndan uzun, shuning uchun zaxira bilan.
MESSAGE_LIMIT = 4000
ITEMS_PER_PAGE = 50
IDS_PER_MESSAGE = 150

_KIND_LABELS = {"static": "statik", "animated": "animatsion", "video": "video"}


def h(value: object) -> str:
    return escape(str(value), quote=False)


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def pack_link(name: str) -> str:
    return f"https://t.me/addemoji/{name}"


def emoji_line(index: int, item: EmojiInfo) -> str:
    code = f"<code>{h(item.custom_emoji_id)}</code>"
    if item.emoji:
        return f"{index}. {h(item.emoji)} — {code}"
    return f"{index}. {code}"


def chunk_lines(
    lines: Sequence[str],
    header: Callable[[int, int], str],
    *,
    max_items: int = ITEMS_PER_PAGE,
    limit: int = MESSAGE_LIMIT,
) -> list[str]:
    """Qatorlarni xabarlarga ajratadi.

    header(start, end) — har bir bo'lak sarlavhasi (1 dan boshlanuvchi raqamlar).
    Har bir bo'lak max_items tadan va limit (UTF-16) dan oshmaydi.
    """
    chunks: list[str] = []
    i = 0
    total = len(lines)
    while i < total:
        end = min(i + max_items, total)
        # Sarlavha uzunligi bo'lak oxiriga bog'liq; eng uzun variant bilan zaxira olamiz.
        head_len = utf16_len(header(i + 1, end)) + 2
        size = head_len
        j = i
        while j < end:
            line_len = utf16_len(lines[j]) + 1
            if size + line_len > limit and j > i:
                break
            size += line_len
            j += 1
        chunks.append(header(i + 1, j) + "\n\n" + "\n".join(lines[i:j]))
        i = j
    return chunks


def format_summary(result: LookupResult, truncated: bool = False) -> str:
    """Foydalanuvchi yuborgan emoji'lar haqida birinchi xabar."""
    parts: list[str] = []
    count = len(result.requested)

    if count == 1:
        item = result.requested[0]
        parts.append("✅ <b>Custom Emoji topildi</b>")
        if item.emoji:
            parts.append(f"\n<b>Emoji:</b> {h(item.emoji)}")
        parts.append(f"<b>Custom Emoji ID:</b>\n<code>{h(item.custom_emoji_id)}</code>")
        parts.append(f"<b>Turi:</b> {_KIND_LABELS.get(item.kind, h(item.kind))}")
        if item.needs_repainting:
            parts.append("<b>Rang:</b> matn rangiga moslashadi")
        pack = _pack_of(result, item)
        if pack is not None:
            parts.append(f"<b>Set:</b> {h(pack.title)}")
            parts.append(f"<b>Set nomi:</b> <code>{h(pack.name)}</code>")
            parts.append(f"<b>Pack ichida:</b> {len(pack.emojis)} ta Custom Emoji")
        elif item.set_name:
            parts.append(f"<b>Set nomi:</b> <code>{h(item.set_name)}</code>")
        else:
            parts.append("<b>Set:</b> aniqlanmadi")
    elif count > 1:
        parts.append(f"✅ <b>{count} ta Custom Emoji topildi</b>\n")
        for idx, item in enumerate(result.requested, start=1):
            line = emoji_line(idx, item)
            if item.set_name:
                line += f"\n    📦 <code>{h(item.set_name)}</code>"
            parts.append(line)
        if result.packs:
            parts.append(f"\n<b>Setlar soni:</b> {len(result.packs)}")

    warnings = format_warnings(result, truncated)
    if warnings:
        parts.append("")
        parts.append(warnings)
    return "\n".join(parts)


def format_warnings(result: LookupResult, truncated: bool = False) -> str:
    lines: list[str] = []
    if truncated:
        lines.append("⚠️ Bitta xabardan ko'pi bilan 200 ta emoji tekshiriladi.")
    if result.missing_ids:
        lines.append("⚠️ Telegram quyidagi ID lar bo'yicha ma'lumot bermadi:")
        lines.extend(f"<code>{h(i)}</code>" for i in result.missing_ids)
    if result.failed_sets:
        lines.append("⚠️ Telegram Bot API quyidagi set(lar) uchun to'liq pack ma'lumotini bermadi:")
        lines.extend(f"• <code>{h(n)}</code>" for n in result.failed_sets)
    no_set = [i for i in result.orphans if not i.set_name]
    if no_set:
        lines.append("ℹ️ Ba'zi emoji'lar uchun Telegram set nomini qaytarmadi.")
    if result.skipped_sets:
        lines.append(
            f"ℹ️ Ko'p set yuborildi: yana {len(result.skipped_sets)} ta set yuklanmadi. "
            "Ularning emoji'larini alohida yuboring."
        )
    return "\n".join(lines)


def format_pack_messages(pack: EmojiPack, set_number: int | None = None) -> list[str]:
    """Pack ichidagi barcha emoji'larni 50 tadan bo'laklarga ajratilgan xabarlar."""
    lines = [emoji_line(idx, item) for idx, item in enumerate(pack.emojis, start=1)]
    total = len(lines)
    label = f"📦 <b>SET {set_number}</b>\n" if set_number else "📦 "

    def header(start: int, end: int) -> str:
        return (
            f"{label}<b>{h(pack.title)}</b>\n"
            f"Nomi: <code>{h(pack.name)}</code>\n"
            f"Havola: {h(pack_link(pack.name))}\n"
            f"Jami: {total} ta · <b>{start}–{end}</b>"
        )

    return chunk_lines(lines, header)


def format_orphans_messages(items: Sequence[EmojiInfo]) -> list[str]:
    lines = [emoji_line(idx, item) for idx, item in enumerate(items, start=1)]

    def header(start: int, end: int) -> str:
        return f"🔹 <b>To'liq pack olinmagan emoji'lar</b> · {start}–{end}"

    return chunk_lines(lines, header)


def format_ids_messages(result: LookupResult) -> list[str]:
    """Faqat ID'lar — <pre> blok ichida, bosib nusxalash oson bo'lishi uchun."""
    groups: list[tuple[str, list[str]]] = [
        (pack.title, [e.custom_emoji_id for e in pack.emojis]) for pack in result.packs
    ]
    if result.orphans:
        groups.append(("Boshqa emoji'lar", [e.custom_emoji_id for e in result.orphans]))

    messages: list[str] = []
    for title, ids in groups:
        total = len(ids)
        # ID ~19 belgi: 150 ta ≈ 3000 belgi — limitdan xavfsiz uzoq, <pre> har bo'lakda yopiladi.
        step = IDS_PER_MESSAGE
        for start in range(0, total, step):
            part = ids[start : start + step]
            end = start + len(part)
            head = f"📋 <b>{h(title)}</b> · {start + 1}–{end} / {total}"
            messages.append(f"{head}\n<pre>{h(chr(10).join(part))}</pre>")
    return messages


def copy_payload(ids: Sequence[str], limit: int = 256) -> str | None:
    """copy_text tugmasi uchun matn (Bot API: 1–256 belgi). Sig'masa None."""
    text = "\n".join(ids)
    return text if 0 < len(text) <= limit else None


def _pack_of(result: LookupResult, item: EmojiInfo) -> EmojiPack | None:
    for pack in result.packs:
        if pack.name == item.set_name:
            return pack
    return None
