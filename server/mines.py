"""Quản lý các ván dò mìn đang chơi trong bộ nhớ máy chủ."""

from __future__ import annotations

import time
from typing import Any

from minesweeper_game import MINES_LEVELS, MinesweeperGame
from .solo import SoloManager, SoloSession

GAME_TTL = 3600  # 1 giờ không tương tác thì xóa ván


class ActiveMinesGame(SoloSession):
    GAME = "minesweeper"

    def __init__(self, user_id: int, level: str, game: MinesweeperGame | None = None):
        super().__init__(user_id, level, start_timer=False)
        if game is not None:
            self.game = game
        else:
            _, rows, cols, mines = MINES_LEVELS[level]
            self.game = MinesweeperGame(rows, cols, mines)

    @property
    def elapsed_ms(self) -> int:
        if self.start_mono is None:
            return 0
        if self.game.state in ("won", "lost") and self.final_ms > 0:
            return self.final_ms
        return max(0, round((time.monotonic() - self.start_mono) * 1000))

    def on_reveal(self, r: int, c: int):
        self.touch()
        if self.game.state in ("won", "lost"):
            raise ValueError("Ván đã kết thúc.")

        if self.start_mono is None:
            self.start_mono = time.monotonic()

        self.game.reveal(r, c)

        if self.game.state in ("won", "lost"):
            self.finish(won=(self.game.state == "won"))

    def on_flag(self, r: int, c: int):
        self.touch()
        if self.game.state in ("won", "lost"):
            raise ValueError("Ván đã kết thúc.")
        self.game.toggle_flag(r, c)

    def snapshot(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "rows": self.game.rows,
            "cols": self.game.cols,
            "mines": self.game.mines,
            "minesLeft": self.game.mines_left,
            "state": self.game.state,
            "cells": self.game.view(),
            "elapsedMs": self.elapsed_ms,
            "newRecord": self.new_record,
        }


_manager = SoloManager(GAME_TTL)
_ACTIVE_GAMES = _manager.games


def cleanup_games():
    _manager.cleanup()


def new_game(user_id: int, level: str, game: MinesweeperGame | None = None) -> ActiveMinesGame:
    cleanup_games()
    if level not in MINES_LEVELS:
        raise ValueError("Cấp độ không hợp lệ.")
    return _manager.new(user_id, ActiveMinesGame(user_id, level, game=game))


def get_game(user_id: int) -> ActiveMinesGame | None:
    cleanup_games()
    return _manager.get(user_id)
