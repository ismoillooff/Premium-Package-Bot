"""Har bir foydalanuvchining faol explorer sessiyasi (in-memory, TTL bilan).

Sessiya user_id bo'yicha saqlanadi, callback'dagi sessiya ID bilan solishtiriladi:
boshqa foydalanuvchi yoki eski menyu tugmasi sessiyani o'zgartira olmaydi.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from app.constants import SESSION_MAX_USERS, SESSION_TTL_SECONDS
from app.models.emoji import EmojiItem, EmojiPack
from app.services.cache_service import TTLCache


@dataclass(slots=True)
class Session:
    sid: str
    user_id: int
    packs: list[EmojiPack]
    notes: list[str] = field(default_factory=list)
    """Foydalanuvchiga ko'rsatiladigan ogohlantirishlar (oddiy matn; render paytida escape qilinadi)."""
    sent: list[EmojiItem] = field(default_factory=list)
    """Foydalanuvchi misol sifatida yuborgan emoji'lar (yuborilgan tartibda)."""

    def pack(self, k: int) -> EmojiPack | None:
        if 0 <= k < len(self.packs):
            return self.packs[k]
        return None

    def sent_in_pack(self, k: int) -> list[tuple[int, EmojiItem]]:
        """Yuborilgan emoji'lardan shu pack'dagilari: (pack ichidagi global raqam, element)."""
        pack = self.pack(k)
        if pack is None:
            return []
        positions = {item.custom_emoji_id: n for n, item in enumerate(pack.items, start=1)}
        return [(positions[s.custom_emoji_id], s) for s in self.sent if s.custom_emoji_id in positions]


class SessionStore:
    def __init__(self, ttl: float = SESSION_TTL_SECONDS, max_users: int = SESSION_MAX_USERS) -> None:
        self._sessions: TTLCache[int, Session] = TTLCache(ttl=ttl, max_size=max_users)

    def create(
        self,
        user_id: int,
        packs: list[EmojiPack],
        notes: list[str] | None = None,
        sent: list[EmojiItem] | None = None,
    ) -> Session:
        session = Session(
            sid=secrets.token_urlsafe(4), user_id=user_id, packs=packs, notes=notes or [], sent=list(sent or [])
        )
        self._sessions.set(user_id, session)
        return session

    def get(self, user_id: int, sid: str) -> Session | None:
        session = self._sessions.get(user_id)
        if session is None or session.sid != sid or session.user_id != user_id:
            return None
        self._sessions.set(user_id, session)  # faollikda muddatni uzaytirish
        return session

    def drop(self, user_id: int) -> bool:
        existed = user_id in self._sessions
        self._sessions.delete(user_id)
        return existed
