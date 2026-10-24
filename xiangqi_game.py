# -*- coding: utf-8 -*-
"""Engine luật cờ tướng (Xiangqi): bàn cờ, nước đi hợp lệ, chiếu, lộ mặt tướng, chiếu bí, hòa lặp lại.

Kiểm tra luật và engine:
    python xiangqi_game.py --self-test
Đo tốc độ duyệt cây (perft):
    python xiangqi_game.py --perft 4
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import random
import sys
import threading
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

EMPTY = '.'
RED = 1    # Quân Đỏ, luôn đi trước
BLACK = 2  # Quân Đen, đi sau

PIECE_NAMES: dict[str, str] = {
    'K': 'Tướng',
    'A': 'Sĩ',
    'B': 'Tượng',
    'N': 'Mã',
    'R': 'Xe',
    'C': 'Pháo',
    'P': 'Tốt',
}

START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w"

# Các hằng số bước đi tiền tính toán ở cấp module để tối ưu vòng lặp nóng
HORSE_OFFSETS = (
    (-2, -1, -1, 0), (-2, 1, -1, 0),
    (2, -1, 1, 0), (2, 1, 1, 0),
    (-1, -2, 0, -1), (1, -2, 0, -1),
    (-1, 2, 0, 1), (1, 2, 0, 1),
)

HORSE_CHECK_OFFSETS = (
    (-2, -1, -1, -1),
    (-2, 1, -1, 1),
    (2, -1, 1, -1),
    (2, 1, 1, 1),
    (-1, -2, -1, -1),
    (1, -2, 1, -1),
    (-1, 2, -1, 1),
    (1, 2, 1, 1),
)

ELEPHANT_OFFSETS = (
    (-2, -2, -1, -1), (-2, 2, -1, 1),
    (2, -2, 1, -1), (2, 2, 1, 1),
)

ADVISOR_OFFSETS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
KING_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))
ORTHO_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))

# Bảng Zobrist băm 64-bit với hạt giống ngẫu nhiên cố định để đếm lặp thế cờ
_rng = random.Random(20261024)
_PIECES_ALL = ('K', 'A', 'B', 'N', 'R', 'C', 'P', 'k', 'a', 'b', 'n', 'r', 'c', 'p')
ZOBRIST_PIECES: dict[str, list[int]] = {
    p: [_rng.getrandbits(64) for _ in range(90)] for p in _PIECES_ALL
}
ZOBRIST_SIDE = _rng.getrandbits(64)


class XiangqiBoard:
    """Bàn cờ tướng 10 hàng x 9 cột theo luật cờ tướng tiêu chuẩn."""

    def __init__(self, fen: str = START_FEN):
        self.board: list[list[str]] = [[EMPTY] * 9 for _ in range(10)]
        self.side_to_move: int = RED
        self.history: list[dict] = []
        self.kings: dict[int, tuple[int, int]] = {RED: (9, 4), BLACK: (0, 4)}
        self.zobrist: int = 0
        self.position_counts: dict[int, int] = {}
        self._load_fen(fen)

    def _compute_zobrist(self) -> int:
        """Tính toán mã Zobrist hash 64-bit đầy đủ của bàn cờ hiện tại."""
        h = 0
        board = self.board
        for r in range(10):
            row = board[r]
            offset = r * 9
            for c in range(9):
                p = row[c]
                if p != EMPTY:
                    h ^= ZOBRIST_PIECES[p][offset + c]
        if self.side_to_move == BLACK:
            h ^= ZOBRIST_SIDE
        return h

    def _load_fen(self, fen: str):
        parts = fen.strip().split()
        placement = parts[0]
        turn = parts[1] if len(parts) > 1 else 'w'

        rows = placement.split('/')
        if len(rows) != 10:
            raise ValueError(f"FEN không hợp lệ: phải có đúng 10 hàng (nhận được {len(rows)})")

        red_k = None
        black_k = None

        for r, row_str in enumerate(rows):
            c = 0
            for ch in row_str:
                if ch.isdigit():
                    empty_count = int(ch)
                    for _ in range(empty_count):
                        self.board[r][c] = EMPTY
                        c += 1
                else:
                    if c >= 9:
                        raise ValueError(f"Hàng {r} trong FEN vượt quá 9 cột")
                    self.board[r][c] = ch
                    if ch == 'K':
                        red_k = (r, c)
                    elif ch == 'k':
                        black_k = (r, c)
                    c += 1
            if c != 9:
                raise ValueError(f"Hàng {r} trong FEN không đủ 9 cột (nhận được {c})")

        if red_k:
            self.kings[RED] = red_k
        if black_k:
            self.kings[BLACK] = black_k

        self.side_to_move = RED if turn.lower() == 'w' else BLACK
        self.zobrist = self._compute_zobrist()
        self.position_counts = {self.zobrist: 1}

    def _position_key(self) -> str:
        """Tạo chuỗi định danh thế cờ dạng FEN."""
        rows = []
        board = self.board
        for r in range(10):
            row = board[r]
            empty_count = 0
            row_str = []
            for c in range(9):
                ch = row[c]
                if ch == EMPTY:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_str.append(str(empty_count))
                        empty_count = 0
                    row_str.append(ch)
            if empty_count > 0:
                row_str.append(str(empty_count))
            rows.append("".join(row_str))
        turn_str = 'w' if self.side_to_move == RED else 'b'
        return f"{'/'.join(rows)} {turn_str}"

    def to_fen(self) -> str:
        """Xuất thế cờ hiện tại thành chuỗi FEN."""
        return self._position_key()

    def copy(self) -> XiangqiBoard:
        """Tạo bản sao độc lập của bàn cờ."""
        other = XiangqiBoard.__new__(XiangqiBoard)
        other.board = [row[:] for row in self.board]
        other.side_to_move = self.side_to_move
        other.kings = dict(self.kings)
        other.history = [dict(h) for h in self.history]
        other.zobrist = self.zobrist
        other.position_counts = dict(self.position_counts)
        return other

    @staticmethod
    def side_of(piece: str) -> int | None:
        """Xác định phe sở hữu quân cờ: RED (chữ hoa), BLACK (chữ thường) hoặc None."""
        if piece == EMPTY:
            return None
        return RED if piece.isupper() else BLACK

    def are_kings_facing(self) -> bool:
        """Kiểm tra luật lộ mặt tướng: 2 tướng trên cùng cột không có quân cản ở giữa."""
        rk = self.kings[RED]
        bk = self.kings[BLACK]
        if rk[1] != bk[1]:
            return False
        col = rk[1]
        top = bk[0]
        bot = rk[0]
        if top > bot:
            top, bot = bot, top
        board = self.board
        for r in range(top + 1, bot):
            if board[r][col] != EMPTY:
                return False
        return True

    def in_check(self, side: int) -> bool:
        """Kiểm tra Tướng của phe `side` có đang bị chiếu hay không."""
        kr, kc = self.kings[side]
        board = self.board

        # 1. Hai tướng lộ mặt
        rk = self.kings[RED]
        bk = self.kings[BLACK]
        if rk[1] == bk[1]:
            col = rk[1]
            top, bot = (bk[0], rk[0]) if bk[0] < rk[0] else (rk[0], bk[0])
            facing = True
            for r in range(top + 1, bot):
                if board[r][col] != EMPTY:
                    facing = False
                    break
            if facing:
                return True

        # 2. Xe và Pháo (chiếu theo 4 hướng trực giao)
        enemy_rook = 'r' if side == RED else 'R'
        enemy_cannon = 'c' if side == RED else 'C'

        for dr, dc in ORTHO_DIRS:
            curr_r, curr_c = kr + dr, kc + dc
            screen_count = 0
            while 0 <= curr_r < 10 and 0 <= curr_c < 9:
                p = board[curr_r][curr_c]
                if p != EMPTY:
                    if screen_count == 0:
                        if p == enemy_rook:
                            return True
                        screen_count = 1
                    else:
                        if p == enemy_cannon:
                            return True
                        break
                curr_r += dr
                curr_c += dc

        # 3. Mã (dùng bảng kiểm tra chân mã trực tiếp từ vị trí Tướng)
        enemy_horse = 'n' if side == RED else 'N'
        for dr, dc, leg_dr, leg_dc in HORSE_CHECK_OFFSETS:
            hr = kr + dr
            hc = kc + dc
            if 0 <= hr < 10 and 0 <= hc < 9:
                if board[hr][hc] == enemy_horse:
                    if board[kr + leg_dr][kc + leg_dc] == EMPTY:
                        return True

        # 4. Tốt
        enemy_pawn = 'p' if side == RED else 'P'
        if side == RED:
            if kr > 0 and board[kr - 1][kc] == enemy_pawn:
                return True
        else:
            if kr < 9 and board[kr + 1][kc] == enemy_pawn:
                return True

        if kc > 0 and board[kr][kc - 1] == enemy_pawn:
            return True
        if kc < 8 and board[kr][kc + 1] == enemy_pawn:
            return True

        return False

    def _is_legal_after_pseudo(self, fr: int, fc: int, tr: int, tc: int, p: str, side: int) -> bool:
        """Hàm nội bộ: giả lập nước đi và kiểm tra xem Tướng phe mình có bị chiếu / lộ mặt tướng không."""
        board = self.board
        orig_to = board[tr][tc]
        board[tr][tc] = p
        board[fr][fc] = EMPTY

        if p == 'K':
            self.kings[RED] = (tr, tc)
        elif p == 'k':
            self.kings[BLACK] = (tr, tc)

        illegal = self.in_check(side)

        board[fr][fc] = p
        board[tr][tc] = orig_to

        if p == 'K':
            self.kings[RED] = (fr, fc)
        elif p == 'k':
            self.kings[BLACK] = (fr, fc)

        return not illegal

    def is_pseudo_legal(self, fr: int, fc: int, tr: int, tc: int) -> tuple[bool, str]:
        """Kiểm tra sơ bộ quy tắc di chuyển cơ bản của từng quân cờ (chưa xét lộ mặt tướng/chiếu)."""
        if not (type(fr) is int and type(fc) is int and type(tr) is int and type(tc) is int):
            return False, "Tọa độ nước đi phải là số nguyên."
        if not (0 <= fr < 10 and 0 <= fc < 9 and 0 <= tr < 10 and 0 <= tc < 9):
            return False, "Tọa độ nước đi ngoài bàn cờ."
        if fr == tr and fc == tc:
            return False, "Ô đích trùng ô xuất phát."

        p = self.board[fr][fc]
        if p == EMPTY:
            return False, "Ô xuất phát không có quân cờ."

        side = self.side_of(p)
        if side != self.side_to_move:
            who = "Đỏ" if self.side_to_move == RED else "Đen"
            return False, f"Chưa đến lượt đi của quân này (lượt {who})."

        target_piece = self.board[tr][tc]
        if target_piece != EMPTY and self.side_of(target_piece) == side:
            return False, "Không thể đi vào ô có quân cùng bên."

        dr = tr - fr
        dc = tc - fc
        p_upper = p.upper()

        # 1. Tướng (K)
        if p_upper == 'K':
            if side == RED and not (7 <= tr <= 9 and 3 <= tc <= 5):
                return False, "Tướng không được ra khỏi cung."
            if side == BLACK and not (0 <= tr <= 2 and 3 <= tc <= 5):
                return False, "Tướng không được ra khỏi cung."
            if abs(dr) + abs(dc) != 1:
                return False, "Tướng chỉ được đi 1 ô ngang hoặc dọc."

        # 2. Sĩ (A)
        elif p_upper == 'A':
            if side == RED and not (7 <= tr <= 9 and 3 <= tc <= 5):
                return False, "Sĩ không được ra khỏi cung."
            if side == BLACK and not (0 <= tr <= 2 and 3 <= tc <= 5):
                return False, "Sĩ không được ra khỏi cung."
            if abs(dr) != 1 or abs(dc) != 1:
                return False, "Sĩ chỉ được đi chéo 1 ô."

        # 3. Tượng (B)
        elif p_upper == 'B':
            if side == RED and tr < 5:
                return False, "Tượng không được qua sông."
            if side == BLACK and tr > 4:
                return False, "Tượng không được qua sông."
            if abs(dr) != 2 or abs(dc) != 2:
                return False, "Tượng chỉ được đi chéo 2 ô."
            eye_r = (fr + tr) // 2
            eye_c = (fc + tc) // 2
            if self.board[eye_r][eye_c] != EMPTY:
                return False, "Tượng bị cản mắt."

        # 4. Mã (N)
        elif p_upper == 'N':
            if not ((abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2)):
                return False, "Mã chỉ được đi hình chữ L."
            if abs(dr) == 2:
                leg_r = fr + dr // 2
                leg_c = fc
            else:
                leg_r = fr
                leg_c = fc + dc // 2
            if self.board[leg_r][leg_c] != EMPTY:
                return False, "Mã bị cản chân."

        # 5. Xe (R)
        elif p_upper == 'R':
            if dr != 0 and dc != 0:
                return False, "Xe chỉ được đi ngang hoặc dọc."
            step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
            step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
            curr_r, curr_c = fr + step_r, fc + step_c
            while (curr_r, curr_c) != (tr, tc):
                if self.board[curr_r][curr_c] != EMPTY:
                    return False, "Xe không được nhảy qua quân khác."
                curr_r += step_r
                curr_c += step_c

        # 6. Pháo (C)
        elif p_upper == 'C':
            if dr != 0 and dc != 0:
                return False, "Pháo chỉ được đi ngang hoặc dọc."
            step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
            step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
            screen_count = 0
            curr_r, curr_c = fr + step_r, fc + step_c
            while (curr_r, curr_c) != (tr, tc):
                if self.board[curr_r][curr_c] != EMPTY:
                    screen_count += 1
                curr_r += step_r
                curr_c += step_c

            if target_piece == EMPTY:
                if screen_count != 0:
                    return False, "Pháo khi không ăn quân không được nhảy qua quân khác."
            else:
                if screen_count != 1:
                    return False, f"Pháo khi ăn quân phải nhảy qua đúng 1 quân (ngòi), hiện có {screen_count} ngòi."

        # 7. Tốt (P)
        elif p_upper == 'P':
            if side == RED:
                if dr > 0:
                    return False, "Tốt không được đi lùi."
                if fr >= 5:
                    if not (dr == -1 and dc == 0):
                        return False, "Tốt chưa qua sông chỉ được tiến 1 ô, không được đi ngang."
                else:
                    if not ((dr == -1 and dc == 0) or (dr == 0 and abs(dc) == 1)):
                        return False, "Tốt qua sông chỉ được tiến hoặc đi ngang 1 ô."
            else:
                if dr < 0:
                    return False, "Tốt không được đi lùi."
                if fr <= 4:
                    if not (dr == 1 and dc == 0):
                        return False, "Tốt chưa qua sông chỉ được tiến 1 ô, không được đi ngang."
                else:
                    if not ((dr == 1 and dc == 0) or (dr == 0 and abs(dc) == 1)):
                        return False, "Tốt qua sông chỉ được tiến hoặc đi ngang 1 ô."

        return True, ""

    def is_legal(self, move: tuple[int, int, int, int]) -> tuple[bool, str]:
        """Kiểm tra tính hợp lệ đầy đủ của nước đi.

        Trả về (hợp_lệ, lý_do_tiếng_Việt).
        """
        if not (isinstance(move, (tuple, list)) and len(move) == 4):
            return False, "Nước đi phải là tuple 4 số nguyên (fr, fc, tr, tc)."
        fr, fc, tr, tc = move
        ok, reason = self.is_pseudo_legal(fr, fc, tr, tc)
        if not ok:
            return False, reason

        side = self.side_to_move
        p = self.board[fr][fc]
        board = self.board
        orig_to = board[tr][tc]

        board[tr][tc] = p
        board[fr][fc] = EMPTY

        if p == 'K':
            self.kings[RED] = (tr, tc)
        elif p == 'k':
            self.kings[BLACK] = (tr, tc)

        facing = self.are_kings_facing()
        in_chk = False
        if not facing:
            in_chk = self.in_check(side)

        board[fr][fc] = p
        board[tr][tc] = orig_to

        if p == 'K':
            self.kings[RED] = (fr, fc)
        elif p == 'k':
            self.kings[BLACK] = (fr, fc)

        if facing:
            return False, "Nước đi phạm luật lộ mặt tướng."
        if in_chk:
            return False, "Nước đi để Tướng của mình bị chiếu."

        return True, ""

    def legal_moves(self) -> list[tuple[int, int, int, int]]:
        """Sinh toàn bộ nước đi hợp lệ của bên đang tới lượt (tối ưu hóa sinh trực tiếp)."""
        side = self.side_to_move
        moves: list[tuple[int, int, int, int]] = []
        board = self.board

        for fr in range(10):
            row = board[fr]
            for fc in range(9):
                p = row[fc]
                if p == EMPTY:
                    continue
                p_is_upper = p.isupper()
                if (p_is_upper and side != RED) or (not p_is_upper and side != BLACK):
                    continue

                p_upper = p.upper()

                if p_upper == 'P':
                    if side == RED:
                        if fr > 0:
                            tr = fr - 1
                            target = board[tr][fc]
                            if target == EMPTY or not target.isupper():
                                if self._is_legal_after_pseudo(fr, fc, tr, fc, p, side):
                                    moves.append((fr, fc, tr, fc))
                        if fr <= 4:  # Đã qua sông
                            if fc > 0:
                                target = board[fr][fc - 1]
                                if target == EMPTY or not target.isupper():
                                    if self._is_legal_after_pseudo(fr, fc, fr, fc - 1, p, side):
                                        moves.append((fr, fc, fr, fc - 1))
                            if fc < 8:
                                target = board[fr][fc + 1]
                                if target == EMPTY or not target.isupper():
                                    if self._is_legal_after_pseudo(fr, fc, fr, fc + 1, p, side):
                                        moves.append((fr, fc, fr, fc + 1))
                    else:
                        if fr < 9:
                            tr = fr + 1
                            target = board[tr][fc]
                            if target == EMPTY or target.isupper():
                                if self._is_legal_after_pseudo(fr, fc, tr, fc, p, side):
                                    moves.append((fr, fc, tr, fc))
                        if fr >= 5:  # Đã qua sông
                            if fc > 0:
                                target = board[fr][fc - 1]
                                if target == EMPTY or target.isupper():
                                    if self._is_legal_after_pseudo(fr, fc, fr, fc - 1, p, side):
                                        moves.append((fr, fc, fr, fc - 1))
                            if fc < 8:
                                target = board[fr][fc + 1]
                                if target == EMPTY or target.isupper():
                                    if self._is_legal_after_pseudo(fr, fc, fr, fc + 1, p, side):
                                        moves.append((fr, fc, fr, fc + 1))

                elif p_upper == 'R':
                    for dr, dc in ORTHO_DIRS:
                        tr, tc = fr + dr, fc + dc
                        while 0 <= tr < 10 and 0 <= tc < 9:
                            target = board[tr][tc]
                            if target == EMPTY:
                                if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                    moves.append((fr, fc, tr, tc))
                            else:
                                if (side == RED and not target.isupper()) or (side == BLACK and target.isupper()):
                                    if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                        moves.append((fr, fc, tr, tc))
                                break
                            tr += dr
                            tc += dc

                elif p_upper == 'C':
                    for dr, dc in ORTHO_DIRS:
                        tr, tc = fr + dr, fc + dc
                        # Đi không ăn quân
                        while 0 <= tr < 10 and 0 <= tc < 9:
                            target = board[tr][tc]
                            if target == EMPTY:
                                if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                    moves.append((fr, fc, tr, tc))
                            else:
                                # Gặp ngòi thứ nhất, quét tìm quân phía sau để ăn
                                tr += dr
                                tc += dc
                                while 0 <= tr < 10 and 0 <= tc < 9:
                                    target2 = board[tr][tc]
                                    if target2 != EMPTY:
                                        if (side == RED and not target2.isupper()) or (side == BLACK and target2.isupper()):
                                            if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                                moves.append((fr, fc, tr, tc))
                                        break
                                    tr += dr
                                    tc += dc
                                break
                            tr += dr
                            tc += dc

                elif p_upper == 'N':
                    for dr, dc, leg_dr, leg_dc in HORSE_OFFSETS:
                        tr, tc = fr + dr, fc + dc
                        if 0 <= tr < 10 and 0 <= tc < 9:
                            if board[fr + leg_dr][fc + leg_dc] == EMPTY:
                                target = board[tr][tc]
                                if target == EMPTY or (side == RED and not target.isupper()) or (side == BLACK and target.isupper()):
                                    if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                        moves.append((fr, fc, tr, tc))

                elif p_upper == 'B':
                    for dr, dc, eye_dr, eye_dc in ELEPHANT_OFFSETS:
                        tr, tc = fr + dr, fc + dc
                        if (side == RED and 5 <= tr <= 9) or (side == BLACK and 0 <= tr <= 4):
                            if 0 <= tc < 9:
                                if board[fr + eye_dr][fc + eye_dc] == EMPTY:
                                    target = board[tr][tc]
                                    if target == EMPTY or (side == RED and not target.isupper()) or (side == BLACK and target.isupper()):
                                        if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                            moves.append((fr, fc, tr, tc))

                elif p_upper == 'A':
                    for dr, dc in ADVISOR_OFFSETS:
                        tr, tc = fr + dr, fc + dc
                        if (side == RED and 7 <= tr <= 9 and 3 <= tc <= 5) or (side == BLACK and 0 <= tr <= 2 and 3 <= tc <= 5):
                            target = board[tr][tc]
                            if target == EMPTY or (side == RED and not target.isupper()) or (side == BLACK and target.isupper()):
                                if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                    moves.append((fr, fc, tr, tc))

                elif p_upper == 'K':
                    for dr, dc in KING_OFFSETS:
                        tr, tc = fr + dr, fc + dc
                        if (side == RED and 7 <= tr <= 9 and 3 <= tc <= 5) or (side == BLACK and 0 <= tr <= 2 and 3 <= tc <= 5):
                            target = board[tr][tc]
                            if target == EMPTY or (side == RED and not target.isupper()) or (side == BLACK and target.isupper()):
                                if self._is_legal_after_pseudo(fr, fc, tr, tc, p, side):
                                    moves.append((fr, fc, tr, tc))

        return moves

    def play(self, move: tuple[int, int, int, int]) -> str | None:
        """Thực hiện nước đi.

        Trả về quân cờ bị ăn (ký tự str) hoặc None.
        Báo lỗi ValueError nếu nước đi không hợp lệ.
        """
        legal, reason = self.is_legal(move)
        if not legal:
            raise ValueError(reason)

        fr, fc, tr, tc = move
        moving_piece = self.board[fr][fc]
        captured_piece = self.board[tr][tc]
        captured = captured_piece if captured_piece != EMPTY else None

        # Cập nhật mã băm Zobrist gia số
        self.zobrist ^= ZOBRIST_PIECES[moving_piece][fr * 9 + fc]
        if captured:
            self.zobrist ^= ZOBRIST_PIECES[captured][tr * 9 + tc]
        self.zobrist ^= ZOBRIST_PIECES[moving_piece][tr * 9 + tc]
        self.zobrist ^= ZOBRIST_SIDE

        self.board[tr][tc] = moving_piece
        self.board[fr][fc] = EMPTY

        if moving_piece == 'K':
            self.kings[RED] = (tr, tc)
        elif moving_piece == 'k':
            self.kings[BLACK] = (tr, tc)

        self.side_to_move = 3 - self.side_to_move
        self.position_counts[self.zobrist] = self.position_counts.get(self.zobrist, 0) + 1

        self.history.append({
            "move": move,
            "moving_piece": moving_piece,
            "captured": captured_piece,
            "zobrist": self.zobrist,
        })
        return captured

    def undo(self) -> bool:
        """Hoàn tác nước đi gần nhất."""
        if not self.history:
            return False
        last = self.history.pop()
        fr, fc, tr, tc = last["move"]
        moving_piece = last["moving_piece"]
        captured = last["captured"]
        zob = last["zobrist"]

        # Giảm số lần lặp
        if zob in self.position_counts:
            self.position_counts[zob] -= 1
            if self.position_counts[zob] <= 0:
                del self.position_counts[zob]

        self.board[fr][fc] = moving_piece
        self.board[tr][tc] = captured

        if moving_piece == 'K':
            self.kings[RED] = (fr, fc)
        elif moving_piece == 'k':
            self.kings[BLACK] = (fr, fc)

        # Khôi phục mã băm Zobrist
        self.zobrist ^= ZOBRIST_PIECES[moving_piece][tr * 9 + tc]
        if captured != EMPTY:
            self.zobrist ^= ZOBRIST_PIECES[captured][tr * 9 + tc]
        self.zobrist ^= ZOBRIST_PIECES[moving_piece][fr * 9 + fc]
        self.zobrist ^= ZOBRIST_SIDE

        self.side_to_move = 3 - self.side_to_move
        return True

    def _push_perft(self, move: tuple[int, int, int, int]) -> str:
        """Hàm nội bộ đi nước cực nhanh cho perft (không kiểm tra lại, không ghi lịch sử)."""
        fr, fc, tr, tc = move
        p = self.board[fr][fc]
        captured = self.board[tr][tc]
        self.board[tr][tc] = p
        self.board[fr][fc] = EMPTY
        self.side_to_move = 3 - self.side_to_move
        if p == 'K':
            self.kings[RED] = (tr, tc)
        elif p == 'k':
            self.kings[BLACK] = (tr, tc)
        return captured

    def _pop_perft(self, move: tuple[int, int, int, int], captured: str):
        """Hàm nội bộ hoàn tác cực nhanh cho perft."""
        fr, fc, tr, tc = move
        p = self.board[tr][tc]
        self.board[fr][fc] = p
        self.board[tr][tc] = captured
        self.side_to_move = 3 - self.side_to_move
        if p == 'K':
            self.kings[RED] = (fr, fc)
        elif p == 'k':
            self.kings[BLACK] = (fr, fc)

    def _push_bot(self, move: tuple[int, int, int, int]) -> str:
        """Hàm nội bộ đi nước cực nhanh cho bot (cập nhật luôn mã băm Zobrist)."""
        fr, fc, tr, tc = move
        p = self.board[fr][fc]
        captured = self.board[tr][tc]

        self.zobrist ^= ZOBRIST_PIECES[p][fr * 9 + fc]
        if captured != EMPTY:
            self.zobrist ^= ZOBRIST_PIECES[captured][tr * 9 + tc]
        self.zobrist ^= ZOBRIST_PIECES[p][tr * 9 + tc]
        self.zobrist ^= ZOBRIST_SIDE

        self.board[tr][tc] = p
        self.board[fr][fc] = EMPTY
        self.side_to_move = 3 - self.side_to_move

        if p == 'K':
            self.kings[RED] = (tr, tc)
        elif p == 'k':
            self.kings[BLACK] = (tr, tc)

        return captured

    def _pop_bot(self, move: tuple[int, int, int, int], captured: str):
        """Hàm nội bộ hoàn tác cực nhanh cho bot."""
        fr, fc, tr, tc = move
        p = self.board[tr][tc]

        self.board[fr][fc] = p
        self.board[tr][tc] = captured
        self.side_to_move = 3 - self.side_to_move

        if p == 'K':
            self.kings[RED] = (fr, fc)
        elif p == 'k':
            self.kings[BLACK] = (fr, fc)

        self.zobrist ^= ZOBRIST_PIECES[p][tr * 9 + tc]
        if captured != EMPTY:
            self.zobrist ^= ZOBRIST_PIECES[captured][tr * 9 + tc]
        self.zobrist ^= ZOBRIST_PIECES[p][fr * 9 + fc]
        self.zobrist ^= ZOBRIST_SIDE

    def result(self) -> dict:
        """Kiểm tra trạng thái kết thúc ván cờ.

        Trả về dict: {"over": bool, "winner": RED/BLACK/None, "reason": str | None}
        """
        # 1. Lặp lại 3 lần
        if self.position_counts.get(self.zobrist, 0) >= 3:
            return {
                "over": True,
                "winner": None,
                "reason": "lặp lại 3 lần",
            }

        # 2. Kiểm tra nước đi hợp lệ
        moves = self.legal_moves()
        if not moves:
            winner = 3 - self.side_to_move
            if self.in_check(self.side_to_move):
                return {
                    "over": True,
                    "winner": winner,
                    "reason": "chiếu bí",
                }
            else:
                return {
                    "over": True,
                    "winner": winner,
                    "reason": "hết nước đi",
                }

        return {
            "over": False,
            "winner": None,
            "reason": None,
        }

    def perft(self, depth: int) -> int:
        """Đếm số lượng thế cờ ở độ sâu `depth` (dùng để kiểm thử sinh nước đi)."""
        if depth <= 0:
            return 1
        moves = self.legal_moves()
        if depth == 1:
            return len(moves)
        if depth == 2:
            nodes = 0
            for m in moves:
                captured = self._push_perft(m)
                nodes += len(self.legal_moves())
                self._pop_perft(m, captured)
            return nodes
        nodes = 0
        for m in moves:
            captured = self._push_perft(m)
            nodes += self.perft(depth - 1)
            self._pop_perft(m, captured)
        return nodes


# ==============================================================================
# BOT CỜ TƯỚNG (XIANGQI BOT)
# ==============================================================================

XIANGQI_LEVELS = [
    ("Dễ", 0.5),
    ("Vừa", 1.5),
    ("Khó", 4.0),
]


@dataclass
class XiangqiSearchResult:
    """Kết quả tính toán nước đi của bot cờ tướng."""
    move: tuple[int, int, int, int] | None
    score: int
    depth: int
    nodes: int
    elapsed: float


# Bảng giá trị vật chất của từng loại quân
PIECE_VALUES: dict[str, int] = {
    'R': 900,
    'C': 450,
    'N': 400,
    'B': 200,
    'A': 200,
    'P': 100,  # Qua sông là 200
    'K': 0,
}

# Bảng điểm vị trí (PST) đơn giản cho quân Đỏ (hàng 0-9, cột 0-8)
# Quân Đen sẽ dùng chỉ số hàng đối xứng: 9 - r

PST_PAWN_RED = (
    ( 0,  3,  6,  9, 12,  9,  6,  3,  0),  # Hàng 0 (đáy cung đối phương)
    (18, 36, 56, 80, 90, 80, 56, 36, 18),  # Hàng 1
    (14, 26, 42, 60, 70, 60, 42, 26, 14),  # Hàng 2
    (10, 20, 30, 45, 55, 45, 30, 20, 10),  # Hàng 3
    ( 6, 12, 18, 25, 30, 25, 18, 12,  6),  # Hàng 4 (vừa qua sông)
    ( 0,  0,  0,  0,  0,  0,  0,  0,  0),  # Hàng 5 (bờ sông sân nhà)
    ( 0,  0, -2,  0,  4,  0, -2,  0,  0),  # Hàng 6 (vị trí ban đầu)
    ( 0,  0,  0,  0,  0,  0,  0,  0,  0),  # Hàng 7
    ( 0,  0,  0,  0,  0,  0,  0,  0,  0),  # Hàng 8
    ( 0,  0,  0,  0,  0,  0,  0,  0,  0),  # Hàng 9
)

PST_HORSE = (
    ( 4,  8, 16, 12,  4, 12, 16,  8,  4),
    ( 4, 10, 28, 16,  8, 16, 28, 10,  4),
    (12, 16, 30, 36, 20, 36, 30, 16, 12),
    ( 8, 24, 34, 40, 24, 40, 34, 24,  8),
    ( 6, 16, 24, 32, 20, 32, 24, 16,  6),
    ( 4, 12, 16, 24, 12, 24, 16, 12,  4),
    ( 2,  8, 12, 14, 10, 14, 12,  8,  2),
    ( 2,  4,  6,  8,  4,  8,  6,  4,  2),
    ( 0,  2,  4,  4, -2,  4,  4,  2,  0),
    ( 0, -4,  0,  0,  0,  0,  0, -4,  0),
)

PST_CANNON = (
    ( 6,  8,  4,  0,  0,  0,  4,  8,  6),
    ( 2,  4,  0, -4, -6, -4,  0,  4,  2),
    ( 0,  4,  4,  4,  4,  4,  4,  4,  0),
    ( 0,  2,  2,  4,  6,  4,  2,  2,  0),
    ( 0,  0,  2,  6,  8,  6,  2,  0,  0),
    ( 0,  0,  0,  2,  4,  2,  0,  0,  0),
    ( 0,  0,  0,  0,  0,  0,  0,  0,  0),
    (-2,  0,  4,  2,  2,  2,  4,  0, -2),
    ( 0,  0,  0,  0,  0,  0,  0,  0,  0),
    ( 0,  0, -2,  0,  4,  0, -2,  0,  0),
)

PST_ROOK = (
    (14, 14, 12, 18, 16, 18, 12, 14, 14),
    (16, 20, 18, 24, 26, 24, 18, 20, 16),
    (12, 12, 12, 18, 18, 18, 12, 12, 12),
    (12, 18, 16, 22, 22, 22, 16, 18, 12),
    (12, 14, 12, 18, 18, 18, 12, 14, 12),
    ( 8, 10,  8, 14, 14, 14,  8, 10,  8),
    ( 8,  8,  8,  8,  8,  8,  8,  8,  8),
    ( 0,  6,  4,  4,  0,  4,  4,  6,  0),
    ( 4,  8,  6, 12,  0, 12,  6,  8,  4),
    ( 0,  6,  4,  4,  0,  4,  4,  6,  0),
)

MATE_SCORE = 100000
MATE_THRESHOLD = 90000

TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2


def evaluate_board(board: XiangqiBoard) -> int:
    """Hàm đánh giá tĩnh bàn cờ từ góc nhìn của bên tới lượt đi (board.side_to_move)."""
    red_score = 0
    black_score = 0
    b = board.board
    for r in range(10):
        row = b[r]
        for c in range(9):
            p = row[c]
            if p == EMPTY:
                continue
            if p.isupper():
                if p == 'R':
                    red_score += 900 + PST_ROOK[r][c]
                elif p == 'C':
                    red_score += 450 + PST_CANNON[r][c]
                elif p == 'N':
                    red_score += 400 + PST_HORSE[r][c]
                elif p == 'B':
                    red_score += 200
                elif p == 'A':
                    red_score += 200
                elif p == 'P':
                    red_score += (200 if r <= 4 else 100) + PST_PAWN_RED[r][c]
            else:
                br = 9 - r
                if p == 'r':
                    black_score += 900 + PST_ROOK[br][c]
                elif p == 'c':
                    black_score += 450 + PST_CANNON[br][c]
                elif p == 'n':
                    black_score += 400 + PST_HORSE[br][c]
                elif p == 'b':
                    black_score += 200
                elif p == 'a':
                    black_score += 200
                elif p == 'p':
                    black_score += (200 if r >= 5 else 100) + PST_PAWN_RED[br][c]

    score = red_score - black_score
    return score if board.side_to_move == RED else -score


class SearchInterrupted(Exception):
    """Ngoại lệ nội bộ khi hết giờ suy nghĩ hoặc nhận tín hiệu hủy."""
    pass


class XiangqiBot:
    """Bot cờ tướng sử dụng Iterative Deepening Negamax với Alpha-Beta."""

    def __init__(self, level: int = 1):
        if not (0 <= level < len(XIANGQI_LEVELS)):
            raise ValueError(f"Độ khó bot không hợp lệ: {level}")
        self.level = level
        self.time_limit = XIANGQI_LEVELS[level][1]
        self.tt: dict[int, tuple[int, int, int, tuple[int, int, int, int] | None]] = {}
        self.history: dict[tuple[int, int, int, int], int] = {}
        self.nodes = 0

    def choose(self, board: XiangqiBoard, cancel_event: threading.Event | None = None) -> XiangqiSearchResult:
        """Chọn nước đi tốt nhất cho bên tới lượt.

        Không làm thay đổi bàn cờ truyền vào.
        """
        b = board.copy()
        if len(self.tt) > 1_000_000:  # giữ TT giữa các nước nhưng không để phình mãi
            self.tt.clear()
        start_time = time.perf_counter()
        deadline = start_time + self.time_limit
        self.nodes = 0

        legals = b.legal_moves()
        if not legals:
            return XiangqiSearchResult(None, -MATE_SCORE, 0, 0, 0.0)

        # Nếu cancel_event đã set trước thì trả ngay một nước hợp lệ
        if cancel_event is not None and cancel_event.is_set():
            return XiangqiSearchResult(legals[0], 0, 0, 0, 0.0)

        best_move = legals[0]
        best_score = 0
        completed_depth = 0

        for depth in range(1, 30):
            try:
                score, move, _ = self._search_root(b, depth, deadline, cancel_event)
                best_score = score
                best_move = move
                completed_depth = depth
                # Nếu đã phát hiện chiếu bí thì dừng sớm
                if abs(score) >= MATE_THRESHOLD:
                    break
            except SearchInterrupted:
                break

            if time.perf_counter() >= deadline or (cancel_event is not None and cancel_event.is_set()):
                break

        elapsed = time.perf_counter() - start_time

        # Mức "Dễ": chọn ngẫu nhiên trong các nước chênh <= 30 điểm so với nước tốt nhất.
        # Điểm ở gốc alpha-beta chỉ là chặn trên (nước tệ cũng báo bằng alpha), nên chấm lại
        # từng nước bằng tìm tĩnh cửa sổ đầy đủ. Thấy chiếu bí thì vẫn đi nước chiếu bí.
        if self.level == 0 and abs(best_score) < MATE_THRESHOLD:
            scored = []
            try:
                for m in legals:
                    cap = b._push_bot(m)
                    try:
                        scored.append((m, -self._quiescence(
                            b, -MATE_SCORE - 1, MATE_SCORE + 1, 1, time.perf_counter() + 1.0, cancel_event)))
                    finally:
                        b._pop_bot(m, cap)
            except SearchInterrupted:
                scored = []
            if scored:
                top = max(sc for _, sc in scored)
                best_move = random.choice([m for m, sc in scored if sc >= top - 30])

        return XiangqiSearchResult(
            move=best_move,
            score=best_score,
            depth=completed_depth,
            nodes=self.nodes,
            elapsed=round(elapsed, 4),
        )

    def _search_root(
        self,
        board: XiangqiBoard,
        depth: int,
        deadline: float,
        cancel_event: threading.Event | None,
    ) -> tuple[int, tuple[int, int, int, int], list[tuple[tuple[int, int, int, int], int]]]:
        moves = board.legal_moves()
        if not moves:
            return -MATE_SCORE, moves[0] if moves else None, []

        zob = board.zobrist
        tt_entry = self.tt.get(zob)
        hash_move = tt_entry[3] if tt_entry else None

        def move_priority(m):
            if m == hash_move:
                return 2_000_000
            tr, tc = m[2], m[3]
            target = board.board[tr][tc]
            if target != EMPTY:
                vic = PIECE_VALUES.get(target.upper(), 0)
                att = PIECE_VALUES.get(board.board[m[0]][m[1]].upper(), 0)
                return 1_000_000 + vic * 10 - att
            return self.history.get(m, 0)

        moves.sort(key=move_priority, reverse=True)

        alpha = -MATE_SCORE - 1
        beta = MATE_SCORE + 1
        best_score = -MATE_SCORE - 1
        best_move = moves[0]
        move_scores: list[tuple[tuple[int, int, int, int], int]] = []

        for m in moves:
            cap = board._push_bot(m)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, 1, deadline, cancel_event)
            finally:
                board._pop_bot(m, cap)

            move_scores.append((m, score))
            if score > best_score:
                best_score = score
                best_move = m
            if score > alpha:
                alpha = score

        self.tt[zob] = (depth, TT_EXACT, best_score, best_move)
        return best_score, best_move, move_scores

    def _negamax(
        self,
        board: XiangqiBoard,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        deadline: float,
        cancel_event: threading.Event | None,
    ) -> int:
        self.nodes += 1
        if (self.nodes & 1023) == 0:
            if (cancel_event is not None and cancel_event.is_set()) or (time.perf_counter() >= deadline):
                raise SearchInterrupted()

        if depth <= 0:
            return self._quiescence(board, alpha, beta, ply, deadline, cancel_event)

        zob = board.zobrist
        tt_entry = self.tt.get(zob)
        hash_move = None
        if tt_entry is not None:
            tt_depth, tt_flag, tt_score, tt_move = tt_entry
            hash_move = tt_move
            if tt_depth >= depth:
                adj_score = tt_score
                if adj_score > MATE_THRESHOLD:
                    adj_score -= ply
                elif adj_score < -MATE_THRESHOLD:
                    adj_score += ply

                if tt_flag == TT_EXACT:
                    return adj_score
                elif tt_flag == TT_LOWERBOUND and adj_score >= beta:
                    return adj_score
                elif tt_flag == TT_UPPERBOUND and adj_score <= alpha:
                    return adj_score

        moves = board.legal_moves()
        if not moves:
            return -MATE_SCORE + ply

        def move_priority(m):
            if m == hash_move:
                return 2_000_000
            tr, tc = m[2], m[3]
            target = board.board[tr][tc]
            if target != EMPTY:
                vic = PIECE_VALUES.get(target.upper(), 0)
                att = PIECE_VALUES.get(board.board[m[0]][m[1]].upper(), 0)
                return 1_000_000 + vic * 10 - att
            return self.history.get(m, 0)

        moves.sort(key=move_priority, reverse=True)

        best_score = -MATE_SCORE - 1
        best_move = None
        orig_alpha = alpha

        for m in moves:
            cap = board._push_bot(m)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, deadline, cancel_event)
            finally:
                board._pop_bot(m, cap)

            if score > best_score:
                best_score = score
                best_move = m
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if board.board[m[2]][m[3]] == EMPTY:
                    self.history[m] = self.history.get(m, 0) + depth * depth
                break

        flag = TT_EXACT
        if best_score <= orig_alpha:
            flag = TT_UPPERBOUND
        elif best_score >= beta:
            flag = TT_LOWERBOUND

        stored_score = best_score
        if stored_score > MATE_THRESHOLD:
            stored_score += ply
        elif stored_score < -MATE_THRESHOLD:
            stored_score -= ply

        self.tt[zob] = (depth, flag, stored_score, best_move)
        return best_score

    def _quiescence(
        self,
        board: XiangqiBoard,
        alpha: int,
        beta: int,
        ply: int,
        deadline: float,
        cancel_event: threading.Event | None,
    ) -> int:
        self.nodes += 1
        if (self.nodes & 1023) == 0:
            if (cancel_event is not None and cancel_event.is_set()) or (time.perf_counter() >= deadline):
                raise SearchInterrupted()

        stand_pat = evaluate_board(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        all_moves = board.legal_moves()
        captures = [m for m in all_moves if board.board[m[2]][m[3]] != EMPTY]
        if not captures:
            return alpha

        captures.sort(
            key=lambda m: PIECE_VALUES.get(board.board[m[2]][m[3]].upper(), 0) * 10
            - PIECE_VALUES.get(board.board[m[0]][m[1]].upper(), 0),
            reverse=True,
        )

        for m in captures:
            cap = board._push_bot(m)
            try:
                score = -self._quiescence(board, -beta, -alpha, ply + 1, deadline, cancel_event)
            finally:
                board._pop_bot(m, cap)

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha


def self_test():
    """Kiểm tra toàn bộ luật cờ tướng: các loại quân, lộ mặt tướng, ghim, chiếu bí, lặp lại."""
    print("Bắt đầu self-test cờ tướng...")

    # 1. Thế mở đầu và perft
    b = XiangqiBoard()
    assert len(b.legal_moves()) == 44, f"Thế mở đầu Đỏ phải có đúng 44 nước, nhận được {len(b.legal_moves())}"
    p1 = b.perft(1)
    assert p1 == 44, f"perft(1) phải là 44, nhận được {p1}"
    p2 = b.perft(2)
    assert p2 == 1920, f"perft(2) phải là 1920, nhận được {p2}"
    p3 = b.perft(3)
    assert p3 == 79666, f"perft(3) phải là 79666, nhận được {p3}"
    print("✓ Test 1: Thế mở đầu và perft(1=44, 2=1920, 3=79666) - THÀNH CÔNG")

    # 2. Từng loại quân (hợp lệ và bị cấm)
    # Tướng ra khỏi cung
    b = XiangqiBoard("3k5/9/9/9/9/9/9/9/9/4K4 w")
    ok, _ = b.is_legal((9, 4, 8, 4))
    assert ok, "Tướng đi 1 ô trong cung phải hợp lệ"
    ok, reason = b.is_legal((9, 4, 9, 2))
    assert not ok and "cung" in reason, "Tướng ra khỏi cung ngang phải bị cấm"
    b_edge = XiangqiBoard("3k5/9/9/9/9/9/9/4K4/9/9 w")
    ok, reason = b_edge.is_legal((7, 4, 6, 4))
    assert not ok and "cung" in reason, "Tướng ra khỏi cung dọc phải bị cấm"

    # Sĩ ra khỏi cung
    b_advisor = XiangqiBoard("3k5/9/9/9/9/9/9/9/9/3A5 w")
    ok, _ = b_advisor.is_legal((9, 3, 8, 4))
    assert ok, "Sĩ đi chéo vào tâm cung phải hợp lệ"
    b_adv_out = XiangqiBoard("3k5/9/9/9/9/9/9/9/4A4/9 w")
    ok, reason = b_adv_out.is_legal((8, 4, 7, 2))
    assert not ok and "cung" in reason, "Sĩ đi chéo ra ngoài cung phải bị cấm"

    # Tượng qua sông và cản mắt
    b_eleph_river = XiangqiBoard("3k5/9/9/9/9/2B6/9/9/9/4K4 w")
    ok, reason = b_eleph_river.is_legal((5, 2, 3, 0))
    assert not ok and "sông" in reason, "Tượng qua sông phải bị cấm"

    b_eye = XiangqiBoard("3k5/9/9/9/9/9/9/9/1P7/2B1K4 w")  # P tại (8, 1) cản mắt Tượng
    ok, reason = b_eye.is_legal((9, 2, 7, 0))
    assert not ok and "mắt" in reason, "Tượng bị cản mắt phải bị cấm"
    ok, _ = b_eye.is_legal((9, 2, 7, 4))
    assert ok, "Tượng đi hướng không bị cản mắt phải hợp lệ"

    # Mã bị cản chân
    b_horse = XiangqiBoard("3k5/9/9/9/9/9/9/9/P8/N3K4 w")  # P tại (8, 0) cản chân Mã
    ok, reason = b_horse.is_legal((9, 0, 7, 1))
    assert not ok and "chân" in reason, "Mã bị cản chân phải bị cấm"
    b_horse_free = XiangqiBoard("3k5/9/9/9/9/9/9/9/9/N3K4 w")
    ok, _ = b_horse_free.is_legal((9, 0, 7, 1))
    assert ok, "Mã không bị cản chân phải đi được"

    # Xe không nhảy qua quân
    b_rook = XiangqiBoard("3k5/9/9/9/9/9/9/P8/9/R3K4 w")  # P tại (7, 0)
    ok, _ = b_rook.is_legal((9, 0, 8, 0))
    assert ok, "Xe đi trước quân cản phải hợp lệ"
    ok, reason = b_rook.is_legal((9, 0, 6, 0))
    assert not ok and "nhảy qua" in reason, "Xe không được nhảy qua quân khác"

    # Pháo ăn với 0/1/2 ngòi
    b_c0 = XiangqiBoard("3k5/9/9/9/9/9/9/1r7/9/1C2K4 w")
    ok, reason = b_c0.is_legal((9, 1, 7, 1))
    assert not ok and "ngòi" in reason, "Pháo không được ăn quân khi có 0 ngòi"
    ok, _ = b_c0.is_legal((9, 1, 8, 1))
    assert ok, "Pháo đi không ăn quân khi đường trống phải hợp lệ"

    b_c1 = XiangqiBoard("3k5/9/9/9/9/9/9/1r7/1P7/1C2K4 w")  # P tại (8, 1) là đúng 1 ngòi
    ok, _ = b_c1.is_legal((9, 1, 7, 1))
    assert ok, "Pháo ăn quân khi có đúng 1 ngòi phải hợp lệ"

    b_c2 = XiangqiBoard("3k5/9/9/9/9/9/1r7/1P7/1P7/1C2K4 w")  # 2 quân P làm 2 ngòi
    ok, reason = b_c2.is_legal((9, 1, 6, 1))
    assert not ok and "ngòi" in reason, "Pháo không được ăn quân khi có 2 ngòi"

    # Tốt chưa qua sông và đã qua sông
    b_pawn = XiangqiBoard("3k5/9/9/9/9/9/P8/9/9/4K4 w")
    ok, _ = b_pawn.is_legal((6, 0, 5, 0))
    assert ok, "Tốt chưa qua sông được tiến 1 ô"
    ok, reason = b_pawn.is_legal((6, 0, 6, 1))
    assert not ok and "ngang" in reason, "Tốt chưa qua sông không được đi ngang"
    ok, reason = b_pawn.is_legal((6, 0, 7, 0))
    assert not ok and "lùi" in reason, "Tốt không bao giờ được đi lùi"

    b_pawn_river = XiangqiBoard("3k5/9/9/9/P8/9/9/9/9/4K4 w")  # Đã qua sông
    ok, _ = b_pawn_river.is_legal((4, 0, 4, 1))
    assert ok, "Tốt qua sông được đi ngang"
    ok, _ = b_pawn_river.is_legal((4, 0, 3, 0))
    assert ok, "Tốt qua sông được tiến"
    print("✓ Test 2: Từng loại quân (hợp lệ và bị cấm) - THÀNH CÔNG")

    # 3. Lộ mặt tướng
    b_face = XiangqiBoard("4k4/9/9/9/4R4/9/9/9/9/4K4 w")
    ok, reason = b_face.is_legal((4, 4, 4, 3))  # R rời cột 4 làm 2 tướng lộ mặt
    assert not ok and "lộ mặt tướng" in reason, "Quân duy nhất chắn giữa 2 Tướng không được rời cột"
    ok, _ = b_face.is_legal((4, 4, 3, 4))
    assert ok, "Quân đi dọc cột vẫn chắn giữa 2 Tướng phải hợp lệ"

    b_face_k = XiangqiBoard("5k3/9/9/9/9/9/9/9/9/4K4 w")
    ok, reason = b_face_k.is_legal((9, 4, 9, 5))
    assert not ok and "lộ mặt tướng" in reason, "Tướng không được bước sang cột đối mặt Tướng kia"
    print("✓ Test 3: Lộ mặt tướng - THÀNH CÔNG")

    # 4. Quân bị ghim không được đi
    b_pin = XiangqiBoard("4k4/9/9/9/4r4/9/9/9/4N4/4K4 w")  # r ghim N vào K
    ok, reason = b_pin.is_legal((8, 4, 6, 3))
    assert not ok and "chiếu" in reason, "Quân bị ghim không được di chuyển để Tướng bị chiếu"
    print("✓ Test 4: Quân bị ghim không được đi - THÀNH CÔNG")

    # 5. Thế chiếu bí
    b_mate = XiangqiBoard("3k4R/8R/9/9/9/9/9/9/9/5K3 b")
    assert b_mate.in_check(BLACK)
    res = b_mate.result()
    assert res["over"] is True
    assert res["winner"] == RED
    assert res["reason"] == "chiếu bí"
    print("✓ Test 5: Thế chiếu bí - THÀNH CÔNG")

    # 6. Thế hết nước đi nhưng không bị chiếu
    b_stalemate = XiangqiBoard("3k5/8R/9/9/9/9/9/9/9/4K4 b")
    assert not b_stalemate.in_check(BLACK), "Đen không được bị chiếu ở thế hết nước đi"
    res = b_stalemate.result()
    assert res["over"] is True
    assert res["winner"] == RED
    assert res["reason"] == "hết nước đi"
    print("✓ Test 6: Thế hết nước đi nhưng không bị chiếu - THÀNH CÔNG")

    # 7. Lặp lại 3 lần và kiểm tra undo không còn hòa
    b_rep = XiangqiBoard("3k5/9/9/9/9/9/9/9/R8/5K3 w")
    # Lần 1: thế cờ ban đầu
    b_rep.play((8, 0, 9, 0))  # Red
    b_rep.play((0, 3, 1, 3))  # Black
    b_rep.play((9, 0, 8, 0))  # Red
    b_rep.play((1, 3, 0, 3))  # Black -> lần 2
    assert not b_rep.result()["over"]

    b_rep.play((8, 0, 9, 0))  # Red
    b_rep.play((0, 3, 1, 3))  # Black
    b_rep.play((9, 0, 8, 0))  # Red
    b_rep.play((1, 3, 0, 3))  # Black -> lần 3!

    res = b_rep.result()
    assert res["over"] is True
    assert res["winner"] is None
    assert res["reason"] == "lặp lại 3 lần"

    # Sau undo 1 nước: không còn hòa
    b_rep.undo()
    res_after_undo = b_rep.result()
    assert not res_after_undo["over"], "Sau khi hoàn tác 1 nước, ván cờ không được còn ở trạng thái hòa"
    assert res_after_undo["reason"] is None
    print("✓ Test 7: Lặp lại 3 lần hòa cờ và hoàn tác không còn hòa - THÀNH CÔNG")

    # 8. Undo 40 nước ngẫu nhiên
    b_undo = XiangqiBoard()
    initial_fen = b_undo.to_fen()
    random.seed(42)
    moves_played = []
    for _ in range(40):
        legals = b_undo.legal_moves()
        if not legals or b_undo.result()["over"]:
            break
        m = random.choice(legals)
        b_undo.play(m)
        moves_played.append(m)

    assert len(moves_played) == 40
    for _ in range(40):
        b_undo.undo()
    assert b_undo.to_fen() == initial_fen, "Sau khi hoàn tác hết, FEN phải trùng khớp ban đầu"
    print("✓ Test 8: Undo 40 nước ngẫu nhiên - THÀNH CÔNG")

    # 9. FEN roundtrip
    fens = [
        START_FEN,
        "4k4/9/9/9/4R4/9/9/9/9/4K4 w",
        "3k5/8R/9/9/9/9/9/9/9/4R1K2 b",
        "r1bakab1r/9/1cn4c1/p1p1p1p1p/9/2P6/P3P1P1P/1C2C4/9/RNBAKABNR b",
    ]
    for f in fens:
        assert XiangqiBoard(f).to_fen() == f, f"FEN roundtrip không khớp: {f}"
    print("✓ Test 9: FEN roundtrip - THÀNH CÔNG")

    # 10. Chơi 30 ván ngẫu nhiên, đối chiếu sorted(legal_moves()) == is_legal mọi ô, undo kiểm tra toàn vẹn
    print("Đang chạy Test 10: 30 ván ngẫu nhiên đối chiếu legal_moves() và is_legal()...")
    random.seed(12345)
    for game_idx in range(30):
        game_b = XiangqiBoard()
        init_fen = game_b.to_fen()
        init_counts = dict(game_b.position_counts)
        played = []

        for move_idx in range(200):
            legals = game_b.legal_moves()
            if not legals or game_b.result()["over"]:
                break

            side = game_b.side_to_move
            brute_force_legals = []
            for fr in range(10):
                for fc in range(9):
                    p = game_b.board[fr][fc]
                    if game_b.side_of(p) == side:
                        for tr in range(10):
                            for tc in range(9):
                                if (fr, fc) != (tr, tc):
                                    ok, _ = game_b.is_legal((fr, fc, tr, tc))
                                    if ok:
                                        brute_force_legals.append((fr, fc, tr, tc))

            assert sorted(legals) == sorted(brute_force_legals), (
                f"Ván {game_idx} nước {move_idx}: legal_moves() không khớp với is_legal!"
            )

            m = random.choice(legals)
            game_b.play(m)
            played.append(m)

        for _ in range(len(played)):
            game_b.undo()

        assert game_b.to_fen() == init_fen, f"Ván {game_idx}: to_fen sau khi undo không khớp ban đầu"
        assert game_b.position_counts == init_counts, f"Ván {game_idx}: position_counts sau khi undo không khớp"

    print("✓ Test 10: 30 ván ngẫu nhiên đối chiếu legal_moves() và hoàn tác hoàn hảo - THÀNH CÔNG")

    # 11. Kiểm thử Bot Cờ Tướng (XiangqiBot)
    print("Đang chạy Test 11: Kiểm thử bot cờ tướng...")
    # 11.1. choose() không đổi FEN gốc
    bot_b = XiangqiBoard()
    orig_fen = bot_b.to_fen()
    bot_tester = XiangqiBot(level=0)
    bot_tester.time_limit = 0.05
    bot_res = bot_tester.choose(bot_b)
    assert bot_b.to_fen() == orig_fen, "choose() đã làm thay đổi FEN gốc!"
    assert bot_res.move is not None

    # 11.2. cancel_event đã set thì trả ngay nước hợp lệ
    cancel = threading.Event()
    cancel.set()
    bot_res_cancel = bot_tester.choose(bot_b, cancel_event=cancel)
    assert bot_res_cancel.move is not None
    ok, _ = bot_b.is_legal(bot_res_cancel.move)
    assert ok, "cancel_event trả về nước không hợp lệ"

    # 11.3. bot thấy chiếu bí 1 nước
    fen_mate = "3ka4/3r5/9/9/9/9/9/9/9/R4K3 w"
    b_mate = XiangqiBoard(fen_mate)
    bot_mate = XiangqiBot(level=1)
    bot_mate.time_limit = 0.5
    res_mate = bot_mate.choose(b_mate)
    assert res_mate.move == (9, 0, 0, 0), f"Bot không thấy chiếu bí! Chọn {res_mate.move}"

    # 11.4. bot không bỏ Xe cho không ở thế đơn giản
    fen_save = "3k5/9/9/4p4/4R4/9/P8/9/9/4K4 w"
    b_save = XiangqiBoard(fen_save)
    bot_save = XiangqiBot(level=1)
    bot_save.time_limit = 0.5
    res_save = bot_save.choose(b_save)
    fr, fc, tr, tc = res_save.move
    assert fr == 4 and fc == 4, f"Bot bỏ Xe! Chọn đi quân ở ({fr}, {fc})"

    # 11.5. bot Khó thắng bot Dễ trong ít nhất 1 ván ngắn (<= 120 nước)
    print("  Đang chạy ván đấu: Bot Khó (Đỏ) vs Bot Dễ (Đen)...")
    b_game = XiangqiBoard()
    bot_hard = XiangqiBot(level=2)
    bot_hard.time_limit = 0.08
    bot_easy = XiangqiBot(level=0)
    bot_easy.time_limit = 0.01

    winner = None
    for ply in range(120):
        if b_game.side_to_move == RED:
            r_move = bot_hard.choose(b_game)
        else:
            r_move = bot_easy.choose(b_game)

        if r_move.move is None:
            break
        b_game.play(r_move.move)
        res_game = b_game.result()
        if res_game["over"]:
            winner = res_game["winner"]
            break

    assert winner == RED, f"Bot Khó không thắng được bot Dễ! winner={winner}"
    print("✓ Test 11: Kiểm thử bot cờ tướng - THÀNH CÔNG")

    print("\n===> TẤT CẢ SELF-TEST CỜ TƯỚNG ĐỀU ĐẠT! <===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Engine luật cờ tướng (Xiangqi)")
    parser.add_argument("--self-test", action="store_true", help="Chạy kiểm thử tự động")
    parser.add_argument("--perft", type=int, default=None, help="Chạy đo perft ở độ sâu chỉ định")
    args = parser.parse_args()

    if args.perft is not None:
        b = XiangqiBoard()
        t0 = time.perf_counter()
        nodes = b.perft(args.perft)
        elapsed = time.perf_counter() - t0
        nps = nodes / elapsed if elapsed > 0 else 0
        print(f"perft({args.perft}) = {nodes} thế cờ trong {elapsed:.4f}s ({nps:.0f} nps)")
    elif args.self_test:
        self_test()
    else:
        print("Chạy kiểm thử: python xiangqi_game.py --self-test")
