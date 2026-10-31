"""Engine trò chơi Hải chiến (Battleship) 10x10."""

from __future__ import annotations

import random
import sys
import threading
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SIZE = 10

SHIPS = [
    ("Tàu sân bay", 5),
    ("Thiết giáp hạm", 4),
    ("Tuần dương hạm", 3),
    ("Tàu ngầm", 3),
    ("Khu trục hạm", 2),
]

BATTLESHIP_LEVELS = [
    ("Dễ", 0.6),
    ("Vừa", 0.6),
    ("Khó", 0.6),
]


def validate_fleet(ships: list[dict]) -> list[dict]:
    """Kiểm tra và chuẩn hóa hạm đội 5 tàu. Tàu kề nhau là hợp lệ; cấm chồng nhau hoặc ra ngoài bàn."""
    if not isinstance(ships, list) or len(ships) != 5:
        raise ValueError("Hạm đội phải có đúng 5 tàu.")

    lengths = []
    normalized: list[dict] = []
    occupied: set[tuple[int, int]] = set()

    for idx, s in enumerate(ships):
        if not isinstance(s, dict):
            raise ValueError("Dữ liệu tàu không hợp lệ.")
        if "r" not in s or "c" not in s or "len" not in s or "vertical" not in s:
            raise ValueError("Mỗi tàu phải có r, c, len và vertical.")

        r = s["r"]
        c = s["c"]
        length = s["len"]
        vertical = s["vertical"]

        if type(r) is not int or type(c) is not int or type(length) is not int or type(vertical) is not bool:
            raise ValueError("Tọa độ r, c, độ dài len phải là số nguyên và vertical là boolean.")

        if not (0 <= r < SIZE and 0 <= c < SIZE):
            raise ValueError(f"Tọa độ gốc ({r}, {c}) của tàu nằm ngoài bàn cờ 10x10.")

        lengths.append(length)

        if vertical:
            cells = [(r + i, c) for i in range(length)]
        else:
            cells = [(r, c + i) for i in range(length)]

        for cr, cc in cells:
            if not (0 <= cr < SIZE and 0 <= cc < SIZE):
                raise ValueError("Tàu vượt ra ngoài phạm vi bàn cờ 10x10.")
            if (cr, cc) in occupied:
                raise ValueError("Các tàu không được đặt chồng lên nhau.")
            occupied.add((cr, cc))

        ship_name = s.get("name")
        normalized.append({
            "name": ship_name,
            "r": r,
            "c": c,
            "len": length,
            "vertical": vertical,
            "cells": cells,
        })

    # Kiểm tra tập độ dài phải khớp [5, 4, 3, 3, 2]
    if sorted(lengths, reverse=True) != [5, 4, 3, 3, 2]:
        raise ValueError("Hạm đội phải gồm 5 tàu với các độ dài: 5, 4, 3, 3, 2.")

    # Gán tên chuẩn cho tàu nếu chưa có tên
    name_pool = {
        5: ["Tàu sân bay"],
        4: ["Thiết giáp hạm"],
        3: ["Tuần dương hạm", "Tàu ngầm"],
        2: ["Khu trục hạm"],
    }
    assigned_names: set[str] = set()
    for item in normalized:
        if item["name"] in assigned_names or not item["name"]:
            # Chọn tên chưa dùng trong pool
            for candidate in name_pool[item["len"]]:
                if candidate not in assigned_names:
                    item["name"] = candidate
                    break
        assigned_names.add(item["name"])

    return normalized


def random_fleet(rng: random.Random | None = None) -> list[dict]:
    """Sinh ngẫu nhiên một hạm đội 5 tàu hợp lệ trên bàn 10x10."""
    rng = rng or random.Random()
    while True:
        ships: list[dict] = []
        occupied: set[tuple[int, int]] = set()
        success = True

        for name, length in SHIPS:
            placed = False
            for _ in range(300):
                vertical = rng.choice([True, False])
                if vertical:
                    r = rng.randint(0, SIZE - length)
                    c = rng.randint(0, SIZE - 1)
                    cells = [(r + i, c) for i in range(length)]
                else:
                    r = rng.randint(0, SIZE - 1)
                    c = rng.randint(0, SIZE - length)
                    cells = [(r, c + i) for i in range(length)]

                if not any(cell in occupied for cell in cells):
                    occupied.update(cells)
                    ships.append({
                        "name": name,
                        "r": r,
                        "c": c,
                        "len": length,
                        "vertical": vertical,
                        "cells": cells,
                    })
                    placed = True
                    break

            if not placed:
                success = False
                break

        if success:
            return ships


class Fleet:
    """Quản lý các tàu và xử lý các phát bắn vào hạm đội."""

    def __init__(self, ships: list[dict]):
        self.ships = validate_fleet(ships)
        self.ship_by_cell: dict[tuple[int, int], dict] = {}
        for s in self.ships:
            for cell in s["cells"]:
                self.ship_by_cell[cell] = s

        self.hits: set[tuple[int, int]] = set()
        self.misses: set[tuple[int, int]] = set()
        self.sunk_ships: list[dict] = []

    def fire(self, r: int, c: int) -> dict:
        """Thực hiện bắn vào tọa độ (r, c)."""
        if type(r) is not int or type(c) is not int:
            raise ValueError("Tọa độ bắn phải là số nguyên.")
        if not (0 <= r < SIZE and 0 <= c < SIZE):
            raise ValueError(f"Tọa độ ({r}, {c}) nằm ngoài bàn cờ.")
        if (r, c) in self.hits or (r, c) in self.misses:
            raise ValueError(f"Ô ({r}, {c}) đã được bắn trước đó.")

        if (r, c) in self.ship_by_cell:
            self.hits.add((r, c))
            ship = self.ship_by_cell[(r, c)]
            if all(cell in self.hits for cell in ship["cells"]):
                self.sunk_ships.append(ship)
                return {
                    "result": "sunk",
                    "ship": ship["name"],
                    "cells": list(ship["cells"]),
                }
            return {"result": "hit"}
        else:
            self.misses.add((r, c))
            return {"result": "miss"}

    @property
    def all_sunk(self) -> bool:
        """Toàn bộ hạm đội đã bị đánh chìm."""
        return len(self.sunk_ships) == len(self.ships)

    @property
    def shots(self) -> list[list[str | None]]:
        """Lưới 10x10 ghi nhận kết quả các phát bắn: 'hit', 'miss' hoặc None."""
        grid: list[list[str | None]] = [[None] * SIZE for _ in range(SIZE)]
        for r, c in self.hits:
            grid[r][c] = "hit"
        for r, c in self.misses:
            grid[r][c] = "miss"
        return grid


class BattleshipBot:
    """Bot chơi hải chiến 3 mức độ: Dễ (ngẫu nhiên), Vừa (bàn cờ/hướng), Khó (bản đồ xác suất)."""

    def __init__(self, level: int | str = "Khó", rng: random.Random | None = None):
        if level == 0 or level in ("Dễ", "easy"):
            self.level = "Dễ"
        elif level == 1 or level in ("Vừa", "medium"):
            self.level = "Vừa"
        else:
            self.level = "Khó"
        self.rng = rng or random.Random()

    def choose(self, view: dict, cancel_event: threading.Event | None = None) -> tuple[int, int]:
        """Chọn tọa độ bắn tiếp theo dựa trên những gì bot đã thấy."""
        misses = set(view.get("misses", []))
        hits = set(view.get("hits", []))
        sunk_cells: set[tuple[int, int]] = set()
        for s in view.get("sunk_ships", []):
            for cell in s["cells"]:
                sunk_cells.add((cell[0], cell[1]))

        # Các ô trúng chưa thuộc về tàu đã chìm
        unsunk_hits = hits - sunk_cells
        remaining_lens = view.get("remaining_ships", [5, 4, 3, 3, 2])

        unshot = [
            (r, c)
            for r in range(SIZE)
            for c in range(SIZE)
            if (r, c) not in misses and (r, c) not in hits
        ]

        if not unshot:
            return (0, 0)

        # Mức DỄ: bắn ngẫu nhiên; nếu có ô trúng chưa chìm thì bắn lân cận
        if self.level == "Dễ":
            if unsunk_hits:
                cands = []
                for hr, hc in unsunk_hits:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = hr + dr, hc + dc
                        if (nr, nc) in unshot:
                            cands.append((nr, nc))
                if cands:
                    return self.rng.choice(cands)
            return self.rng.choice(unshot)

        # Mức VỪA: săn theo ô chẵn (checkerboard) + dò theo hướng khi trúng
        if self.level == "Vừa":
            if unsunk_hits:
                if len(unsunk_hits) >= 2:
                    rows = {r for r, c in unsunk_hits}
                    cols = {c for r, c in unsunk_hits}
                    line_cands = []
                    if len(rows) == 1:
                        # Thẳng hàng ngang
                        r = next(iter(rows))
                        min_c = min(c for _, c in unsunk_hits)
                        max_c = max(c for _, c in unsunk_hits)
                        for nc in [min_c - 1, max_c + 1]:
                            if (r, nc) in unshot:
                                line_cands.append((r, nc))
                    elif len(cols) == 1:
                        # Thẳng hàng dọc
                        c = next(iter(cols))
                        min_r = min(r for r, _ in unsunk_hits)
                        max_r = max(r for r, _ in unsunk_hits)
                        for nr in [min_r - 1, max_r + 1]:
                            if (nr, c) in unshot:
                                line_cands.append((nr, c))
                    if line_cands:
                        return self.rng.choice(line_cands)

                # Dò quanh các ô unsunk_hits
                cands = []
                for hr, hc in unsunk_hits:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = hr + dr, hc + dc
                        if (nr, nc) in unshot:
                            cands.append((nr, nc))
                if cands:
                    return self.rng.choice(cands)

            # Săn theo ô bàn cờ (r + c chẵn)
            parity_cands = [(r, c) for r, c in unshot if (r + c) % 2 == 0]
            if parity_cands:
                return self.rng.choice(parity_cands)
            return self.rng.choice(unshot)

        # Mức KHÓ: Bản đồ mật độ xác suất (Probability Density Map)
        prob: dict[tuple[int, int], int] = {cell: 0 for cell in unshot}
        has_unsunk = len(unsunk_hits) > 0

        for L in remaining_lens:
            # Ngang
            for r in range(SIZE):
                for c in range(SIZE - L + 1):
                    cells = [(r, c + i) for i in range(L)]
                    # Không được đè ô trượt hoặc ô tàu đã chìm
                    if any(cell in misses or cell in sunk_cells for cell in cells):
                        continue

                    hit_count = sum(1 for cell in cells if cell in unsunk_hits)
                    if has_unsunk:
                        if hit_count == 0:
                            continue
                        weight = 50 ** hit_count
                    else:
                        weight = 1

                    for cell in cells:
                        if cell in prob:
                            prob[cell] += weight

            # Dọc
            for c in range(SIZE):
                for r in range(SIZE - L + 1):
                    cells = [(r + i, c) for i in range(L)]
                    if any(cell in misses or cell in sunk_cells for cell in cells):
                        continue

                    hit_count = sum(1 for cell in cells if cell in unsunk_hits)
                    if has_unsunk:
                        if hit_count == 0:
                            continue
                        weight = 50 ** hit_count
                    else:
                        weight = 1

                    for cell in cells:
                        if cell in prob:
                            prob[cell] += weight

        max_val = max(prob.values()) if prob else -1
        if max_val > 0:
            best_cells = [cell for cell, val in prob.items() if val == max_val]
            return self.rng.choice(best_cells)

        # Phương án dự phòng khi không có cấu hình khớp unsunk_hits
        if has_unsunk:
            cands = []
            for hr, hc in unsunk_hits:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = hr + dr, hc + dc
                    if (nr, nc) in unshot:
                        cands.append((nr, nc))
            if cands:
                return self.rng.choice(cands)

        parity_cands = [(r, c) for r, c in unshot if (r + c) % 2 == 0]
        if parity_cands:
            return self.rng.choice(parity_cands)
        return self.rng.choice(unshot)


def random_clustered_fleet(rng: random.Random | None = None) -> list[dict]:
    """Tạo hạm đội ngẫu nhiên có các tàu kề sát nhau thành cụm ở vị trí ngẫu nhiên."""
    rng = rng or random.Random()
    for _ in range(50):
        start_r = rng.randint(0, 5)
        start_c = rng.randint(0, 5)
        occupied: set[tuple[int, int]] = set()
        ships: list[dict] = []
        possible = True
        for name, length in SHIPS:
            placed = False
            for _ in range(200):
                vertical = rng.choice([True, False])
                if vertical:
                    r = start_r + rng.randint(0, max(0, 5 - length))
                    c = start_c + rng.randint(0, 4)
                else:
                    r = start_r + rng.randint(0, 4)
                    c = start_c + rng.randint(0, max(0, 5 - length))
                if vertical:
                    cells = [(r + i, c) for i in range(length)]
                else:
                    cells = [(r, c + i) for i in range(length)]
                if all(0 <= cr < SIZE and 0 <= cc < SIZE for cr, cc in cells) and not any(cell in occupied for cell in cells):
                    occupied.update(cells)
                    ships.append({"name": name, "r": r, "c": c, "len": length, "vertical": vertical, "cells": cells})
                    placed = True
                    break
            if not placed:
                possible = False
                break
        if possible and len(ships) == 5:
            return ships
    return random_fleet(rng)


def self_test():
    print("Bắt đầu self-test Hải chiến (battleship_game.py)...")

    # 1. validate_fleet bắt đúng từng lỗi và chấp nhận tàu kề nhau
    print("  Test 1: validate_fleet kiểm tra lỗi và chấp nhận tàu kề nhau...")
    # Tàu kề nhau kề cạnh và kề chéo
    adjacent_fleet = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},  # (0, 0) -> (0, 4)
        {"r": 1, "c": 0, "len": 4, "vertical": False},  # (1, 0) -> (1, 3) ngay sát cạnh
        {"r": 2, "c": 0, "len": 3, "vertical": False},  # (2, 0) -> (2, 2)
        {"r": 3, "c": 0, "len": 3, "vertical": False},  # (3, 0) -> (3, 2)
        {"r": 4, "c": 0, "len": 2, "vertical": False},  # (4, 0) -> (4, 1)
    ]
    norm = validate_fleet(adjacent_fleet)
    assert len(norm) == 5, "Tàu kề nhau phải hợp lệ!"

    # Thiếu tàu
    try:
        validate_fleet(adjacent_fleet[:4])
        assert False, "Thiếu tàu mà không báo lỗi"
    except ValueError as exc:
        assert "đúng 5 tàu" in str(exc)

    # Chồng nhau
    overlap_fleet = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},
        {"r": 0, "c": 3, "len": 4, "vertical": True},  # chồng ở (0, 3)
        {"r": 2, "c": 0, "len": 3, "vertical": False},
        {"r": 3, "c": 0, "len": 3, "vertical": False},
        {"r": 4, "c": 0, "len": 2, "vertical": False},
    ]
    try:
        validate_fleet(overlap_fleet)
        assert False, "Chồng nhau mà không báo lỗi"
    except ValueError as exc:
        assert "chồng lên nhau" in str(exc)

    # Ra ngoài bàn cờ
    out_fleet = [
        {"r": 0, "c": 7, "len": 5, "vertical": False},  # c + 5 = 12 > 10
        {"r": 1, "c": 0, "len": 4, "vertical": False},
        {"r": 2, "c": 0, "len": 3, "vertical": False},
        {"r": 3, "c": 0, "len": 3, "vertical": False},
        {"r": 4, "c": 0, "len": 2, "vertical": False},
    ]
    try:
        validate_fleet(out_fleet)
        assert False, "Ra ngoài bàn mà không báo lỗi"
    except ValueError as exc:
        assert "ngoài" in str(exc)

    # Sai độ dài
    bad_len_fleet = [
        {"r": 0, "c": 0, "len": 6, "vertical": False},
        {"r": 1, "c": 0, "len": 4, "vertical": False},
        {"r": 2, "c": 0, "len": 3, "vertical": False},
        {"r": 3, "c": 0, "len": 3, "vertical": False},
        {"r": 4, "c": 0, "len": 2, "vertical": False},
    ]
    try:
        validate_fleet(bad_len_fleet)
        assert False, "Sai độ dài mà không báo lỗi"
    except ValueError as exc:
        assert "độ dài" in str(exc)

    # Dữ liệu rác
    for garbage in [None, "ships", [1, 2, 3], [{"r": "0", "c": 0, "len": 5, "vertical": False}] * 5]:
        try:
            validate_fleet(garbage)
            assert False, f"Không bắt lỗi dữ liệu rác: {garbage}"
        except (ValueError, TypeError):
            pass
    print("    ✓ Test 1: Đạt.")

    # 2. random_fleet hợp lệ 500 lần
    print("  Test 2: random_fleet sinh hợp lệ 500 lần...")
    rng = random.Random(100)
    for _ in range(500):
        f = random_fleet(rng)
        assert len(f) == 5
        validate_fleet(f)
    print("    ✓ Test 2: Đạt.")

    # 3. Fleet fire: miss/hit/sunk/all_sunk đúng
    print("  Test 3: Fleet fire: miss/hit/sunk/all_sunk...")
    fleet = Fleet(adjacent_fleet)
    # Bắn trượt
    res_miss = fleet.fire(9, 9)
    assert res_miss["result"] == "miss"
    assert (9, 9) in fleet.misses
    # Bắn trùng -> lỗi
    try:
        fleet.fire(9, 9)
        assert False, "Bắn trùng mà không báo lỗi"
    except ValueError as exc:
        assert "đã được bắn" in str(exc)

    # Bắn trúng ô đầu tàu 2 ô (4, 0)
    res_hit = fleet.fire(4, 0)
    assert res_hit["result"] == "hit"
    assert (4, 0) in fleet.hits

    # Bắn chìm ô còn lại (4, 1)
    res_sunk = fleet.fire(4, 1)
    assert res_sunk["result"] == "sunk"
    assert res_sunk["ship"] == "Khu trục hạm"
    assert set(res_sunk["cells"]) == {(4, 0), (4, 1)}
    assert len(fleet.sunk_ships) == 1
    assert not fleet.all_sunk

    # Bắn chìm các tàu còn lại
    for s in fleet.ships:
        for r, c in s["cells"]:
            if (r, c) not in fleet.hits:
                fleet.fire(r, c)
    assert fleet.all_sunk
    print("    ✓ Test 3: Đạt.")

    # 4. Mô phỏng 200 ván mỗi mức (kèm hạm đội xếp sát nhau thành cụm)
    print("  Test 4: Mô phỏng 200 ván mỗi mức...")
    sim_rng = random.Random(2026)
    results = {}

    for lvl in ["Dễ", "Vừa", "Khó"]:
        shots_list = []
        for i in range(200):
            # Nửa số ván dùng hạm đội ngẫu nhiên, nửa số ván dùng hạm đội kề sát nhau thành cụm
            if i % 2 == 0:
                fleet_ships = random_fleet(sim_rng)
            else:
                fleet_ships = random_clustered_fleet(sim_rng)
            test_fleet = Fleet(fleet_ships)
            bot = BattleshipBot(lvl, sim_rng)
            shots = 0

            while not test_fleet.all_sunk:
                shots += 1
                assert shots <= 100, f"Ván đấu vượt quá 100 phát bắn ở mức {lvl}!"
                view = {
                    "misses": list(test_fleet.misses),
                    "hits": list(test_fleet.hits),
                    "sunk_ships": [
                        {"name": s["name"], "len": s["len"], "cells": s["cells"]}
                        for s in test_fleet.sunk_ships
                    ],
                    "remaining_ships": [
                        s["len"] for s in test_fleet.ships if s not in test_fleet.sunk_ships
                    ],
                }
                r, c = bot.choose(view)
                # Kiểm tra bot không bao giờ bắn trùng hoặc ngoài bàn
                assert 0 <= r < SIZE and 0 <= c < SIZE, f"Bot bắn ra ngoài bàn: ({r}, {c})"
                assert (r, c) not in test_fleet.hits and (r, c) not in test_fleet.misses, f"Bot bắn trùng ô ({r}, {c})"
                test_fleet.fire(r, c)

            shots_list.append(shots)

        avg = sum(shots_list) / len(shots_list)
        max_shots = max(shots_list)
        results[lvl] = (avg, max_shots)
        print(f"    ✓ Mức {lvl}: trung bình {avg:.2f} phát (tối đa {max_shots} phát)")

    # Kiểm tra yêu cầu: Khó < Vừa < Dễ, Khó <= 50 phát, tối đa <= 100 phát
    assert results["Khó"][0] < results["Vừa"][0] < results["Dễ"][0], (
        f"Thứ tự sức mạnh không đạt: Khó ({results['Khó'][0]}) < Vừa ({results['Vừa'][0]}) < Dễ ({results['Dễ'][0]})"
    )
    assert results["Khó"][0] <= 50.0, f"Mức Khó trung bình {results['Khó'][0]} phát vượt quá 50 phát!"
    assert all(max_s <= 100 for _, max_s in results.values()), "Có ván vượt quá 100 phát!"
    print("    ✓ Test 4: Đạt tất cả yêu cầu về số phát bắn.")

    print("\n===> TẤT CẢ SELF-TEST HẢI CHIẾN ĐỀU ĐẠT! <===\n")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        print("Dùng: python battleship_game.py --self-test")
