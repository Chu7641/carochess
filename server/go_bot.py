"""Quản lý bot cờ vây chạy ở luồng nền cho một phòng GoRoom."""

from __future__ import annotations

import logging
from typing import Any

from go_game import GoBot
from server.bot_driver import ThreadedBotDriver
from server.go_room import GoRoom

log = logging.getLogger("go.bot")


class GoBotDriver(ThreadedBotDriver):
    """Điều phối bot cờ vây ở luồng nền cho GoRoom."""

    name = "cờ vây"
    log = log

    def __init__(self, room: GoRoom, loop, on_change):
        super().__init__(room, loop, on_change)
        self.engine = GoBot(level=room.level)

    def make_input(self) -> Any:
        return self.room.engine.copy()

    def compute(self, data: Any, cancel_event) -> Any:
        return self.engine.choose(data, self.room.bot_side, cancel_event)

    def apply(self, res: Any):
        room = self.room
        room.stats_nodes = res.nodes
        room.stats_elapsed = res.elapsed

        if res.is_pass or res.move is None:
            room.pass_turn(room.bot_side)
        else:
            try:
                room.place(room.bot_side, *res.move)
            except Exception as exc:
                self.log.warning("Bot cờ vây đánh nước không hợp lệ: %s", exc)
                room.pass_turn(room.bot_side)
