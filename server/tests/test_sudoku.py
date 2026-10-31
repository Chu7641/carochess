import time

from server.tests.conftest import account, login, user_id


def test_sudoku_requires_auth(client):
    assert client.get("/api/sudoku/state").status_code == 401
    assert client.post("/api/sudoku/new", json={"level": "easy"}).status_code == 401
    assert client.post("/api/sudoku/set", json={"r": 0, "c": 0, "v": 1}).status_code == 401
    assert client.post("/api/sudoku/hint", json={}).status_code == 401
    assert client.get("/api/sudoku/leaderboard").status_code == 401


def test_sudoku_new_invalid_level(client):
    h = account(client, "sdk_user1")
    res = client.post("/api/sudoku/new", json={"level": "master"}, headers=h)
    assert res.status_code == 400
    assert "Cấp độ không hợp lệ" in res.json()["detail"]
    for level in ([], {}, None, 1):  # list/dict/None không băm được: phải trả về 400, không phải 500
        assert client.post("/api/sudoku/new", json={"level": level}, headers=h).status_code == 400


def test_sudoku_response_no_solution_and_initial_grid(client):
    h = account(client, "sdk_user2")
    res = client.post("/api/sudoku/new", json={"level": "easy"}, headers=h)
    assert res.status_code == 200
    data = res.json()

    # Kiểm tra tuyệt đối không chứa lời giải trong phản hồi
    for key in data.keys():
        assert "solution" not in key.lower()

    # Grid ban đầu phải có ô trống (số 0)
    has_empty = any(cell == 0 for row in data["grid"] for cell in row)
    assert has_empty is True
    assert data["solved"] is False
    assert len(data["given"]) == 9 and len(data["given"][0]) == 9

    # Kiểm tra GET /api/sudoku/state cũng không chứa lời giải
    st = client.get("/api/sudoku/state", headers=h).json()
    for key in st.keys():
        assert "solution" not in key.lower()


def test_sudoku_cannot_modify_given_cells(client):
    h = account(client, "sdk_user3")
    res = client.post("/api/sudoku/new", json={"level": "easy"}, headers=h)
    data = res.json()

    # Tìm một ô cho sẵn
    given_r, given_c = None, None
    for r in range(9):
        for c in range(9):
            if data["given"][r][c]:
                given_r, given_c = r, c
                break
        if given_r is not None:
            break

    # Cố tình sửa ô cho sẵn -> 400
    res_bad = client.post("/api/sudoku/set", json={"r": given_r, "c": given_c, "v": 9}, headers=h)
    assert res_bad.status_code == 400
    assert "Không thể sửa" in res_bad.json()["detail"]


def test_sudoku_garbage_data(client):
    h = account(client, "sdk_garbage")
    client.post("/api/sudoku/new", json={"level": "easy"}, headers=h)

    # Chuỗi, số âm, vượt biên, float, bool, thiếu trường
    assert client.post("/api/sudoku/set", json={"r": "0", "c": 0, "v": 1}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": -1, "c": 0, "v": 1}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": 9, "c": 0, "v": 1}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": 0, "c": 0, "v": 10}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": 0, "c": 0, "v": -1}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": 0, "c": 0, "v": 1.5}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": 0, "c": 0, "v": True}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={"r": 0, "c": 0}, headers=h).status_code == 400
    assert client.post("/api/sudoku/set", json={}, headers=h).status_code == 400


def test_sudoku_predetermined_win_and_leaderboard(client):
    from sudoku_game import SudokuGame, _generate_full_solution
    from server import sudoku
    import random

    admin = login(client, "admin", "admin-secret")
    h = account(client, "sdk_winner")
    uid = user_id(client, admin, "sdk_winner")

    # Tạo một bảng Sudoku hoàn chỉnh, chừa trống đúng 1 ô (8, 8)
    solution = _generate_full_solution(random.Random(123))
    puzzle = [row[:] for row in solution]
    puzzle[8][8] = 0

    custom_game = SudokuGame(puzzle, solution)
    active = sudoku.new_game(uid, "easy", game=custom_game)
    active.start_mono = time.monotonic() - 4.5  # Giả lập đã chơi 4.5 giây

    # Điền đúng ô (8, 8) -> hoàn thành ván
    res = client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": solution[8][8]}, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert data["solved"] is True
    assert data["newRecord"] is True
    assert data["elapsedMs"] >= 4400

    # Kiểm tra bảng xếp hạng
    lb_res = client.get("/api/sudoku/leaderboard?level=easy", headers=h)
    assert lb_res.status_code == 200
    top = lb_res.json()["top"]
    assert len(top) == 1
    assert top[0]["username"] == "sdk_winner"
    assert top[0]["rank"] == 1
    assert top[0]["ms"] == data["elapsedMs"]

    me = lb_res.json()["me"]
    assert me["rank"] == 1
    assert me["ms"] == data["elapsedMs"]


def test_sudoku_win_twice_keeps_best_and_new_record_flag(client):
    from sudoku_game import SudokuGame, _generate_full_solution
    from server import sudoku
    import random

    admin = login(client, "admin", "admin-secret")
    h = account(client, "sdk_twice")
    uid = user_id(client, admin, "sdk_twice")

    solution = _generate_full_solution(random.Random(456))
    puzzle = [row[:] for row in solution]
    puzzle[8][8] = 0

    # Lần 1: giải xong trong 6000ms
    g1 = SudokuGame(puzzle, solution)
    act1 = sudoku.new_game(uid, "easy", game=g1)
    act1.start_mono = time.monotonic() - 6.0
    res1 = client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": solution[8][8]}, headers=h)
    assert res1.json()["solved"] is True
    assert res1.json()["newRecord"] is True

    # Lần 2: giải chậm hơn (12000ms) -> newRecord phải là False
    g2 = SudokuGame(puzzle, solution)
    act2 = sudoku.new_game(uid, "easy", game=g2)
    act2.start_mono = time.monotonic() - 12.0
    res2 = client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": solution[8][8]}, headers=h)
    assert res2.json()["solved"] is True
    assert res2.json()["newRecord"] is False

    # Leaderboard vẫn giữ thành tích tốt nhất (6000ms)
    lb = client.get("/api/sudoku/leaderboard?level=easy", headers=h).json()
    assert len(lb["top"]) == 1
    assert lb["top"][0]["ms"] == res1.json()["elapsedMs"]

    # Lần 3: giải nhanh hơn (2500ms) -> newRecord là True và leaderboard cập nhật
    g3 = SudokuGame(puzzle, solution)
    act3 = sudoku.new_game(uid, "easy", game=g3)
    act3.start_mono = time.monotonic() - 2.5
    res3 = client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": solution[8][8]}, headers=h)
    assert res3.json()["solved"] is True
    assert res3.json()["newRecord"] is True

    lb3 = client.get("/api/sudoku/leaderboard?level=easy", headers=h).json()
    assert len(lb3["top"]) == 1
    assert lb3["top"][0]["ms"] == res3.json()["elapsedMs"]


def test_sudoku_hint_adds_penalty_and_fills_cell(client):
    from sudoku_game import SudokuGame, _generate_full_solution
    from server import sudoku
    import random

    admin = login(client, "admin", "admin-secret")
    h = account(client, "sdk_hint")
    uid = user_id(client, admin, "sdk_hint")

    solution = _generate_full_solution(random.Random(789))
    puzzle = [row[:] for row in solution]
    puzzle[0][0] = 0
    puzzle[0][1] = 0

    g = SudokuGame(puzzle, solution)
    act = sudoku.new_game(uid, "easy", game=g)

    # Lấy gợi ý
    res = client.post("/api/sudoku/hint", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert data["hints"] == 1
    # Bị phạt 30 giây (30000 ms)
    assert data["elapsedMs"] >= 30000
    # Ô (0, 0) đã được điền đúng
    assert data["grid"][0][0] == solution[0][0]


def test_sudoku_solved_prevents_set_and_hint(client):
    from sudoku_game import SudokuGame, _generate_full_solution
    from server import sudoku
    import random

    admin = login(client, "admin", "admin-secret")
    h = account(client, "sdk_locked")
    uid = user_id(client, admin, "sdk_locked")

    solution = _generate_full_solution(random.Random(999))
    puzzle = [row[:] for row in solution]
    puzzle[8][8] = 0

    g = SudokuGame(puzzle, solution)
    sudoku.new_game(uid, "easy", game=g)
    client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": solution[8][8]}, headers=h)

    # Đã giải xong: set tiếp hoặc hint phải báo lỗi
    res_set = client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": 1}, headers=h)
    assert res_set.status_code == 400
    assert "kết thúc" in res_set.json()["detail"]

    res_hint = client.post("/api/sudoku/hint", headers=h)
    assert res_hint.status_code == 400
    assert "kết thúc" in res_hint.json()["detail"]


def test_sudoku_two_users_separate_games(client):
    h_a = account(client, "sdk_user_a")
    h_b = account(client, "sdk_user_b")

    res_a = client.post("/api/sudoku/new", json={"level": "easy"}, headers=h_a)
    res_b = client.post("/api/sudoku/new", json={"level": "hard"}, headers=h_b)

    assert res_a.json()["level"] == "easy"
    assert res_b.json()["level"] == "hard"

    st_a = client.get("/api/sudoku/state", headers=h_a).json()
    st_b = client.get("/api/sudoku/state", headers=h_b).json()

    assert st_a["level"] == "easy"
    assert st_b["level"] == "hard"


def test_sudoku_delete_user_clears_scores(client):
    from sudoku_game import SudokuGame, _generate_full_solution
    from server import sudoku
    import random

    admin = login(client, "admin", "admin-secret")
    h = account(client, "sdk_todelete")
    uid = user_id(client, admin, "sdk_todelete")

    solution = _generate_full_solution(random.Random(111))
    puzzle = [row[:] for row in solution]
    puzzle[8][8] = 0

    g = SudokuGame(puzzle, solution)
    sudoku.new_game(uid, "easy", game=g)
    client.post("/api/sudoku/set", json={"r": 8, "c": 8, "v": solution[8][8]}, headers=h)

    # Kiểm tra có điểm
    lb = client.get("/api/sudoku/leaderboard?level=easy", headers=h).json()
    assert len(lb["top"]) == 1

    # Admin xóa người dùng
    client.post(f"/api/admin/users/{uid}/delete", headers=admin)

    # Điểm trong leaderboard phải biến mất
    lb_after = client.get("/api/sudoku/leaderboard?level=easy", headers=admin).json()
    assert len(lb_after["top"]) == 0

