"""Premium UI qoidalari: oddiy Unicode emoji yo'q; ikonkalar faqat registry orqali; Telegram rad etsa — toza matn."""

import re
from pathlib import Path

import pytest

from app.premium_emojis import REQUIRED_ROLES, PremiumEmoji, PremiumEmojiRegistry, env_var_name
from app.views import Views
from tests.conftest import FakeBot, FakeTelegram, Harness, ce, eid, make_sticker, pack_tg

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Emoji / piktogramma diapazonlari (strelkalar, dingbat'lar, variation selector, ZWJ ham).
EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"
    "\u2190-\u21ff"
    "\u2300-\u23ff"
    "\u2460-\u24ff"
    "\u25a0-\u27bf"
    "\u2900-\u297f"
    "\u2b00-\u2bff"
    "\u3030\u303d\u3297\u3299"
    "\ufe0f\u200d\u20e3"
    "]"
)

UI_ICON_IDS = {role: str(9_000_000_000_000_000_000 + n) for n, role in enumerate(PremiumEmoji)}


def configured_registry() -> PremiumEmojiRegistry:
    registry = PremiumEmojiRegistry(UI_ICON_IDS)
    for role, value in UI_ICON_IDS.items():
        registry.assign(role, value, alternative="\u2b50")  # testdagi alternativ belgi (Telegram'dan keladi)
    return registry


def ui_texts(screen_text: str) -> str:
    """Pack kontenti UI emas — tekshiruvdan chiqariladi: <tg-emoji> ichidagi alternativ belgilar va
    emoji'ning Telegram bergan alternativ belgisi (metama'lumot qatori)."""
    text = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", "", screen_text)
    return re.sub(r"<b>Alternativ emoji:</b>.*", "", text)


def test_no_standard_unicode_emoji_in_ui_strings() -> None:
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if EMOJI_RE.search(line):
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{lineno}: {line.strip()}")
    assert offenders == []


def test_emoji_regex_catches_forbidden_samples() -> None:
    for sample in ["📦", "✨", "🔥", "👁", "📋", "🔄", "⬅️", "➡️", "🐍", "💎", "⚠️", "❌", "✅", "☕"]:
        assert EMOJI_RE.search(sample), sample
    for allowed in ["—", "…", "·", "«»", "№", "Hammasini ko'rish"]:
        assert not EMOJI_RE.search(allowed), allowed


# ---------- registry ----------


def test_registry_reports_missing_and_invalid() -> None:
    registry = PremiumEmojiRegistry({PremiumEmoji.COPY: "abc", PremiumEmoji.BACK: "123", PremiumEmoji.NEXT: "123"})
    problems = registry.problems()
    assert "Premium emoji ID for COPY is not configured" in problems  # raqam emas -> e'tiborsiz
    assert registry.get(PremiumEmoji.BACK) == "123"
    assert any("duplicates" in p for p in problems)
    assert len([p for p in problems if "not configured" in p]) == len(REQUIRED_ROLES) - 2


def test_registry_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(env_var_name(PremiumEmoji.COPY), "5368324170671202286")
    registry = PremiumEmojiRegistry.from_sources({role: "" for role in PremiumEmoji})
    assert registry.get(PremiumEmoji.COPY) == "5368324170671202286"
    assert registry.get(PremiumEmoji.BACK) is None


async def test_registry_verify_gets_alternative_and_drops_unknown() -> None:
    tg = FakeTelegram(stickers={"111": make_sticker("111", emoji="\u2b50", set_name=None)})
    registry = PremiumEmojiRegistry({PremiumEmoji.COPY: "111", PremiumEmoji.BACK: "222"})
    assert registry.text_icon(PremiumEmoji.COPY) is None  # alternativ belgi hali noma'lum
    await registry.verify(FakeBot(tg))
    assert registry.text_icon(PremiumEmoji.COPY) == ("111", "\u2b50")
    assert registry.get(PremiumEmoji.BACK) is None


# ---------- ekranlar ----------


def test_unconfigured_ui_is_clean_text() -> None:
    views = Views(PremiumEmojiRegistry())
    for screen in (views.start(), views.help(), views.expired(), views.not_custom(), views.api_error()):
        assert "<tg-emoji" not in screen.html
        assert not EMOJI_RE.search(screen.html)
        for row in screen.keyboard.inline_keyboard if screen.keyboard else []:
            for button in row:
                assert button.icon_custom_emoji_id is None and not EMOJI_RE.search(button.text)


def test_configured_ui_uses_premium_emoji() -> None:
    views = Views(configured_registry())
    start = views.start().html
    assert f'<tg-emoji emoji-id="{UI_ICON_IDS[PremiumEmoji.HOME]}">' in start
    assert views.expired().keyboard.inline_keyboard[0][0].icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.REFRESH]
    assert views.error("x").html.startswith(f'<tg-emoji emoji-id="{UI_ICON_IDS[PremiumEmoji.ERROR]}">')


async def test_configured_flow_icons_on_every_ui_button() -> None:
    h = Harness(pack_tg(45), configured_registry())
    await h.send_text("x", [ce(eid(0))])
    heading = h.last.rich.blocks[0]
    assert heading.text[0].custom_emoji_id == UI_ICON_IDS[PremiumEmoji.PACK]
    assert h.button("Yuborilgan emojni nusxalash").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.COPY]
    assert h.button("Keyingi").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.NEXT]
    await h.click(h.button("Keyingi").callback_data)
    assert h.button("Oldingi").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.PREVIOUS]
    assert h.button("2 / 2").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.PAGE]

    await h.click(h.button("30").callback_data)
    expected = {
        "Python": PremiumEmoji.PYTHON,
        "JavaScript": PremiumEmoji.JAVASCRIPT,
        "TypeScript": PremiumEmoji.TYPESCRIPT,
        "PHP": PremiumEmoji.PHP,
        "Java": PremiumEmoji.JAVA,
        "Go": PremiumEmoji.GO,
        "cURL": PremiumEmoji.CURL,
        "ID'ni nusxalash": PremiumEmoji.COPY,
        "Jadvalga qaytish": PremiumEmoji.TABLE,
        "Button Preview": PremiumEmoji.PREVIEW,
        "Ro'yxat yaratish": PremiumEmoji.LIST_CREATE,
    }
    for label, role in expected.items():
        assert h.button(label).icon_custom_emoji_id == UI_ICON_IDS[role], label
    assert not EMOJI_RE.search(ui_texts(h.last.text))
    for button in h.buttons():
        assert not EMOJI_RE.search(button.text)


async def test_dropped_custom_emoji_rerenders_without_icons() -> None:
    # Bot egasida Premium yo'q: Telegram entity'ni olib tashlaydi -> alternativ Unicode belgi qolmasligi kerak.
    h = Harness(FakeTelegram(drop_custom_emoji=True), configured_registry())
    await h.send_text("/start")
    assert "<tg-emoji" not in h.last.text
    assert not h.registry.text.supported


async def test_rejected_button_icons_fall_back_to_text() -> None:
    h = Harness(pack_tg(30, reject_icons=True), configured_registry())
    await h.send_text("x", [ce(eid(0))])
    assert h.button("Keyingi").icon_custom_emoji_id is None
    assert not h.registry.icons.supported


async def test_dropped_button_icons_learned() -> None:
    h = Harness(pack_tg(10, drop_icons=True), configured_registry())
    await h.send_text("x", [ce(eid(0))])
    assert not h.registry.icons.supported


def test_configured_language_icons_are_real_ids() -> None:
    # Foydalanuvchi bergan ID'lar (Telegram'da tekshirilgan, dev_emojis_solid pack'i).
    from app.premium_emojis import PREMIUM_EMOJIS

    assert PREMIUM_EMOJIS[PremiumEmoji.PYTHON] == "5300928913956938544"
    assert PREMIUM_EMOJIS[PremiumEmoji.JAVASCRIPT] == "5300896259320586992"
    assert PREMIUM_EMOJIS[PremiumEmoji.TYPESCRIPT] == "5300896259320586992"
    assert PREMIUM_EMOJIS[PremiumEmoji.PHP] == "5303045701473671851"
    assert PREMIUM_EMOJIS[PremiumEmoji.JAVA] == "5301179216061015693"
    assert PREMIUM_EMOJIS[PremiumEmoji.GO] == "5300888829027165969"
    assert PREMIUM_EMOJIS[PremiumEmoji.CURL] == "5300884628549149586"
    # Navigatsiya (tgiosicons pack'i).
    assert PREMIUM_EMOJIS[PremiumEmoji.NEXT] == "6037622221625626773"
    assert PREMIUM_EMOJIS[PremiumEmoji.PREVIOUS] == "6039539366177541657"
    assert PREMIUM_EMOJIS[PremiumEmoji.TABLE] == "6037475557082403885"
    assert PREMIUM_EMOJIS[PremiumEmoji.PAGE] == "5767244474040192942"
    assert PREMIUM_EMOJIS[PremiumEmoji.COPY] == "6034969813032374911"
    assert PREMIUM_EMOJIS[PremiumEmoji.FILE] == "5766994197705921104"
    assert PREMIUM_EMOJIS[PremiumEmoji.LIST] == "5766994197705921104"
    assert PREMIUM_EMOJIS[PremiumEmoji.PREVIEW] == "6037397706505195857"
    assert PREMIUM_EMOJIS[PremiumEmoji.LIST_CREATE] == "6041919344995209164"
    assert PREMIUM_EMOJIS[PremiumEmoji.ADMIN] == "5368424251999134211"


async def test_table_icon_only_on_table_button() -> None:
    h = Harness(pack_tg(30), configured_registry())
    await h.send_text("x", [ce(eid(0))])
    await h.click(h.button("1").callback_data)
    await h.click(h.button("Python").callback_data)
    assert h.button("Jadvalga qaytish").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.TABLE]
    assert h.button("Emoji ma'lumotlari").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.BACK]


async def test_every_copy_button_uses_copy_icon() -> None:
    h = Harness(pack_tg(30), configured_registry())
    await h.send_text("x", [ce(eid(0))])
    copy_ids = [UI_ICON_IDS[PremiumEmoji.COPY]]
    assert h.button("Yuborilgan emojni nusxalash").icon_custom_emoji_id in copy_ids
    await h.click(h.button("1").callback_data)
    assert h.button("ID'ni nusxalash").icon_custom_emoji_id in copy_ids
    await h.click(h.button("Python").callback_data)
    assert h.button("Button kodini nusxalash").icon_custom_emoji_id in copy_ids
    for button in h.buttons():
        if button.copy_text is not None:
            assert button.icon_custom_emoji_id in copy_ids, button.text


async def test_list_type_buttons_use_list_icons() -> None:
    h = Harness(pack_tg(30), configured_registry())
    await h.send_text("x", [ce(eid(0))])
    await h.click(h.button("1").callback_data)
    await h.click(h.button("Python").callback_data)
    assert h.button("Kodni fayl sifatida olish").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.FILE]


async def test_admin_button_icon() -> None:
    h = Harness(pack_tg(30), configured_registry())
    h.dp["views"].admin_url = "https://t.me/admin_username"
    await h.send_text("x", [ce(eid(0))])
    assert h.button("Admin").icon_custom_emoji_id == UI_ICON_IDS[PremiumEmoji.ADMIN]
