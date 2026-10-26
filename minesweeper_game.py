"""Engine trò chơi Dò mìn (Minesweeper) tuân thủ luật Windows cổ điển."""

from __future__ import annotations

import random
import sys
from collections import deque

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MINES_LEVELS = {
    "easy": ("Dễ", 9, 9, 10),
    "medium": ("Vừa", 16, 16, 40),
    "hard": ("Khó", 16, 30, 99),
}


class MinesweeperGame:
    def __init__(
        self,
        rows: int,
        cols: int,
        mines: int,
        rng: random.Random | None = None,
        mine_cells: set[tuple[int, int]] | None = None,
    ):
        if type(rows) is not int or type(cols) is not int or type(mines) is not int:
            raise ValueError("Kích thước và số mìn phải là số nguyên.")
        if rows <= 0 or cols <= 0 or mines < 0:
            raise ValueError("Kích thước và số mìn không hợp lệ.")
        if mines > rows * cols:
            raise ValueError("Số mìn không thể vượt quá tổng số ô.")

        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.rng = rng or random.Random()
        self.state = "ready"  # "ready" | "playing" | "won" | "lost"
        self.revealed: set[tuple[int, int]] = set()
        self.flags: set[tuple[int, int]] = set()
        self.exploded: tuple[int, int] | None = None

        if mine_cells is not None:
            self.mines_set: set[tuple[int, int]] | None = set(mine_cells)
            self._precompute_adjacent()
        else:
            self.mines_set = None
            self._adj: dict[tuple[int, int], int] = {}

    def _validate_coords(self, r: int, c: int):
        if type(r) is not int or type(c) is not int:
            raise ValueError("Tọa độ phải là số nguyên.")
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise ValueError(f"Tọa độ ({r}, {c}) nằm ngoài bàn cờ.")

    def _neighbors(self, r: int, c: int):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield nr, nc

    def _precompute_adjacent(self):
        self._adj = {}
        if self.mines_set is None:
            return
        for r in range(self.rows):
            for c in range(self.cols):
                self._adj[(r, c)] = sum(
                    1 for nr, nc in self._neighbors(r, c)
                    if (nr, nc) in self.mines_set
                )

    def _place_mines_avoiding(self, first_r: int, first_c: int):
        # Tránh ô được mở VÀ 8 ô xung quanh để lần mở đầu luôn mở ra một vùng
        forbidden = {(first_r, first_c)} | set(self._neighbors(first_r, first_c))
        all_cells = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        available = [cell for cell in all_cells if cell not in forbidden]

        if len(available) >= self.mines:
            chosen = self.rng.sample(available, self.mines)
        else:
            # Dự phòng cho trường hợp bàn quá nhỏ mà mìn quá nhiều
            backup = [cell for cell in all_cells if cell != (first_r, first_c)]
            chosen = self.rng.sample(backup, min(self.mines, len(backup)))

        self.mines_set = set(chosen)
        self._precompute_adjacent()

    @property
    def mines_left(self) -> int:
        return self.mines - len(self.flags)

    def toggle_flag(self, r: int, c: int):
        self._validate_coords(r, c)
        if self.state in ("won", "lost"):
            raise ValueError("Ván đã kết thúc.")
        if (r, c) in self.revealed:
            return
        if (r, c) in self.flags:
            self.flags.remove((r, c))
        else:
            self.flags.add((r, c))

    def _flood_reveal(self, start_r: int, start_c: int):
        if (start_r, start_c) in self.revealed or (start_r, start_c) in self.flags:
            return
        self.revealed.add((start_r, start_c))
        if self._adj.get((start_r, start_c), 0) != 0:
            return

        # Dùng hàng đợi queue (BFS) tránh đệ quy để không tràn stack với bàn lớn
        queue = deque([(start_r, start_c)])
        while queue:
            cr, cc = queue.popleft()
            for nr, nc in self._neighbors(cr, cc):
                if (nr, nc) in self.revealed or (nr, nc) in self.flags:
                    continue
                self.revealed.add((nr, nc))
                if self._adj.get((nr, nc), 0) == 0:
                    queue.append((nr, nc))

    def _check_win(self) -> bool:
        if self.state == "lost":
            return False
        if self.mines_set is None:
            return False
        total_safe = self.rows * self.cols - len(self.mines_set)
        if len(self.revealed) == total_safe:
            self.state = "won"
            return True
        return False

    def reveal(self, r: int, c: int):
        self._validate_coords(r, c)
        if self.state in ("won", "lost"):
            raise ValueError("Ván đã kết thúc.")
        if (r, c) in self.flags:
            return

        # Mở vào ô SỐ đã mở (chording)
        if (r, c) in self.revealed:
            adj = self._adj.get((r, c), 0)
            if adj > 0:
                flag_count = sum(1 for nr, nc in self._neighbors(r, c) if (nr, nc) in self.flags)
                if flag_count == adj:
                    to_open = [
                        (nr, nc) for nr, nc in self._neighbors(r, c)
                        if (nr, nc) not in self.flags and (nr, nc) not in self.revealed
                    ]
                    for nr, nc in to_open:
                        if (nr, nc) in self.revealed or (nr, nc) in self.flags:
                            continue
                        if (nr, nc) in self.mines_set:
                            self.state = "lost"
                            self.exploded = (nr, nc)
                            return
                        self._flood_reveal(nr, nc)
                        if self._check_win():
                            return
            return

        # Lần mở đầu tiên
        if self.mines_set is None:
            self._place_mines_avoiding(r, c)

        # Kiểm tra trúng mìn
        if (r, c) in self.mines_set:
            self.state = "lost"
            self.exploded = (r, c)
            return

        # Mở ô bình thường
        self._flood_reveal(r, c)
        if self._check_win():
            return
        self.state = "playing"

    def view(self) -> list[list[str | int]]:
        grid: list[list[str | int]] = []
        for r in range(self.rows):
            row: list[str | int] = []
            for c in range(self.cols):
                cell = (r, c)
                if self.state in ("ready", "playing"):
                    if cell in self.revealed:
                        row.append(self._adj.get(cell, 0))
                    elif cell in self.flags:
                        row.append("f")
                    else:
                        row.append("h")
                elif self.state == "lost":
                    if cell == self.exploded:
                        row.append("x")
                    elif cell in self.flags:
                        if self.mines_set and cell in self.mines_set:
                            row.append("f")
                        else:
                            row.append("w")  # cờ cắm sai vị trí
                    elif self.mines_set and cell in self.mines_set:
                        row.append("m")
                    elif cell in self.revealed:
                        row.append(self._adj.get(cell, 0))
                    else:
                        row.append("h")
                elif self.state == "won":
                    if cell in self.revealed:
                        row.append(self._adj.get(cell, 0))
                    elif cell in self.flags:
                        row.append("f")
                    elif self.mines_set and cell in self.mines_set:
                        row.append("m")
                    else:
                        row.append("h")
            grid.append(row)
        return grid


def self_test():
    print("Bắt đầu self-test Dò mìn (Minesweeper)...")

    # 1. Lần mở đầu không bao giờ trúng mìn (thử 200 lần ngẫu nhiên, cả 3 mức)
    print("  Test 1: Lần mở đầu không bao giờ trúng mìn (200 lần x 3 mức)...")
    for level_key, (_, rows, cols, mines) in MINES_LEVELS.items():
        for _ in range(200):
            g = MinesweeperGame(rows, cols, mines)
            r = random.randint(0, rows - 1)
            c = random.randint(0, cols - 1)
            g.reveal(r, c)
            assert g.state != "lost", f"Thua ngay nước đầu tại {level_key} ({r}, {c})!"
            # Kiểm tra ô đầu và các lân cận không chứa mìn
            assert (r, c) not in g.mines_set
            for nr, nc in g._neighbors(r, c):
                assert (nr, nc) not in g.mines_set
            # Ô đầu tiên phải mở ra ít nhất một vùng (số 0)
            assert g._adj.get((r, c)) == 0
            assert (r, c) in g.revealed
    print("  ✓ Test 1: Đạt.")

    # 2. Đếm số mìn lân cận đúng
    print("  Test 2: Đếm số mìn lân cận...")
    # Bàn 3x3 với mìn tại (0, 0)
    g = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    assert g._adj[(0, 1)] == 1
    assert g._adj[(1, 0)] == 1
    assert g._adj[(1, 1)] == 1
    assert g._adj[(2, 2)] == 0
    print("  ✓ Test 2: Đạt.")

    # 3. Loang mở đúng và cờ chặn mở
    print("  Test 3: Loang mở và cờ chặn...")
    # Bàn 4x4, mìn tại (3, 3). Mở tại (0, 0) sẽ loang.
    g = MinesweeperGame(4, 4, 1, mine_cells={(3, 3)})
    # Cắm cờ tại (1, 1) trước khi mở
    g.toggle_flag(1, 1)
    g.reveal(0, 0)
    # Ô (1, 1) có cờ nên không bị mở
    assert (1, 1) not in g.revealed
    assert (1, 1) in g.flags
    # Bỏ cờ và mở tiếp
    g.toggle_flag(1, 1)
    g.reveal(1, 1)
    assert (1, 1) in g.revealed
    print("  ✓ Test 3: Đạt.")

    # 4. Chording
    print("  Test 4: Chording...")
    # Bàn 3x3: mìn tại (0, 0) và (0, 2). Ô (1, 1) có số 2.
    g = MinesweeperGame(3, 3, 2, mine_cells={(0, 0), (0, 2)})
    g.reveal(1, 1)  # Ô số 2, không phải 0 nên chỉ mở đúng ô (1, 1)
    assert (1, 1) in g.revealed
    assert g._adj[(1, 1)] == 2
    assert len(g.revealed) == 1
    # Chưa cắm đủ 2 cờ, bấm vào (1, 1) không chording
    g.toggle_flag(0, 0)  # Cắm 1 cờ
    g.reveal(1, 1)
    assert len(g.revealed) == 1
    # Cắm nốt cờ thứ 2 vào (0, 2) -> đủ 2 cờ -> bấm (1, 1) chording mở hết 6 ô an toàn còn lại -> thắng
    g.toggle_flag(0, 2)
    g.reveal(1, 1)
    assert g.state == "won"
    assert len(g.revealed) == 7  # 7 ô an toàn đều đã mở
    print("  ✓ Test 4: Đạt.")

    # 5. Chording cắm cờ sai -> nổ mìn thua
    print("  Test 5: Chording cắm cờ sai dẫn đến thua...")
    g = MinesweeperGame(3, 3, 2, mine_cells={(0, 0), (0, 2)})
    g.reveal(1, 1)
    # Cắm cờ vào (0, 0) và cắm nhầm cờ vào (0, 1) thay vì (0, 2)
    g.toggle_flag(0, 0)
    g.toggle_flag(0, 1)
    g.reveal(1, 1)  # chording mở các ô lân cận chưa cắm cờ gồm ô mìn (0, 2) -> thua!
    assert g.state == "lost"
    assert g.exploded == (0, 2)
    v = g.view()
    assert v[0][2] == "x"  # mìn bị kích nổ
    assert v[0][1] == "w"  # cờ cắm sai vị trí
    assert v[0][0] == "f"  # cờ đúng
    print("  ✓ Test 5: Đạt.")

    # 6. Thắng / thua & view() không lộ mìn khi đang chơi
    print("  Test 6: Thắng/thua và view()...")
    g = MinesweeperGame(2, 2, 1, mine_cells={(0, 0)})
    v = g.view()
    assert all(cell == "h" for row in v for cell in row)
    g.reveal(1, 1)
    assert g.state == "playing"
    v = g.view()
    # Kiểm tra tuyệt đối không có "m", "x", "w" trong view khi đang chơi
    for r in range(2):
        for c in range(2):
            assert v[r][c] not in ("m", "x", "w")
    # Mở 2 ô an toàn còn lại -> thắng
    g.reveal(0, 1)
    g.reveal(1, 0)
    assert g.state == "won"
    v = g.view()
    assert v[0][0] == "m"  # mìn lộ ra khi thắng
    # Đã thắng mà bấm tiếp thì báo lỗi
    try:
        g.reveal(0, 0)
        assert False, "Phải báo lỗi khi đã thắng"
    except ValueError as e:
        assert "Ván đã kết thúc" in str(e)
    print("  ✓ Test 6: Đạt.")

    # 7. Bàn Khó (16x30, 99 mìn) loang toàn bộ không lỗi
    print("  Test 7: Bàn Khó loang toàn bộ không lỗi...")
    # Bàn không mìn để loang toàn bộ 480 ô
    g_hard = MinesweeperGame(16, 30, 0, mine_cells=set())
    g_hard.reveal(0, 0)
    assert len(g_hard.revealed) == 16 * 30
    assert g_hard.state == "won"
    print("  ✓ Test 7: Đạt.")

    # 8. Tọa độ rác báo lỗi tiếng Việt
    print("  Test 8: Tọa độ rác báo lỗi...")
    g = MinesweeperGame(9, 9, 10)
    for bad in [(-1, 0), (9, 0), (0, 9), ("a", 0), (0, None)]:
        try:
            g.reveal(*bad)
            assert False, f"Không báo lỗi với {bad}"
        except ValueError as e:
            assert "Tọa độ" in str(e)
    print("  ✓ Test 8: Đạt.")

    print("\n===> TẤT CẢ SELF-TEST DÒ MÌN ĐỀU ĐẠT! <===\n")


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        self_test()
    else:
        print("Dùng: python minesweeper_game.py --self-test")
