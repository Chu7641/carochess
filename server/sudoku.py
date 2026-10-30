"""Quản lý các ván Sudoku đang chơi trong bộ nhớ máy chủ."""

from __future__ import annotations

import time
from typing import Any

from sudoku_game import SUDOKU_LEVELS, SudokuGame, generate
from . import auth

GAME_TTL = 7200  # 2 giờ không tương tác thì xóa ván


class ActiveSudokuGame:
    def __init__(self, user_id: int, level: str, game: SudokuGame | None = None):
        self.user_id = user_id
        self.level = level
        if game is not None:
            self.game = game
        else:
            puzzle, solution = generate(level)
            self.game = SudokuGame(puzzle, solution)
        self.start_mono: float = time.monotonic()
        self.penalty_ms: int = 0
        self.hints_used: int = 0
        self.final_ms: int = 0
        self.score_recorded: bool = False
        self.new_record: bool = False
        self.last_active: float = time.time()

    def touch(self):
        self.last_active = time.time()

    @property
    def elapsed_ms(self) -> int:
        if self.game.solved:
            return self.final_ms
        return max(0, round((time.monotonic() - self.start_mono) * 1000) + self.penalty_ms)

    def _check_and_record_win(self):
        if self.game.solved and not self.score_recorded:
            self.score_recorded = True
            self.final_ms = max(1, round((time.monotonic() - self.start_mono) * 1000) + self.penalty_ms)
            prev_best = auth.sudoku_best(self.user_id, self.level)
            self.new_record = (prev_best is None) or (self.final_ms < prev_best["ms"])
            auth.record_sudoku(self.user_id, self.level, self.final_ms)

    def on_set(self, r: int, c: int, v: int):
        self.touch()
        if self.game.solved:
            raise ValueError("Ván đã kết thúc.")
        self.game.set_cell(r, c, v)
        self._check_and_record_win()

    def on_hint(self) -> tuple[int, int, int]:
        self.touch()
        if self.game.solved:
            raise ValueError("Ván đã kết thúc.")
        self.penalty_ms += 30000  # Phạt 30 giây vào thời gian
        self.hints_used += 1
        res = self.game.hint()
        self._check_and_record_win()
        return res

    def snapshot(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "given": self.game.given,
            "grid": self.game.grid,
            "conflicts": self.game.conflicts(),
            "solved": self.game.solved,
            "elapsedMs": self.elapsed_ms,
            "hints": self.hints_used,
            "newRecord": self.new_record,
        }


# user_id -> ActiveSudokuGame (mỗi tài khoản đúng 1 ván)
_ACTIVE_GAMES: dict[int, ActiveSudokuGame] = {}


def cleanup_games():
    now = time.time()
    expired = [uid for uid, g in list(_ACTIVE_GAMES.items()) if now - g.last_active > GAME_TTL]
    for uid in expired:
        _ACTIVE_GAMES.pop(uid, None)


def new_game(user_id: int, level: str, game: SudokuGame | None = None) -> ActiveSudokuGame:
    cleanup_games()
    if not isinstance(level, str) or level not in SUDOKU_LEVELS:
        raise ValueError("Cấp độ không hợp lệ.")
    active = ActiveSudokuGame(user_id, level, game=game)
    _ACTIVE_GAMES[user_id] = active
    return active


def get_game(user_id: int) -> ActiveSudokuGame | None:
    cleanup_games()
    return _ACTIVE_GAMES.get(user_id)

