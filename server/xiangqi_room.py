"""Trạng thái một phòng chơi cờ tướng (Xiangqi)."""

from __future__ import annotations

import time
from typing import Any

from server.game import (
    TURN_SECONDS,
    GameError,
    Room,
    Seat,
)
from xiangqi_game import (
    BLACK,
    EMPTY,
    RED,
    XIANGQI_LEVELS,
    XiangqiBoard,
)


class XiangqiRoom(Room):
    """Phòng chơi cờ tướng (Xiangqi), hiện hỗ trợ đấu với máy."""

    game_type = "xiangqi"

    def __init__(
        self,
        code: str,
        mode: str,
        level: int = 1,
        human_side: int = RED,
    ):
        if mode != "bot":
            raise GameError("Cờ tướng hiện chỉ có chế độ đấu với máy.")
        try:
            level = int(level)
            human_side = int(human_side)
        except (TypeError, ValueError) as exc:
            raise GameError("Thiết lập phòng không hợp lệ.") from exc

        if not 0 <= level < len(XIANGQI_LEVELS):
            raise GameError("Độ khó không hợp lệ.")
        if human_side not in (RED, BLACK):
            raise GameError("Bên chơi phải là Đỏ (1) hoặc Đen (2).")

        self.code = code
        self.mode = mode
        self.rows = 10
        self.cols = 9
        self.strict = False
        self.level = level
        self.seats: dict[int, Seat | None] = {RED: None, BLACK: None}
        self.bot_side = 3 - human_side if mode == "bot" else None
        if self.bot_side:
            self.seats[self.bot_side] = Seat(f"Bot Cờ Tướng · {XIANGQI_LEVELS[level][0]}", None)

        self.notice = ""
        self.empty_since = time.monotonic()
        self.turn_deadline = None
        self._clock_key = None
        self.stats_nodes = 0
        self.stats_elapsed = 0.0
        self.stats_depth = 0
        self.stats_score = 0
        self.new_game()

    def new_game(self):
        self.engine = XiangqiBoard()
        self.board = [row[:] for row in self.engine.board]
        self.history: list[tuple[int, int, int, int, int]] = []
        self.current = RED  # Đỏ luôn đi trước
        self.winner = 0
        self.win_line = []
        self.request = None
        self.ready = set()
        self.started = self.mode == "bot"
        self.rated = False
        self.stats_nodes = 0
        self.stats_elapsed = 0.0
        self.stats_depth = 0
        self.stats_score = 0
        self.notice = ""
        for seat in self.seats.values():
            if seat is not None:
                seat.elo_delta = None

    def place(self, side: int, r: int, c: int):
        """Chống lỗi khi tin 'move' kiểu caro gửi vào phòng cờ tướng."""
        raise GameError("Phòng cờ tướng dùng lệnh di chuyển quân (move_piece).")

    def move(self, side: int, fr: int, fc: int, tr: int, tc: int):
        if self.winner != 0:
            raise GameError("Ván cờ đã kết thúc.")
        if self.waiting:
            raise GameError("Đang chờ người chơi thứ hai.")
        if side is None:
            raise GameError("Bạn đang xem, không thể đánh.")
        if not self.started:
            raise GameError("Ván chưa bắt đầu: cả hai bên cần bấm Sẵn sàng.")
        if side != self.current:
            raise GameError("Chưa đến lượt bạn.")
        if not (type(fr) is int and type(fc) is int and type(tr) is int and type(tc) is int
                and 0 <= fr < 10 and 0 <= fc < 9 and 0 <= tr < 10 and 0 <= tc < 9):
            raise GameError("Nước đi không hợp lệ.")

        m = (fr, fc, tr, tc)
        legal, reason = self.engine.is_legal(m)
        if not legal:
            raise GameError(reason)

        self.engine.play(m)
        self.board = [row[:] for row in self.engine.board]
        self.history.append((fr, fc, tr, tc, side))
        self.request = None

        res = self.engine.result()
        if res["over"]:
            if res["winner"] is not None:
                self.winner = res["winner"]
                win_name = "Đỏ" if self.winner == RED else "Đen"
                if res["reason"] == "chiếu bí":
                    self.notice = f"{win_name} chiếu bí, {win_name} thắng!"
                else:
                    lose_name = "Đen" if self.winner == RED else "Đỏ"
                    self.notice = f"{lose_name} hết nước đi, {win_name} thắng!"
            else:
                self.winner = -1
                self.notice = "Lặp lại thế cờ 3 lần, hòa."
        else:
            self.current = 3 - side
            if self.engine.in_check(self.current):
                self.notice = "Chiếu tướng!"
            else:
                self.notice = ""

    def undo(self, side: int):
        if side is None:
            raise GameError("Người xem không xin đi lại được.")
        if not any(s == side for _, _, _, _, s in self.history):
            raise GameError("Chưa có nước nào của bạn để đi lại.")
        if self.mode == "pvp":
            if self.winner != 0:
                raise GameError("Ván cờ đã kết thúc.")
            self._ask(side, "undo")
        else:
            self._take_back(side)

    def _take_back(self, side: int):
        while self.history:
            fr, fc, tr, tc, s = self.history.pop()
            self.engine.undo()
            if s == side:
                break
        self.board = [row[:] for row in self.engine.board]
        self.current = side
        self.winner = 0
        self.request = None
        self.notice = ""

    def restart(self, side: int):
        if side is None:
            raise GameError("Người xem không mở được ván mới.")
        if self.mode == "pvp" and self.history:
            self.seats[RED], self.seats[BLACK] = self.seats[BLACK], self.seats[RED]
        self.new_game()

    def snapshot(self, token: str | None = None, bot_thinking: bool = False) -> dict[str, Any]:
        def seat(side: int):
            s = self.seats[side]
            if s is None:
                return None
            return {
                "name": s.name,
                "bot": s.token is None,
                "online": s.token is None or s.online > 0,
                "elo": s.elo,
                "eloDelta": s.elo_delta,
            }

        last = self.history[-1] if self.history else None
        last_move = [last[0], last[1], last[2], last[3]] if last else None
        you_side = self.side_of(token)
        is_human_turn = (self.winner == 0 and you_side == self.current and self.started)

        return {
            "code": self.code,
            "game": "xiangqi",
            "mode": self.mode,
            "rows": self.rows,
            "cols": self.cols,
            "board": self.engine.board,
            "level": self.level,
            "levelName": XIANGQI_LEVELS[self.level][0],
            "moves": len(self.history),
            "lastMove": last_move,
            "current": self.current,
            "winner": self.winner,
            "winLine": [],
            "inCheck": self.engine.in_check(self.current) if self.winner == 0 else False,
            "legalMoves": self.engine.legal_moves() if is_human_turn else [],
            "players": {str(RED): seat(RED), str(BLACK): seat(BLACK)},
            "you": you_side,
            "waiting": self.waiting,
            "botThinking": bot_thinking,
            "stats": {
                "depth": self.stats_depth,
                "nodes": self.stats_nodes,
                "elapsed": round(self.stats_elapsed, 2),
                "score": self.stats_score,
            },
            "notice": self.notice,
            "request": self.request,
            "started": self.started,
            "ready": sorted(self.ready),
            "turnSeconds": TURN_SECONDS,
            "turnLeft": (
                None
                if self.turn_deadline is None
                else round(max(0.0, self.turn_deadline - time.monotonic()), 2)
            ),
        }

