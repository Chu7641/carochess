"""Quản lý bot cờ tướng chạy ở luồng nền cho một phòng XiangqiRoom."""

from __future__ import annotations

import logging
from typing import Any

from xiangqi_game import XiangqiBot
from server.bot_driver import ThreadedBotDriver
from server.xiangqi_room import XiangqiRoom

log = logging.getLogger("xiangqi.bot")


class XiangqiBotDriver(ThreadedBotDriver):
    """Điều phối bot cờ tướng ở luồng nền cho XiangqiRoom."""

    name = "cờ tướng"
    log = log

    def __init__(self, room: XiangqiRoom, loop, on_change):
        super().__init__(room, loop, on_change)
        self.engine = XiangqiBot(level=room.level)

    def make_input(self) -> Any:
        return self.room.engine.copy()

    def compute(self, data: Any, cancel_event) -> Any:
        return self.engine.choose(data, cancel_event)

    def apply(self, res: Any):
        room = self.room
        room.stats_nodes = res.nodes
        room.stats_elapsed = res.elapsed
        room.stats_depth = res.depth
        room.stats_score = res.score

        if res.move is None:
            self.log.warning("Bot cờ tướng không tìm được nước đi (hết nước).")
        else:
            try:
                room.move(room.bot_side, *res.move)
            except Exception as exc:
                self.log.warning("Bot cờ tướng đánh nước không hợp lệ: %s", exc)
