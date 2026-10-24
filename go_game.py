# -*- coding: utf-8 -*-
"""Engine cờ vây (Go / Baduk): luật bắt quân, khí, tự sát, kiếp (Ko), bỏ lượt và đếm điểm.

Dùng cho máy chủ LAN (server/go_room.py) và bot chơi cờ vây.
Kiểm tra luật và bot:
    python go_game.py --self-test
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import threading
import time
from dataclasses import dataclass
from typing import Sequence

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

EMPTY = 0
BLACK = 1  # Quân đen, luôn đi trước
WHITE = 2  # Quân trắng, đi sau và nhận komi

GO_SIZES = (9, 13, 19)

DEFAULT_KOMI = {
    9: 5.5,
    13: 6.5,
    19: 7.5,
}

# Tọa độ các điểm sao (hoshi) theo chuẩn
STAR_POINTS: dict[int, list[tuple[int, int]]] = {
    9: [(2, 2), (2, 6), (6, 2), (6, 6), (4, 4)],
    13: [(3, 3), (3, 9), (9, 3), (9, 9), (6, 6)],
    19: [
        (3, 3), (3, 9), (3, 15),
        (9, 3), (9, 9), (9, 15),
        (15, 3), (15, 9), (15, 15),
    ],
}

GO_LEVELS = [
    ("Dễ", 0.5),
    ("Vừa", 1.0),
    ("Khó", 2.0),
]


class GoBoard:
    """Bàn cờ vây kích thước size x size (9, 13, 19)."""

    def __init__(self, size: int = 19, komi: float | None = None):
        if size not in GO_SIZES and not (5 <= size <= 25):
            raise ValueError(f"Kích thước bàn cờ vây không hợp lệ: {size}")
        self.size = size
        self.komi = DEFAULT_KOMI.get(size, 7.5) if komi is None else float(komi)
        self.board: list[list[int]] = [[EMPTY] * size for _ in range(size)]
        self.captured: dict[int, int] = {BLACK: 0, WHITE: 0}  # số quân đối phương đã bắt
        self.ko: tuple[int, int] | None = None  # ô bị cấm do luật kiếp đơn
        self.consecutive_passes: int = 0
        self.history: list[dict] = []

    def copy(self) -> GoBoard:
        other = GoBoard(self.size, self.komi)
        other.board = [row[:] for row in self.board]
        other.captured = dict(self.captured)
        other.ko = self.ko
        other.consecutive_passes = self.consecutive_passes
        other.history = [dict(h) for h in self.history]
        return other

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        res = []
        if r > 0:
            res.append((r - 1, c))
        if r + 1 < self.size:
            res.append((r + 1, c))
        if c > 0:
            res.append((r, c - 1))
        if c + 1 < self.size:
            res.append((r, c + 1))
        return res

    def get_group(self, r: int, c: int) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
        """Tìm đám quân liên kết tại (r, c).

        Trả về (tập các ô của đám quân, tập các ô khí).
        """
        color = self.board[r][c]
        if color == EMPTY:
            return set(), set()
        stones: set[tuple[int, int]] = set()
        liberties: set[tuple[int, int]] = set()
        queue = [(r, c)]
        stones.add((r, c))

        while queue:
            curr_r, curr_c = queue.pop()
            for nr, nc in self.neighbors(curr_r, curr_c):
                n_color = self.board[nr][nc]
                if n_color == EMPTY:
                    liberties.add((nr, nc))
                elif n_color == color and (nr, nc) not in stones:
                    stones.add((nr, nc))
                    queue.append((nr, nc))
        return stones, liberties

    def is_legal(self, side: int, r: int, c: int) -> tuple[bool, str]:
        """Kiểm tra tính hợp lệ của nước đi.

        Trả về (hợp_lệ, lý_do_nếu_sai).
        """
        if not self.in_bounds(r, c):
            return False, "Ô cờ ngoài phạm vi bàn."
        if self.board[r][c] != EMPTY:
            return False, "Ô này đã có quân."
        if self.ko == (r, c):
            return False, "Nước đi phạm luật Kiếp (Ko): không được lặp lại ngay trạng thái cũ."

        # Giả lập đặt quân để kiểm tra bắt quân và cấm tự sát
        opponent = 3 - side
        captured_count = 0
        self.board[r][c] = side

        # Kiểm tra xem nước đi có bắt được đám quân nào của đối thủ không
        for nr, nc in self.neighbors(r, c):
            if self.board[nr][nc] == opponent:
                _, opp_liberties = self.get_group(nr, nc)
                if len(opp_liberties) == 0:
                    captured_count += 1

        # Kiểm tra khí của đám quân vừa đặt
        _, my_liberties = self.get_group(r, c)
        is_suicide = (len(my_liberties) == 0 and captured_count == 0)

        # Hoàn lại bàn cờ sau giả lập
        self.board[r][c] = EMPTY

        if is_suicide:
            return False, "Nước đi tự sát (không còn khí và không bắt được quân đối phương)."

        return True, ""

    def play(self, side: int, r: int, c: int) -> list[tuple[int, int]]:
        """Thực hiện nước đi.

        Trả về danh sách các quân của đối thủ bị bắt (nếu có).
        Báo lỗi ValueError nếu nước đi không hợp lệ.
        """
        legal, reason = self.is_legal(side, r, c)
        if not legal:
            raise ValueError(reason)

        opponent = 3 - side
        self.board[r][c] = side
        all_captured: list[tuple[int, int]] = []

        # Bắt các đám quân đối phương hết khí
        opp_checked: set[tuple[int, int]] = set()
        for nr, nc in self.neighbors(r, c):
            if self.board[nr][nc] == opponent and (nr, nc) not in opp_checked:
                opp_stones, opp_liberties = self.get_group(nr, nc)
                opp_checked.update(opp_stones)
                if len(opp_liberties) == 0:
                    for gr, gc in opp_stones:
                        self.board[gr][gc] = EMPTY
                        all_captured.append((gr, gc))

        self.captured[side] += len(all_captured)

        # Cập nhật luật Kiếp (Ko)
        # Chỉ xảy ra khi bắt đúng 1 quân, và quân vừa đặt chỉ có đúng 1 khí (chính là ô vừa bị bắt)
        prev_ko = self.ko
        if len(all_captured) == 1:
            my_stones, my_liberties = self.get_group(r, c)
            if len(my_stones) == 1 and len(my_liberties) == 1 and all_captured[0] in my_liberties:
                self.ko = all_captured[0]
            else:
                self.ko = None
        else:
            self.ko = None

        self.consecutive_passes = 0
        self.history.append({
            "action": "move",
            "side": side,
            "r": r,
            "c": c,
            "captured": all_captured,
            "prev_ko": prev_ko,
        })
        return all_captured

    def pass_turn(self, side: int):
        """Bỏ lượt."""
        prev_ko = self.ko
        self.ko = None
        self.consecutive_passes += 1
        self.history.append({
            "action": "pass",
            "side": side,
            "prev_ko": prev_ko,
        })

    def undo(self) -> bool:
        """Hoàn tác nước đi hoặc lượt bỏ qua gần nhất."""
        if not self.history:
            return False
        last = self.history.pop()
        self.ko = last["prev_ko"]

        if last["action"] == "pass":
            self.consecutive_passes = max(0, self.consecutive_passes - 1)
            return True

        r, c, side = last["r"], last["c"], last["side"]
        self.board[r][c] = EMPTY
        opponent = 3 - side
        for cr, cc in last["captured"]:
            self.board[cr][cc] = opponent
        self.captured[side] -= len(last["captured"])
        self.consecutive_passes = 0
        return True

    def is_game_over(self) -> bool:
        """Trò chơi kết thúc khi cả hai bên liên tiếp bỏ lượt (2 lần pass)."""
        return self.consecutive_passes >= 2

    def score(self) -> dict:
        """Tính điểm theo luật Diện tích (Tromp-Taylor / Area scoring).

        Điểm = số quân sống trên bàn + số ô đất trống được bao hoàn toàn bởi quân của mình.
        Trắng nhận thêm điểm komi.
        """
        black_stones = 0
        white_stones = 0
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == BLACK:
                    black_stones += 1
                elif self.board[r][c] == WHITE:
                    white_stones += 1

        black_territory = 0
        white_territory = 0
        visited: set[tuple[int, int]] = set()

        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] != EMPTY or (r, c) in visited:
                    continue
                # Loang vùng trống
                comp: list[tuple[int, int]] = []
                queue = [(r, c)]
                visited.add((r, c))
                borders: set[int] = set()

                while queue:
                    curr_r, curr_c = queue.pop()
                    comp.append((curr_r, curr_c))
                    for nr, nc in self.neighbors(curr_r, curr_c):
                        color = self.board[nr][nc]
                        if color == EMPTY:
                            if (nr, nc) not in visited:
                                visited.add((nr, nc))
                                queue.append((nr, nc))
                        else:
                            borders.add(color)

                if borders == {BLACK}:
                    black_territory += len(comp)
                elif borders == {WHITE}:
                    white_territory += len(comp)
                # Nếu chạm cả hai hoặc không chạm ai (dame) thì 0 điểm đất

        black_total = black_stones + black_territory
        white_total = white_stones + white_territory + self.komi
        winner = BLACK if black_total > white_total else WHITE

        return {
            "black": {
                "stones": black_stones,
                "territory": black_territory,
                "total": black_total,
            },
            "white": {
                "stones": white_stones,
                "territory": white_territory,
                "komi": self.komi,
                "total": white_total,
            },
            "winner": winner,
            "margin": round(abs(black_total - white_total), 1),
        }


# ==============================================================================
# BOT CỜ VÂY (MONTE CARLO TREE SEARCH / UCT & BẢN SAO NHANH FASTBOARD)
# ==============================================================================

@dataclass
class GoSearchResult:
    move: tuple[int, int] | None
    is_pass: bool
    elapsed: float = 0.0
    nodes: int = 0
    message: str = ""


_NEIGHBORS_CACHE: dict[int, list[tuple[int, ...]]] = {}
_DIAGONALS_CACHE: dict[int, list[tuple[int, ...]]] = {}


def get_neighbors_table(size: int) -> list[tuple[int, ...]]:
    """Bảng tra cứu tọa độ các ô láng giềng trực giao (4 hướng)."""
    if size not in _NEIGHBORS_CACHE:
        table = []
        for r in range(size):
            for c in range(size):
                nbrs = []
                if r > 0:
                    nbrs.append((r - 1) * size + c)
                if r + 1 < size:
                    nbrs.append((r + 1) * size + c)
                if c > 0:
                    nbrs.append(r * size + (c - 1))
                if c + 1 < size:
                    nbrs.append(r * size + (c + 1))
                table.append(tuple(nbrs))
        _NEIGHBORS_CACHE[size] = table
    return _NEIGHBORS_CACHE[size]


def get_diagonals_table(size: int) -> list[tuple[int, ...]]:
    """Bảng tra cứu tọa độ các ô đường chéo (4 góc)."""
    if size not in _DIAGONALS_CACHE:
        table = []
        for r in range(size):
            for c in range(size):
                diags = []
                if r > 0 and c > 0:
                    diags.append((r - 1) * size + (c - 1))
                if r > 0 and c + 1 < size:
                    diags.append((r - 1) * size + (c + 1))
                if r + 1 < size and c > 0:
                    diags.append((r + 1) * size + (c - 1))
                if r + 1 < size and c + 1 < size:
                    diags.append((r + 1) * size + (c + 1))
                table.append(tuple(diags))
        _DIAGONALS_CACHE[size] = table
    return _DIAGONALS_CACHE[size]


class FastBoard:
    """Bản sao bàn cờ siêu nhẹ dùng riêng cho mô phỏng MCTS (không lưu history)."""

    __slots__ = (
        "size",
        "grid",
        "ko",
        "captured_black",
        "captured_white",
        "consecutive_passes",
        "_nbrs",
        "_diags",
    )

    def __init__(self, size: int):
        self.size = size
        self.grid = [EMPTY] * (size * size)
        self.ko: int | None = None
        self.captured_black = 0
        self.captured_white = 0
        self.consecutive_passes = 0
        self._nbrs = get_neighbors_table(size)
        self._diags = get_diagonals_table(size)

    @classmethod
    def from_go_board(cls, board: GoBoard) -> FastBoard:
        fb = cls(board.size)
        size = board.size
        grid = fb.grid
        for r in range(size):
            row = board.board[r]
            offset = r * size
            for c in range(size):
                grid[offset + c] = row[c]
        if board.ko is not None:
            fb.ko = board.ko[0] * size + board.ko[1]
        else:
            fb.ko = None
        fb.captured_black = board.captured[BLACK]
        fb.captured_white = board.captured[WHITE]
        fb.consecutive_passes = board.consecutive_passes
        return fb

    def clone(self) -> FastBoard:
        """Sao chép cực nhanh chỉ grid, ko, captured và consecutive_passes."""
        other = FastBoard.__new__(FastBoard)
        other.size = self.size
        other.grid = self.grid[:]
        other.ko = self.ko
        other.captured_black = self.captured_black
        other.captured_white = self.captured_white
        other.consecutive_passes = self.consecutive_passes
        other._nbrs = self._nbrs
        other._diags = self._diags
        return other

    def get_group(self, pos: int) -> tuple[list[int], set[int]]:
        color = self.grid[pos]
        if color == EMPTY:
            return [], set()
        stones = [pos]
        liberties: set[int] = set()
        visited = {pos}
        queue = [pos]
        nbrs = self._nbrs
        grid = self.grid

        while queue:
            curr = queue.pop()
            for n in nbrs[curr]:
                ncol = grid[n]
                if ncol == EMPTY:
                    liberties.add(n)
                elif ncol == color and n not in visited:
                    visited.add(n)
                    stones.append(n)
                    queue.append(n)
        return stones, liberties

    def is_legal(self, side: int, pos: int) -> bool:
        if self.grid[pos] != EMPTY or self.ko == pos:
            return False

        opponent = 3 - side
        grid = self.grid
        nbrs = self._nbrs

        grid[pos] = side
        captured_count = 0

        for n in nbrs[pos]:
            if grid[n] == opponent:
                _, opp_libs = self.get_group(n)
                if len(opp_libs) == 0:
                    captured_count += 1

        _, my_libs = self.get_group(pos)
        is_suicide = (len(my_libs) == 0 and captured_count == 0)

        grid[pos] = EMPTY
        return not is_suicide

    def play(self, side: int, pos: int) -> list[int] | None:
        if self.grid[pos] != EMPTY or self.ko == pos:
            return None

        opponent = 3 - side
        grid = self.grid
        nbrs = self._nbrs
        grid[pos] = side
        all_captured: list[int] = []

        opp_checked: set[int] = set()
        for n in nbrs[pos]:
            if grid[n] == opponent and n not in opp_checked:
                opp_stones, opp_libs = self.get_group(n)
                opp_checked.update(opp_stones)
                if len(opp_libs) == 0:
                    for s in opp_stones:
                        grid[s] = EMPTY
                        all_captured.append(s)

        my_stones, my_libs = self.get_group(pos)
        if len(my_libs) == 0 and len(all_captured) == 0:
            grid[pos] = EMPTY
            return None

        if side == BLACK:
            self.captured_black += len(all_captured)
        else:
            self.captured_white += len(all_captured)

        if len(all_captured) == 1:
            if len(my_stones) == 1 and len(my_libs) == 1 and all_captured[0] in my_libs:
                self.ko = all_captured[0]
            else:
                self.ko = None
        else:
            self.ko = None

        self.consecutive_passes = 0
        return all_captured

    def pass_turn(self, side: int):
        self.ko = None
        self.consecutive_passes += 1

    def is_own_eye(self, pos: int, side: int) -> bool:
        """Kiểm tra ô trống pos có phải là mắt thật của bên side hay không."""
        if self.grid[pos] != EMPTY:
            return False
        nbrs = self._nbrs[pos]
        grid = self.grid
        for n in nbrs:
            if grid[n] != side:
                return False

        diags = self._diags[pos]
        opp = 3 - side
        opp_diags = sum(1 for d in diags if grid[d] == opp)
        max_opp_diags = 1 if len(nbrs) == 4 else 0
        return opp_diags <= max_opp_diags

    def find_atari_liberties(self, side: int) -> set[int]:
        """Tìm các ô khí duy nhất của các nhóm quân thuộc side đang ở thế Atari."""
        atari_libs: set[int] = set()
        counted: set[int] = set()
        grid = self.grid
        for pos, col in enumerate(grid):
            if col == side and pos not in counted:
                stones, liberties = self.get_group(pos)
                counted.update(stones)
                if len(liberties) == 1:
                    atari_libs.add(next(iter(liberties)))
        return atari_libs

    def fast_area_scores(self, komi: float = 7.5) -> tuple[float, float]:
        """Tính điểm diện tích Tromp-Taylor nhanh cho cuối ván mô phỏng."""
        grid = self.grid
        size = self.size
        black_total = float(sum(1 for c in grid if c == BLACK))
        white_total = float(sum(1 for c in grid if c == WHITE))

        visited: set[int] = set()
        nbrs = self._nbrs
        total_cells = size * size

        for i in range(total_cells):
            if grid[i] != EMPTY or i in visited:
                continue
            comp = [i]
            queue = [i]
            visited.add(i)
            borders: set[int] = set()

            while queue:
                curr = queue.pop()
                for n in nbrs[curr]:
                    col = grid[n]
                    if col == EMPTY:
                        if n not in visited:
                            visited.add(n)
                            queue.append(n)
                            comp.append(n)
                    else:
                        borders.add(col)

            if borders == {BLACK}:
                black_total += len(comp)
            elif borders == {WHITE}:
                white_total += len(comp)

        white_total += komi
        return black_total, white_total


def playout_fast(
    board: FastBoard,
    current_side: int,
    last_move: int | None,
    max_steps: int = 30,
) -> tuple[float, float]:
    """Mô phỏng ngẫu nhiên có ưu tiên nhẹ: ưu tiên bắt quân atari và không tự lấp mắt mình."""
    curr = current_side
    size = board.size
    total_cells = size * size
    last = last_move

    for _ in range(max_steps):
        if board.consecutive_passes >= 2:
            break

        opp = 3 - curr
        nbrs = board._nbrs
        grid = board.grid
        move: int | None = None

        # 1. Ưu tiên kiểm tra bắt quân atari của đối phương quanh nước vừa đánh
        if last is not None:
            for n in nbrs[last]:
                if grid[n] == opp:
                    _, libs = board.get_group(n)
                    if len(libs) == 1:
                        target = next(iter(libs))
                        if board.is_legal(curr, target):
                            move = target
                            break

        # Nếu chưa tìm được, quét nhanh các nhóm đối phương bị atari trên bàn
        if move is None:
            opp_ataris = board.find_atari_liberties(opp)
            for target in opp_ataris:
                if board.is_legal(curr, target):
                    move = target
                    break

        # 2. Cứu quân mình bị atari nếu có thể
        if move is None:
            my_ataris = board.find_atari_liberties(curr)
            for target in my_ataris:
                if not board.is_own_eye(target, curr) and board.is_legal(curr, target):
                    move = target
                    break

        # 3. Chọn ngẫu nhiên nước đi hợp lệ không tự lấp mắt mình
        if move is None:
            empty_positions = [i for i in range(total_cells) if grid[i] == EMPTY]
            if not empty_positions:
                board.pass_turn(curr)
                last = None
                curr = opp
                continue

            random.shuffle(empty_positions)
            for p in empty_positions:
                if not board.is_own_eye(p, curr) and board.is_legal(curr, p):
                    move = p
                    break

        if move is not None:
            board.play(curr, move)
            last = move
        else:
            board.pass_turn(curr)
            last = None

        curr = opp

    return board.fast_area_scores()


class MCTSNode:
    """Nút trên cây tìm kiếm Monte Carlo (UCT / PUCT)."""

    __slots__ = (
        "move",
        "parent",
        "side_to_move",
        "children",
        "untried_moves",
        "visits",
        "value",
        "prior",
    )

    def __init__(
        self,
        move: int | None,
        parent: MCTSNode | None,
        side_to_move: int,
        prior: float = 1.0,
    ):
        self.move = move
        self.parent = parent
        self.side_to_move = side_to_move
        self.children: list[MCTSNode] = []
        self.untried_moves: list[tuple[int, float]] | None = None
        self.visits = 0
        self.value = 0.0
        self.prior = prior

    def select_child(self, c_param: float = 1.414) -> MCTSNode:
        sqrt_n = math.sqrt(self.visits)
        best_score = -float("inf")
        best_child = self.children[0]
        for child in self.children:
            if child.visits == 0:
                q = 0.5
            else:
                q = child.value / child.visits
            u = c_param * child.prior * (sqrt_n / (1 + child.visits))
            score = q + u
            if score > best_score:
                best_score = score
                best_child = child
        return best_child


class GoBot:
    """Bot cờ vây sử dụng Monte Carlo Tree Search (MCTS/UCT) với 3 mức độ khó:

    - Dễ (0.5s): Giới hạn 0.5s, playout nông, thỉnh thoảng có sai sót nhẹ.
    - Vừa (1.0s): Giới hạn 1.0s, playout cân bằng, chọn nước đi tối ưu theo số lần duyệt.
    - Khó (2.0s): Giới hạn 2.0s, playout sâu và nhiều mô phỏng nhất.
    """

    def __init__(self, level: int = 1):
        self.level = level

    def _get_scored_moves(self, fb: FastBoard, side: int) -> list[tuple[int, float]]:
        """Lọc các nước hợp lệ không tự hại/lấp mắt và gán trọng số heuristic (prior)."""
        size = fb.size
        total_cells = size * size
        opp = 3 - side

        opp_atari = fb.find_atari_liberties(opp)
        my_atari = fb.find_atari_liberties(side)

        star_points = set()
        for r, c in STAR_POINTS.get(size, []):
            star_points.add(r * size + c)

        candidates: list[tuple[int, float]] = []

        for pos in range(total_cells):
            if fb.grid[pos] != EMPTY or fb.ko == pos:
                continue
            # Không tự lấp mắt của mình
            if fb.is_own_eye(pos, side):
                continue
            if not fb.is_legal(side, pos):
                continue

            test_fb = fb.clone()
            captured = test_fb.play(side, pos)
            if captured is None:
                continue
            _, my_libs = test_fb.get_group(pos)

            # Phạt loại bỏ nước tự hại (self-atari không bắt được quân nào)
            is_self_harm = (len(captured) == 0 and len(my_libs) == 1)
            if is_self_harm:
                continue

            prior = 1.0

            # 1. Bắt quân đối phương trong thế Atari (ưu tiên cực cao)
            if pos in opp_atari or len(captured) > 0:
                prior += 50.0 + len(captured) * 10.0

            # 2. Cứu quân mình đang bị Atari (nếu thoát được >= 2 khí)
            if pos in my_atari and len(my_libs) >= 2:
                prior += 30.0

            # 3. Tạo thế đe dọa (Atari nhóm 2 khí của đối thủ)
            for n in test_fb._nbrs[pos]:
                if test_fb.grid[n] == opp:
                    _, opp_libs = test_fb.get_group(n)
                    if len(opp_libs) == 1:
                        prior += 15.0
                    elif len(opp_libs) == 2:
                        prior += 5.0

            # Ưu tiên điểm sao hoặc các điểm góc khai cuộc
            if pos in star_points:
                prior += 5.0

            candidates.append((pos, prior))

        # Chuẩn hóa prior
        total_prior = sum(p for _, p in candidates)
        if total_prior > 0:
            candidates = [(pos, p / total_prior * len(candidates)) for pos, p in candidates]

        # Sắp xếp để nước ưu tiên cao nhất ở cuối danh sách (được pop() trước trong MCTS)
        candidates.sort(key=lambda x: x[1])
        return candidates

    def choose(
        self,
        board: GoBoard,
        side: int,
        cancel_event=None,
    ) -> GoSearchResult:
        start_time = time.perf_counter()
        if cancel_event and cancel_event.is_set():
            return GoSearchResult(None, True, time.perf_counter() - start_time, 0)

        # Ngân sách thời gian theo GO_LEVELS (0.5s / 1.0s / 2.0s)
        time_budget = GO_LEVELS[self.level][1] if 0 <= self.level < len(GO_LEVELS) else 1.0

        if self.level == 0:
            max_steps = 15
        elif self.level == 1:
            max_steps = 30
        else:
            max_steps = 50

        fb = FastBoard.from_go_board(board)
        candidate_moves = self._get_scored_moves(fb, side)

        # Bot chỉ bỏ lượt khi mọi nước còn lại đều là lấp mắt mình hoặc tự hại
        if not candidate_moves:
            return GoSearchResult(None, True, time.perf_counter() - start_time, 0, "Bỏ lượt (thế cờ đã an bài)")

        # Nếu chỉ có duy nhất 1 nước hợp lệ an toàn, đánh luôn không cần tìm kiếm
        if len(candidate_moves) == 1:
            best_pos = candidate_moves[0][0]
            move = (best_pos // fb.size, best_pos % fb.size)
            return GoSearchResult(move, False, time.perf_counter() - start_time, 1, f"Đánh tại ({move[0]}, {move[1]})")

        root = MCTSNode(move=None, parent=None, side_to_move=side)
        root.untried_moves = candidate_moves[:]
        nodes = 0

        while (time.perf_counter() - start_time) < time_budget:
            # Kiểm tra hủy thường xuyên
            if cancel_event and cancel_event.is_set():
                return GoSearchResult(None, True, time.perf_counter() - start_time, nodes)

            nodes += 1

            # 1. Selection
            node = root
            sim_board = fb.clone()
            curr_side = side

            while not node.untried_moves and node.children:
                node = node.select_child()
                if node.move is not None:
                    sim_board.play(curr_side, node.move)
                else:
                    sim_board.pass_turn(curr_side)
                curr_side = 3 - curr_side

            # 2. Expansion
            if node.untried_moves:
                m, prior = node.untried_moves.pop()
                sim_board.play(curr_side, m)
                child_side = 3 - curr_side
                child_node = MCTSNode(move=m, parent=node, side_to_move=child_side, prior=prior)
                node.children.append(child_node)
                node = child_node
                curr_side = child_side

            # 3. Simulation (Playout)
            b_score, w_score = playout_fast(sim_board, curr_side, node.move, max_steps=max_steps)

            # 4. Backpropagation
            curr_node = node
            while curr_node is not None:
                curr_node.visits += 1
                if curr_node.parent is not None:
                    player = curr_node.parent.side_to_move
                    diff = (b_score - w_score) if player == BLACK else (w_score - b_score)
                    reward = 1.0 / (1.0 + math.exp(-diff / 8.0))
                    curr_node.value += reward
                curr_node = curr_node.parent

        if not root.children:
            best_pos = candidate_moves[-1][0]
        else:
            sorted_c = sorted(root.children, key=lambda c: c.visits, reverse=True)
            # Mức Dễ: có xác suất chọn nước ngẫu nhiên trong top 3 nếu không chênh lệch quá lớn
            if (
                self.level == 0
                and len(sorted_c) > 1
                and sorted_c[0].visits < 2 * sorted_c[1].visits
                and random.random() < 0.25
            ):
                chosen = random.choice(sorted_c[:min(3, len(sorted_c))])
            else:
                chosen = sorted_c[0]
            best_pos = chosen.move

        if best_pos is None:
            return GoSearchResult(None, True, time.perf_counter() - start_time, nodes, "Bỏ lượt")

        move = (best_pos // fb.size, best_pos % fb.size)
        elapsed = time.perf_counter() - start_time
        return GoSearchResult(move, False, elapsed, nodes, f"Đánh tại ({move[0]}, {move[1]})")


# ==============================================================================
# KIỂM THỬ TỰ ĐỘNG (--self-test)
# ==============================================================================

def self_test():
    """Kiểm tra toàn bộ các luật cờ vây: bắt quân, tự sát, kiếp, bỏ lượt, đếm điểm, bot."""
    print("Bắt đầu self-test cờ vây...")

    # 1. Bắt 1 quân ở giữa bàn
    b = GoBoard(9)
    # Trắng ở (4, 4)
    b.board[4][4] = WHITE
    # Đen vây 4 phía: (3, 4), (5, 4), (4, 3)
    b.play(BLACK, 3, 4)
    b.play(BLACK, 5, 4)
    b.play(BLACK, 4, 3)
    # Nước cuối của Đen tại (4, 5) để bắt Trắng
    captured = b.play(BLACK, 4, 5)
    assert (4, 4) in captured, "Đen phải bắt được quân Trắng tại (4, 4)"
    assert b.board[4][4] == EMPTY, "Ô (4, 4) phải trở thành trống sau khi bị bắt"
    assert b.captured[BLACK] == 1
    print("✓ Test 1: Bắt 1 quân ở giữa bàn - THÀNH CÔNG")

    # 2. Bắt quân ở góc (chỉ cần 2 quân vây)
    b = GoBoard(9)
    b.board[0][0] = WHITE
    b.play(BLACK, 0, 1)
    captured = b.play(BLACK, 1, 0)
    assert (0, 0) in captured
    assert b.board[0][0] == EMPTY
    print("✓ Test 2: Bắt quân ở góc - THÀNH CÔNG")

    # 3. Bắt cả một đám quân (group capture)
    b = GoBoard(9)
    # Đám Trắng gồm (2, 2) và (2, 3)
    b.board[2][2] = WHITE
    b.board[2][3] = WHITE
    # Đen vây kín: (1, 2), (1, 3), (3, 2), (3, 3), (2, 1)
    for r, c in [(1, 2), (1, 3), (3, 2), (3, 3), (2, 1)]:
        b.play(BLACK, r, c)
    # Đen đánh ô cuối (2, 4)
    captured = b.play(BLACK, 2, 4)
    assert len(captured) == 2
    assert (2, 2) in captured and (2, 3) in captured
    assert b.board[2][2] == EMPTY and b.board[2][3] == EMPTY
    print("✓ Test 3: Bắt cả một đám quân - THÀNH CÔNG")

    # 4. Cấm tự sát (Suicide is illegal)
    b = GoBoard(9)
    # Đen bao quanh ô (0, 0): (0, 1) và (1, 0)
    b.play(BLACK, 0, 1)
    b.play(BLACK, 1, 0)
    # Trắng đánh vào (0, 0) là tự sát vì không còn khí và không bắt được ai
    legal, reason = b.is_legal(WHITE, 0, 0)
    assert not legal, "Trắng tự sát ở góc phải bị cấm"
    try:
        b.play(WHITE, 0, 0)
        assert False, "Phải raise ValueError khi tự sát"
    except ValueError:
        pass
    print("✓ Test 4: Cấm tự sát - THÀNH CÔNG")

    # 5. Cho phép đánh vào ô hết khí NẾU bắt được quân đối phương
    b = GoBoard(9)
    # Trắng tại (0, 0). Đen tại (0, 1). Trắng tại (1, 1).
    # Đen đánh vào (1, 0) để bắt quân Trắng tại (0, 0)
    b.board[0][0] = WHITE
    b.board[0][1] = BLACK
    b.board[1][1] = WHITE
    # Ô (1, 0) không có khí trực tiếp nhưng bắt được (0, 0)
    legal, _ = b.is_legal(BLACK, 1, 0)
    assert legal, "Được phép đánh nếu bắt được quân đối phương"
    captured = b.play(BLACK, 1, 0)
    assert (0, 0) in captured
    print("✓ Test 5: Đánh bắt quân khi hết khí - THÀNH CÔNG")

    # 6. Luật Kiếp (Ko rule)
    b = GoBoard(9)
    # Thiết lập thế cờ Kiếp kinh điển:
    # Đen tại (1, 0), (0, 1), (1, 2)
    # Trắng tại (2, 1), (1, 2) -> (1, 2) không được trùng
    # Hãy xếp:
    # Đen: (1, 1), (0, 2), (2, 2)
    # Trắng: (0, 3), (2, 3), (1, 4)
    # Quân tranh chấp: Đen (1, 3), Trắng (1, 2)
    b.board[1][1] = BLACK
    b.board[0][2] = BLACK
    b.board[2][2] = BLACK
    b.board[1][3] = BLACK  # Đen ở đây

    b.board[0][3] = WHITE
    b.board[2][3] = WHITE
    b.board[1][4] = WHITE
    # Lúc này Đen (1, 3) chỉ còn 1 khí tại (1, 2).
    # Trắng đánh vào (1, 2) bắt quân Đen tại (1, 3).
    captured = b.play(WHITE, 1, 2)
    assert (1, 3) in captured
    assert b.ko == (1, 3), "Ô (1, 3) phải bị khóa do luật Kiếp"

    # Đen không được đánh ngay lại vào (1, 3)
    legal, reason = b.is_legal(BLACK, 1, 3)
    assert not legal, "Đen không được bắt lại ngay do luật Kiếp"

    # Đen đánh nước khác (ví dụ 8, 8)
    b.play(BLACK, 8, 8)
    # Lúc này Ko đã được giải tỏa
    assert b.ko is None
    # Trắng đánh nước khác (8, 7)
    b.play(WHITE, 8, 7)
    # Giờ Đen lại được quyền đánh vào (1, 3)
    legal, _ = b.is_legal(BLACK, 1, 3)
    assert legal, "Sau khi đối kháng ở nơi khác, Đen được quyền bắt lại Kiếp"
    print("✓ Test 6: Luật Kiếp (Ko rule) - THÀNH CÔNG")

    # 7. Hoàn tác (Undo)
    b = GoBoard(9)
    b.play(BLACK, 4, 4)
    b.play(WHITE, 4, 5)
    assert b.board[4][4] == BLACK and b.board[4][5] == WHITE
    b.undo()
    assert b.board[4][5] == EMPTY
    assert b.board[4][4] == BLACK
    print("✓ Test 7: Hoàn tác (Undo) - THÀNH CÔNG")

    # 8. Bỏ lượt (Pass) và Đếm điểm (Scoring)
    b = GoBoard(9, komi=5.5)
    # Đen chiếm góc trên (0, 0), Trắng chiếm góc dưới (8, 8)
    b.play(BLACK, 0, 0)
    b.play(WHITE, 8, 8)
    b.pass_turn(BLACK)
    assert not b.is_game_over()
    b.pass_turn(WHITE)
    assert b.is_game_over(), "2 bên cùng bỏ lượt thì ván kết thúc"

    score_result = b.score()
    assert "black" in score_result and "white" in score_result
    assert score_result["white"]["komi"] == 5.5
    print("✓ Test 8: Bỏ lượt và đếm điểm - THÀNH CÔNG")

    # 9. Bot cờ vây
    bot = GoBot(level=1)
    b = GoBoard(9)
    res = bot.choose(b, BLACK)
    assert res.move is not None
    assert b.is_legal(BLACK, *res.move)[0]
    print(f"✓ Test 9: Bot cờ vây hoạt động tốt ({res.message}, thời gian: {res.elapsed:.3f}s)")

    # 10. Bot bắt quân khi đối phương bị atari
    b = GoBoard(9)
    b.board[0][0] = WHITE
    b.board[0][1] = BLACK
    bot = GoBot(level=1)
    res = bot.choose(b, BLACK)
    assert res.move == (1, 0), f"Bot Đen phải bắt quân Trắng tại (1, 0), nhưng đánh tại {res.move}"
    print("✓ Test 10: Bot bắt quân khi đối phương bị atari - THÀNH CÔNG")

    # 11. Bot cứu quân mình khi bị atari
    b = GoBoard(9)
    b.board[4][4] = WHITE
    b.board[3][4] = BLACK
    b.board[5][4] = BLACK
    b.board[4][3] = BLACK
    bot = GoBot(level=1)
    res = bot.choose(b, WHITE)
    assert res.move == (4, 5), f"Bot Trắng phải nối khí cứu mình tại (4, 5), nhưng đánh tại {res.move}"
    print("✓ Test 11: Bot cứu quân mình khi bị atari - THÀNH CÔNG")

    # 12. Bot không tự lấp mắt
    b = GoBoard(9)
    b.board[0][1] = BLACK
    b.board[1][0] = BLACK
    b.board[1][1] = BLACK
    bot = GoBot(level=1)
    res = bot.choose(b, BLACK)
    assert res.move != (0, 0), "Bot không được tự lấp mắt của mình tại (0, 0)"
    assert res.move is not None, "Bot phải chọn nước đi khác thay vì bỏ lượt khi còn nước an toàn"
    print("✓ Test 12: Bot không tự lấp mắt - THÀNH CÔNG")

    # 13. Bot dừng đúng hạn khi cancel_event được set
    bot = GoBot(level=2)  # Mức Khó (2.0s) nhưng phải dừng ngay khi có tín hiệu hủy
    cancel_event = threading.Event()
    cancel_event.set()
    t0 = time.perf_counter()
    res = bot.choose(b, BLACK, cancel_event=cancel_event)
    elapsed = time.perf_counter() - t0
    assert res.is_pass is True, "Bot phải trả về is_pass = True khi cancel_event được set"
    assert elapsed < 0.1, f"Bot phải dừng ngay lập tức khi cancel_event được set (mất {elapsed:.4f}s)"

    # Kiểm tra hủy luồng bot đang tìm kiếm dở
    cancel_event_bg = threading.Event()
    th = threading.Thread(target=lambda: bot.choose(b, BLACK, cancel_event=cancel_event_bg))
    th.start()
    time.sleep(0.05)
    cancel_event_bg.set()
    th.join(timeout=0.5)
    assert not th.is_alive(), "Luồng bot phải dừng kịp thời khi cancel_event được set giữa chừng"
    print("✓ Test 13: Bot dừng đúng hạn khi cancel_event được set - THÀNH CÔNG")

    print("\n===> TẤT CẢ SELF-TEST CỜ VÂY ĐỀU ĐẠT! <===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Engine cờ vây")
    parser.add_argument("--self-test", action="store_true", help="Chạy kiểm thử tự động")
    args = parser.parse_args()

    if args.self_test:
        self_test()
    else:
        print("Chạy kiểm thử: python go_game.py --self-test")
