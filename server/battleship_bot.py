"""Quản lý bot hải chiến chạy ở luồng nền cho một phòng BattleshipRoom."""

from __future__ import annotations

import logging
from typing import Any

from battleship_game import BATTLESHIP_LEVELS, BattleshipBot
from server.bot_driver import ThreadedBotDriver
from server.battleship_room import BattleshipRoom

log = logging.getLogger("battleship.bot")


class BattleshipBotDriver(ThreadedBotDriver):
    """Điều phối bot hải chiến ở luồng nền cho BattleshipRoom."""

    name = "hải chiến"
    log = log

    def __init__(self, room: BattleshipRoom, loop, on_change):
        super().__init__(room, loop, on_change)
        self.engine = BattleshipBot(level=room.level)

    def can_think(self) -> bool:
        return getattr(self.room, "phase", "") == "playing" and self.room.started

    def make_input(self) -> Any:
        return self.room.bot_view()

    def compute(self, data: Any, cancel_event) -> Any:
        move = self.engine.choose(data, cancel_event)
        delay = BATTLESHIP_LEVELS[self.room.level][1]
        if not cancel_event.is_set():
            cancel_event.wait(delay)
        return move

    def apply(self, res: Any):
        r, c = res
        try:
            self.room.fire(self.room.bot_side, r, c)
        except Exception as exc:
            self.log.warning("Bot hải chiến bắn không hợp lệ: %s", exc)
