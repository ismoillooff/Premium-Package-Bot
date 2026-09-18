"""Bot ekranlari: matn (HTML), ixtiyoriy native rich jadval va klaviatura.

UI qoidasi: oddiy Unicode emoji yo'q. Ikonkalar faqat registry'dagi premium custom emoji;
mavjud bo'lmasa — toza matn.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import (
    InlineKeyboardMarkup,
    InputRichBlockParagraph,
    InputRichBlockSectionHeading,
    InputRichBlockTable,
    InputRichMessage,
    RichBlockTableCell,
    RichTextBold,
    RichTextCode,
    RichTextCustomEmoji,
)

from app.keyboards import emoji_keyboard as kb
from app.keyboards.factory import PremiumButtonFactory
from app.models.emoji import EmojiItem, EmojiPack
from app.premium_emojis import PremiumEmoji, PremiumEmojiRegistry
from app.services.code_generator_service import LANGUAGES, GeneratedCode
from app.services.session_service import Session
from app.utils.callback_data import EmojiCb, PageCb
from app.utils.formatting import content_emoji, h, pack_link, ui_icon
from app.utils.pagination import PageInfo
from app.utils.table import build_emoji_table

_SENT_SHOWN_MAX = 10
_KIND_LABELS = {"static": "statik", "animated": "animatsion", "video": "video"}


@dataclass(frozen=True, slots=True)
class Screen:
    html: str
    keyboard: InlineKeyboardMarkup | None = None
    rich: InputRichMessage | None = None
    """Native jadval (sendRichMessage). Telegram rad etsa, html ishlatiladi."""


class Views:
    def __init__(self, registry: PremiumEmojiRegistry, admin_url: str | None = None) -> None:
        self.registry = registry
        self.buttons = PremiumButtonFactory(registry)
        self.admin_url = admin_url
        """"Admin" tugmasi havolasi (ishga tushishda ADMIN_ID bo'yicha aniqlanadi); None — tugma yo'q."""

    # ---------- umumiy ----------

    def _i(self, role: PremiumEmoji) -> str:
        return ui_icon(self.registry, role)

    def start(self) -> Screen:
        text = (
            f"{self._i(PremiumEmoji.HOME)}<b>Custom Emoji Explorer</b>\n\n"
            "Telegram Premium / Custom Emoji yuboring.\n\n"
            "Bot avtomatik ravishda:\n"
            f"{self._i(PremiumEmoji.INFO)}emoji ID'sini topadi;\n"
            f"{self._i(PremiumEmoji.PACK)}emoji pack'ini aniqlaydi;\n"
            f"{self._i(PremiumEmoji.VIEW)}pack ichidagi barcha emoji'larni jadvalda ko'rsatadi;\n"
            f"{self._i(PremiumEmoji.CODE)}raqam orqali emoji tanlab, Python, JavaScript, TypeScript, "
            "PHP, Java va cURL kodini yaratadi;\n"
            f"{self._i(PremiumEmoji.COPY)}ID va kodni bir bosishda nusxalash imkonini beradi.\n\n"
            "Custom Emoji yuboring."
        )
        return Screen(text)

    def help(self) -> Screen:
        text = (
            f"{self._i(PremiumEmoji.INFO)}<b>Qanday ishlaydi</b>\n\n"
            "1. Botga bitta yoki bir nechta Premium / Custom Emoji yuboring.\n"
            "2. Bot emoji tegishli pack'ni topadi va 25 tadan (5×5) jadval ko'rsatadi.\n"
            "3. Raqamli tugmani bosing — emoji ID'si va ma'lumotlari ochiladi.\n"
            "4. Tilni tanlang — tugmada shu emoji'ni ikonka qilib ishlatadigan tayyor kod chiqadi.\n"
            "5. <b>Button Preview</b> — tugma Telegram'da qanday ko'rinishini sinab ko'rish.\n\n"
            "Turli pack'lardagi emoji'lar yuborilsa, avval pack tanlanadi.\n\n"
            "<b>Buyruqlar</b>\n"
            "/start — bosh sahifa\n"
            "/help — qo'llanma\n"
            "/cancel — joriy sessiyani tozalash"
        )
        return Screen(text)

    def cancelled(self, existed: bool) -> Screen:
        if existed:
            return Screen(f"{self._i(PremiumEmoji.SUCCESS)}Sessiya tozalandi. Yangi Custom Emoji yuboring.")
        return Screen(f"{self._i(PremiumEmoji.INFO)}Faol sessiya yo'q. Custom Emoji yuboring.")

    def loading(self) -> Screen:
        return Screen(f"{self._i(PremiumEmoji.LOADING)}Emoji pack yuklanmoqda...")

    def error(self, message: str, *, restart: bool = False) -> Screen:
        keyboard = kb.restart_keyboard(self.buttons) if restart else None
        return Screen(f"{self._i(PremiumEmoji.ERROR)}{message}", keyboard)

    def warning(self, message: str, *, restart: bool = False) -> Screen:
        keyboard = kb.restart_keyboard(self.buttons) if restart else None
        return Screen(f"{self._i(PremiumEmoji.WARNING)}{message}", keyboard)

    def not_custom(self) -> Screen:
        return self.error("<b>Custom Emoji topilmadi.</b>\n\nBu Custom/Premium Emoji emas. Telegram Premium Custom Emoji yuboring.")

    def api_error(self) -> Screen:
        return self.warning(
            "Telegram'dan emoji ma'lumotlarini olishda xatolik yuz berdi.\nKeyinroq qayta urinib ko'ring."
        )

    def not_found(self, ids: list[str]) -> Screen:
        lines = "\n".join(f"<code>{h(i)}</code>" for i in ids)
        return self.warning(f"Telegram Bot API ushbu emoji uchun ma'lumot bermadi.\n\n<b>Emoji ID:</b>\n{lines}")

    def expired(self) -> Screen:
        return self.warning("Bu menyu eskirgan.\n\nEmoji'ni qayta yuboring.", restart=True)

    # ---------- pack ro'yxati ----------

    def pack_list(self, session: Session) -> Screen:
        text = f"{self._i(PremiumEmoji.PACK)}<b>{len(session.packs)} ta Emoji Pack topildi</b>\n\nPack'ni tanlang:"
        text += self._notes(session)
        return Screen(text, kb.pack_list_keyboard(self.buttons, session))

    def _notes(self, session: Session) -> str:
        if not session.notes:
            return ""
        return "\n\n" + self._i(PremiumEmoji.WARNING) + "\n".join(h(n) for n in session.notes)

    # ---------- explorer (jadval) ----------

    def explorer(self, session: Session, k: int, info: PageInfo) -> Screen:
        """Xabar: pack nomi -> yuborilgan emoji (№, emoji, ID) -> jadval. Sahifa raqami tugmada."""
        pack = session.packs[k]
        rows = build_emoji_table(pack.items[info.start : info.end], info.first_index)
        sent = session.sent_in_pack(k)
        shown_sent = sent[:_SENT_SHOWN_MAX]
        hidden = len(sent) - len(shown_sent)

        lines = [f"{self._i(PremiumEmoji.PACK)}<b>{h(pack.title)}</b>"]
        lines += [
            f"№ {n} {content_emoji(item)} — <code>{h(item.custom_emoji_id)}</code>".replace("  ", " ")
            for n, item in shown_sent
        ]
        if hidden:
            lines.append(f"<i>... yana {hidden} ta</i>")

        # HTML fallback jadvali: kod ichidagi raqamlar monospace'da tekislanadi.
        width = len(str(info.end))
        table_lines = [
            "   ".join(f"<code>{i:>{width}}</code> {content_emoji(item) or '·'}" for i, item in filter(None, row))
            for row in rows
        ]
        html = "\n".join(lines) + "\n\n" + "\n".join(table_lines)

        rich = self._explorer_rich(pack, rows, shown_sent, hidden)
        return Screen(html, kb.explorer_keyboard(self.buttons, session, k, info, self.admin_url), rich)

    def _rich_icon(self, role: PremiumEmoji) -> list[object]:
        icon = self.registry.text_icon(role)
        if icon is None:
            return []
        return [RichTextCustomEmoji(custom_emoji_id=icon[0], alternative_text=icon[1]), " "]

    def _explorer_rich(
        self,
        pack: EmojiPack,
        rows: list,
        shown_sent: list[tuple[int, EmojiItem]],
        hidden: int,
    ) -> InputRichMessage:
        def emoji(item: EmojiItem) -> RichTextCustomEmoji | RichTextCode:
            if item.emoji:
                return RichTextCustomEmoji(custom_emoji_id=item.custom_emoji_id, alternative_text=item.emoji)
            return RichTextCode(text=item.custom_emoji_id)

        def cell(index: int, item: EmojiItem) -> RichBlockTableCell:
            return RichBlockTableCell(
                align="center", valign="middle", text=[RichTextBold(text=str(index)), " ", emoji(item)]
            )

        empty = RichBlockTableCell(align="center", valign="middle")
        cells = [[cell(*c) if c is not None else empty for c in row] for row in rows]

        blocks: list = [InputRichBlockSectionHeading(text=[*self._rich_icon(PremiumEmoji.PACK), pack.title], size=3)]
        blocks += [
            InputRichBlockParagraph(text=[f"№ {n} ", emoji(item), " — ", RichTextCode(text=item.custom_emoji_id)])
            for n, item in shown_sent
        ]
        if hidden:
            blocks.append(InputRichBlockParagraph(text=f"... yana {hidden} ta"))
        blocks.append(InputRichBlockTable(cells=cells, is_bordered=True, is_striped=True, is_compact=True))
        return InputRichMessage(blocks=blocks)

    # ---------- emoji tafsiloti ----------

    def detail(self, session: Session, k: int, index: int, page: int) -> Screen:
        pack = session.packs[k]
        item = pack.items[index - 1]
        lines = [
            f"{self._i(PremiumEmoji.INFO)}<b>Custom Emoji</b>",
            "",
            content_emoji(item) or "",
            "",
            f"<b>№ {index}</b> / {pack.total}",
            "",
            "<b>ID:</b>",
            f"<code>{h(item.custom_emoji_id)}</code>",
            "",
            f"<b>Pack:</b> {h(pack.title)}",
        ]
        if not pack.is_virtual:
            lines.append(f"<b>Set:</b> <code>{h(pack.name)}</code>")
            lines.append(f"<b>Havola:</b> {h(pack_link(pack.name))}")
        if item.emoji:
            lines.append(f"<b>Alternativ emoji:</b> {h(item.emoji)}")
        lines.append(f"<b>Turi:</b> {_KIND_LABELS.get(item.kind, h(item.kind))}")
        if item.needs_repainting:
            lines.append("<b>Rang:</b> matn rangiga moslashadi")
        lines += ["", "Tugma kodi uchun tilni tanlang:"]
        keyboard = kb.detail_keyboard(self.buttons, session.sid, k, item, index, page)
        return Screen("\n".join(lines), keyboard)

    # ---------- kod sahifasi ----------

    def code(
        self, session: Session, k: int, index: int, page: int, generated: GeneratedCode
    ) -> Screen:
        pack = session.packs[k]
        item = pack.items[index - 1]
        spec = LANGUAGES[generated.language]
        lines = [
            f"{self._i(spec.icon)}<b>{h(generated.title)}</b>",
            "",
            f"<b>Emoji:</b> {content_emoji(item)} № {index}".rstrip(),
            f"<b>ID:</b> <code>{h(item.custom_emoji_id)}</code>",
            f"<b>Kutubxona:</b> {h(generated.library)}",
            "",
            f'<pre><code class="language-{h(generated.pre_language)}">{h(generated.code)}</code></pre>',
        ]
        if not generated.copy_supported:
            lines.append(
                f"{self._i(PremiumEmoji.INFO)}<i>Kod {len(generated.code)} belgidan iborat. Telegram nusxalash tugmasi "
                "256 belgigacha qo'llaydi: kod blokini bosib nusxalang yoki fayl sifatida oling.</i>"
            )
        lines.append(
            "<i>Reply keyboard uchun ham KeyboardButton'da icon_custom_emoji_id maydoni mavjud (Bot API 10.3).</i>"
        )
        keyboard = kb.code_keyboard(self.buttons, session.sid, k, index, page, generated)
        return Screen("\n".join(lines), keyboard)

    # ---------- button preview ----------

    def preview(self, session: Session, k: int, index: int, page: int, note: str | None = None) -> Screen:
        item = session.packs[k].items[index - 1]
        text = (
            f"{self._i(PremiumEmoji.PREVIEW)}<b>Button Preview</b>\n\n"
            "Quyidagi «Test button» tugmasi <code>icon_custom_emoji_id</code> = "
            f"<code>{h(item.custom_emoji_id)}</code> bilan yaratildi."
        )
        if note:
            text += f"\n\n{self._i(PremiumEmoji.WARNING)}{note}"
        keyboard = kb.preview_keyboard(self.buttons, session.sid, k, item, index, page)
        return Screen(text, keyboard)

    def preview_failed(self, session: Session, k: int, index: int, page: int) -> Screen:
        text = (
            f"{self._i(PremiumEmoji.ERROR)}<b>Button Preview yaratilmadi</b>\n\n"
            "Telegram bu emoji'ni tugma ikonkasi sifatida ishlatishga ruxsat bermadi. "
            "Ikonka faqat Fragment'dan qo'shimcha username sotib olgan botlarda yoki bot egasida "
            "Telegram Premium bo'lganda ishlaydi."
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [self.buttons.back(EmojiCb(s=session.sid, k=k, i=index, p=page).pack(), "Emoji ma'lumotlari")],
                kb.table_row(self.buttons, session.sid, k, index, page),
            ]
        )
        return Screen(text, keyboard)

