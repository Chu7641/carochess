import time

from server.tests.conftest import account, login, user_id


def test_mines_requires_auth(client):
    assert client.get("/api/mines/state").status_code == 401
    assert client.post("/api/mines/new", json={"level": "easy"}).status_code == 401
    assert client.post("/api/mines/reveal", json={"r": 0, "c": 0}).status_code == 401
    assert client.post("/api/mines/flag", json={"r": 0, "c": 0}).status_code == 401
    assert client.get("/api/mines/leaderboard").status_code == 401


def test_mines_new_invalid_level(client):
    h = account(client, "mn_user1")
    res = client.post("/api/mines/new", json={"level": "super_hard"}, headers=h)
    assert res.status_code == 400
    assert "Cấp độ không hợp lệ" in res.json()["detail"]
    for level in ([], {}, None, 1):  # không băm được / sai kiểu: phải là 400, không phải 500
        assert client.post("/api/mines/new", json={"level": level}, headers=h).status_code == 400


def test_mines_first_click_never_hits_mine_and_view_safe(client):
    h = account(client, "mn_user2")
    res = client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    assert res.status_code == 200
    assert res.json()["state"] == "ready"

    # Mở ô đầu tiên
    res = client.post("/api/mines/reveal", json={"r": 4, "c": 4}, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "playing"
    assert data["mines"] == 10
    # Trong lúc chơi, view không bao giờ chứa "m", "x", "w"
    for row in data["cells"]:
        for cell in row:
            assert cell not in ("m", "x", "w")


def test_mines_predetermined_win_and_leaderboard(client):
    from minesweeper_game import MinesweeperGame
    from server import mines

    admin = login(client, "admin", "admin-secret")
    h = account(client, "mn_winner")
    uid = user_id(client, admin, "mn_winner")

    # Tạo ván nhưng thay engine bằng bàn biết trước
    client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    custom_game = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    active = mines.new_game(uid, "easy", game=custom_game)
    active.start_mono = time.monotonic() - 3.5  # giả lập chơi 3.5 giây

    # Mở ô (2, 2) có số 0 -> loang mở toàn bộ 8 ô an toàn -> thắng
    res = client.post("/api/mines/reveal", json={"r": 2, "c": 2}, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "won"
    assert data["newRecord"] is True
    assert data["elapsedMs"] >= 3400

    # Kiểm tra điểm trong leaderboard
    lb_res = client.get("/api/mines/leaderboard?level=easy", headers=h)
    assert lb_res.status_code == 200
    top = lb_res.json()["top"]
    assert len(top) == 1
    assert top[0]["username"] == "mn_winner"
    assert top[0]["rank"] == 1
    assert top[0]["ms"] == data["elapsedMs"]

    me = lb_res.json()["me"]
    assert me["rank"] == 1
    assert me["ms"] == data["elapsedMs"]


def test_mines_win_twice_keeps_best_and_new_record_flag(client):
    from minesweeper_game import MinesweeperGame
    from server import mines

    admin = login(client, "admin", "admin-secret")
    h = account(client, "mn_twice")
    uid = user_id(client, admin, "mn_twice")

    # Lần 1: thắng với thời gian 5000ms
    client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    g1 = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    act1 = mines.new_game(uid, "easy", game=g1)
    act1.start_mono = time.monotonic() - 5.0
    res1 = client.post("/api/mines/reveal", json={"r": 2, "c": 2}, headers=h)
    assert res1.json()["state"] == "won"
    assert res1.json()["newRecord"] is True

    # Lần 2: thắng chậm hơn (10000ms) -> newRecord phải là False
    client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    g2 = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    act2 = mines.new_game(uid, "easy", game=g2)
    act2.start_mono = time.monotonic() - 10.0
    res2 = client.post("/api/mines/reveal", json={"r": 2, "c": 2}, headers=h)
    assert res2.json()["state"] == "won"
    assert res2.json()["newRecord"] is False

    # Leaderboard chỉ giữ 1 bản ghi thời gian tốt nhất của người đó
    lb = client.get("/api/mines/leaderboard?level=easy", headers=h).json()
    assert len(lb["top"]) == 1
    assert lb["top"][0]["ms"] == res1.json()["elapsedMs"]

    # Lần 3: thắng nhanh hơn (2000ms) -> newRecord phải là True và leaderboard cập nhật
    client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    g3 = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    act3 = mines.new_game(uid, "easy", game=g3)
    act3.start_mono = time.monotonic() - 2.0
    res3 = client.post("/api/mines/reveal", json={"r": 2, "c": 2}, headers=h)
    assert res3.json()["state"] == "won"
    assert res3.json()["newRecord"] is True

    lb3 = client.get("/api/mines/leaderboard?level=easy", headers=h).json()
    assert len(lb3["top"]) == 1
    assert lb3["top"][0]["ms"] == res3.json()["elapsedMs"]


def test_mines_loss_does_not_record_score_and_cannot_reveal(client):
    from minesweeper_game import MinesweeperGame
    from server import mines

    admin = login(client, "admin", "admin-secret")
    h = account(client, "mn_loser")
    uid = user_id(client, admin, "mn_loser")

    client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    g = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    mines.new_game(uid, "easy", game=g)

    # Bấm trúng mìn tại (0, 0) -> thua
    res = client.post("/api/mines/reveal", json={"r": 0, "c": 0}, headers=h)
    assert res.status_code == 200
    assert res.json()["state"] == "lost"
    assert res.json()["cells"][0][0] == "x"

    # Thua không lưu vào bảng xếp hạng
    lb = client.get("/api/mines/leaderboard?level=easy", headers=h).json()
    assert len(lb["top"]) == 0
    assert lb["me"] is None

    # Đã thua thì bấm tiếp phải báo lỗi
    res_next = client.post("/api/mines/reveal", json={"r": 1, "c": 1}, headers=h)
    assert res_next.status_code == 400
    assert "kết thúc" in res_next.json()["detail"]


def test_mines_two_users_separate_games(client):
    h_a = account(client, "mn_user_a")
    h_b = account(client, "mn_user_b")

    res_a = client.post("/api/mines/new", json={"level": "easy"}, headers=h_a)
    res_b = client.post("/api/mines/new", json={"level": "medium"}, headers=h_b)

    assert res_a.json()["level"] == "easy"
    assert res_b.json()["level"] == "medium"

    # Người A mở ô
    client.post("/api/mines/reveal", json={"r": 0, "c": 0}, headers=h_a)
    st_a = client.get("/api/mines/state", headers=h_a).json()
    st_b = client.get("/api/mines/state", headers=h_b).json()

    assert st_a["state"] == "playing"
    assert st_b["state"] == "ready"  # Người B không bị ảnh hưởng


def test_mines_delete_user_clears_scores(client):
    from minesweeper_game import MinesweeperGame
    from server import mines

    admin = login(client, "admin", "admin-secret")
    h = account(client, "mn_todelete")
    uid = user_id(client, admin, "mn_todelete")

    client.post("/api/mines/new", json={"level": "easy"}, headers=h)
    g = MinesweeperGame(3, 3, 1, mine_cells={(0, 0)})
    mines.new_game(uid, "easy", game=g)
    client.post("/api/mines/reveal", json={"r": 2, "c": 2}, headers=h)

    # Kiểm tra có điểm
    lb = client.get("/api/mines/leaderboard?level=easy", headers=h).json()
    assert len(lb["top"]) == 1

    # Admin xóa người dùng
    client.post(f"/api/admin/users/{uid}/delete", headers=admin)

    # Điểm trong leaderboard phải biến mất
    lb_after = client.get("/api/mines/leaderboard?level=easy", headers=admin).json()
    assert len(lb_after["top"]) == 0


def test_mines_garbage_coordinates(client):
    h = account(client, "mn_garbage")
    client.post("/api/mines/new", json={"level": "easy"}, headers=h)

    # Tọa độ chuỗi
    assert client.post("/api/mines/reveal", json={"r": "abc", "c": 0}, headers=h).status_code == 400
    # Tọa độ số âm
    assert client.post("/api/mines/reveal", json={"r": -1, "c": 0}, headers=h).status_code == 400
    # Tọa độ vượt quá bàn cờ
    assert client.post("/api/mines/reveal", json={"r": 100, "c": 0}, headers=h).status_code == 400
    # Thiếu tọa độ
    assert client.post("/api/mines/reveal", json={"r": 0}, headers=h).status_code == 400
    assert client.post("/api/mines/reveal", json={}, headers=h).status_code == 400
    # Tọa độ số thực
    assert client.post("/api/mines/reveal", json={"r": 1.5, "c": 0}, headers=h).status_code == 400

