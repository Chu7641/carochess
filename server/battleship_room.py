"""Trạng thái một phòng chơi Hải chiến (Battleship)."""

from __future__ import annotations

import time
from typing import Any

from battleship_game import (
    BATTLESHIP_LEVELS,
    SIZE,
    Fleet,
    random_fleet,
)
from server.game import (
    TURN_SECONDS,
    GameError,
    Room,
    Seat,
)


class BattleshipRoom(Room):
    """Phòng chơi Hải chiến (Battleship 10x10), hỗ trợ đấu máy và đấu người qua mạng LAN."""

    game_type = "battleship"

    def __init__(
        self,
        code: str,
        mode: str,
        level: int = 1,
        human_side: int = 1,
    ):
        if mode not in ("pvp", "bot"):
            raise GameError("Chế độ chơi không hợp lệ.")

        try:
            level = int(level)
            human_side = int(human_side)
        except (TypeError, ValueError) as exc:
            raise GameError("Thiết lập phòng không hợp lệ.") from exc

        if not 0 <= level < len(BATTLESHIP_LEVELS):
            raise GameError("Độ khó không hợp lệ.")
        if human_side not in (1, 2):
            raise GameError("Bên chơi phải là 1 (bắn trước) hoặc 2 (bắn sau).")

        self.code = code
        self.mode = mode
        self.rows = SIZE
        self.cols = SIZE
        self.strict = False
        self.level = level
        self.bot_side = (3 - human_side) if mode == "bot" else None
        self.seats: dict[int, Seat | None] = {1: None, 2: None}
        if self.bot_side:
            self.seats[self.bot_side] = Seat(f"Bot Hải Chiến · {BATTLESHIP_LEVELS[level][0]}", None)

        self.notice = ""
        self.empty_since = time.monotonic()
        self.turn_deadline = None
        self._clock_key = None
        self.new_game()

    def new_game(self):
        self.phase = "placing"  # "placing" | "playing" | "ended"
        self.fleets: dict[int, Fleet | None] = {1: None, 2: None}
        # Đấu máy: bot xếp hạm đội ngẫu nhiên ngay khi tạo ván
        if self.bot_side:
            self.fleets[self.bot_side] = Fleet(random_fleet())

        self.history: list[tuple[int, int, int]] = []  # (r, c, side)
        self.current = 1  # Bên 1 luôn đi trước
        self.winner = 0
        self.win_line = []
        self.request = None
        self.ready = set()  # Tập các bên đã xếp xong hạm đội
        self.started = False  # Bắt đầu khi cả hai bên xếp xong
        self.rated = False
        self.notice = "Xếp 5 tàu của bạn rồi bấm Xác nhận để bắt đầu trận chiến."
        self._clock_key = None
        self.turn_deadline = None
        self.last_shot: dict[str, Any] | None = None
        for seat in self.seats.values():
            if seat is not None:
                seat.elo_delta = None

    def place(self, side: int, r: int, c: int):
        """Chống lỗi khi tin 'move' kiểu caro gửi vào phòng hải chiến."""
        raise GameError("Phòng hải chiến dùng lệnh bắn (fire).")

    def place_ships(self, side: int, ships: list[dict] | None):
        """Người chơi xếp hạm đội. ships = None là xếp ngẫu nhiên giúp."""
        if side is None:
            raise GameError("Người xem không thể xếp tàu.")
        if side not in (1, 2):
            raise GameError("Bên chơi không hợp lệ.")
        if self.phase != "placing":
            raise GameError("Đã qua giai đoạn xếp tàu.")
        if side in self.ready or self.fleets[side] is not None:
            raise GameError("Bạn đã xếp tàu xong, đang chờ đối thủ.")

        if ships is None:
            ships = random_fleet()

        try:
            fleet = Fleet(ships)
        except ValueError as exc:
            raise GameError(str(exc)) from exc

        self.fleets[side] = fleet
        self.ready.add(side)

        if self.mode == "bot":
            self.phase = "playing"
            self.started = True
            if self.current == self.human_side:
                self.notice = "Trận chiến bắt đầu! Đến lượt bạn bắn."
            else:
                self.notice = "Trận chiến bắt đầu! Bot bắn trước."
        else:
            # Chế độ đấu người (pvp)
            if len(self.ready) == 2 and not self.waiting:
                self.phase = "playing"
                self.started = True
                p1 = self.seats.get(1)
                p1_name = p1.name if p1 else "Bên 1"
                self.notice = f"Trận chiến bắt đầu! Lượt của {p1_name} bắn."
            else:
                self.notice = "Bạn đã xếp tàu xong, đang chờ đối thủ..."

    def seat_freed(self, side: int):
        """Một người rời phòng: nếu chưa có phát bắn nào thì reset tàu của bên đó."""
        self.ready.discard(side)
        if not self.history and self.winner == 0:
            self.fleets[side] = None
            self.phase = "placing"
            self.started = False

    def fire(self, side: int, r: int, c: int):
        if self.winner != 0:
            raise GameError("Ván cờ đã kết thúc.")
        if self.waiting:
            raise GameError("Đang chờ người chơi thứ hai.")
        if side is None:
            raise GameError("Bạn đang xem, không thể bắn.")
        if self.phase != "playing" or not self.started:
            raise GameError("Chưa đến giai đoạn bắn tàu.")
        if side != self.current:
            raise GameError("Chưa đến lượt bạn.")

        if type(r) is not int or type(c) is not int or not (0 <= r < SIZE and 0 <= c < SIZE):
            raise GameError("Tọa độ bắn không hợp lệ.")

        target_side = 3 - side
        target_fleet = self.fleets[target_side]
        if target_fleet is None:
            raise GameError("Đối thủ chưa xếp tàu.")

        try:
            res = target_fleet.fire(r, c)
        except ValueError as exc:
            raise GameError(str(exc)) from exc

        self.history.append((r, c, side))
        self.last_shot = {
            "side": side,
            "r": r,
            "c": c,
            "result": res["result"],
            "cells": res.get("cells"),
        }

        shooter_seat = self.seats.get(side)
        shooter_name = shooter_seat.name if shooter_seat else ("Bên 1" if side == 1 else "Bên 2")

        if target_fleet.all_sunk:
            self.winner = side
            self.phase = "ended"
            self.notice = f"{shooter_name} đã đánh chìm toàn bộ hạm đội đối phương! {shooter_name} thắng!"
        else:
            if res["result"] == "miss":
                self.notice = f"{shooter_name} bắn trượt." if self.mode == "pvp" else "Trượt."
                self.current = 3 - side  # Đổi lượt khi bắn trượt
            elif res["result"] == "hit":
                self.notice = f"{shooter_name} bắn trúng! Bắn tiếp." if self.mode == "pvp" else "Trúng! Bắn tiếp."
            elif res["result"] == "sunk":
                ship_name = res["ship"]
                self.notice = (
                    f"{shooter_name} đánh chìm {ship_name}! Bắn tiếp."
                    if self.mode == "pvp"
                    else f"Đánh chìm {ship_name}! Bắn tiếp."
                )

    def undo(self, side: int):
        raise GameError("Hải chiến không có đi lại.")

    def restart(self, side: int):
        if side is None:
            raise GameError("Người xem không mở được ván mới.")
        if self.mode == "pvp" and self.history:
            self.seats[1], self.seats[2] = self.seats[2], self.seats[1]
        self.new_game()

    def timeout(self):
        loser = self.current
        self.winner, self.win_line, self.request = 3 - loser, [], None
        self.phase = "ended"
        loser_seat = self.seats.get(loser)
        loser_name = loser_seat.name if loser_seat else f"Bên {loser}"
        self.notice = f"{loser_name} hết thời gian, bị tính thua."

    def forfeit(self, side: int, reason: str):
        """Bỏ ván đấu người đang dở: bên bỏ bị tính thua."""
        if (
            side is not None
            and self.mode == "pvp"
            and self.winner == 0
            and not self.waiting
            and self.history
        ):
            self.winner, self.win_line, self.request = 3 - side, [], None
            self.phase = "ended"
            seat = self.seats.get(side)
            name = seat.name if seat else f"Bên {side}"
            self.notice = f"{name} {reason}, bị tính thua."

    def bot_view(self) -> dict[str, Any]:
        """Tạo góc nhìn bí mật cho bot (không đọc vị trí tàu chưa chìm của người)."""
        human_fleet = self.fleets[self.human_side]
        if human_fleet is None:
            return {
                "misses": [],
                "hits": [],
                "sunk_ships": [],
                "remaining_ships": [5, 4, 3, 3, 2],
            }
        return {
            "misses": list(human_fleet.misses),
            "hits": list(human_fleet.hits),
            "sunk_ships": [
                {
                    "name": s["name"],
                    "len": s["len"],
                    "cells": s["cells"],
                }
                for s in human_fleet.sunk_ships
            ],
            "remaining_ships": [
                s["len"] for s in human_fleet.ships if s not in human_fleet.sunk_ships
            ],
        }

    def snapshot(self, token: str | None = None, bot_thinking: bool = False) -> dict[str, Any]:
        """Tạo snapshot an toàn chống lộ thông tin hạm đội đối thủ."""
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

        you_side = self.side_of(token)
        fleet_1 = self.fleets[1]
        fleet_2 = self.fleets[2]

        def get_ships_left(fleet: Fleet | None) -> list[dict]:
            if fleet is None:
                return [
                    {"name": name, "len": length, "sunk": False}
                    for name, length in [
                        ("Tàu sân bay", 5),
                        ("Thiết giáp hạm", 4),
                        ("Tuần dương hạm", 3),
                        ("Tàu ngầm", 3),
                        ("Khu trục hạm", 2),
                    ]
                ]
            sunk_names = {s["name"] for s in fleet.sunk_ships}
            res = []
            for s in fleet.ships:
                res.append({
                    "name": s["name"],
                    "len": s["len"],
                    "sunk": s["name"] in sunk_names,
                })
            return res

        my_fleet_data = None
        opponent_board_data = None
        boards_data = None

        if you_side in (1, 2):
            my_fleet = self.fleets[you_side]
            opp_fleet = self.fleets[3 - you_side]

            # Bàn của mình: vị trí tàu của mình + các phát đối thủ đã bắn vào mình
            if my_fleet is not None:
                my_fleet_data = {
                    "ships": my_fleet.ships,
                    "hits": list(my_fleet.hits),
                    "misses": list(my_fleet.misses),
                    "sunkShips": my_fleet.sunk_ships,
                }

            # Bàn đối thủ: CHỈ các phát mình đã bắn (misses/hits) + ô tàu đối thủ ĐÃ CHÌM
            if opp_fleet is not None:
                opponent_board_data = {
                    "hits": list(opp_fleet.hits),
                    "misses": list(opp_fleet.misses),
                    "sunkShips": opp_fleet.sunk_ships,
                    # CHỈ gửi toàn bộ tàu đối thủ khi ván đã kết thúc
                    "revealedShips": opp_fleet.ships if self.winner != 0 else [],
                }
        else:
            # Người xem: chỉ thấy các phát bắn và tàu đã chìm, không thấy tàu chưa chìm của ai
            boards_data = {}
            for s in (1, 2):
                fl = self.fleets[s]
                boards_data[str(s)] = {
                    "hits": list(fl.hits) if fl else [],
                    "misses": list(fl.misses) if fl else [],
                    "sunkShips": fl.sunk_ships if fl else [],
                    "revealedShips": fl.ships if (self.winner != 0 and fl) else [],
                }

        return {
            "code": self.code,
            "game": "battleship",
            "mode": self.mode,
            "rows": self.rows,
            "cols": self.cols,
            "phase": self.phase,
            "level": self.level,
            "levelName": BATTLESHIP_LEVELS[self.level][0],
            "moves": len(self.history),
            "current": self.current,
            "winner": self.winner,
            "winLine": [],
            "myFleet": my_fleet_data,
            "opponentBoard": opponent_board_data,
            "boards": boards_data,
            "placed": sorted(self.ready),
            "lastShot": self.last_shot,
            "shipsLeft": {
                "1": get_ships_left(fleet_1),
                "2": get_ships_left(fleet_2),
            },
            "players": {"1": seat(1), "2": seat(2)},
            "you": you_side,
            "waiting": self.waiting,
            "botThinking": bot_thinking,
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
