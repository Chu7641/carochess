"""Quản lý các ván dò mìn đang chơi trong bộ nhớ máy chủ."""

from __future__ import annotations

import time
from typing import Any

from minesweeper_game import MINES_LEVELS, MinesweeperGame
from . import auth

GAME_TTL = 3600  # 1 giờ không tương tác thì xóa ván


class ActiveMinesGame:
    def __init__(self, user_id: int, level: str, game: MinesweeperGame | None = None):
        self.user_id = user_id
        self.level = level
        if game is not None:
            self.game = game
        else:
            _, rows, cols, mines = MINES_LEVELS[level]
            self.game = MinesweeperGame(rows, cols, mines)
        self.start_mono: float | None = None
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
        if self.game.state in ("won", "lost"):
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
            self.final_ms = max(1, round((time.monotonic() - self.start_mono) * 1000))
            if self.game.state == "won" and not self.score_recorded:
                self.score_recorded = True
                prev_best = auth.mines_best(self.user_id, self.level)
                self.new_record = (prev_best is None) or (self.final_ms < prev_best["ms"])
                auth.record_mines(self.user_id, self.level, self.final_ms)

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


# user_id -> ActiveMinesGame (mỗi tài khoản đúng 1 ván)
_ACTIVE_GAMES: dict[int, ActiveMinesGame] = {}


def cleanup_games():
    now = time.time()
    expired = [uid for uid, g in list(_ACTIVE_GAMES.items()) if now - g.last_active > GAME_TTL]
    for uid in expired:
        _ACTIVE_GAMES.pop(uid, None)


def new_game(user_id: int, level: str, game: MinesweeperGame | None = None) -> ActiveMinesGame:
    cleanup_games()
    if level not in MINES_LEVELS:
        raise ValueError("Cấp độ không hợp lệ.")
    active = ActiveMinesGame(user_id, level, game=game)
    _ACTIVE_GAMES[user_id] = active
    return active


def get_game(user_id: int) -> ActiveMinesGame | None:
    cleanup_games()
    return _ACTIVE_GAMES.get(user_id)

