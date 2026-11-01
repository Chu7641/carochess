"""Lớp cơ sở và trình quản lý cho các trò chơi một người (Dò mìn, Sudoku...)."""

from __future__ import annotations

import time
from typing import Any

from . import auth


class SoloSession:
    """Phiên chơi một người cơ sở: theo dõi thời gian và ghi điểm khi thắng."""

    GAME: str = ""

    def __init__(self, user_id: int, level: str, *, start_timer: bool = True):
        self.user_id = user_id
        self.level = level
        self.start_mono: float | None = time.monotonic() if start_timer else None
        self.final_ms: int = 0
        self.score_recorded: bool = False
        self.new_record: bool = False
        self.last_active: float = time.time()

    def touch(self):
        self.last_active = time.time()

    @property
    def elapsed_ms(self) -> int:
        if self.start_mono is None:
            return 0
        return max(0, round((time.monotonic() - self.start_mono) * 1000))

    def finish(self, won: bool = False, ms: int | None = None):
        """Kết thúc ván: chốt thời gian cuối; nếu thắng thì ghi điểm một lần."""
        if self.final_ms == 0:
            self.final_ms = max(1, self.elapsed_ms if ms is None else ms)
        if won and not self.score_recorded:
            self.score_recorded = True
            prev_best = auth.solo_best(self.GAME, self.user_id, self.level)
            self.new_record = (prev_best is None) or (self.final_ms < prev_best["ms"])
            auth.record_solo(self.GAME, self.user_id, self.level, self.final_ms)


class SoloManager:
    """Quản lý các ván chơi một người trong bộ nhớ, mỗi tài khoản tối đa 1 ván."""

    def __init__(self, ttl: int):
        self.ttl = ttl
        self.games: dict[int, Any] = {}

    def cleanup(self):
        now = time.time()
        expired = [uid for uid, g in list(self.games.items()) if now - g.last_active > self.ttl]
        for uid in expired:
            self.games.pop(uid, None)

    def new(self, user_id: int, session: Any) -> Any:
        self.cleanup()
        self.games[user_id] = session
        return session

    def get(self, user_id: int) -> Any | None:
        self.cleanup()
        return self.games.get(user_id)

