"""In-memory session store with TTL and a turn cap. Swap for Redis later if needed."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import Message


@dataclass
class _Session:
    messages: list[Message] = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)


class InMemorySessionStore:
    def __init__(self, ttl_s: int = 1800, max_turns: int = 12, clock=time.monotonic) -> None:
        self._ttl = ttl_s
        self._max_messages = max_turns * 2
        self._clock = clock
        self._data: dict[str, _Session] = {}

    def _sweep(self) -> None:
        now = self._clock()
        dead = [k for k, s in self._data.items() if now - s.touched > self._ttl]
        for k in dead:
            del self._data[k]

    def get_history(self, session_id: str) -> list[Message]:
        self._sweep()
        s = self._data.get(session_id)
        if not s:
            return []
        s.touched = self._clock()
        return list(s.messages)

    def append(self, session_id: str, *messages: Message) -> None:
        self._sweep()
        s = self._data.setdefault(session_id, _Session())
        s.messages.extend(messages)
        if len(s.messages) > self._max_messages:
            s.messages = s.messages[-self._max_messages :]
        s.touched = self._clock()

    def clear(self, session_id: str) -> None:
        self._data.pop(session_id, None)
