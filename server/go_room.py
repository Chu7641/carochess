"""Trạng thái một phòng chơi cờ vây (Go / Baduk)."""

from __future__ import annotations

import time
from typing import Any

from go_game import (
    BLACK,
    DEFAULT_KOMI,
    EMPTY,
    GO_LEVELS,
    GO_SIZES,
    WHITE,
    GoBoard,
)
from server.game import (
    TURN_SECONDS,
    GameError,
    Room,
    Seat,
    clean_name,
)


class GoRoom(Room):
    """Phòng chơi cờ vây (Go), hỗ trợ bàn 9x9, 13x13, 19x19 và luật cờ vây chuẩn."""

    game_type = "go"

    def __init__(
        self,
        code: str,
        mode: str,
        size: int = 19,
        komi: float | None = None,
        level: int = 1,
        human_side: int = BLACK,
    ):
        if mode not in ("pvp", "bot"):
            raise GameError("Chế độ chơi không hợp lệ.")
        try:
            size = int(size)
            level = int(level)
            human_side = int(human_side)
            komi = None if komi is None else float(komi)
        except (TypeError, ValueError) as exc:
            raise GameError("Thiết lập phòng không hợp lệ.") from exc
        if komi is not None and not -50 <= komi <= 50:  # cũng loại nan, inf
            raise GameError("Komi phải từ -50 đến 50.")

        if size not in GO_SIZES:
            raise GameError(f"Kích thước bàn cờ vây phải là 9, 13 hoặc 19 (nhận được {size}).")
        if not 0 <= level < len(GO_LEVELS):
            raise GameError("Độ khó không hợp lệ.")
        if human_side not in (BLACK, WHITE):
            raise GameError("Bên chơi phải là Đen (1) hoặc Trắng (2).")

        self.code = code
        self.mode = mode
        self.size = size
        self.rows = size
        self.cols = size
        self.strict = False
        self.komi = DEFAULT_KOMI.get(size, 7.5) if komi is None else float(komi)
        self.level = level
        self.seats: dict[int, Seat | None] = {BLACK: None, WHITE: None}
        self.bot_side = 3 - human_side if mode == "bot" else None
        if self.bot_side:
            self.seats[self.bot_side] = Seat(f"Bot Cờ Vây · {GO_LEVELS[level][0]}", None)

        self.notice = ""
        self.empty_since = time.monotonic()
        self.turn_deadline = None
        self._clock_key = None
        self.stats_nodes = 0
        self.stats_elapsed = 0.0
        self.score_details: dict[str, Any] | None = None
        self.new_game()

    def new_game(self):
        self.engine = GoBoard(self.size, self.komi)
        self.board = [row[:] for row in self.engine.board]
        self.history: list[tuple[int | None, int | None, int]] = []
        self.current = BLACK  # Đen luôn đi trước
        self.winner = EMPTY
        self.win_line = []
        self.score_details = None
        self.request = None
        self.ready = set()
        self.started = self.mode == "bot"
        self.rated = False
        self.stats_nodes = 0
        self.stats_elapsed = 0.0
        for seat in self.seats.values():
            if seat is not None:
                seat.elo_delta = None

    def place(self, side: int, r: int, c: int):
        if self.winner != EMPTY:
            raise GameError("Ván cờ đã kết thúc.")
        if self.waiting:
            raise GameError("Đang chờ người chơi thứ hai.")
        if side is None:
            raise GameError("Bạn đang xem, không thể đánh.")
        if not self.started:
            raise GameError("Ván chưa bắt đầu: cả hai bên cần bấm Sẵn sàng.")
        if side != self.current:
            raise GameError("Chưa đến lượt bạn.")
        if not (type(r) is int and type(c) is int and self.engine.in_bounds(r, c)):
            raise GameError("Ô cờ không hợp lệ.")

        legal, reason = self.engine.is_legal(side, r, c)
        if not legal:
            raise GameError(reason)

        captured = self.engine.play(side, r, c)
        self.board = [row[:] for row in self.engine.board]
        self.history.append((r, c, side))
        self.request = None

        if captured:
            who = "Đen" if side == BLACK else "Trắng"
            self.notice = f"{who} đã bắt {len(captured)} quân đối phương!"

        self.current = 3 - side

    def pass_turn(self, side: int):
        """Người chơi bỏ lượt."""
        if self.winner != EMPTY:
            raise GameError("Ván cờ đã kết thúc.")
        if self.waiting:
            raise GameError("Đang chờ người chơi thứ hai.")
        if side is None:
            raise GameError("Bạn đang xem, không thể bỏ lượt.")
        if not self.started:
            raise GameError("Ván chưa bắt đầu: cả hai bên cần bấm Sẵn sàng.")
        if side != self.current:
            raise GameError("Chưa đến lượt bạn.")

        self.engine.pass_turn(side)
        self.history.append((None, None, side))
        self.request = None

        who = "Đen" if side == BLACK else "Trắng"

        if self.engine.is_game_over():
            # Cả 2 bên cùng bỏ lượt: kết thúc ván và đếm điểm
            res = self.engine.score()
            self.winner = res["winner"]
            self.score_details = res
            win_name = "Đen" if self.winner == BLACK else "Trắng"
            margin = res["margin"]
            self.notice = f"Cả hai bên đã bỏ lượt. {win_name} thắng cách biệt {margin} mục!"
        else:
            self.notice = f"{who} đã bỏ lượt."
            self.current = 3 - side

    def undo(self, side: int):
        if side is None:
            raise GameError("Người xem không xin đi lại được.")
        if not any(s == side for _, _, s in self.history):
            raise GameError("Chưa có nước nào của bạn để đi lại.")
        if self.mode == "pvp":
            if self.winner != EMPTY:
                raise GameError("Ván cờ đã kết thúc.")
            self._ask(side, "undo")
        else:
            self._take_back(side)

    def _take_back(self, side: int):
        while self.history:
            r, c, s = self.history.pop()
            self.engine.undo()
            if s == side:
                break
        self.board = [row[:] for row in self.engine.board]
        self.current = side
        self.winner = EMPTY
        self.score_details = None
        self.request = None

    def restart(self, side: int):
        if side is None:
            raise GameError("Người xem không mở được ván mới.")
        if self.mode == "pvp" and self.history:
            # Đổi bên sau mỗi ván để hai bên lần lượt cầm Đen đi trước
            self.seats[BLACK], self.seats[WHITE] = self.seats[WHITE], self.seats[BLACK]
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
        last_move = [last[0], last[1]] if (last and last[0] is not None) else None
        last_action = "pass" if (last and last[0] is None) else ("move" if last else None)

        return {
            "code": self.code,
            "game": "go",
            "mode": self.mode,
            "rows": self.rows,
            "cols": self.cols,
            "size": self.size,
            "komi": self.komi,
            "captured": {
                str(BLACK): self.engine.captured[BLACK],
                str(WHITE): self.engine.captured[WHITE],
            },
            "level": self.level,
            "levelName": GO_LEVELS[self.level][0],
            "board": self.board,
            "moves": len(self.history),
            "lastMove": last_move,
            "lastAction": last_action,
            "current": self.current,
            "winner": self.winner,
            "winLine": [],
            "score": self.score_details,
            "players": {str(BLACK): seat(BLACK), str(WHITE): seat(WHITE)},
            "you": self.side_of(token),
            "waiting": self.waiting,
            "botThinking": bot_thinking,
            "stats": {
                "depth": 0,
                "nodes": self.stats_nodes,
                "elapsed": round(self.stats_elapsed, 2),
                "proven": False,
                "forcingPlies": 0,
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
