import re

from app.models.emoji import EmojiItem, EmojiPack
from app.premium_emojis import PremiumEmojiRegistry
from app.services.code_generator_service import CodeGeneratorService, CodeLanguage
from app.services.session_service import Session
from app.utils.formatting import content_emoji, premium_emoji, utf16_len
from app.utils.pagination import get_page
from app.utils.telegram_limits import MESSAGE_TEXT_MAX_CHARS
from app.views import Views

EVIL = '<b>x</b> & <script>"'


def tags_balanced(html: str) -> bool:
    stack: list[str] = []
    for closing, tag in re.findall(r"<(/?)([\w-]+)[^>]*>", html):
        if closing:
            if not stack or stack.pop() != tag:
                return False
        else:
            stack.append(tag)
    return not stack


def make_session(n: int, title: str = "Animals Premium", name: str = "animals_by_example", emoji: str | None = "🔥") -> Session:
    items = tuple(EmojiItem(str(5368324170671200000 + i), emoji, name) for i in range(n))
    return Session(sid="sid", user_id=1, packs=[EmojiPack(name=name, title=title, items=items)])


views = Views(PremiumEmojiRegistry())


def test_premium_emoji_markup_escaped() -> None:
    assert premium_emoji("123", "<x>") == '<tg-emoji emoji-id="123">&lt;x&gt;</tg-emoji>'
    assert content_emoji(EmojiItem("1", None)) == ""


def test_explorer_message_is_title_sent_line_and_table_only() -> None:
    session = make_session(105, title="Telegram Emoji's by @trillio", name="emojiuzbek", emoji="✈️")
    session.sent = [session.packs[0].items[34]]
    screen = views.explorer(session, 0, get_page(105, 2))
    lines = screen.html.split("\n")
    assert lines[0] == "<b>Telegram Emoji's by @trillio</b>"
    assert lines[1] == '№ 35 <tg-emoji emoji-id="5368324170671200034">✈️</tg-emoji> — <code>5368324170671200034</code>'
    assert lines[2] == ""
    assert all(line.startswith("<code>") for line in lines[3:]) and len(lines[3:]) == 5  # 5x5 jadval
    for unwanted in ("Set:", "emojiuzbek", "ta Custom Emoji", "Sahifa", "Yuborilgan", "Raqamni bosing"):
        assert unwanted not in screen.html
    assert tags_balanced(screen.html)

    blocks = screen.rich.blocks
    assert [b.type for b in blocks] == ["heading", "paragraph", "table"]
    assert blocks[0].text == ["Telegram Emoji's by @trillio"]
    number, emoji, dash, code = blocks[1].text
    assert (number, dash, code.text) == ("№ 35 ", " — ", "5368324170671200034")
    assert emoji.custom_emoji_id == "5368324170671200034"


def test_explorer_without_sent_emoji_is_title_and_table() -> None:
    screen = views.explorer(make_session(10), 0, get_page(10, 1))
    assert [b.type for b in screen.rich.blocks] == ["heading", "table"]
    assert screen.html.split("\n")[1] == ""


def test_explorer_html_table_layout() -> None:
    screen = views.explorer(make_session(25), 0, get_page(25, 1))
    rows = [line for line in screen.html.splitlines() if line.startswith("<code>")]
    assert len(rows) == 5 and all(r.count("<code>") == 5 for r in rows)
    assert rows[0].startswith("<code> 1</code>") and "<code> 5</code>" in rows[0]
    assert rows[-1].startswith("<code>21</code>") and "<code>25</code>" in rows[-1]


def test_html_escaping_everywhere() -> None:
    session = make_session(3, title=EVIL, name="Evil", emoji="<i>")
    screens = [
        views.explorer(session, 0, get_page(3, 1)),
        views.detail(session, 0, 1, 1),
        views.code(session, 0, 1, 1, CodeGeneratorService().generate(CodeLanguage.PHP, "1")),
    ]
    for screen in screens:
        assert "<script>" not in screen.html and "<b>x</b>" not in screen.html
        assert tags_balanced(screen.html), screen.html
    assert "&lt;?php" in screens[2].html
    rich = screens[0].rich
    assert rich.blocks[0].text[-1] == EVIL  # rich bloklar strukturali — HTML parse qilinmaydi


def test_detail_contents() -> None:
    html = views.detail(make_session(5), 0, 2, 1).html
    assert "<b>№ 2</b> / 5" in html
    assert "<code>5368324170671200001</code>" in html
    assert '<tg-emoji emoji-id="5368324170671200001">🔥</tg-emoji>' in html
    assert "https://t.me/addemoji/animals_by_example" in html


def test_virtual_pack_has_no_set_link() -> None:
    session = make_session(2)
    session.packs[0] = EmojiPack(name="", title="Yuborilgan emoji'lar", items=session.packs[0].items, is_virtual=True)
    html = views.detail(session, 0, 1, 1).html
    assert "addemoji" not in html and "Set:" not in html


def test_message_limits_worst_case() -> None:
    session = make_session(200, title="T" * 64, name="N" * 64)
    gen = CodeGeneratorService()
    screens = [views.explorer(session, 0, get_page(200, p)) for p in (1, 8)]
    screens.append(views.detail(session, 0, 200, 8))
    screens += [views.code(session, 0, 200, 8, gen.generate(lang, "5368324170671200199")) for lang in CodeLanguage]
    for screen in screens:
        assert utf16_len(screen.html) < MESSAGE_TEXT_MAX_CHARS
        total_buttons = sum(len(r) for r in screen.keyboard.inline_keyboard)
        assert total_buttons <= 100


def test_sent_emoji_other_pack_not_shown_and_many_truncated() -> None:
    session = make_session(40)
    session.sent = [EmojiItem("999", "x", "other")]
    assert "№" not in views.explorer(session, 0, get_page(40, 1)).html
    session.sent = list(session.packs[0].items[:15])
    html = views.explorer(session, 0, get_page(40, 1)).html
    assert html.count("№ ") == 10 and "yana 5 ta" in html
    assert utf16_len(html) < MESSAGE_TEXT_MAX_CHARS
