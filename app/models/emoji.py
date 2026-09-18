from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EmojiItem:
    custom_emoji_id: str
    emoji: str | None = None
    set_name: str | None = None
    kind: str = "static"  # static | animated | video
    needs_repainting: bool = False


@dataclass(frozen=True, slots=True)
class EmojiPack:
    """Telegram custom emoji set'i (yoki seti aniqlanmagan emoji'lar guruhi).

    `items` pack'dagi original tartibda; global index = pozitsiya + 1.
    """

    name: str
    title: str
    items: tuple[EmojiItem, ...]
    is_virtual: bool = False  # True — Telegram set emas, foydalanuvchi yuborgan emoji'lar

    @property
    def total(self) -> int:
        return len(self.items)

    def item(self, index: int) -> EmojiItem | None:
        """1 dan boshlanuvchi global index bo'yicha element."""
        if 1 <= index <= len(self.items):
            return self.items[index - 1]
        return None


@dataclass(slots=True)
class LookupResult:
    requested: list[EmojiItem] = field(default_factory=list)
    """Foydalanuvchi yuborgan va Telegram tasdiqlagan emoji'lar (yuborilgan tartibda)."""
    missing_ids: list[str] = field(default_factory=list)
    """Telegram hech qanday ma'lumot bermagan ID'lar."""
    packs: list[EmojiPack] = field(default_factory=list)
    orphans: list[EmojiItem] = field(default_factory=list)
    """Seti aniqlanmagan yoki yuklanmagan emoji'lar."""
    failed_sets: list[str] = field(default_factory=list)
    skipped_sets: list[str] = field(default_factory=list)
