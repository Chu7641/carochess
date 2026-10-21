# -*- coding: utf-8 -*-
"""Cờ caro / Gomoku: chơi bằng chuột, bot tìm kiếm ở luồng nền.

Cài đặt (Python 3.10 trở lên):
    python -m pip install pygame
Chạy:
    python caro_game.py
Kiểm tra bộ luật và các tình huống chiến thuật, không cần pygame:
    python caro_game.py --self-test

Chuột trái: đánh quân. Chuột phải / U: hoàn tác. R: ván mới.
F: đổi quân đi trước. S: đổi bên bot. B: đổi luật và bắt đầu ván mới.
P: bật/tắt bot nghĩ trước trong lượt của bạn.
+/-: đổi cả hai chiều bàn. 1/2/3: chọn độ khó. Esc: thoát.

Luật mặc định: từ 5 quân liên tiếp trở lên là thắng, kể cả khi bị chặn hai đầu.
Nhấn B để bật luật chặn hai đầu (dãy bị chặn cả hai đầu bởi đối thủ
hoặc biên không thắng).
Đây không phải bộ luật Renju (không có luật cấm ba-ba, bốn-bốn).

Bot có bộ tìm chuỗi ép thắng VCF (ép bằng bốn) và VCT (ép bằng ba và bốn),
kiểm tra phòng thủ theo đúng bộ luật, iterative deepening, alpha-beta/PVS,
transposition table và đánh giá gia tăng bằng bảng mẫu dòng mã hóa cơ số 3.
Các chuỗi ép được kiểm tra với mọi cách chặn hợp lệ và nước phản công bằng bốn.
Trong lượt người chơi, bot đoán nước đi và tính trước nước đáp (ponder).
Tìm kiếm có giới hạn thời gian
và giới hạn nhánh; không có bảo đảm bất bại trên mọi thế cờ.
Chỉ pygame là thư viện ngoài; không tải model hoặc gọi dịch vụ mạng.
"""

from __future__ import annotations

import argparse
import math
import queue
import random
import re
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from functools import lru_cache


# ---------------- CẤU HÌNH ----------------
BOARD_ROWS = 15
BOARD_COLS = 15
WIN_LENGTH = 5
BOT_ENABLED = True
BOT_PLAYER = 2
FIRST_PLAYER = 1
STRICT_BLOCKED_MODE = False

# Mặc định là mức 3: chuyên gia. Tăng thời gian để bot xét được nhiều hơn.
BOT_DEPTH = 12
BOT_MOVE_LIMIT = 24
BOT_TIME_BUDGET = 12.0
VCF_MAX_ATTACKS = 12     # tối đa 12 nước tấn công trong chuỗi ép; không phải độ sâu toàn ván
VCT_MAX_THREATS = 4      # tối đa 4 nước dọa (ba hoặc bốn) trong chuỗi VCT
VCT_VCF_ATTACKS = 6      # độ sâu VCF thử ở mỗi nút VCT
VCT_BRANCH = 10          # số nước dọa thử ở mỗi lượt tấn công VCT
THREAT_MIN_SCORE = 700   # điểm tăng tối thiểu để coi một nước là nước tạo ba
BOT_PONDER = True        # bot nghĩ trước trong lượt người chơi

CELL = 42
MARGIN = 36
PANEL_W = 320
TITLE_H = 56
MIN_WIDTH = 780
MIN_HEIGHT = 760
EMPTY, X, O = 0, 1, 2
DIRS = ((1, 0), (0, 1), (1, 1), (1, -1))
MATE = 1_000_000_000
MATE_BOUND = MATE - 100_000
STATIC_LIMIT = 20_000_000
INF = MATE * 2

LEVELS = (
    ("Nhanh", 2.0, 4, 12),
    ("Mạnh", 5.0, 7, 18),
    ("Chuyên gia", BOT_TIME_BUDGET, BOT_DEPTH, BOT_MOVE_LIMIT),
)

C_BG = (244, 237, 222)
C_BOARD = (222, 184, 135)
C_LINE = (95, 67, 44)
C_TEXT = (43, 42, 39)
C_TITLE = (52, 47, 40)
C_PANEL = (255, 252, 245)
C_GREEN = (56, 126, 87)
C_RED = (184, 72, 62)
C_BLUE = (67, 99, 145)
C_GREY = (102, 108, 116)
C_X = (32, 34, 37)
C_O = (191, 42, 48)


def winning_line(board, r, c, player, win_length=5, strict=False):
    """Luật dùng chung cho giao diện và bot; ô gốc phải chứa đúng quân."""
    rows, cols = len(board), len(board[0])
    if not (0 <= r < rows and 0 <= c < cols) or board[r][c] != player:
        return None
    for dr, dc in DIRS:
        cells = [(r, c)]
        free_ends = 0
        for sign in (-1, 1):
            rr, cc = r + sign * dr, c + sign * dc
            part = []
            while 0 <= rr < rows and 0 <= cc < cols and board[rr][cc] == player:
                part.append((rr, cc))
                rr += sign * dr
                cc += sign * dc
            if sign == -1:
                cells = list(reversed(part)) + cells
            else:
                cells.extend(part)
            if 0 <= rr < rows and 0 <= cc < cols and board[rr][cc] == EMPTY:
                free_ends += 1
        if len(cells) >= win_length and (not strict or free_ends):
            return cells
    return None


def _winning_slots(text, win_length, strict):
    """Các dấu '.' có thể biến thành một dãy thắng hợp lệ trong dòng."""
    slots = set()
    for start in range(len(text) - win_length + 1):
        window = text[start:start + win_length]
        if window.count("X") != win_length - 1 or window.count(".") != 1:
            continue
        slot = start + window.index(".")
        if strict:
            left, right = slot - 1, slot + 1
            while left >= 0 and text[left] == "X":
                left -= 1
            while right < len(text) and text[right] == "X":
                right += 1
            if not ((left >= 0 and text[left] == ".")
                    or (right < len(text) and text[right] == ".")):
                continue
        slots.add(slot)
    return tuple(sorted(slots))


@lru_cache(maxsize=90_000)
def line_features(text, win_length, strict):
    """Điểm + các ô thắng ngay. X: quân mình, #: đối thủ, .: ô trống."""
    slots = _winning_slots(text, win_length, strict)
    score = len(slots) * 50_000
    if len(slots) >= 2:
        # Với luật chặn hai đầu, hai ô thắng có thể cùng bị vô hiệu
        # bởi một quân đối thủ. Chỉ cộng điểm đòn kép thật khi đã kiểm tra.
        forced = not strict or all(
            _winning_slots(text[:i] + "#" + text[i + 1:], win_length, strict)
            for i, value in enumerate(text) if value == ".")
        score += 180_000 if forced else 8_000
    for match in re.finditer("X+", text):
        a, b = match.span()
        run = b - a
        open_ends = int(a > 0 and text[a - 1] == ".")
        open_ends += int(b < len(text) and text[b] == ".")
        if run >= win_length:
            if not strict or open_ends:
                score += 10_000_000
        elif open_ends:
            if run == win_length - 1:
                # Các điểm thắng thật đã được tính ở slots; không coi
                # một dãy bị chặn hai đầu sau khi nối thành chiến thắng.
                score += 150 * open_ends
            elif run == win_length - 2:
                score += 8_000 if open_ends == 2 else 650
            elif run == win_length - 3:
                score += 350 if open_ends == 2 else 45
            else:
                score += 5 * open_ends
    # Chuỗi đứt: XX.X., X.XX., X.X.X... Các ô thắng ở giữa đã được
    # nhận diện bởi _winning_slots; ở đây chấm tiềm năng thấp hơn.
    for start in range(len(text) - win_length + 1):
        window = text[start:start + win_length]
        if "#" in window or "." not in window[1:-1]:
            continue
        count = window.count("X")
        if count == win_length - 2:
            score += 900
        elif win_length >= 4 and count == win_length - 3:
            score += 50
    return score, slots


# (độ dài dòng, WIN_LENGTH, luật chặn) -> {mã cơ số 3 -> đặc trưng hai bên}.
_LINE_TABLES = {}


def _line_table(length, win_length, strict):
    return _LINE_TABLES.setdefault((length, win_length, strict), {})


def _line_info(table, length, code, win_length, strict):
    """Đặc trưng của dòng mã hóa cơ số 3; ô đầu dòng là chữ số thấp nhất.

    Trả ((điểm X, điểm O), (ô thắng X, ô thắng O)), ô tính theo vị trí trong dòng.
    """
    digits, value = [], code
    for _ in range(length):
        value, digit = divmod(value, 3)
        digits.append(digit)
    fx = line_features("".join(".X#"[d] for d in digits), win_length, strict)
    fo = line_features("".join(".#X"[d] for d in digits), win_length, strict)
    info = (fx[0], fo[0]), (fx[1], fo[1])
    if len(table) > 250_000:
        table.clear()
    table[code] = info
    return info


class Position:
    """Bản sao bàn cờ riêng của bot; make/unmake luôn có dữ liệu phục hồi."""

    def __init__(self, board, win_length=5, strict=False):
        if not board or not board[0] or any(len(row) != len(board[0]) for row in board):
            raise ValueError("Bàn cờ phải là một hình chữ nhật không rỗng.")
        self.rows, self.cols = len(board), len(board[0])
        self.win_length, self.strict = win_length, strict
        self.size = self.rows * self.cols
        self.cells = [v for row in board for v in row]
        if any(v not in (EMPTY, X, O) for v in self.cells):
            raise ValueError("Quân cờ phải là 0, 1 hoặc 2.")
        if not 3 <= win_length <= max(self.rows, self.cols):
            raise ValueError("WIN_LENGTH không hợp lệ.")
        self.empty_count = self.cells.count(EMPTY)
        self.coords = [divmod(i, self.cols) for i in range(self.size)]
        rng = random.Random(0xCA40 + self.rows * 101 + self.cols)
        self.zobrist = [(0, rng.getrandbits(64), rng.getrandbits(64))
                        for _ in self.cells]
        self.hash = 0
        self.near = [[] for _ in self.cells]
        self.neighbors = [0] * self.size
        self.rays = []
        for i, (r, c) in enumerate(self.coords):
            for rr in range(max(0, r - 2), min(self.rows, r + 3)):
                for cc in range(max(0, c - 2), min(self.cols, c + 3)):
                    j = rr * self.cols + cc
                    if j != i:
                        self.near[i].append(j)
            directions = []
            for dr, dc in DIRS:
                pair = []
                for sign in (-1, 1):
                    ray = []
                    rr, cc = r + sign * dr, c + sign * dc
                    while 0 <= rr < self.rows and 0 <= cc < self.cols:
                        ray.append(rr * self.cols + cc)
                        rr += sign * dr
                        cc += sign * dc
                    pair.append(tuple(ray))
                directions.append(tuple(pair))
            self.rays.append(tuple(directions))
            if self.cells[i]:
                self.hash ^= self.zobrist[i][self.cells[i]]
                for j in self.near[i]:
                    self.neighbors[j] += 1
        # Ô trống có quân trong bán kính 2; cập nhật dần để không phải quét cả bàn.
        self.frontier = {i for i, v in enumerate(self.cells) if v == EMPTY and self.neighbors[i]}
        self.lines = []
        for dr, dc in DIRS:
            for r in range(self.rows):
                for c in range(self.cols):
                    pr, pc = r - dr, c - dc
                    if 0 <= pr < self.rows and 0 <= pc < self.cols:
                        continue
                    line = []
                    rr, cc = r, c
                    while 0 <= rr < self.rows and 0 <= cc < self.cols:
                        line.append(rr * self.cols + cc)
                        rr += dr
                        cc += dc
                    if len(line) >= win_length:
                        self.lines.append(tuple(line))
        # Mỗi dòng là một số cơ số 3; đánh quân chỉ cần cộng player * 3^vị trí.
        self.cell_lines = [[] for _ in self.cells]
        self.codes = []
        for line_id, line in enumerate(self.lines):
            code = 0
            for pos, i in enumerate(line):
                weight = 3 ** pos
                self.cell_lines[i].append((line_id, weight))
                code += self.cells[i] * weight
            self.codes.append(code)
        self.tables = [_line_table(len(line), win_length, strict) for line in self.lines]
        data = [self._data(i, self.codes[i]) for i in range(len(self.lines))]
        self.line_scores = [item[0] for item in data]
        self.line_wins = [item[1] for item in data]
        self.win_counts = [[0] * self.size for _ in range(3)]
        self.win_points = [set(), set(), set()]
        for wins in self.line_wins:
            for side in (X, O):
                for i in wins[side - 1]:
                    self.win_counts[side][i] += 1
                    self.win_points[side].add(i)
        self.total = [0, sum(s[0] for s in self.line_scores),
                      sum(s[1] for s in self.line_scores)]

    def _info(self, line_id, code):
        info = self.tables[line_id].get(code)
        if info is None:
            info = _line_info(self.tables[line_id], len(self.lines[line_id]), code,
                              self.win_length, self.strict)
        return info

    def _data(self, line_id, code):
        scores, (slots_x, slots_o) = self._info(line_id, code)
        line = self.lines[line_id]
        return scores, (tuple(line[i] for i in slots_x), tuple(line[i] for i in slots_o))

    def _replace_line(self, lid, scores, wins):
        old_scores, old_wins = self.line_scores[lid], self.line_wins[lid]
        for side in (X, O):
            self.total[side] += scores[side - 1] - old_scores[side - 1]
            for i in old_wins[side - 1]:
                self.win_counts[side][i] -= 1
                if not self.win_counts[side][i]:
                    self.win_points[side].discard(i)
            for i in wins[side - 1]:
                self.win_counts[side][i] += 1
                self.win_points[side].add(i)
        self.line_scores[lid], self.line_wins[lid] = scores, wins

    def winning_moves(self, player):
        return sorted(i for i in self.win_points[player] if self.cells[i] == EMPTY)

    def defensive_moves(self, winning_points, attacker):
        """Toàn bộ nước có thể xóa TẤT CẢ các ô thắng hiện có của attacker.

        Đối thủ có thể chiếm ô thắng, hoặc (luật chặn hai đầu) bịt đầu
        trống cuối cùng của dãy sẽ hình thành. Lấy giao của các tập này
        theo mọi hướng và mọi ô thắng, không cắt theo điểm heuristic.
        Nước thắng phản công phải được bên gọi kiểm tra riêng, trước hàm này.
        """
        all_defenses = None
        for i in winning_points:
            if self.cells[i] != EMPTY:
                continue
            square_defenses = None
            for pair in self.rays[i]:
                count, ends = 1, []
                for ray in pair:
                    for j in ray:
                        if self.cells[j] != attacker:
                            if self.cells[j] == EMPTY:
                                ends.append(j)
                            break
                        count += 1
                if count < self.win_length or (self.strict and not ends):
                    continue
                blocks = {i}
                if self.strict and len(ends) == 1:
                    blocks.add(ends[0])
                square_defenses = blocks if square_defenses is None else square_defenses & blocks
            if square_defenses is not None:
                all_defenses = (square_defenses if all_defenses is None
                                else all_defenses & square_defenses)
                if not all_defenses:
                    return []
        return sorted(all_defenses) if all_defenses is not None else []

    def candidates(self):
        if not self.empty_count:
            return []
        if self.empty_count == self.size:
            return [(self.rows // 2) * self.cols + self.cols // 2]
        return sorted(self.frontier) or [i for i, v in enumerate(self.cells) if v == EMPTY]

    def wins(self, i, player):
        """Thắng nếu đánh vào ô trống i; không sửa bàn cờ."""
        if self.cells[i] != EMPTY:
            return False
        for pair in self.rays[i]:
            count, open_ends = 1, 0
            for ray in pair:
                for j in ray:
                    if self.cells[j] != player:
                        open_ends += int(self.cells[j] == EMPTY)
                        break
                    count += 1
            if count >= self.win_length and (not self.strict or open_ends):
                return True
        return False

    def play(self, i, player):
        if self.cells[i] != EMPTY:
            raise ValueError("Không được đánh đè lên quân đã có.")
        old = tuple((lid, self.codes[lid], self.line_scores[lid], self.line_wins[lid])
                    for lid, _weight in self.cell_lines[i])
        self.cells[i] = player
        self.hash ^= self.zobrist[i][player]
        self.empty_count -= 1
        self.frontier.discard(i)
        for j in self.near[i]:
            self.neighbors[j] += 1
            if self.cells[j] == EMPTY:
                self.frontier.add(j)
        for lid, weight in self.cell_lines[i]:
            code = self.codes[lid] + player * weight
            self.codes[lid] = code
            self._replace_line(lid, *self._data(lid, code))
        return i, player, old

    def undo(self, token):
        i, player, old = token
        for lid, code, previous, wins in old:
            self.codes[lid] = code
            self._replace_line(lid, previous, wins)
        for j in self.near[i]:
            self.neighbors[j] -= 1
            if not self.neighbors[j]:
                self.frontier.discard(j)
        self.empty_count += 1
        self.hash ^= self.zobrist[i][player]
        self.cells[i] = EMPTY
        if self.neighbors[i]:
            self.frontier.add(i)

    def evaluate(self, player):
        score = self.total[player] - self.total[3 - player]
        return max(-STATIC_LIMIT, min(STATIC_LIMIT, score))

    def preview(self, i, player, details=False):
        """Giá trị tấn công và các ô thắng được tạo ra sau một nước giả."""
        if self.cells[i] != EMPTY:
            raise ValueError("Ô xem trước phải trống.")
        side = player - 1
        score, wins = 0, set()
        for lid, weight in self.cell_lines[i]:
            code = self.codes[lid] + player * weight
            info = self.tables[lid].get(code) or self._info(lid, code)
            score += info[0][side] - self.line_scores[lid][side]
            slots = info[1][side]
            if slots:
                line = self.lines[lid]
                wins.update(line[slot] for slot in slots)
        if not details:
            return score, len(wins)
        forced = False
        if len(wins) >= 2:
            self.cells[i] = player
            try:
                forced = not self.defensive_moves(wins, player)
            finally:
                self.cells[i] = EMPTY
        return score, tuple(wins), forced

    def threat_cells(self, k, player):
        """Ô k, các ô thắng mà k tạo ra và (luật chặn) các đầu trống của dãy thắng.

        Chỉ quân đối thủ ở một trong các ô này mới làm thay đổi đòn kép tại k:
        chiếm ô thắng, hoặc bịt đầu dãy làm đổi tập nước chặn hợp lệ.
        """
        _score, wins, _forced = self.preview(k, player, details=True)
        cells = {k, *wins}
        if self.strict and wins:
            self.cells[k] = player
            try:
                for w in wins:
                    for pair in self.rays[w]:
                        count, ends = 1, []
                        for ray in pair:
                            for j in ray:
                                if self.cells[j] != player:
                                    if self.cells[j] == EMPTY:
                                        ends.append(j)
                                    break
                                count += 1
                        if count >= self.win_length:
                            cells.update(ends)
            finally:
                self.cells[k] = EMPTY
        return cells


class SearchStopped(Exception):
    pass


class TacticalStopped(Exception):
    pass


@dataclass
class SearchResult:
    move: tuple[int, int] | None
    depth: int = 0
    nodes: int = 0
    elapsed: float = 0.0
    score: int = 0
    forcing_plies: int = 0
    proven: bool = False


@dataclass
class TTEntry:
    depth: int
    value: int
    flag: int  # 0: exact; 1: lower bound; 2: upper bound
    move: int | None


@dataclass
class Clock:
    """Hạn chót dùng chung; luồng giao diện được đổi khi bot đoán trúng nước."""
    deadline: float = math.inf


class CaroBot:
    def __init__(self, depth=BOT_DEPTH, rows=None, cols=None,
                 time_budget=BOT_TIME_BUDGET, move_limit=BOT_MOVE_LIMIT,
                 win_length=WIN_LENGTH, strict=STRICT_BLOCKED_MODE):
        self.max_depth = max(1, int(depth))
        self.time_budget = max(0.05, float(time_budget))
        self.move_limit = max(4, int(move_limit))
        self.win_length, self.strict = win_length, strict
        self.cancel = threading.Event()
        self.clock = Clock()
        self.nodes = 0
        # Các bảng dưới đây khóa theo hash của thế cờ nên được giữ qua
        # nhiều nước, kể cả giữa lúc nghĩ trước và lúc tìm thật.
        self.tt = {}
        self.history_scores = {}
        self.vcf_cache = {}
        self.vct_cache = {}
        self.vcf_frontiers = {}
        self.proofs = {}
        self.proof_context = None
        self.phase_deadline = float("inf")

    def _check(self):
        if self.cancel.is_set() or time.perf_counter() >= self.clock.deadline:
            raise SearchStopped

    def _tactics(self, pos, side, moves):
        """Không cắt nhánh trước khi kiểm tra thắng/chặn trên mọi ứng viên."""
        self._check()
        enemy = 3 - side
        own_wins, enemy_wins = pos.winning_moves(side), pos.winning_moves(enemy)
        if own_wins:
            return own_wins, "win"
        if not enemy_wins:
            return moves, "normal"
        defenses = pos.defensive_moves(enemy_wins, enemy)
        return (defenses, "defend") if defenses else (enemy_wins, "lost")

    def _rank(self, pos, side, moves, preferred=None, limit=None):
        scored = []
        forced_fork = None
        cr, cc = (pos.rows - 1) / 2, (pos.cols - 1) / 2
        for number, i in enumerate(moves):
            if not number & 7:
                self._check()
            attack, own_points, own_fork = pos.preview(i, side, details=True)
            defend, enemy_points, enemy_fork = pos.preview(i, 3 - side, details=True)
            own_threats, enemy_threats = len(own_points), len(enemy_points)
            if own_fork:
                forced_fork = i
            r, c = pos.coords[i]
            value = attack * 10 + defend * 11
            value += own_threats * 160_000 + enemy_threats * 190_000
            value += int(own_fork) * 4_000_000 + int(enemy_fork) * 4_400_000
            value += self.history_scores.get((side, i), 0)
            value -= int((abs(r - cr) + abs(c - cc)) * 8)
            if i == preferred:
                value += 200_000_000
            scored.append((value, -i, i))
        scored.sort(reverse=True)
        ranked = [i for _, _, i in scored]
        return (ranked if limit is None else ranked[:limit]), forced_fork

    def _vcf_check(self):
        self._check()
        if time.perf_counter() >= self.phase_deadline:
            raise TacticalStopped

    def _vcf(self, pos, attacker, remaining):
        """OR ở lượt tấn công, AND trên mọi cách chặn và phản công thắng.

        Chỉ tìm các chuỗi liên tiếp tạo nước thắng ngay (VCF). None có
        nghĩa là chưa chứng minh được trong phạm vi này, KHÔNG phải hòa/thua.
        Một kết quả dương là chuỗi ép đã được xét đủ các nước phòng thủ.
        """
        self._vcf_check()
        self.nodes += 1
        own_wins = pos.winning_moves(attacker)
        if own_wins:
            return own_wins[0], 1
        proof_key = (pos.hash, attacker)
        known = self.proofs.get(proof_key)
        if known is not None and known[1] <= remaining * 2 + 1:
            return known
        if not remaining or not pos.empty_count:
            return None
        key = (pos.hash, attacker, remaining)
        if key in self.vcf_cache:
            return self.vcf_cache[key]
        enemy = 3 - attacker
        forcing = self.vcf_frontiers.get(proof_key)
        if forcing is None:
            enemy_wins = pos.winning_moves(enemy)
            candidates = (pos.defensive_moves(enemy_wins, enemy)
                          if enemy_wins else pos.candidates())
            forcing = []
            for i in candidates:
                self._vcf_check()
                attack, points, fork = pos.preview(i, attacker, details=True)
                if not points:
                    continue
                if fork:
                    result = i, 3
                    self.proofs[proof_key] = result
                    return result
                forcing.append((attack, -i, i))
            forcing.sort(reverse=True)
            if len(self.vcf_frontiers) > 70_000:
                self.vcf_frontiers.clear()
            self.vcf_frontiers[proof_key] = tuple(forcing)
        for _, _, i in forcing:
            self._vcf_check()
            attack_token = pos.play(i, attacker)
            try:
                # Bên phòng thủ có thể thắng ngay thay vì chặn.
                if pos.winning_moves(enemy):
                    continue
                points = pos.winning_moves(attacker)
                if not points:
                    continue
                replies = pos.defensive_moves(points, attacker)
                if not replies:
                    result = i, 3
                else:
                    longest, all_proven = 0, True
                    for reply in replies:
                        self._vcf_check()
                        reply_token = pos.play(reply, enemy)
                        try:
                            continuation = self._vcf(pos, attacker, remaining - 1)
                        finally:
                            pos.undo(reply_token)
                        if continuation is None:
                            all_proven = False
                            break
                        longest = max(longest, continuation[1])
                    if not all_proven:
                        continue
                    result = i, longest + 2
                self.proofs[proof_key] = result
                self.vcf_cache[key] = result
                return result
            finally:
                pos.undo(attack_token)
        if len(self.vcf_cache) > 70_000:
            self.vcf_cache.clear()
        self.vcf_cache[key] = None
        return None

    def _probe_vcf(self, pos, side, seconds, attacks=VCF_MAX_ATTACKS):
        """Dùng một phần ngân sách; luôn dành thời gian cho tìm kiếm tổng quát."""
        if seconds <= 0 or pos.cells.count(side) < self.win_length - 2:
            return None
        previous_deadline = self.phase_deadline
        self.phase_deadline = min(self.clock.deadline, time.perf_counter() + seconds)
        try:
            for remaining in range(1, attacks + 1):
                result = self._vcf(pos, side, remaining)
                if result is not None:
                    return result
                if not self.vcf_frontiers.get((pos.hash, side)):
                    break  # Không có nước tạo bốn: tăng độ sâu VCF không giúp.
        except TacticalStopped:
            return None
        finally:
            self.phase_deadline = previous_deadline
        return None

    def _forks(self, pos, attacker):
        """Các ô mà attacker đánh vào sẽ có đòn kép không chặn nổi bằng một nước."""
        forks = []
        for number, k in enumerate(pos.candidates()):
            if not number & 15:
                self._vcf_check()
            if pos.preview(k, attacker)[1] >= 2 and pos.preview(k, attacker, details=True)[2]:
                forks.append(k)
        return forks

    def _fork_blocks(self, pos, attacker, forks):
        """Mọi nước của đối thủ vô hiệu hóa được TẤT CẢ các ô đòn kép.

        Một quân đối thủ chỉ đổi được đòn kép tại k nếu nằm trong
        threat_cells(k), nên chỉ cần thử giao của các tập đó.
        """
        enemy = 3 - attacker
        cells = None
        for k in forks:
            zone = pos.threat_cells(k, attacker)
            cells = zone if cells is None else cells & zone
            if not cells:
                return []
        blocks = []
        for m in sorted(cells):
            if pos.cells[m] != EMPTY:
                continue
            token = pos.play(m, enemy)
            try:
                if not any(pos.cells[k] == EMPTY and pos.preview(k, attacker, details=True)[2]
                           for k in forks):
                    blocks.append(m)
            finally:
                pos.undo(token)
        return blocks

    def _threat_moves(self, pos, attacker, enemy_wins):
        """Ứng viên tạo bốn hoặc tạo ba; khi bị dọa bốn chỉ xét nước chặn."""
        moves = (pos.defensive_moves(enemy_wins, 3 - attacker) if enemy_wins
                 else pos.candidates())
        scored = []
        for number, i in enumerate(moves):
            if not number & 15:
                self._vcf_check()
            score, wins = pos.preview(i, attacker)
            if wins or score >= THREAT_MIN_SCORE:
                scored.append((score + wins * 100_000, -i, i))
        scored.sort(reverse=True)
        return [i for _, _, i in scored[:VCT_BRANCH]]

    def _vct(self, pos, attacker, remaining):
        """OR ở lượt tấn công: một nước dọa (bốn hoặc ba) dẫn tới thắng.

        Như _vcf, None nghĩa là chưa chứng minh được trong phạm vi này.
        Kết quả dương đã được xét với mọi nước đáp của đối thủ (_vct_defend).
        """
        self._vcf_check()
        self.nodes += 1
        own_wins = pos.winning_moves(attacker)
        if own_wins:
            return own_wins[0], 1
        proof_key = (pos.hash, attacker)
        known = self.proofs.get(proof_key)
        if known is not None:
            return known
        quick = self._vcf(pos, attacker, VCT_VCF_ATTACKS)
        if quick is not None:
            return quick
        if remaining <= 0 or not pos.empty_count:
            return None
        key = (pos.hash, attacker, remaining)
        if key in self.vct_cache:
            return self.vct_cache[key]
        enemy_wins = pos.winning_moves(3 - attacker)
        result = None
        for t in self._threat_moves(pos, attacker, enemy_wins):
            token = pos.play(t, attacker)
            try:
                # Nước buộc phải chặn bốn phản công không tính vào số lượt dọa.
                plies = self._vct_defend(pos, attacker,
                                         remaining if enemy_wins else remaining - 1)
            finally:
                pos.undo(token)
            if plies is not None:
                result = t, plies + 1
                self.proofs[proof_key] = result
                break
        if len(self.vct_cache) > 70_000:
            self.vct_cache.clear()
        self.vct_cache[key] = result
        return result

    def _vct_defend(self, pos, attacker, remaining):
        """AND ở lượt phòng thủ: số nước tới khi attacker thắng, hoặc None.

        Nếu attacker có bốn, đối thủ phải chặn. Nếu không, attacker phải có
        ô đòn kép; đối thủ thoát được chỉ bằng nước vô hiệu hóa mọi ô đòn kép
        hoặc tạo bốn phản công. Mọi nước khác thua: attacker đánh đòn kép,
        đối thủ không có ô thắng nào để đáp. Không bỏ sót nước đáp nào.
        """
        self._vcf_check()
        enemy = 3 - attacker
        if pos.winning_moves(enemy):
            return None
        threats = pos.winning_moves(attacker)
        if threats:
            replies = pos.defensive_moves(threats, attacker)
            if not replies:
                return 2
        else:
            forks = self._forks(pos, attacker)
            if not forks:
                return None
            replies = set(self._fork_blocks(pos, attacker, forks))
            replies.update(i for i in pos.candidates() if pos.preview(i, enemy)[1])
            if not replies:
                return 4
        longest = 0
        for reply in sorted(replies):
            self._vcf_check()
            token = pos.play(reply, enemy)
            try:
                result = self._vct(pos, attacker, remaining)
            finally:
                pos.undo(token)
            if result is None:
                return None
            longest = max(longest, result[1])
        return longest + 1

    def _probe_vct(self, pos, side, seconds, threats=VCT_MAX_THREATS):
        """Tìm VCT theo độ sâu tăng dần trong ngân sách thời gian riêng."""
        if seconds <= 0 or pos.cells.count(side) < 3:
            return None
        previous_deadline = self.phase_deadline
        self.phase_deadline = min(self.clock.deadline, time.perf_counter() + seconds)
        try:
            for remaining in range(1, threats + 1):
                result = self._vct(pos, side, remaining)
                if result is not None:
                    return result
        except TacticalStopped:
            return None
        finally:
            self.phase_deadline = previous_deadline
        return None

    def _probe_threats(self, pos, side, seconds):
        """VCF trước (rẻ), rồi VCT với phần thời gian còn lại."""
        stop = time.perf_counter() + seconds
        return (self._probe_vcf(pos, side, seconds)
                or self._probe_vct(pos, side, stop - time.perf_counter()))

    @staticmethod
    def _pack(value, ply):
        if value > MATE_BOUND:
            return value + ply
        if value < -MATE_BOUND:
            return value - ply
        return value

    @staticmethod
    def _unpack(value, ply):
        if value > MATE_BOUND:
            return value - ply
        if value < -MATE_BOUND:
            return value + ply
        return value

    def _search(self, pos, side, depth, alpha, beta, ply, extension=6):
        self._check()
        self.nodes += 1
        if not pos.empty_count:
            return 0
        key = (pos.hash, side)
        proof = self.proofs.get(key)
        if proof is not None:
            return MATE - ply - proof[1]
        cached = self.tt.get(key)
        # Các nút mở rộng ở đường chân trời phụ thuộc số lượt mở rộng
        # còn lại; không dùng cache của chúng như một tìm kiếm đầy đủ.
        if cached is not None and depth > 0 and cached.depth >= depth:
            value = self._unpack(cached.value, ply)
            if cached.flag == 0:
                return value
            if cached.flag == 1:
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                return value
        window_alpha, window_beta = alpha, beta
        moves, kind = self._tactics(pos, side, pos.candidates())
        if kind == "win":
            return MATE - ply - 1
        if kind == "lost":
            return -MATE + ply + 2
        if depth <= 0:
            if kind == "defend" and extension > 0:
                extension -= 1
            else:
                return pos.evaluate(side)
        preferred = cached.move if cached else None
        # Không giới hạn danh sách nước phòng thủ bắt buộc.
        cap = None if kind == "defend" else max(8, self.move_limit - 2 * min(ply, 5))
        moves, fork = self._rank(pos, side, moves, preferred, cap)
        if fork is not None:
            return MATE - ply - 3
        best, best_move = -INF, moves[0]
        for number, i in enumerate(moves):
            token = pos.play(i, side)
            try:
                if number == 0:
                    value = -self._search(pos, 3 - side, depth - 1,
                                          -beta, -alpha, ply + 1, extension)
                else:
                    # Principal Variation Search: chỉ tìm lại đầy đủ
                    # nếu nước đang xét thực sự cải thiện cận alpha.
                    value = -self._search(pos, 3 - side, depth - 1,
                                          -alpha - 1, -alpha, ply + 1, extension)
                    if alpha < value < beta:
                        value = -self._search(pos, 3 - side, depth - 1,
                                              -beta, -alpha, ply + 1, extension)
            finally:
                pos.undo(token)
            if value > best:
                best, best_move = value, i
            alpha = max(alpha, value)
            if alpha >= beta:
                self.history_scores[(side, i)] = min(
                    50_000, self.history_scores.get((side, i), 0) + max(1, depth) ** 2 * 16)
                break
        if depth > 0:
            flag = 2 if best <= window_alpha else 1 if best >= window_beta else 0
            if len(self.tt) > 160_000:
                self.tt.clear()
            self.tt[key] = TTEntry(depth, self._pack(best, ply), flag, best_move)
        return best

    def _prepare(self, pos):
        context = (pos.rows, pos.cols, self.win_length, self.strict)
        if self.proof_context != context:
            for cache in (self.tt, self.history_scores, self.vcf_cache, self.vct_cache,
                          self.vcf_frontiers, self.proofs):
                cache.clear()
        self.proof_context = context
        if len(self.proofs) > 100_000:
            self.proofs.clear()
        # Giảm dần điểm lịch sử để nước cũ không lấn át thế cờ mới.
        self.history_scores = {key: value // 2 for key, value in self.history_scores.items()
                               if value > 1}

    def predict(self, board, side, cancel=None):
        """Đoán nước của side để nghĩ trước; ưu tiên nước tốt nhất trong TT."""
        self.cancel = cancel if cancel is not None else threading.Event()
        self.clock = Clock(time.perf_counter() + min(0.5, self.time_budget))
        pos = Position(board, self.win_length, self.strict)
        self._prepare(pos)
        entry = self.tt.get((pos.hash, side))
        if entry is not None and entry.move is not None and pos.cells[entry.move] == EMPTY:
            return pos.coords[entry.move]
        candidates = pos.candidates()
        if not candidates:
            return None
        try:
            moves, _kind = self._tactics(pos, side, candidates)
            moves, _fork = self._rank(pos, side, moves, limit=1)
        except SearchStopped:
            return None
        return pos.coords[moves[0]]

    def choose(self, board, bot_player, cancel=None, progress=None, clock=None):
        started = time.perf_counter()
        self.cancel = cancel if cancel is not None else threading.Event()
        self.clock = clock if clock is not None else Clock(started + self.time_budget)
        self.nodes = 0
        self.phase_deadline = float("inf")
        pos = Position(board, self.win_length, self.strict)
        self._prepare(pos)
        candidates = pos.candidates()
        if not candidates:
            return SearchResult(None, elapsed=time.perf_counter() - started)
        # Có nước dự phòng hợp lệ ngay cả khi hết giờ trong lúc xếp hạng.
        center = (pos.rows // 2, pos.cols // 2)
        best = min(candidates, key=lambda i: (
            abs(pos.coords[i][0] - center[0]) + abs(pos.coords[i][1] - center[1]), i))
        result = SearchResult(pos.coords[best])
        if pos.empty_count == pos.size:
            result.elapsed = time.perf_counter() - started
            return result
        try:
            moves, kind = self._tactics(pos, bot_player, candidates)
            best = moves[0]
            result.move = pos.coords[best]
            if kind in ("win", "lost"):
                result.score = MATE - 1 if kind == "win" else -MATE + 2
                result.proven = kind == "win"
                result.forcing_plies = 1 if kind == "win" else 0
                return result
            saved_plan = self.proofs.get((pos.hash, bot_player))
            if saved_plan is not None and pos.cells[saved_plan[0]] == EMPTY:
                result.move, result.score = pos.coords[saved_plan[0]], MATE - saved_plan[1]
                result.proven, result.forcing_plies = True, saved_plan[1]
                return result
            legal_root = set(moves)
            # Một nước chặn duy nhất luôn được giữ làm dự phòng.
            limit = None if kind == "defend" else self.move_limit + 6
            moves, fork = self._rank(pos, bot_player, moves, limit=limit)
            best = moves[0]
            result.move = pos.coords[best]
            if fork is not None:
                result.move, result.score = pos.coords[fork], MATE - 3
                result.proven, result.forcing_plies = True, 3
                return result
            # Tìm chuỗi ép dài trước tìm kiếm tổng quát, với ngân sách riêng.
            # VCF có thể đi sâu hơn nhiều khi mỗi lượt đều ép đối thủ phải chặn.
            forcing = self._probe_vcf(pos, bot_player,
                                      min(2.5, self.time_budget * 0.20))
            if forcing is None:
                # Chuỗi ép bằng ba chậm hơn VCF nhiều, nên có ngân sách riêng.
                forcing = self._probe_vct(pos, bot_player,
                                          min(3.0, self.time_budget * 0.20))
            if forcing is not None:
                result.move, result.score = pos.coords[forcing[0]], MATE - forcing[1]
                result.proven, result.forcing_plies = True, forcing[1]
                return result
            # Nếu đối thủ đang có chuỗi ép, ưu tiên thử nước phá chuỗi và
            # loại những ứng viên đã chứng minh sẽ thua sau khi mình đánh.
            enemy_forcing = self._probe_threats(pos, 3 - bot_player,
                                                min(1.5, self.time_budget * 0.10))
            if enemy_forcing is not None:
                first_threat = enemy_forcing[0]
                if first_threat in legal_root:
                    if first_threat in moves:
                        moves.remove(first_threat)
                    moves.insert(0, first_threat)
                filter_deadline = min(self.clock.deadline,
                                      time.perf_counter() + min(2.5, self.time_budget * 0.15))
                losing = set()
                for number, i in enumerate(moves):
                    self._check()
                    remaining = filter_deadline - time.perf_counter()
                    if remaining <= 0:
                        break
                    token = pos.play(i, bot_player)
                    try:
                        # Chia đều thời gian còn lại để không dồn hết cho nước đầu.
                        refutation = self._probe_threats(
                            pos, 3 - bot_player,
                            min(remaining, remaining / max(1, len(moves) - number) * 2))
                    finally:
                        pos.undo(token)
                    if refutation is not None:
                        losing.add(i)
                unproven = [i for i in moves if i not in losing]
                if unproven:
                    moves = unproven
                best = moves[0]
                result.move = pos.coords[best]
            root_scores = {}
            for depth in range(1, self.max_depth + 1):
                self._check()
                moves.sort(key=lambda i: (i == best, root_scores.get(i, -INF)), reverse=True)
                alpha = -INF
                iteration_best, iteration_score = best, -INF
                iteration_scores = {}
                for number, i in enumerate(moves):
                    self._check()
                    token = pos.play(i, bot_player)
                    try:
                        if number == 0:
                            value = -self._search(pos, 3 - bot_player, depth - 1,
                                                  -INF, -alpha, 1)
                        else:
                            value = -self._search(pos, 3 - bot_player, depth - 1,
                                                  -alpha - 1, -alpha, 1)
                            if value > alpha:
                                value = -self._search(pos, 3 - bot_player, depth - 1,
                                                      -INF, -alpha, 1)
                    finally:
                        pos.undo(token)
                    iteration_scores[i] = value
                    if value > iteration_score:
                        iteration_best, iteration_score = i, value
                    alpha = max(alpha, value)
                    if value > MATE_BOUND:
                        break
                best, root_scores = iteration_best, iteration_scores
                result = SearchResult(pos.coords[best], depth, self.nodes,
                                      time.perf_counter() - started, iteration_score)
                if progress:
                    progress(result)
                if abs(iteration_score) > MATE_BOUND:
                    break
        except SearchStopped:
            pass
        finally:
            result.nodes = self.nodes
            result.elapsed = time.perf_counter() - started
        return result

    def get_best_move(self, board, bot_player, history=None):
        """Tên hàm tương thích cách gọi trong bản cũ; không cần history."""
        return self.choose(board, bot_player).move


@dataclass
class BotJob:
    kind: str                # "search": lượt bot; "ponder": nghĩ trước trong lượt người
    cancel: threading.Event
    clock: Clock
    base_moves: int          # số nước trên bàn khi bắt đầu
    thread: threading.Thread | None = None
    predicted: tuple[int, int] | None = None
    search_started: float = 0.0
    result: SearchResult | None = None


class CaroGame:
    def __init__(self):
        # Import muộn: --self-test không cần cài pygame.
        global pygame
        try:
            import pygame
        except ImportError as exc:
            raise SystemExit("Chưa có pygame. Chạy: python -m pip install pygame") from exc
        pygame.init()
        self.rows = max(9, min(25, BOARD_ROWS))
        self.cols = max(9, min(25, BOARD_COLS))
        if not 3 <= WIN_LENGTH <= min(self.rows, self.cols):
            raise SystemExit("WIN_LENGTH phải từ 3 đến kích thước nhỏ nhất của bàn cờ.")
        self.bot_enabled = BOT_ENABLED
        self.bot_player = BOT_PLAYER if BOT_PLAYER in (X, O) else O
        self.human_player = 3 - self.bot_player
        self.first_player = FIRST_PLAYER if FIRST_PLAYER in (X, O) else X
        self.strict = STRICT_BLOCKED_MODE
        self.level = 2
        self.messages = queue.Queue()
        self.worker = None
        self.job = None
        self.ponder = BOT_PONDER
        self.bot_thinking = False
        self.search_started = 0.0
        self.stats = SearchResult(None)
        self.notice = ""
        self.notice_until = 0.0
        info = pygame.display.Info()
        width = min(1050, max(MIN_WIDTH, info.current_w - 80))
        height = min(820, max(MIN_HEIGHT, info.current_h - 100))
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption("Cờ caro — Gomoku | Bot chuyên gia")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui,arial,dejavusans", 18)
        self.font_big = pygame.font.SysFont("segoeui,arial,dejavusans", 26, bold=True)
        self.font_small = pygame.font.SysFont("segoeui,arial,dejavusans", 15)
        self.font_tiny = pygame.font.SysFont("segoeui,arial,dejavusans", 13)
        self.font_piece = pygame.font.SysFont("arial", 20, bold=True)
        self._layout()
        self.reset()

    def _layout(self):
        self.width, self.height = self.screen.get_size()
        self.board_area = pygame.Rect(0, TITLE_H, self.width - PANEL_W, self.height - TITLE_H)
        self.cell = min(CELL, (self.board_area.width - MARGIN * 2) / (self.cols - 1),
                        (self.board_area.height - MARGIN * 2) / (self.rows - 1))
        grid_w, grid_h = self.cell * (self.cols - 1), self.cell * (self.rows - 1)
        self.origin_x = self.board_area.centerx - grid_w / 2
        self.origin_y = self.board_area.centery - grid_h / 2
        self.panel = pygame.Rect(self.width - PANEL_W + 8, TITLE_H + 12,
                                 PANEL_W - 20, self.height - TITLE_H - 24)
        x, y = self.panel.left + 12, self.panel.top
        width = self.panel.width - 24
        self.buttons = {}
        for name, dy in (("undo", 326), ("restart", 366), ("swap", 406),
                         ("first", 446), ("rule", 486), ("quit", 594)):
            self.buttons[name] = pygame.Rect(x, y + dy, width, 34)
        dw = (width - 8) // 3
        for level in range(3):
            self.buttons[f"level{level}"] = pygame.Rect(x + level * (dw + 4), y + 234, dw, 30)
        sw = (width - 12) // 4
        for offset, name in enumerate(("row-", "row+", "col-", "col+")):
            self.buttons[name] = pygame.Rect(x + offset * (sw + 4), y + 554, sw, 30)

    def _cancel_search(self):
        if self.job is not None:
            self.job.cancel.set()
            self.job = None
        self.bot_thinking = False

    def reset(self):
        self._cancel_search()
        self.board = [[EMPTY] * self.cols for _ in range(self.rows)]
        self.current = self.first_player
        self.history = []
        self.winner = EMPTY
        self.win_line = []
        self.stats = SearchResult(None)
        self.bot_failed = False
        self.notice_until = 0.0
        self.engine = self._make_engine()

    def _make_engine(self):
        if not self.bot_enabled:
            return None
        _, seconds, depth, limit = LEVELS[self.level]
        return CaroBot(depth=depth, time_budget=seconds, move_limit=limit,
                       win_length=WIN_LENGTH, strict=self.strict)

    def set_board_size(self, rows, cols):
        lower = max(9, WIN_LENGTH)
        rows, cols = max(lower, min(25, rows)), max(lower, min(25, cols))
        if (rows, cols) != (self.rows, self.cols):
            self.rows, self.cols = rows, cols
            self._layout()
            self.reset()

    def swap_sides(self):
        if not self.bot_enabled:
            return
        self.bot_player = 3 - self.bot_player
        self.human_player = 3 - self.bot_player
        self.first_player = self.human_player
        self.reset()

    def toggle_first_player(self):
        self.first_player = 3 - self.first_player
        self.reset()

    def toggle_blocked_mode(self):
        self.strict = not self.strict
        self.reset()

    def set_level(self, level):
        if level != self.level:
            self.level = level
            self._cancel_search()
            self.stats = SearchResult(None)
            self.engine = self._make_engine()

    def cell_center(self, r, c):
        return round(self.origin_x + c * self.cell), round(self.origin_y + r * self.cell)

    def mouse_to_cell(self, pos):
        if not self.board_area.collidepoint(pos):
            return None
        mx, my = pos
        c = math.floor((mx - self.origin_x) / self.cell + 0.5)
        r = math.floor((my - self.origin_y) / self.cell + 0.5)
        if 0 <= r < self.rows and 0 <= c < self.cols:
            cx, cy = self.cell_center(r, c)
            if abs(mx - cx) <= self.cell / 2 and abs(my - cy) <= self.cell / 2:
                return r, c
        return None

    def check_win(self, r, c, player):
        return winning_line(self.board, r, c, player, WIN_LENGTH, self.strict)

    def place(self, r, c):
        if (self.winner != EMPTY or not 0 <= r < self.rows or not 0 <= c < self.cols
                or self.board[r][c] != EMPTY):
            return False
        self.board[r][c] = self.current
        self.history.append((r, c, self.current))
        line =self.check_win(r, c, self.current)
        if line:
            self.winner, self.win_line = self.current, line
        elif len(self.history) == self.rows * self.cols:
            self.winner = -1
        else:
            self.current = 3 - self.current
        return True

    def undo(self):
        if not self.history:
            return
        self._cancel_search()
        if self.bot_enabled:
            # Nếu người vừa đánh và bot chưa đáp (hoặc người vừa thắng),
            # chỉ bỏ một nước. Nếu bot đã đáp, bỏ cả cặp người + bot.
            remove = 1
            if (self.history[-1][2] == self.bot_player and len(self.history) >= 2
                    and self.history[-2][2] == self.human_player):
                remove = 2
        else:
            remove = 1
        for _ in range(remove):
            r, c, _ = self.history.pop()
            self.board[r][c] = EMPTY
        self.current = 3 - self.history[-1][2] if self.history else self.first_player
        self.winner, self.win_line = EMPTY, []
        self.stats = SearchResult(None)
        self.bot_failed = False

    def _worker_main(self, job, snapshot, side, bot):
        try:
            if job.kind == "ponder":
                guess = bot.predict(snapshot, 3 - side, job.cancel)
                if guess is None or job.cancel.is_set():
                    return
                snapshot[guess[0]][guess[1]] = 3 - side
                job.search_started = time.perf_counter()
                job.predicted = guess

            def progress(result):
                self.messages.put(("progress", job, result))
            result = bot.choose(snapshot, side, job.cancel, progress, job.clock)
            if not job.cancel.is_set():
                self.messages.put(("done", job, result))
        except Exception:
            self.messages.put(("error", job, traceback.format_exc()))

    def _start_job(self, kind):
        # Mỗi thời điểm chỉ có một worker; worker cũ sẽ thoát khi thấy cancel.
        if self.worker is not None and self.worker.is_alive():
            return
        now = time.perf_counter()
        clock = Clock(math.inf if kind == "ponder" else now + self.engine.time_budget)
        job = BotJob(kind, threading.Event(), clock, len(self.history))
        job.thread = threading.Thread(
            target=self._worker_main,
            args=(job, [row[:] for row in self.board], self.bot_player, self.engine),
            daemon=True,
        )
        self.job, self.worker = job, job.thread
        if kind == "search":
            self.stats = SearchResult(None)
        job.thread.start()

    def _ponder_hit(self, job):
        return (job.kind == "ponder" and job.predicted is not None
                and len(self.history) == job.base_moves + 1
                and job.predicted == self.history[-1][:2])

    def update_bot(self):
        while True:
            try:
                kind, job, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if job is not self.job:
                continue  # Kết quả của bàn cờ đã bị reset/undo/đổi luật hoặc đoán sai.
            if kind == "progress":
                if job.kind == "search":
                    self.stats = payload
            elif kind == "done":
                job.result = payload
            else:
                self._cancel_search()
                print(payload, file=sys.stderr)
                self.notice = "Lỗi bot; xem cửa sổ console. Nhấn R để chơi lại."
                self.notice_until = time.perf_counter() + 30
                # Không tự chạy lại liên tục khi có lỗi lập trình.
                self.bot_failed = True
        if not self.bot_enabled or self.winner != EMPTY or self.bot_failed:
            self._cancel_search()
            return
        job = self.job
        if self.current != self.bot_player:
            if job is None and self.ponder and self.history:
                self._start_job("ponder")
            return
        now = time.perf_counter()
        if not self.bot_thinking:
            self.bot_thinking, self.search_started = True, now
        if job is not None and job.kind == "ponder":
            if self._ponder_hit(job):
                # Đoán trúng: đã tính từ lúc đoán, nên chỉ cần thêm phần còn
                # thiếu của ngân sách (ít nhất 1/4 để bot không đáp quá vội).
                job.kind = "search"
                budget = self.engine.time_budget
                job.clock.deadline = now + max(budget * 0.25,
                                               budget - (now - job.search_started))
            else:
                self._cancel_search()
                self.bot_thinking, self.search_started = True, now
                job = None
        if job is None:
            self._start_job("search")
        elif job.result is not None:
            self.job, self.bot_thinking, self.stats = None, False, job.result
            if job.result.move is not None:
                self.place(*job.result.move)

    def _button_action(self, name):
        if name == "quit":
            return False
        if name == "restart":
            self.reset()
            self.bot_failed = False
        elif name == "undo":
            self.undo()
            self.bot_failed = False
        elif name == "swap":
            self.swap_sides()
        elif name == "first":
            self.toggle_first_player()
        elif name == "rule":
            self.toggle_blocked_mode()
        elif name == "ponder":
            self.ponder = not self.ponder
            if not self.ponder and self.job is not None and self.job.kind == "ponder":
                self._cancel_search()
            self.notice = f"Bot nghĩ trước trong lượt của bạn: {'BẬT' if self.ponder else 'TẮT'}"
            self.notice_until = time.perf_counter() + 3
        elif name.startswith("level"):
            self.set_level(int(name[-1]))
        elif name.startswith("row"):
            self.set_board_size(self.rows + (1 if name.endswith("+") else -1), self.cols)
        elif name.startswith("col"):
            self.set_board_size(self.rows, self.cols + (1 if name.endswith("+") else -1))
        return True

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            size = max(MIN_WIDTH, event.w), max(MIN_HEIGHT, event.h)
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            self._layout()
        elif event.type == pygame.KEYDOWN:
            actions = {pygame.K_ESCAPE: "quit", pygame.K_r: "restart", pygame.K_u: "undo",
                       pygame.K_s: "swap", pygame.K_f: "first", pygame.K_b: "rule",
                       pygame.K_p: "ponder",
                       pygame.K_1: "level0", pygame.K_2: "level1", pygame.K_3: "level2"}
            if event.key in actions:
                return self._button_action(actions[event.key])
            if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.set_board_size(self.rows + 1, self.cols + 1)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.set_board_size(self.rows - 1, self.cols - 1)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.undo()
            elif event.button == 1:
                for name, rect in self.buttons.items():
                    if rect.collidepoint(event.pos):
                        return self._button_action(name)
                cell = self.mouse_to_cell(event.pos)
                if cell and (not self.bot_enabled or self.current == self.human_player):
                    self.place(*cell)
        return True

    def _text(self, text, pos, font=None, color=C_TEXT, center=False, max_width=None):
        font = font or self.font
        if max_width is not None:
            while text and font.size(text)[0] > max_width:
                text = text[:-2] + "…" if len(text) > 2 else ""
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=pos) if center else surface.get_rect(topleft=pos)
        self.screen.blit(surface, rect)

    def _button(self, name, label, color, selected=False):
        rect = self.buttons[name]
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            color = tuple(min(255, v + 22) for v in color)
        pygame.draw.rect(self.screen, color, rect, border_radius=7)
        if selected:
            pygame.draw.rect(self.screen, (238, 182, 61), rect, 2, border_radius=7)
        font = self.font_small if self.font_small.size(label)[0] <= rect.width - 8 else self.font_tiny
        self._text(label, rect.center, font, (255, 255, 255), True,
                   rect.width - 8)

    def draw_board(self):
        self.screen.fill(C_BG)
        pygame.draw.rect(self.screen, C_TITLE, (0, 0, self.width, TITLE_H))
        self._text("CỜ CARO · GOMOKU", (24, 13), self.font_big, (255, 245, 222))
        a = self.cell_center(0, 0)
        b = self.cell_center(self.rows - 1, self.cols - 1)
        padding = max(9, round(self.cell * 0.48))
        wood = pygame.Rect(a[0] - padding, a[1] - padding,
                           b[0] - a[0] + 2 * padding, b[1] - a[1] + 2 * padding)
        pygame.draw.rect(self.screen, C_BOARD, wood, border_radius=9)
        for r in range(self.rows):
            pygame.draw.line(self.screen, C_LINE, self.cell_center(r, 0),
                             self.cell_center(r, self.cols - 1))
        for c in range(self.cols):
            pygame.draw.line(self.screen, C_LINE, self.cell_center(0, c),
                             self.cell_center(self.rows - 1, c))
        cr, cc = self.rows // 2, self.cols // 2
        for dr, dc in ((0, 0), (-4, -4), (-4, 4), (4, -4), (4, 4)):
            if 0 <= cr + dr < self.rows and 0 <= cc + dc < self.cols:
                pygame.draw.circle(self.screen, C_LINE, self.cell_center(cr + dr, cc + dc), 3)
        radius = max(4, round(self.cell * 0.38))
        for r in range(self.rows):
            for c in range(self.cols):
                player = self.board[r][c]
                if not player:
                    continue
                pos = self.cell_center(r, c)
                pygame.draw.circle(self.screen, C_X if player == X else C_O, pos, radius)
                pygame.draw.circle(self.screen, (255, 247, 230), pos, radius, 1)
                if self.cell >= 27:
                    self._text("X" if player == X else "O", pos, self.font_piece,
                               (255, 255, 255), True)
        if self.history:
            r, c, _ = self.history[-1]
            pygame.draw.circle(self.screen, C_GREEN, self.cell_center(r, c), radius + 3, 2)
        if self.win_line:
            pygame.draw.line(self.screen, (255, 57, 61), self.cell_center(*self.win_line[0]),
                             self.cell_center(*self.win_line[-1]), 4)
        if self.winner == EMPTY and (not self.bot_enabled or self.current == self.human_player):
            cell = self.mouse_to_cell(pygame.mouse.get_pos())
            if cell and self.board[cell[0]][cell[1]] == EMPTY:
                size = radius * 2 + 4
                ghost = pygame.Surface((size, size), pygame.SRCALPHA)
                color = C_X if self.current == X else C_O
                pygame.draw.circle(ghost, color + (90,), (size // 2, size // 2), radius)
                pos = self.cell_center(*cell)
                self.screen.blit(ghost, (pos[0] - size // 2, pos[1] - size // 2))

    def draw_panel(self):
        panel = self.panel
        pygame.draw.rect(self.screen, C_PANEL, panel, border_radius=12)
        pygame.draw.rect(self.screen, (217, 207, 187), panel, 1, border_radius=12)
        x, y = panel.left + 12, panel.top
        self._text("BẢNG ĐIỀU KHIỂN", (panel.centerx, y + 24), self.font,
                   C_TITLE, True)
        if self.winner == -1:
            status, color = "VÁN CỜ HÒA", C_BLUE
        elif self.winner:
            who = "X" if self.winner == X else "O"
            status, color = f"{who} THẮNG!", C_X if self.winner == X else C_O
        elif self.bot_thinking:
            elapsed = time.perf_counter() - self.search_started
            status, color = f"Bot đang tính… {elapsed:.1f}s", C_BLUE
        else:
            status = f"Lượt {'X' if self.current == X else 'O'}"
            if self.bot_enabled:
                status += " · Bạn" if self.current == self.human_player else " · Bot"
            color = C_TEXT
        self._text(status, (panel.centerx, y + 64), self.font, color, True,
                   panel.width - 20)
        lines = [f"Bàn cờ: {self.rows} × {self.cols} · Thắng: {WIN_LENGTH}",
                 (f"Chế độ: Đấu bot · Nghĩ trước (P): {'Bật' if self.ponder else 'Tắt'}"
                  if self.bot_enabled else "Chế độ: Hai người"),
                 f"Bạn: {'X' if self.human_player == X else 'O'} · Bot: {'X' if self.bot_player == X else 'O'}"
                 if self.bot_enabled else "X: đen · O: đỏ",
                 f"Đi trước: {'X' if self.first_player == X else 'O'} · Đã đánh: {len(self.history)}",
                 "Chặn hai đầu: " + ("không thắng" if self.strict else "vẫn thắng")]
        for n, line in enumerate(lines):
            self._text(line, (x, y + 96 + n * 22), self.font_small,
                       max_width=panel.width - 24)
        self._text("Độ khó (phím 1 / 2 / 3)", (x, y + 208), self.font_small)
        for level, (label, *_rest) in enumerate(LEVELS):
            self._button(f"level{level}", label, C_GREEN if level == self.level else C_GREY,
                         level == self.level)
        budget = LEVELS[self.level][1]
        self._text(f"Ngân sách: {budget:g}s/nước · Sâu: {self.stats.depth}",
                   (x, y + 278), self.font_small)
        stat_line = f"Đã xét: {self.stats.nodes:,} nút · {self.stats.elapsed:.2f}s"
        if self.stats.proven and self.stats.forcing_plies:
            stat_line = f"Chuỗi ép thắng: {self.stats.forcing_plies} nước"
        if self.job is not None and self.job.kind == "ponder":
            stat_line = "Bot đang nghĩ trước trong lượt của bạn…"
        self._text(stat_line,
                   (x, y + 300), self.font_small, max_width=panel.width - 24)
        self._button("undo", "HOÀN TÁC (U / chuột phải)", C_GREEN)
        self._button("restart", "VÁN MỚI (R)", C_RED)
        self._button("swap", "ĐỔI BÊN BOT (S) · Bạn đi trước", C_BLUE)
        self._button("first", "ĐỔI QUÂN ĐI TRƯỚC (F)", C_BLUE)
        self._button("rule", f"CHẶN HAI ĐẦU: {'BẬT' if self.strict else 'TẮT'} (B)", C_GREY)
        self._text("Kích thước (+/- đổi cả hàng và cột)", (x, y + 530), self.font_small)
        for name, text in (("row-", "Hàng −"), ("row+", "Hàng +"),
                           ("col-", "Cột −"), ("col+", "Cột +")):
            self._button(name, text, C_GREEN)
        self._button("quit", "THOÁT (ESC)", C_GREY)
        self._text("Đổi luật / bên / đi trước sẽ mở ván mới.",
                   (x, y + 644), self.font_tiny, max_width=panel.width - 24)
        if time.perf_counter() < self.notice_until:
            self._text(self.notice, (24, self.height - 24), self.font_small, C_RED,
                       max_width=self.board_area.width - 36)

    def draw(self):
        self.draw_board()
        self.draw_panel()
        pygame.display.flip()

    def run(self):
        running = True
        try:
            while running:
                for event in pygame.event.get():
                    if not self.handle_event(event):
                        running = False
                        break
                if not running:
                    break
                self.update_bot()
                self.draw()
                self.clock.tick(60)
        finally:
            self._cancel_search()
            if self.worker is not None:
                self.worker.join(timeout=0.3)
            pygame.quit()


def self_test():
    """Kiểm thử hành vi, không chỉ kiểm tra game có import được hay không."""
    import unittest

    class RulesAndBotTests(unittest.TestCase):
        def empty(self, rows=15, cols=15):
            return [[EMPTY] * cols for _ in range(rows)]

        def bot(self, strict=False, seconds=0.4):
            return CaroBot(depth=3, time_budget=seconds, move_limit=10, strict=strict)

        def test_win_in_all_directions(self):
            for dr, dc in DIRS:
                board = self.empty()
                for n in range(5):
                    board[4 + n * dr][7 + n * dc] = X
                self.assertIsNotNone(winning_line(board, 4, 7, X))

        def test_strict_and_overline(self):
            board = self.empty()
            board[7][3:10] = [O, X, X, X, X, X, O]
            self.assertIsNotNone(winning_line(board, 7, 6, X))
            self.assertIsNone(winning_line(board, 7, 6, X, strict=True))
            self.assertEqual(line_features("#XXXXX#", 5, True)[0], 0)
            board[7][9] = X
            self.assertIsNotNone(winning_line(board, 7, 6, X, strict=True))

        def test_take_win_before_defending(self):
            board = self.empty()
            board[5][3:8] = [X, O, O, O, O]
            board[8][3:8] = [O, X, X, X, X]
            self.assertEqual(self.bot().choose(board, O).move, (5, 8))

        def test_block_single_open_end(self):
            board = self.empty()
            board[7][3:8] = [O, X, X, X, X]
            self.assertEqual(self.bot().choose(board, O).move, (7, 8))

        def test_fill_broken_four(self):
            board = self.empty()
            board[6][4:9] = [O, O, EMPTY, O, O]
            self.assertEqual(self.bot().choose(board, O).move, (6, 6))

        def test_block_broken_four(self):
            board = self.empty()
            board[6][4:9] = [X, X, EMPTY, X, X]
            self.assertEqual(self.bot().choose(board, O).move, (6, 6))

        def test_double_threat(self):
            board = self.empty()
            board[7][5:8] = [O, O, O]
            result = self.bot().choose(board, O)
            self.assertIn(result.move, ((7, 4), (7, 8)))
            self.assertGreater(result.score, MATE_BOUND)

        def test_strict_defense_can_remove_two_winning_slots(self):
            board = self.empty()
            board[7][3:11] = [O, EMPTY, X, X, X, X, EMPTY, O]
            result = self.bot(strict=True).choose(board, O)
            self.assertIn(result.move, ((7, 4), (7, 9)))
            board[result.move[0]][result.move[1]] = O
            pos = Position(board, strict=True)
            self.assertFalse(any(pos.wins(i, X) for i in pos.candidates()))
            self.assertGreater(result.score, -MATE_BOUND)

        def test_dynamic_dimensions_and_untouched_input(self):
            for rows, cols in ((9, 9), (9, 25), (25, 9), (25, 25)):
                board = self.empty(rows, cols)
                r = rows - 2
                board[r][cols - 6:cols - 1] = [O, X, X, X, X]
                before = [row[:] for row in board]
                self.assertEqual(self.bot().choose(board, O).move, (r, cols - 1))
                self.assertEqual(board, before)

        def test_full_board_is_draw_and_no_move(self):
            board = [[X if (r + 2 * c) % 4 < 2 else O for c in range(15)]
                     for r in range(15)]
            pos = Position(board)
            self.assertEqual(pos.candidates(), [])
            self.assertIsNone(self.bot().choose(board, O).move)
            self.assertFalse(any(winning_line(board, r, c, board[r][c])
                                 for r in range(15) for c in range(15)))

        def test_make_unmake_and_incremental_evaluation(self):
            board = self.empty(9, 13)
            pos = Position(board)
            initial = (pos.cells[:], pos.neighbors[:], pos.hash, pos.total[:],
                       pos.empty_count, pos.line_scores[:])
            rng, tokens = random.Random(99), []
            for n in range(30):
                i = rng.choice(pos.candidates())
                tokens.append(pos.play(i, 1 + n % 2))
                rebuilt = Position([pos.cells[r * 13:(r + 1) * 13] for r in range(9)])
                self.assertEqual(pos.total, rebuilt.total)
                self.assertEqual(pos.hash, rebuilt.hash)
                self.assertEqual(pos.win_points, rebuilt.win_points)
                self.assertEqual(pos.win_counts, rebuilt.win_counts)
                self.assertEqual(pos.frontier, rebuilt.frontier)
            for token in reversed(tokens):
                pos.undo(token)
                rebuilt = Position([pos.cells[r * 13:(r + 1) * 13] for r in range(9)])
                self.assertEqual(pos.frontier, rebuilt.frontier)
            self.assertEqual((pos.cells, pos.neighbors, pos.hash, pos.total,
                              pos.empty_count, pos.line_scores), initial)

        def test_occupied_cell_rejected(self):
            pos = Position(self.empty())
            pos.play(0, X)
            with self.assertRaises(ValueError):
                pos.play(0, O)

        def test_timeout_and_cancellation_preserve_board(self):
            board = self.empty()
            board[7][7], board[7][8], board[8][7] = X, O, X
            before = [row[:] for row in board]
            started = time.perf_counter()
            result = self.bot(seconds=0.12).choose(board, O)
            self.assertLess(time.perf_counter() - started, 1.5)
            self.assertIsNotNone(result.move)
            self.assertEqual(board[result.move[0]][result.move[1]], EMPTY)
            self.assertEqual(board, before)
            cancel = threading.Event()
            cancel.set()
            result = self.bot().choose(board, O, cancel=cancel)
            self.assertIsNotNone(result.move)
            self.assertEqual(board, before)

        def test_old_regions_are_candidates(self):
            board = self.empty()
            board[1][1] = X
            for r in range(10, 14):
                for c in range(10, 15):
                    board[r][c] = O
            self.assertIn(1 * 15 + 2, Position(board).candidates())

        def test_virtual_win_matches_shared_rules(self):
            rng = random.Random(7)
            for strict in (False, True):
                board = [[rng.choices((EMPTY, X, O), (4, 3, 3))[0]
                          for _ in range(11)] for _ in range(9)]
                pos = Position(board, strict=strict)
                for i, value in enumerate(pos.cells):
                    if value:
                        continue
                    r, c = divmod(i, 11)
                    for side in (X, O):
                        expected = pos.wins(i, side)
                        board[r][c] = side
                        actual = winning_line(board, r, c, side, strict=strict) is not None
                        board[r][c] = EMPTY
                        self.assertEqual(expected, actual)

        def test_cached_wins_and_all_strict_defenses(self):
            rng = random.Random(121)
            for strict in (False, True):
                for _ in range(12):
                    board = [[rng.choices((EMPTY, X, O), (4, 3, 3))[0]
                              for _ in range(11)] for _ in range(9)]
                    pos = Position(board, strict=strict)
                    empty = [i for i, value in enumerate(pos.cells) if value == EMPTY]
                    for attacker in (X, O):
                        wins = [i for i in empty if pos.wins(i, attacker)]
                        self.assertEqual(pos.winning_moves(attacker), wins)
                        if not wins:
                            continue
                        expected = []
                        for reply in empty:
                            pos.cells[reply] = 3 - attacker
                            try:
                                if not any(pos.wins(i, attacker) for i in wins):
                                    expected.append(reply)
                            finally:
                                pos.cells[reply] = EMPTY
                        self.assertEqual(pos.defensive_moves(wins, attacker), expected)

        def test_strict_defense_outside_the_winning_square(self):
            board = self.empty()
            board[7][3:8] = [O, X, X, X, X]
            pos = Position(board, strict=True)
            self.assertEqual(pos.winning_moves(X), [7 * 15 + 8])
            self.assertEqual(pos.defensive_moves(pos.winning_moves(X), X),
                             [7 * 15 + 8, 7 * 15 + 9])

        def test_strict_fake_fork_is_not_a_forced_win(self):
            board = self.empty()
            board[7][3:11] = [O, EMPTY, X, X, X, EMPTY, EMPTY, O]
            pos = Position(board, strict=True)
            _value, points, forced = pos.preview(7 * 15 + 8, X, details=True)
            self.assertEqual(len(points), 2)
            self.assertFalse(forced)
            bot = self.bot(strict=True)
            self.assertIsNone(bot._probe_vcf(pos, X, 0.3, attacks=4))

        def test_vcf_longer_chain_with_all_defensive_branches(self):
            board = self.empty()
            for r, c in ((7, 4), (7, 5), (7, 6), (5, 7), (6, 7)):
                board[r][c] = O
            board[7][3] = X
            for strict in (False, True):
                bot = self.bot(strict=strict, seconds=1.0)
                pos = Position(board, strict=strict)
                before = (pos.cells[:], pos.hash, pos.total[:],
                          [points.copy() for points in pos.win_points])
                self.assertIsNone(bot._probe_vcf(pos, O, 0.4, attacks=1))
                result = bot._probe_vcf(pos, O, 0.4, attacks=2)
                self.assertEqual(result, (7 * 15 + 7, 5))
                self.assertEqual((pos.cells, pos.hash, pos.total, pos.win_points), before)
                chosen = bot.choose(board, O)
                self.assertEqual(chosen.move, (7, 7))
                self.assertTrue(chosen.proven)
                self.assertEqual(chosen.forcing_plies, 5)

        def test_vcf_honors_opponent_immediate_counterwin(self):
            board = self.empty()
            board[7][5:8] = [O, O, O]
            board[10][5:9] = [X, X, X, X]
            for strict in (False, True):
                pos = Position(board, strict=strict)
                self.assertIsNone(self.bot(strict)._probe_vcf(pos, O, 0.3, attacks=5))

        def test_vcf_certificate_against_every_legal_reply(self):
            board = self.empty(11, 11)
            for r, c in ((5, 2), (5, 3), (5, 4), (3, 5), (4, 5)):
                board[r][c] = O
            board[5][1] = X
            for strict in (False, True):
                bot, pos = self.bot(strict, seconds=1), Position(board, strict=strict)
                result = bot._probe_vcf(pos, O, 0.5, attacks=2)
                self.assertEqual(result, (5 * 11 + 5, 5))

                def verify(remaining):
                    # Kiểm tra bằng bộ luật 2D, không dùng win_points hay
                    # bộ lọc defensive_moves của engine để bỏ nước đối thủ.
                    grid = [pos.cells[r * pos.cols:(r + 1) * pos.cols]
                            for r in range(pos.rows)]
                    legal = [i for i, value in enumerate(pos.cells) if value == EMPTY]
                    for i in legal:
                        r, c = pos.coords[i]
                        grid[r][c] = O
                        won = winning_line(grid, r, c, O, strict=strict)
                        grid[r][c] = EMPTY
                        if won:
                            return True
                    proof = bot.proofs.get((pos.hash, O))
                    if remaining < 3 or proof is None:
                        return False
                    i = proof[0]
                    move_token = pos.play(i, O)
                    try:
                        r, c = pos.coords[i]
                        grid[r][c] = O
                        for reply in legal:
                            if reply == i:
                                continue
                            rr, cc = pos.coords[reply]
                            grid[rr][cc] = X
                            opponent_won = winning_line(grid, rr, cc, X, strict=strict)
                            grid[rr][cc] = EMPTY
                            if opponent_won:
                                return False
                            reply_token = pos.play(reply, X)
                            try:
                                if not verify(remaining - 2):
                                    return False
                            finally:
                                pos.undo(reply_token)
                        return True
                    finally:
                        pos.undo(move_token)

                self.assertTrue(verify(5))

        def test_saved_winning_plan_survives_the_next_turn(self):
            board = self.empty()
            for r, c in ((7, 4), (7, 5), (7, 6), (5, 7), (6, 7)):
                board[r][c] = O
            board[7][3] = X
            bot = self.bot(strict=True, seconds=1)
            first = bot.choose(board, O)
            self.assertTrue(first.proven)
            board[first.move[0]][first.move[1]] = O
            board[7][9] = X  # Chặn đầu ngoài, không chiếm trực tiếp ô thắng.

            def should_not_recompute(*args, **kwargs):
                raise AssertionError("Kế hoạch thắng phải được dùng lại trước khi xếp hạng.")

            bot._rank = should_not_recompute
            next_move = bot.choose(board, O)
            self.assertTrue(next_move.proven)
            self.assertEqual(next_move.forcing_plies, 3)
            self.assertEqual(board[next_move.move[0]][next_move.move[1]], EMPTY)

        def test_line_table_matches_text_features(self):
            rng = random.Random(5)
            for strict in (False, True):
                board = [[rng.choices((EMPTY, X, O), (5, 2, 2))[0]
                          for _ in range(13)] for _ in range(10)]
                pos = Position(board, strict=strict)
                for lid, line in enumerate(pos.lines):
                    for side, symbols in ((X, ".X#"), (O, ".#X")):
                        text = "".join(symbols[pos.cells[i]] for i in line)
                        score, slots = line_features(text, 5, strict)
                        self.assertEqual(pos.line_scores[lid][side - 1], score)
                        self.assertEqual(pos.line_wins[lid][side - 1],
                                         tuple(line[s] for s in slots))
                empty = [i for i, value in enumerate(pos.cells) if value == EMPTY]
                for i in empty[:40]:
                    for side in (X, O):
                        score, wins, _forced = pos.preview(i, side, details=True)
                        before = pos.total[side]
                        token = pos.play(i, side)
                        try:
                            self.assertEqual(pos.total[side] - before, score)
                            expected = {j for lid, _w in pos.cell_lines[i]
                                        for j in pos.line_wins[lid][side - 1]}
                            self.assertEqual(set(wins), expected)
                        finally:
                            pos.undo(token)

        def verify_win(self, bot, pos, attacker, strict, plies):
            """Kiểm chứng bằng bộ luật 2D: attacker thắng trước MỌI nước đáp."""
            proof = (bot.proofs.get((pos.hash, attacker))
                     or bot._probe_threats(pos, attacker, 1.0))
            if proof is None or plies < 1:
                return False
            i = proof[0]
            token = pos.play(i, attacker)
            try:
                grid = [pos.cells[r * pos.cols:(r + 1) * pos.cols] for r in range(pos.rows)]
                r, c = pos.coords[i]
                if winning_line(grid, r, c, attacker, strict=strict):
                    return True
                if plies < 3:
                    return False
                legal = [j for j, value in enumerate(pos.cells) if value == EMPTY]
                for reply in legal:
                    rr, cc = pos.coords[reply]
                    grid[rr][cc] = 3 - attacker
                    lost = winning_line(grid, rr, cc, 3 - attacker, strict=strict)
                    grid[rr][cc] = EMPTY
                    if lost:
                        return False
                    reply_token = pos.play(reply, 3 - attacker)
                    try:
                        if not self.verify_win(bot, pos, attacker, strict, plies - 2):
                            return False
                    finally:
                        pos.undo(reply_token)
                return bool(legal)
            finally:
                pos.undo(token)

        def double_three_board(self):
            board = self.empty(9, 9)
            for r, c in ((4, 3), (4, 4), (2, 5), (3, 5)):
                board[r][c] = O
            for r, c in ((0, 0), (0, 8), (8, 0), (8, 8)):
                board[r][c] = X
            return board

        def test_vct_double_three_against_every_reply(self):
            board = self.double_three_board()
            for strict in (False, True):
                bot, pos = self.bot(strict, seconds=2), Position(board, strict=strict)
                self.assertIsNone(bot._probe_vcf(pos, O, 0.5))
                result = bot._probe_vct(pos, O, 2.0, threats=1)
                self.assertEqual(result[0], 4 * 9 + 5)
                self.assertTrue(self.verify_win(bot, pos, O, strict, result[1]))
                chosen = bot.choose(board, O)
                self.assertTrue(chosen.proven)
                self.assertEqual(board[chosen.move[0]][chosen.move[1]], EMPTY)

        def test_vct_respects_counter_four(self):
            board = self.double_three_board()
            board[7][3:6] = [X, X, X]  # X có ba mở: phản công bằng bốn mở sau nước ba của O
            for strict in (False, True):
                pos = Position(board, strict=strict)
                self.assertIsNone(self.bot(strict, seconds=2)._probe_vct(pos, O, 1.5))

        def test_ponder_clock_can_be_shortened(self):
            board = self.empty()
            board[7][7], board[7][8], board[8][7] = X, O, X
            bot = CaroBot(depth=12, time_budget=30, move_limit=12)
            guess = bot.predict(board, X)
            self.assertIsNotNone(guess)
            self.assertEqual(board[guess[0]][guess[1]], EMPTY)
            clock, results = Clock(), []
            worker = threading.Thread(target=lambda: results.append(
                bot.choose(board, O, clock=clock)))
            worker.start()
            time.sleep(0.3)
            clock.deadline = time.perf_counter()
            worker.join(2.0)
            self.assertFalse(worker.is_alive())
            self.assertIsNotNone(results[0].move)

        def test_strict_rectangular_board_defense(self):
            for rows, cols in ((9, 9), (9, 25), (25, 9), (25, 25)):
                board = self.empty(rows, cols)
                r = rows - 2
                board[r][cols - 7:cols - 2] = [O, X, X, X, X]
                chosen = self.bot(strict=True).choose(board, O).move
                self.assertIn(chosen, ((r, cols - 2), (r, cols - 1)))
                board[chosen[0]][chosen[1]] = O
                self.assertFalse(Position(board, strict=True).winning_moves(X))

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RulesAndBotTests)
    return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="Cờ caro với bot chạy nền.")
    parser.add_argument("--self-test", action="store_true", help="kiểm tra luật và bot, không cần pygame")
    args = parser.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    CaroGame().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
