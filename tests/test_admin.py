"""Admin tugmasi havolasini aniqlash va ADMIN_ID konfiguratsiyasi."""

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChat
from aiogram.types import ChatFullInfo

from app.bot import resolve_admin_url
from app.config import ConfigError, load_settings


class ChatBot:
    def __init__(self, chat: ChatFullInfo | None) -> None:
        self.chat = chat

    async def get_chat(self, chat_id: int) -> ChatFullInfo:
        if self.chat is None:
            raise TelegramBadRequest(GetChat(chat_id=chat_id), "Bad Request: chat not found")
        return self.chat


def chat(username: str | None = None, private_forwards: bool | None = None) -> ChatFullInfo:
    return ChatFullInfo(
        id=7000454062, type="private", username=username, has_private_forwards=private_forwards,
        accent_color_id=0, max_reaction_count=11, accepted_gift_types={
            "unlimited_gifts": True, "limited_gifts": True, "unique_gifts": True,
            "premium_subscription": True, "gifts_from_channels": True,
        },
    )


async def test_username_link_preferred() -> None:
    assert await resolve_admin_url(ChatBot(chat("ismoillooff", True)), 7000454062) == "https://t.me/ismoillooff"


async def test_id_link_when_no_username_and_allowed() -> None:
    assert await resolve_admin_url(ChatBot(chat(None, None)), 7000454062) == "tg://user?id=7000454062"


async def test_hidden_when_privacy_blocks_id_link() -> None:
    assert await resolve_admin_url(ChatBot(chat(None, True)), 7000454062) is None


async def test_hidden_when_admin_unknown_or_unset() -> None:
    assert await resolve_admin_url(ChatBot(None), 7000454062) is None
    assert await resolve_admin_url(ChatBot(None), None) is None


def test_admin_id_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.load_dotenv", lambda: None)
    monkeypatch.setenv("BOT_TOKEN", "123456:" + "A" * 35)
    monkeypatch.setenv("ADMIN_ID", "7000454062")
    assert load_settings().admin_id == 7000454062
    monkeypatch.setenv("ADMIN_ID", "")
    assert load_settings().admin_id is None
    monkeypatch.setenv("ADMIN_ID", "abc")
    with pytest.raises(ConfigError):
        load_settings()
