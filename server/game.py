"""Trạng thái một phòng chơi. Luật thắng dùng chung với caro_game."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from caro_game import EMPTY, LEVELS, O, WIN_LENGTH, X, SearchResult, winning_line

MIN_SIZE, MAX_SIZE = 9, 50
MODES = ("pvp", "bot")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ I, O, 0, 1 cho dễ đọc


class GameError(Exception):
    """Lỗi do người chơi (nước sai, sai lượt...); gửi nguyên văn về client."""


@dataclass
class Seat:
    name: str
    token: str | None      # None: ghế của bot
    online: int = 0        # số kết nối đang giữ ghế này


def new_code(existing):
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
        if code not in existing:
            return code


def clean_name(name, fallback="Người chơi"):
    name = " ".join(str(name or "").split())[:20]
    return name or fallback


class Room:
    def __init__(self, code, mode, rows=15, cols=15, strict=False, level=1, human_side=X):
        if mode not in MODES:
            raise GameError("Chế độ chơi không hợp lệ.")
        try:
            rows, cols, level, human_side = int(rows), int(cols), int(level), int(human_side)
        except (TypeError, ValueError) as exc:
            raise GameError("Thiết lập phòng không hợp lệ.") from exc
        if not (MIN_SIZE <= rows <= MAX_SIZE and MIN_SIZE <= cols <= MAX_SIZE):
            raise GameError(f"Bàn cờ phải từ {MIN_SIZE} đến {MAX_SIZE} ô mỗi chiều.")
        if not 0 <= level < len(LEVELS):
            raise GameError("Độ khó không hợp lệ.")
        if human_side not in (X, O):
            raise GameError("Bên chơi phải là X hoặc O.")
        self.code, self.mode = code, mode
        self.rows, self.cols, self.strict = rows, cols, bool(strict)
        self.level = level
        self.seats: dict[int, Seat | None] = {X: None, O: None}
        self.bot_side = 3 - human_side if mode == "bot" else None
        if self.bot_side:
            self.seats[self.bot_side] = Seat(f"Bot · {LEVELS[level][0]}", None)
        self.notice = ""
        self.empty_since = time.monotonic()
        self.new_game()

    # ---------- ghế ngồi ----------
    def side_of(self, token):
        for side, seat in self.seats.items():
            if seat is not None and token and seat.token == token:
                return side
        return None

    def take_seat(self, name, token=None, prefer=None):
        """Trả (bên, token). Token cũ giữ lại ghế khi tải lại trang."""
        side = self.side_of(token)
        if side is not None:
            self.seats[side].name = clean_name(name, self.seats[side].name)
            return side, token
        free = [s for s in (prefer, X, O) if s in (X, O) and self.seats[s] is None]
        if not free:
            return None, None  # người xem
        token = secrets.token_urlsafe(16)
        self.seats[free[0]] = Seat(clean_name(name), token)
        return free[0], token

    @property
    def human_side(self):
        return 3 - self.bot_side if self.bot_side else None

    @property
    def waiting(self):
        return self.mode == "pvp" and any(seat is None for seat in self.seats.values())

    # ---------- luật chơi ----------
    def new_game(self):
        self.board = [[EMPTY] * self.cols for _ in range(self.rows)]
        self.history: list[tuple[int, int, int]] = []
        self.current = X  # X luôn đi trước
        self.winner = EMPTY  # -1: hòa
        self.win_line: list[tuple[int, int]] = []
        self.stats = SearchResult(None)

    def place(self, side, r, c):
        if self.winner != EMPTY:
            raise GameError("Ván cờ đã kết thúc.")
        if self.waiting:
            raise GameError("Đang chờ người chơi thứ hai.")
        if side is None:
            raise GameError("Bạn đang xem, không thể đánh.")
        if side != self.current:
            raise GameError("Chưa đến lượt bạn.")
        if not (type(r) is int and type(c) is int
                and 0 <= r < self.rows and 0 <= c < self.cols):
            raise GameError("Ô cờ không hợp lệ.")
        if self.board[r][c] != EMPTY:
            raise GameError("Ô này đã có quân.")
        self.board[r][c] = side
        self.history.append((r, c, side))
        line = winning_line(self.board, r, c, side, WIN_LENGTH, self.strict)
        if line:
            self.winner, self.win_line = side, line
        elif len(self.history) == self.rows * self.cols:
            self.winner = -1
        else:
            self.current = 3 - side

    def undo(self, side):
        """Chỉ ở chế độ đấu máy: bỏ nước gần nhất của người và các nước bot sau đó."""
        if self.mode != "bot":
            raise GameError("Chỉ hoàn tác được khi đấu với máy.")
        if side != self.human_side:
            raise GameError("Người xem không hoàn tác được.")
        if not any(s == side for _, _, s in self.history):
            raise GameError("Chưa có nước nào của bạn để hoàn tác.")
        while True:
            r, c, s = self.history.pop()
            self.board[r][c] = EMPTY
            if s == side:
                break
        self.current = side
        self.winner, self.win_line = EMPTY, []
        self.stats = SearchResult(None)

    def restart(self, side):
        if side is None:
            raise GameError("Người xem không mở được ván mới.")
        if self.mode == "pvp" and self.history:
            # Đổi bên sau mỗi ván để hai người lần lượt được đi trước.
            self.seats[X], self.seats[O] = self.seats[O], self.seats[X]
        self.new_game()

    # ---------- gửi cho client ----------
    def snapshot(self, token=None, bot_thinking=False):
        def seat(side):
            s = self.seats[side]
            if s is None:
                return None
            return {"name": s.name, "bot": s.token is None, "online": s.token is None or s.online > 0}

        last = self.history[-1] if self.history else None
        return {
            "code": self.code,
            "mode": self.mode,
            "rows": self.rows,
            "cols": self.cols,
            "strict": self.strict,
            "winLength": WIN_LENGTH,
            "level": self.level,
            "levelName": LEVELS[self.level][0],
            "board": self.board,
            "moves": len(self.history),
            "lastMove": last[:2] if last else None,
            "current": self.current,
            "winner": self.winner,
            "winLine": self.win_line,
            "players": {str(X): seat(X), str(O): seat(O)},
            "you": self.side_of(token),
            "waiting": self.waiting,
            "botThinking": bot_thinking,
            "stats": {
                "depth": self.stats.depth,
                "nodes": self.stats.nodes,
                "elapsed": round(self.stats.elapsed, 2),
                "proven": self.stats.proven,
                "forcingPlies": self.stats.forcing_plies,
            },
            "notice": self.notice,
        }
