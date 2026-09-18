import re
import unittest
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CopyTextButton

from app.handlers import emoji as handlers
from app.services.emoji_service import EmojiService
from tests.helpers import FakeApi, ce, make_set, make_sticker


def fake_message(text: str | None = "x", entities=None, caption=None, caption_entities=None) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.entities = entities
    msg.caption = caption
    msg.caption_entities = caption_entities
    msg.from_user.id = 123
    msg.bot = None
    msg.answer = AsyncMock()
    return msg


def sent_texts(msg: MagicMock) -> list[str]:
    return [c.args[0] for c in msg.answer.await_args_list]


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_plain_text(self) -> None:
        msg = fake_message("hello")
        await handlers.handle_emoji_message(msg, EmojiService(FakeApi()))
        self.assertEqual(sent_texts(msg), [handlers.NOT_CUSTOM_TEXT])

    async def test_api_error_is_friendly(self) -> None:
        msg = fake_message("🔥", [ce("1")])
        await handlers.handle_emoji_message(msg, EmojiService(FakeApi(fail_lookup=True)))
        self.assertEqual(sent_texts(msg), [handlers.API_ERROR_TEXT])

    async def test_unknown_id(self) -> None:
        msg = fake_message("🔥", [ce("404")])
        await handlers.handle_emoji_message(msg, EmojiService(FakeApi()))
        (text,) = sent_texts(msg)
        self.assertIn("ma'lumot bermadi", text)
        self.assertIn("<code>404</code>", text)

    async def test_full_flow_and_ids_callback(self) -> None:
        ids = [str(5368324170671200000 + i) for i in range(120)]
        api = FakeApi(
            stickers={ids[0]: make_sticker(ids[0], set_name="Big"), "9": make_sticker("9", set_name="Small")},
            sets={"Big": make_set("Big", ids), "Small": make_set("Small", ["9", "8"])},
        )
        msg = fake_message("🔥 ❤️", [ce(ids[0], 0), ce("9", 3), ce(ids[0], 6)])
        await handlers.handle_emoji_message(msg, EmojiService(api))

        texts = sent_texts(msg)
        # summary + Big (3 bo'lak) + Small (1)
        self.assertEqual(len(texts), 5)
        self.assertIn("2 ta Custom Emoji topildi", texts[0])
        self.assertIn("SET 1", texts[1])
        self.assertIn("SET 2", texts[4])

        markup = msg.answer.await_args_list[-1].kwargs["reply_markup"]
        buttons = [b for row in markup.inline_keyboard for b in row]
        copy = next(b for b in buttons if b.copy_text is not None)
        self.assertIsInstance(copy.copy_text, CopyTextButton)
        self.assertEqual(copy.copy_text.text, f"{ids[0]}\n9")
        ids_button = next(b for b in buttons if b.callback_data and b.callback_data.startswith("ids:"))

        callback = MagicMock()
        callback.answer = AsyncMock()
        callback.message = fake_message()
        callback.message.__class__ = handlers.Message  # isinstance tekshiruvi uchun
        data = handlers.IdsCallback.unpack(ids_button.callback_data)
        await handlers.on_ids(callback, data)
        id_texts = sent_texts(callback.message)
        self.assertTrue(all("<pre>" in t for t in id_texts))
        found = re.findall(r"^\d+$", "\n".join(re.findall(r"<pre>(.*?)</pre>", "".join(id_texts), re.S)), re.M)
        self.assertEqual(sorted(found), sorted(ids + ["9", "8"]))

    async def test_expired_callback(self) -> None:
        callback = MagicMock()
        callback.answer = AsyncMock()
        await handlers.on_ids(callback, handlers.IdsCallback(token="nope"))
        callback.answer.assert_awaited_once()
        self.assertTrue(callback.answer.await_args.kwargs.get("show_alert"))


if __name__ == "__main__":
    unittest.main()
