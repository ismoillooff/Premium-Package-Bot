import re
import unittest

from app.services.emoji_service import EmojiInfo, EmojiPack, LookupResult
from app.utils.formatting import (
    MESSAGE_LIMIT,
    chunk_lines,
    copy_payload,
    emoji_line,
    format_ids_messages,
    format_pack_messages,
    format_summary,
    utf16_len,
)


def pack(n: int, name: str = "Big", title: str = "Big Pack") -> EmojiPack:
    return EmojiPack(
        name=name,
        title=title,
        emojis=tuple(EmojiInfo(str(5368324170671200000 + i), "🔥", name) for i in range(n)),
    )


def tags_balanced(html: str) -> bool:
    stack: list[str] = []
    for closing, tag in re.findall(r"<(/?)(\w+)[^>]*>", html):
        if closing:
            if not stack or stack.pop() != tag:
                return False
        else:
            stack.append(tag)
    return not stack


class FormattingTests(unittest.TestCase):
    def test_emoji_line(self) -> None:
        self.assertEqual(emoji_line(1, EmojiInfo("5", "🔥")), "1. 🔥 — <code>5</code>")
        self.assertEqual(emoji_line(2, EmojiInfo("5")), "2. <code>5</code>")

    def test_html_escaped(self) -> None:
        evil = EmojiPack(name="Evil", title="<b>x</b> & <script>", emojis=(EmojiInfo("1", "<i>", "Evil"),))
        text = "\n".join(format_pack_messages(evil))
        self.assertIn("&lt;b&gt;x&lt;/b&gt; &amp; &lt;script&gt;", text)
        self.assertIn("&lt;i&gt;", text)
        self.assertNotIn("<script>", text)
        self.assertTrue(tags_balanced(text))

    def test_single_summary(self) -> None:
        p = pack(24, name="MyEmojiPack", title="My Emoji Pack")
        result = LookupResult(requested=[p.emojis[0]], packs=[p])
        text = format_summary(result)
        self.assertIn("Custom Emoji topildi", text)
        self.assertIn("<code>5368324170671200000</code>", text)
        self.assertIn("24 ta Custom Emoji", text)
        self.assertIn("MyEmojiPack", text)

    def test_summary_without_set(self) -> None:
        item = EmojiInfo("7", "⭐")
        text = format_summary(LookupResult(requested=[item], orphans=[item]))
        self.assertIn("aniqlanmadi", text)
        self.assertIn("set nomini qaytarmadi", text)

    def test_summary_failed_set_warning(self) -> None:
        item = EmojiInfo("7", "⭐", "Gone")
        text = format_summary(LookupResult(requested=[item], orphans=[item], failed_sets=["Gone"]))
        self.assertIn("to'liq pack ma'lumotini bermadi", text)
        self.assertIn("<code>7</code>", text)

    def test_large_pack_chunked(self) -> None:
        messages = format_pack_messages(pack(200))
        self.assertEqual(len(messages), 4)
        self.assertIn("1–50", messages[0])
        self.assertIn("51–100", messages[1])
        self.assertIn("151–200", messages[3])
        for m in messages:
            self.assertLessEqual(utf16_len(m), MESSAGE_LIMIT)
            self.assertTrue(tags_balanced(m))
        joined = "\n".join(messages)
        self.assertEqual(len(re.findall(r"<code>\d+</code>", joined)), 200)

    def test_chunk_respects_char_limit(self) -> None:
        lines = [f"{i}. " + "x" * 300 for i in range(30)]
        chunks = chunk_lines(lines, lambda s, e: f"H {s}–{e}", max_items=50, limit=1000)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(sum(c.count("x" * 300) for c in chunks), 30)
        for c in chunks:
            self.assertLessEqual(utf16_len(c), 1000)

    def test_ids_messages(self) -> None:
        p = pack(200)
        messages = format_ids_messages(LookupResult(packs=[p]))
        self.assertEqual(len(messages), 2)
        for m in messages:
            self.assertLessEqual(utf16_len(m), MESSAGE_LIMIT)
            self.assertTrue(tags_balanced(m))
        body = "".join(re.findall(r"<pre>(.*?)</pre>", "".join(messages), re.S))
        self.assertEqual(len(re.findall(r"\d{19}", body)), 200)

    def test_copy_payload_limit(self) -> None:
        self.assertEqual(copy_payload(["1", "2"]), "1\n2")
        self.assertIsNone(copy_payload([]))
        self.assertIsNone(copy_payload(["5368324170671202286"] * 20))


if __name__ == "__main__":
    unittest.main()
