"""Oddiy in-memory TTL kesh (tashqi dependency'siz)."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")

_MISSING = object()


class TTLCache(Generic[K, V]):
    """Muddati o'tgan yozuvlarni o'chiradigan, hajmi cheklangan kesh.

    Bitta asyncio event loop ichida ishlatiladi, shuning uchun lock kerak emas.
    """

    def __init__(self, ttl: float, max_size: int = 1024) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K, default: V | None = None) -> V | None:
        item = self._data.get(key, _MISSING)
        if item is _MISSING:
            return default
        expires_at, value = item  # type: ignore[misc]
        if expires_at < time.monotonic():
            self._data.pop(key, None)
            return default
        return value

    def __contains__(self, key: object) -> bool:
        return self.get(key, _MISSING) is not _MISSING  # type: ignore[arg-type]

    def set(self, key: K, value: V) -> None:
        if self._ttl <= 0:
            return
        self._data[key] = (time.monotonic() + self._ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)
