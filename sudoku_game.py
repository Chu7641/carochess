"""Engine trò chơi Sudoku (9x9) sinh đề và kiểm tra luật chuẩn."""

from __future__ import annotations

import random
import sys
import time
from typing import Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SUDOKU_LEVELS: dict[str, tuple[str, int]] = {
    "easy": ("Dễ", 40),
    "medium": ("Vừa", 32),
    "hard": ("Khó", 26),
}


def count_solutions(grid: list[list[int]], limit: int = 2) -> int:
    """Đếm số lời giải của đề cờ (dừng sớm khi đạt limit)."""
    row_mask = [0] * 9
    col_mask = [0] * 9
    box_mask = [0] * 9
    empty: list[tuple[int, int]] = []

    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            b = (r // 3) * 3 + (c // 3)
            if v != 0:
                m = 1 << v
                if (row_mask[r] & m) or (col_mask[c] & m) or (box_mask[b] & m):
                    return 0
                row_mask[r] |= m
                col_mask[c] |= m
                box_mask[b] |= m
            else:
                empty.append((r, c))

    count = 0

    def search() -> bool:
        nonlocal count
        if not empty:
            count += 1
            return count >= limit

        best_idx = -1
        min_cands = 10
        best_avail = 0

        for i, (r, c) in enumerate(empty):
            b = (r // 3) * 3 + (c // 3)
            avail = 0x3FE & ~(row_mask[r] | col_mask[c] | box_mask[b])
            cnt = avail.bit_count()
            if cnt < min_cands:
                min_cands = cnt
                best_idx = i
                best_avail = avail
                if cnt <= 1:
                    break

        if min_cands == 0:
            return False

        r, c = empty[best_idx]
        last_rc = empty.pop()
        if best_idx < len(empty):
            empty[best_idx] = last_rc
        b = (r // 3) * 3 + (c // 3)

        for v in range(1, 10):
            m = 1 << v
            if best_avail & m:
                row_mask[r] |= m
                col_mask[c] |= m
                box_mask[b] |= m
                grid[r][c] = v

                if search():
                    grid[r][c] = 0
                    row_mask[r] &= ~m
                    col_mask[c] &= ~m
                    box_mask[b] &= ~m
                    if best_idx < len(empty):
                        empty.append(empty[best_idx])
                        empty[best_idx] = (r, c)
                    else:
                        empty.append((r, c))
                    return True

                grid[r][c] = 0
                row_mask[r] &= ~m
                col_mask[c] &= ~m
                box_mask[b] &= ~m

        if best_idx < len(empty):
            empty.append(empty[best_idx])
            empty[best_idx] = (r, c)
        else:
            empty.append((r, c))
        return False

    search()
    return count


def _solve_random(grid: list[list[int]], rng: random.Random) -> list[list[int]] | None:
    """Tìm một lời giải ngẫu nhiên đầy đủ cho lưới."""
    row_mask = [0] * 9
    col_mask = [0] * 9
    box_mask = [0] * 9
    empty: list[tuple[int, int]] = []

    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            b = (r // 3) * 3 + (c // 3)
            if v != 0:
                m = 1 << v
                row_mask[r] |= m
                col_mask[c] |= m
                box_mask[b] |= m
            else:
                empty.append((r, c))

    solution: list[list[int]] | None = None

    def search() -> bool:
        nonlocal solution
        if not empty:
            solution = [row[:] for row in grid]
            return True

        best_idx = -1
        min_cands = 10
        best_avail = 0

        for i, (r, c) in enumerate(empty):
            b = (r // 3) * 3 + (c // 3)
            avail = 0x3FE & ~(row_mask[r] | col_mask[c] | box_mask[b])
            cnt = avail.bit_count()
            if cnt < min_cands:
                min_cands = cnt
                best_idx = i
                best_avail = avail
                if cnt <= 1:
                    break

        if min_cands == 0:
            return False

        r, c = empty[best_idx]
        last_rc = empty.pop()
        if best_idx < len(empty):
            empty[best_idx] = last_rc
        b = (r // 3) * 3 + (c // 3)

        nums = [v for v in range(1, 10) if (best_avail & (1 << v))]
        rng.shuffle(nums)

        for v in nums:
            m = 1 << v
            row_mask[r] |= m
            col_mask[c] |= m
            box_mask[b] |= m
            grid[r][c] = v

            if search():
                return True

            grid[r][c] = 0
            row_mask[r] &= ~m
            col_mask[c] &= ~m
            box_mask[b] &= ~m

        if best_idx < len(empty):
            empty.append(empty[best_idx])
            empty[best_idx] = (r, c)
        else:
            empty.append((r, c))
        return False

    search()
    return solution


def _generate_full_solution(rng: random.Random) -> list[list[int]]:
    """Tạo bảng Sudoku đầy đủ ngẫu nhiên bằng cách điền 3 khối chéo trước rồi giải."""
    grid = [[0] * 9 for _ in range(9)]
    for box in (0, 4, 8):
        start_r = (box // 3) * 3
        start_c = (box % 3) * 3
        nums = list(range(1, 10))
        rng.shuffle(nums)
        idx = 0
        for r in range(start_r, start_r + 3):
            for c in range(start_c, start_c + 3):
                grid[r][c] = nums[idx]
                idx += 1
    full = _solve_random(grid, rng)
    if full is None:
        raise RuntimeError("Không thể tạo lời giải Sudoku đầy đủ.")
    return full


def generate(level: str | int, rng: random.Random | None = None) -> tuple[list[list[int]], list[list[int]]]:
    """Sinh một đề Sudoku có duy nhất một lời giải và đạt gần đúng số ô cho sẵn."""
    if isinstance(level, str):
        if level not in SUDOKU_LEVELS:
            raise ValueError("Cấp độ không hợp lệ.")
        _, target_clues = SUDOKU_LEVELS[level]
    elif type(level) is int:
        target_clues = level
    else:
        raise ValueError("Cấp độ không hợp lệ.")

    rng = rng or random.Random()
    solution = _generate_full_solution(rng)
    puzzle = [row[:] for row in solution]

    positions = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(positions)

    current_clues = 81
    for r, c in positions:
        val = puzzle[r][c]
        puzzle[r][c] = 0
        if count_solutions(puzzle, limit=2) == 1:
            current_clues -= 1
            if current_clues <= target_clues:
                break
        else:
            puzzle[r][c] = val

    return puzzle, solution


class SudokuGame:
    def __init__(self, puzzle: list[list[int]], solution: list[list[int]]):
        if len(puzzle) != 9 or any(len(row) != 9 for row in puzzle):
            raise ValueError("Kích thước đề Sudoku phải là 9x9.")
        if len(solution) != 9 or any(len(row) != 9 for row in solution):
            raise ValueError("Kích thước lời giải Sudoku phải là 9x9.")

        self.puzzle = [row[:] for row in puzzle]
        self.solution = [row[:] for row in solution]
        self.given: list[list[bool]] = [
            [puzzle[r][c] != 0 for c in range(9)] for r in range(9)
        ]
        self.grid: list[list[int]] = [row[:] for row in puzzle]

    def _validate_coords(self, r: int, c: int):
        if type(r) is not int or type(c) is not int:
            raise ValueError("Tọa độ phải là số nguyên.")
        if not (0 <= r < 9 and 0 <= c < 9):
            raise ValueError(f"Tọa độ ({r}, {c}) nằm ngoài bàn cờ.")

    def set_cell(self, r: int, c: int, v: int):
        self._validate_coords(r, c)
        if type(v) is not int:
            raise ValueError("Giá trị phải là số nguyên.")
        if not (0 <= v <= 9):
            raise ValueError("Giá trị phải nằm trong khoảng từ 0 đến 9.")
        if self.solved:
            raise ValueError("Ván đã kết thúc.")
        if self.given[r][c]:
            raise ValueError("Không thể sửa ô cho sẵn của đề bài.")

        self.grid[r][c] = v

    def conflicts(self) -> list[tuple[int, int]]:
        """Trả về danh sách ô bị trùng lặp số theo luật hàng, cột hoặc khối 3x3."""
        conflict_set: set[tuple[int, int]] = set()

        # Kiểm tra trùng hàng
        for r in range(9):
            seen: dict[int, list[int]] = {}
            for c in range(9):
                v = self.grid[r][c]
                if v != 0:
                    seen.setdefault(v, []).append(c)
            for v, cols in seen.items():
                if len(cols) > 1:
                    for c in cols:
                        conflict_set.add((r, c))

        # Kiểm tra trùng cột
        for c in range(9):
            seen_col: dict[int, list[int]] = {}
            for r in range(9):
                v = self.grid[r][c]
                if v != 0:
                    seen_col.setdefault(v, []).append(r)
            for v, rows in seen_col.items():
                if len(rows) > 1:
                    for r in rows:
                        conflict_set.add((r, c))

        # Kiểm tra trùng khối 3x3
        for b in range(9):
            start_r = (b // 3) * 3
            start_c = (b % 3) * 3
            seen_box: dict[int, list[tuple[int, int]]] = {}
            for r in range(start_r, start_r + 3):
                for c in range(start_c, start_c + 3):
                    v = self.grid[r][c]
                    if v != 0:
                        seen_box.setdefault(v, []).append((r, c))
            for v, cells in seen_box.items():
                if len(cells) > 1:
                    conflict_set.update(cells)

        return sorted(list(conflict_set))

    @property
    def solved(self) -> bool:
        """Đã giải xong khi toàn bộ ô được điền và không có bất kỳ xung đột nào."""
        for r in range(9):
            for c in range(9):
                if self.grid[r][c] == 0:
                    return False
        return len(self.conflicts()) == 0

    def hint(self) -> tuple[int, int, int]:
        """Gợi ý: điền chính xác một ô trống hoặc ô đang điền sai theo lời giải."""
        if self.solved:
            raise ValueError("Ván đã kết thúc.")

        wrong: list[tuple[int, int]] = []
        empty: list[tuple[int, int]] = []

        for r in range(9):
            for c in range(9):
                if self.grid[r][c] != self.solution[r][c]:
                    if self.grid[r][c] != 0:
                        wrong.append((r, c))
                    else:
                        empty.append((r, c))

        if wrong:
            target_r, target_c = wrong[0]
        elif empty:
            target_r, target_c = empty[0]
        else:
            raise ValueError("Ván đã kết thúc.")

        v = self.solution[target_r][target_c]
        self.grid[target_r][target_c] = v
        return (target_r, target_c, v)


def self_test():
    print("Bắt đầu self-test Sudoku (sudoku_game.py)...")

    # 1. Sinh đề mỗi mức 10 lần với seed cố định
    print("  Test 1: Sinh đề 10 lần mỗi mức (seed cố định), kiểm tra duy nhất 1 lời giải & khớp solution...")
    test_rng = random.Random(2026)
    for lvl in ("easy", "medium", "hard"):
        _, target_clues = SUDOKU_LEVELS[lvl]
        t0 = time.time()
        for i in range(10):
            p, s = generate(lvl, test_rng)
            # Kiểm tra khớp solution
            assert count_solutions(s) == 1, "Lời giải không hợp lệ!"
            # Kiểm tra đề có đúng 1 lời giải
            assert count_solutions(p) == 1, f"Đề {lvl} #{i} không có đúng 1 lời giải!"
            # Đề phải là tập con của lời giải
            for r in range(9):
                for c in range(9):
                    if p[r][c] != 0:
                        assert p[r][c] == s[r][c], "Đề không khớp với lời giải!"
            clues = sum(1 for r in range(9) for c in range(9) if p[r][c] != 0)
            assert clues <= target_clues + 2, f"Số ô cho sẵn {clues} vượt quá xa so với {target_clues}"
        dt = time.time() - t0
        print(f"    ✓ Mức {lvl}: 10 lần sinh hoàn thành trong {dt:.3f}s (trung bình {dt/10*1000:.1f}ms/đề).")

    # 2. Đo riêng thời gian sinh mức Khó
    print("  Test 2: Đo thời gian sinh mức Khó...")
    t_start = time.time()
    p_hard, s_hard = generate("hard", random.Random())
    t_hard = time.time() - t_start
    print(f"    ✓ Sinh 1 đề Khó mất: {t_hard:.4f}s (< 3.0s)")
    assert t_hard < 3.0, f"Sinh đề Khó quá chậm: {t_hard}s!"

    # 3. Lớp SudokuGame: ô cho sẵn không sửa được
    print("  Test 3: Ô cho sẵn không sửa được...")
    game = SudokuGame(p_hard, s_hard)
    for r in range(9):
        for c in range(9):
            if game.given[r][c]:
                try:
                    game.set_cell(r, c, 5)
                    assert False, "Sửa ô cho sẵn mà không báo lỗi!"
                except ValueError as exc:
                    assert "Không thể sửa" in str(exc)
                break
        else:
            continue
        break
    print("    ✓ Test 3: Đạt.")

    # 4. Kiểm tra conflicts() theo hàng, cột, khối 3x3
    print("  Test 4: Conflicts() báo đúng ô trùng...")
    empty_board = [[0] * 9 for _ in range(9)]
    empty_solution = [[1] * 9 for _ in range(9)]
    g_conf = SudokuGame(empty_board, empty_solution)
    # Đặt trùng hàng
    g_conf.set_cell(0, 0, 5)
    g_conf.set_cell(0, 8, 5)
    c_list = g_conf.conflicts()
    assert (0, 0) in c_list and (0, 8) in c_list
    assert len(c_list) == 2
    # Xóa 1 ô
    g_conf.set_cell(0, 8, 0)
    assert len(g_conf.conflicts()) == 0
    # Đặt trùng khối 3x3
    g_conf.set_cell(1, 1, 5)
    c_box = g_conf.conflicts()
    assert (0, 0) in c_box and (1, 1) in c_box
    print("    ✓ Test 4: Đạt.")

    # 5. Giải xong -> solved và không cho set/hint tiếp
    print("  Test 5: Điền hết đúng -> solved và chặn set/hint...")
    # Tạo ván từ solution nhưng để trống đúng 1 ô
    p_one = [row[:] for row in s_hard]
    p_one[8][8] = 0
    g_one = SudokuGame(p_one, s_hard)
    assert not g_one.solved
    g_one.set_cell(8, 8, s_hard[8][8])
    assert g_one.solved
    try:
        g_one.set_cell(8, 8, 1)
        assert False, "Ván đã xong nhưng vẫn cho set!"
    except ValueError as exc:
        assert "Ván đã kết thúc" in str(exc)

    try:
        g_one.hint()
        assert False, "Ván đã xong nhưng vẫn cho hint!"
    except ValueError as exc:
        assert "Ván đã kết thúc" in str(exc)
    print("    ✓ Test 5: Đạt.")

    # 6. Hint: sửa ô sai hoặc điền ô trống
    print("  Test 6: Hint đúng...")
    p_hint = [row[:] for row in s_hard]
    p_hint[0][0] = 0
    p_hint[0][1] = 0
    g_hint = SudokuGame(p_hint, s_hard)
    # Điền sai vào ô (0, 0)
    wrong_val = 9 if s_hard[0][0] != 9 else 8
    g_hint.set_cell(0, 0, wrong_val)
    hr, hc, hv = g_hint.hint()
    assert (hr, hc) == (0, 0)
    assert hv == s_hard[0][0]
    assert g_hint.grid[0][0] == s_hard[0][0]
    # Gợi ý tiếp cho ô trống (0, 1)
    hr2, hc2, hv2 = g_hint.hint()
    assert (hr2, hc2) == (0, 1)
    assert hv2 == s_hard[0][1]
    assert g_hint.grid[0][1] == s_hard[0][1]
    print("    ✓ Test 6: Đạt.")

    # 7. Tọa độ và giá trị rác
    print("  Test 7: Tọa độ và giá trị rác báo lỗi...")
    g_bad = SudokuGame(p_hard, s_hard)
    for bad in [(-1, 0, 1), (9, 0, 1), (0, 9, 1), (0, 0, 10), (0, 0, -1), ("a", 0, 1), (0, "b", 1), (0, 0, "c")]:
        try:
            g_bad.set_cell(*bad)
            assert False, f"Không báo lỗi với {bad}"
        except ValueError as exc:
            assert "Tọa độ" in str(exc) or "Giá trị" in str(exc)
    print("    ✓ Test 7: Đạt.")

    print("\n===> TẤT CẢ SELF-TEST SUDOKU ĐỀU ĐẠT! <===\n")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        print("Dùng: python sudoku_game.py --self-test")

