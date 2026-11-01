"""Quản lý các ván Sudoku đang chơi trong bộ nhớ máy chủ."""

from __future__ import annotations

import time
from typing import Any

from sudoku_game import SUDOKU_LEVELS, SudokuGame, generate
from .solo import SoloManager, SoloSession

GAME_TTL = 7200  # 2 giờ không tương tác thì xóa ván


class ActiveSudokuGame(SoloSession):
    GAME = "sudoku"

    def __init__(self, user_id: int, level: str, game: SudokuGame | None = None):
        super().__init__(user_id, level, start_timer=True)
        if game is not None:
            self.game = game
        else:
            puzzle, solution = generate(level)
            self.game = SudokuGame(puzzle, solution)
        self.penalty_ms: int = 0
        self.hints_used: int = 0

    @property
    def elapsed_ms(self) -> int:
        if self.game.solved and self.final_ms > 0:
            return self.final_ms
        return max(0, round((time.monotonic() - self.start_mono) * 1000) + self.penalty_ms)

    def _check_and_record_win(self):
        if self.game.solved:
            self.finish(won=True)

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


_manager = SoloManager(GAME_TTL)
_ACTIVE_GAMES = _manager.games


def cleanup_games():
    _manager.cleanup()


def new_game(user_id: int, level: str, game: SudokuGame | None = None) -> ActiveSudokuGame:
    cleanup_games()
    if not isinstance(level, str) or level not in SUDOKU_LEVELS:
        raise ValueError("Cấp độ không hợp lệ.")
    return _manager.new(user_id, ActiveSudokuGame(user_id, level, game=game))


def get_game(user_id: int) -> ActiveSudokuGame | None:
    cleanup_games()
    return _manager.get(user_id)
