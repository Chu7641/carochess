"""Chạy: python -m pytest server"""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from caro_game import EMPTY, O, X, CaroBot
from server.app import app, hub
from server.bot import BotDriver
from server.game import GameError, Room


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CARO_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")
    with TestClient(app) as test_client:
        yield test_client
    for code in list(hub.rooms):
        hub.remove(code)


def login(client, name, password):
    """Đăng nhập rồi trả header cookie; mỗi kết nối tự mang cookie của mình."""
    res = client.post("/api/login", json={"username": name, "password": password})
    assert res.status_code == 200, res.text
    client.cookies.clear()
    return {"cookie": f"session={res.cookies['session']}"}


def user_id(client, admin, name):
    return next(u["id"] for u in client.get("/api/admin/users", headers=admin).json()
                if u["username"] == name)


def account(client, name):
    """Đăng ký, admin duyệt, đăng nhập."""
    res = client.post("/api/register", json={"username": name, "password": "matkhau1"})
    assert res.status_code == 200, res.text
    admin = login(client, "admin", "admin-secret")
    client.post(f"/api/admin/users/{user_id(client, admin, name)}/approve", headers=admin)
    return login(client, name, "matkhau1")


def receive_until(ws, predicate, limit=200):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("Không nhận được tin nhắn mong đợi")


def state_where(ws, predicate):
    return receive_until(ws, lambda m: m["type"] == "state" and predicate(m["room"]))["room"]


def start(a, b):
    """Hai người cùng bấm Sẵn sàng; trả trạng thái phòng lúc ván bắt đầu."""
    a.send_json({"type": "ready"})
    b.send_json({"type": "ready"})
    state_where(b, lambda r: r["started"])
    return state_where(a, lambda r: r["started"])


# ---------- luật trong phòng ----------
def test_room_rejects_bad_moves():
    room = Room("TEST", "pvp")
    room.take_seat("A", "a")
    with pytest.raises(GameError):
        room.place(X, 7, 7)  # còn thiếu người thứ hai
    assert room.take_seat("A", "a") == X  # cùng tài khoản không chiếm thêm ghế
    room.take_seat("B", "b")
    assert room.take_seat("C", "c") is None  # người xem
    with pytest.raises(GameError):
        room.place(X, 7, 7)  # chưa ai bấm sẵn sàng
    room.toggle_ready(X)
    room.toggle_ready(O)
    room.place(X, 7, 7)
    for side, r, c in ((X, 7, 8), (O, 7, 7), (O, 99, 0), (O, True, 1), (None, 1, 1)):
        with pytest.raises(GameError):
            room.place(side, r, c)


def test_room_win_and_restart_swaps_sides():
    room = pvp_room()
    for n in range(4):
        room.place(X, 7, 3 + n)
        room.place(O, 9, 3 + n)
    room.place(X, 7, 7)
    assert room.winner == X and len(room.win_line) == 5
    with pytest.raises(GameError):
        room.place(O, 9, 7)
    room.restart(X)
    assert room.side_of("a") == O and room.history == [] and room.winner == EMPTY
    assert not room.started  # ván mới: phải sẵn sàng lại


def pvp_room():
    room = Room("TEST", "pvp")
    room.take_seat("A", "a")
    room.take_seat("B", "b")
    room.toggle_ready(X)
    room.toggle_ready(O)
    return room


def test_ready_toggle_and_seat_freed():
    room = Room("TEST", "pvp")
    room.take_seat("A", "a")
    with pytest.raises(GameError):
        room.toggle_ready(X)  # chưa đủ người
    room.take_seat("B", "b")
    room.toggle_ready(X)
    room.toggle_ready(X)  # bấm lại: hủy
    assert room.ready == set() and not room.started
    room.toggle_ready(O)
    with pytest.raises(GameError):
        room.toggle_ready(None)  # người xem
    room.toggle_ready(X)
    assert room.started and room.ready == set()
    with pytest.raises(GameError):
        room.toggle_ready(X)  # đã bắt đầu
    room.seats[O] = None
    room.seat_freed(O)  # rời khi chưa có nước nào: quay về chờ sẵn sàng
    assert not room.started
    assert Room("BOT", "bot").started  # đấu máy không cần sẵn sàng


def test_pvp_undo_needs_opponent_consent():
    room = pvp_room()
    room.place(X, 7, 7)
    room.place(O, 7, 8)
    with pytest.raises(GameError):
        room.respond(X, True)  # chưa có yêu cầu
    room.undo(X)  # X xin đi lại sau khi O đã đáp
    assert room.request == {"kind": "undo", "side": X} and len(room.history) == 2
    with pytest.raises(GameError):
        room.respond(X, True)  # không tự đồng ý yêu cầu của mình
    room.respond(O, False)
    assert room.request is None and len(room.history) == 2 and "B không đồng ý" in room.notice

    room.undo(X)
    room.respond(O, True)  # bỏ nước của O và nước của X
    assert room.history == [] and room.current == X

    room.place(X, 7, 7)
    room.undo(X)
    room.place(O, 8, 8)  # đánh tiếp = bỏ qua yêu cầu
    assert room.request is None
    with pytest.raises(GameError):
        room.undo(None)


def test_forfeit_only_counts_unfinished_pvp_games():
    room = pvp_room()
    room.forfeit(X, "bỏ ván")
    assert room.winner == EMPTY  # chưa có nước nào: không tính
    room.place(X, 7, 7)
    room.forfeit(None, "bỏ ván")
    assert room.winner == EMPTY  # người xem không làm ai thua
    room.forfeit(X, "bỏ ván giữa chừng")
    assert room.winner == O and room.notice == "A bỏ ván giữa chừng, bị tính thua."
    room.forfeit(O, "bỏ ván")
    assert room.winner == O  # ván đã xong: không đổi kết quả
    room.restart(X)  # đổi bên
    assert room.history == [] and room.side_of("a") == O
    with pytest.raises(GameError):
        room.undo(X)  # ván mới chưa có nước nào
    bot_room = Room("BOT", "bot")
    bot_room.take_seat("A", "a")
    bot_room.place(X, 7, 7)
    bot_room.forfeit(X, "bỏ ván")
    assert bot_room.winner == EMPTY  # đấu máy không tính thua


def test_bot_room_undo_removes_bot_replies():
    room = Room("TEST", "bot", human_side=X)
    room.take_seat("A", "a")
    room.place(X, 7, 7)
    room.place(O, 7, 8)
    room.place(X, 8, 8)
    room.undo(X)  # bot chưa đáp: chỉ bỏ nước của người
    assert len(room.history) == 2 and room.current == X
    room.undo(X)  # bỏ nước bot (7, 8) và nước người (7, 7)
    assert room.history == [] and room.current == X
    with pytest.raises(GameError):
        room.undo(X)


def test_bot_first_cannot_be_undone_alone():
    room = Room("TEST", "bot", human_side=O)
    room.take_seat("A", "a", prefer=O)
    room.place(X, 7, 7)
    with pytest.raises(GameError):
        room.undo(O)


def test_bot_replies_after_every_ponder_miss():
    """Đoán sai nước người: bot phải tìm lại, không được treo chờ luồng cũ."""
    async def wait_for(room, moves, seconds):
        stop = time.monotonic() + seconds
        while len(room.history) < moves and room.winner == EMPTY:
            assert time.monotonic() < stop, f"bot không đánh nước thứ {moves}"
            await asyncio.sleep(0.02)

    async def scenario():
        room = Room("TEST", "bot", human_side=X)
        room.take_seat("An", "an")
        driver = BotDriver(room, asyncio.get_running_loop(), lambda: None)
        # Độ sâu lớn: nghĩ trước chạy mãi tới khi bị hủy, giống mức Mạnh.
        driver.engine = CaroBot(depth=12, time_budget=0.2, move_limit=10)
        try:
            for n in range(8):
                if room.winner != EMPTY:
                    break
                if n:
                    await asyncio.sleep(0.15)  # bot đang nghĩ trước
                    guess = driver.job.predicted if driver.job else None
                    move = next((r, c) for r in range(3, 12) for c in range(3, 12)
                                if room.board[r][c] == EMPTY and (r, c) != guess)
                else:
                    move = (7, 7)
                room.place(X, *move)
                driver.sync()
                await wait_for(room, 2 * n + 2, 5)
        finally:
            driver.close()

    async def main():
        # Nhiều phòng cùng lúc tranh GIL: luồng cũ thoát chậm, lỗi treo mới lộ ra.
        await asyncio.gather(*(scenario() for _ in range(4)))

    asyncio.run(main())


# ---------- tài khoản ----------
def test_register_login_logout(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/rooms").status_code == 401
    for name, password in (("ab", "matkhau1"), ("có dấu", "matkhau1"), ("binh", "123")):
        res = client.post("/api/register", json={"username": name, "password": password})
        assert res.status_code == 400 and res.json()["detail"]
    account(client, "Binh")
    res = client.post("/api/register", json={"username": "binh", "password": "matkhau1"})
    assert res.json()["detail"] == "Tên đăng nhập đã có người dùng."

    res = client.post("/api/login", json={"username": "binh", "password": "sai-mat-khau"})
    assert res.status_code == 400
    res = client.post("/api/login", json={"username": "binh", "password": "matkhau1"})
    assert res.json() == {"id": 2, "username": "Binh", "isAdmin": False, "elo": 1000}
    assert client.get("/api/me").json()["username"] == "Binh"
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_change_own_password(client):
    phone = account(client, "binh")
    laptop = login(client, "binh", "matkhau1")
    change = lambda current, new: client.post(
        "/api/password", json={"current": current, "new": new}, headers=laptop)
    assert change("sai-mat-khau", "moi12345").json()["detail"] == "Mật khẩu hiện tại không đúng."
    assert change("matkhau1", "123").status_code == 400  # quá ngắn
    assert client.post("/api/password", json={"current": "matkhau1", "new": "moi12345"}).status_code == 401

    assert change("matkhau1", "moi12345").status_code == 200
    assert client.get("/api/me", headers=laptop).status_code == 200  # phiên đang dùng vẫn giữ
    assert client.get("/api/me", headers=phone).status_code == 401   # máy khác bị đăng xuất
    assert client.post("/api/login", json={"username": "binh", "password": "matkhau1"}).status_code == 400
    login(client, "binh", "moi12345")


def test_registration_needs_approval_and_admin_tools(client):
    for name in ("cho_duyet", "bi_tu_choi"):
        assert client.post("/api/register", json={"username": name, "password": "matkhau1"}).json() == {"pending": True}
    res = client.post("/api/login", json={"username": "cho_duyet", "password": "matkhau1"})
    assert res.json()["detail"] == "Tài khoản đang chờ admin phê duyệt."
    assert "session" not in res.cookies

    admin = login(client, "admin", "admin-secret")
    assert client.get("/api/me", headers=admin).json()["isAdmin"] is True
    users = {u["username"]: u for u in client.get("/api/admin/users", headers=admin).json()}
    assert not users["cho_duyet"]["approved"] and users["admin"]["approved"]
    wait_id, reject_id = users["cho_duyet"]["id"], users["bi_tu_choi"]["id"]

    act = lambda uid, action: client.post(f"/api/admin/users/{uid}/{action}", headers=admin)
    assert act(wait_id, "make-admin").status_code == 400  # chưa duyệt thì chưa nâng cấp được
    assert act(reject_id, "reject").status_code == 200
    assert client.post("/api/login", json={"username": "bi_tu_choi", "password": "matkhau1"}).status_code == 400
    assert act(wait_id, "approve").status_code == 200
    assert act(wait_id, "reject").status_code == 400  # đã duyệt thì không xóa bằng "từ chối"
    member = login(client, "cho_duyet", "matkhau1")

    # Người thường không vào được trang quản trị.
    assert client.get("/api/admin/users", headers=member).status_code == 403
    assert client.post(f"/api/admin/users/{wait_id}/make-admin", headers=member).status_code == 403

    new_password = act(wait_id, "reset-password").json()["password"]
    assert client.get("/api/me", headers=member).status_code == 401  # phiên cũ bị đăng xuất
    assert client.post("/api/login", json={"username": "cho_duyet", "password": "matkhau1"}).status_code == 400
    promoted = login(client, "cho_duyet", new_password)
    assert act(wait_id, "make-admin").status_code == 200
    assert client.get("/api/admin/users", headers=promoted).status_code == 200
    assert act(wait_id, "khong-co").status_code == 404

    admin_id = user_id(client, admin, "admin")
    assert act(admin_id, "delete").json()["detail"] == "Không thể tự xóa tài khoản của chính mình."
    assert act(wait_id, "delete").status_code == 200
    assert client.get("/api/me", headers=promoted).status_code == 401  # phiên bị xóa theo
    assert client.post("/api/login", json={"username": "cho_duyet", "password": new_password}).status_code == 400
    assert act(wait_id, "delete").status_code == 400  # đã xóa rồi


def test_websocket_requires_login(client):
    with client.websocket_connect("/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


# ---------- WebSocket ----------
def test_pvp_over_websocket_and_reconnect(client):
    an, binh = account(client, "anh"), account(client, "binh")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "mode": "pvp", "rows": 9, "cols": 9})
        joined = receive_until(a, lambda m: m["type"] == "joined")
        assert joined["side"] == X
        code = joined["room"]
        listed = client.get("/api/rooms", headers=an).json()
        assert [(r["code"], r["status"], r["players"]) for r in listed] == [(code, "waiting", ["anh"])]

        b.send_json({"type": "join", "room": code.lower()})
        assert receive_until(b, lambda m: m["type"] == "joined")["side"] == O
        state_where(a, lambda r: not r["waiting"])
        assert client.get("/api/rooms", headers=an).json()[0]["status"] == "playing"
        a.send_json({"type": "move", "r": 4, "c": 4})
        assert "Sẵn sàng" in receive_until(a, lambda m: m["type"] == "error")["message"]
        start(a, b)

        a.send_json({"type": "move", "r": 4, "c": 4})
        room = state_where(b, lambda r: r["moves"] == 1)
        assert room["board"][4][4] == X and room["current"] == O and room["you"] == O

        a.send_json({"type": "move", "r": 0, "c": 0})
        assert receive_until(a, lambda m: m["type"] == "error")["message"] == "Chưa đến lượt bạn."

        a.send_json({"type": "undo"})
        assert state_where(b, lambda r: r["request"] is not None)["request"] == {"kind": "undo", "side": X}
        b.send_json({"type": "respond", "accept": True})
        room = state_where(a, lambda r: r["moves"] == 0)
        assert room["request"] is None and room["current"] == X
        a.send_json({"type": "move", "r": 4, "c": 4})
        state_where(b, lambda r: r["moves"] == 1)

    # Tải lại trang (hoặc đổi máy): cùng tài khoản lấy lại đúng ghế.
    with client.websocket_connect("/ws", headers=binh) as again:
        again.send_json({"type": "join", "room": code})
        assert receive_until(again, lambda m: m["type"] == "joined")["side"] == O
        room = state_where(again, lambda r: True)
        assert room["players"][str(O)]["online"] and not room["players"][str(X)]["online"]


def test_elo_after_win_and_resign(client):
    an, binh = account(client, "anh"), account(client, "binh")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "mode": "pvp", "rows": 9, "cols": 9})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        room = state_where(a, lambda r: not r["waiting"])
        assert room["players"]["1"]["elo"] == room["players"]["2"]["elo"] == 1000
        start(a, b)

        for n in range(4):  # "anh" (X) thắng hàng ngang
            a.send_json({"type": "move", "r": 2, "c": n})
            state_where(b, lambda r, n=n: r["moves"] == 2 * n + 1)
            b.send_json({"type": "move", "r": 6, "c": n})
            state_where(a, lambda r, n=n: r["moves"] == 2 * n + 2)
        a.send_json({"type": "move", "r": 2, "c": 4})
        room = state_where(b, lambda r: r["winner"] == X)
        assert (room["players"]["1"]["elo"], room["players"]["1"]["eloDelta"]) == (1016, 16)
        assert (room["players"]["2"]["elo"], room["players"]["2"]["eloDelta"]) == (984, -16)

        # Ván mới (đổi bên): "binh" cầm X, đánh một nước rồi bấm "Ván mới" giữa ván.
        a.send_json({"type": "restart"})
        state_where(b, lambda r: r["moves"] == 0 and r["you"] == X)
        start(a, b)  # ván mới: sẵn sàng lại
        b.send_json({"type": "move", "r": 4, "c": 4})
        state_where(a, lambda r: r["moves"] == 1)
        b.send_json({"type": "restart"})
        room = state_where(a, lambda r: r["moves"] == 0)
        assert "binh bỏ ván giữa chừng, bị tính thua." == room["notice"]
        assert room["you"] == X  # đổi bên tiếp

    assert client.get("/api/me", headers=an).json()["elo"] > 1016
    assert client.get("/api/me", headers=binh).json()["elo"] < 984

    admin = login(client, "admin", "admin-secret")
    reset = client.post(f"/api/admin/users/{user_id(client, admin, 'binh')}/reset-elo", headers=admin)
    assert reset.status_code == 200 and client.get("/api/me", headers=binh).json()["elo"] == 1000
    assert client.post(f"/api/admin/users/{user_id(client, admin, 'anh')}/reset-elo",
                       headers=binh).status_code == 403  # chỉ admin


def test_leaving_frees_seat_and_player_can_come_back(client):
    an, binh = account(client, "anh"), account(client, "binh")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "mode": "pvp", "rows": 9, "cols": 9})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        start(a, b)
        a.send_json({"type": "move", "r": 4, "c": 4})
        state_where(b, lambda r: r["moves"] == 1)

        a.send_json({"type": "leave"})  # bấm "Rời phòng" giữa ván: thua
        room = state_where(b, lambda r: r["waiting"])
        assert room["players"][str(X)] is None and room["winner"] == O
        assert room["players"][str(O)]["elo"] == 1016
        assert "rời phòng, bị tính thua" in room["notice"]
        assert client.get("/api/rooms", headers=binh).json()[0]["status"] == "waiting"
        assert client.get("/api/me", headers=an).json()["elo"] == 984

        a.send_json({"type": "join", "room": code})  # quay lại ghế trống, rồi mở ván mới
        assert receive_until(a, lambda m: m["type"] == "joined")["side"] == X
        state_where(b, lambda r: not r["waiting"])
        b.send_json({"type": "restart"})
        room = state_where(a, lambda r: r["moves"] == 0)
        assert room["you"] == O and room["winner"] == EMPTY  # đổi bên sau mỗi ván


def test_turn_timeout_loses(client, monkeypatch):
    monkeypatch.setattr("server.game.TURN_SECONDS", 0.6)
    an, binh = account(client, "anh"), account(client, "binh")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "mode": "pvp", "rows": 9, "cols": 9})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        room = state_where(a, lambda r: not r["waiting"])
        assert room["turnLeft"] is None  # chưa sẵn sàng: đồng hồ chưa chạy
        room = start(a, b)
        assert 0 < room["turnLeft"] <= 0.6 and room["turnSeconds"] == 0.6
        a.send_json({"type": "move", "r": 4, "c": 4})
        state_where(b, lambda r: r["moves"] == 1)
        room = state_where(a, lambda r: r["winner"] != EMPTY)  # "binh" không đánh: hết giờ
        assert room["winner"] == X and room["turnLeft"] is None
        assert "hết thời gian" in room["notice"] and room["players"]["1"]["elo"] == 1016


def test_bot_replies_over_websocket(client):
    with client.websocket_connect("/ws", headers=account(client, "anh")) as ws:
        ws.send_json({"type": "create", "mode": "bot", "level": 0,
                      "side": X, "rows": 9, "cols": 9})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == X
        ws.send_json({"type": "move", "r": 4, "c": 4})
        room = state_where(ws, lambda r: r["moves"] == 2)
        assert room["current"] == X and not room["botThinking"]
        ws.send_json({"type": "undo"})
        room = state_where(ws, lambda r: r["moves"] == 0)
        assert room["current"] == X


def test_bot_moves_first_when_human_is_o(client):
    with client.websocket_connect("/ws", headers=account(client, "anh")) as ws:
        ws.send_json({"type": "create", "mode": "bot", "level": 0,
                      "side": O, "rows": 9, "cols": 9})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == O
        room = state_where(ws, lambda r: r["moves"] == 1)
        assert room["current"] == O


def test_largest_board(client):
    with client.websocket_connect("/ws", headers=account(client, "anh")) as ws:
        ws.send_json({"type": "create", "mode": "pvp", "rows": 51, "cols": 51})
        assert "Bàn cờ" in receive_until(ws, lambda m: m["type"] == "error")["message"]
        ws.send_json({"type": "create", "mode": "bot", "level": 0, "side": X,
                      "rows": 50, "cols": 50})
        receive_until(ws, lambda m: m["type"] == "joined")
        ws.send_json({"type": "move", "r": 49, "c": 0})  # góc bàn
        room = state_where(ws, lambda r: r["moves"] == 2)
        assert len(room["board"]) == 50 and len(room["board"][0]) == 50
        assert room["current"] == X


def test_unknown_room_and_bad_settings(client):
    with client.websocket_connect("/ws", headers=account(client, "anh")) as ws:
        ws.send_json({"type": "join", "room": "ZZZZ"})
        assert receive_until(ws, lambda m: m["type"] == "error")
        ws.send_json({"type": "create", "mode": "pvp", "rows": 100})
        assert "Bàn cờ" in receive_until(ws, lambda m: m["type"] == "error")["message"]


def test_go_pvp_pass_and_score(client):
    an = account(client, "an_go")
    binh = account(client, "binh_go")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "go", "mode": "pvp", "size": 9})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        start(a, b)

        # Đen đánh (0, 0)
        a.send_json({"type": "move", "r": 0, "c": 0})
        state_where(b, lambda r: r["moves"] == 1)

        # Trắng đánh (8, 8)
        b.send_json({"type": "move", "r": 8, "c": 8})
        state_where(a, lambda r: r["moves"] == 2)

        # Đen bỏ lượt
        a.send_json({"type": "pass"})
        state_where(b, lambda r: r["moves"] == 3 and r["winner"] == 0)

        # Trắng bỏ lượt -> Ván kết thúc do 2 lần pass liên tiếp
        b.send_json({"type": "pass"})
        room = state_where(a, lambda r: r["winner"] != 0)
        assert room["score"] is not None
        assert "black" in room["score"] and "white" in room["score"]
        assert "bỏ lượt" in room["notice"]


def test_go_bot_survives_reset_while_thinking():
    """Ván mới lúc bot cờ vây (cầm Đen, đi trước) đang tính: bot phải tính lại, không treo."""
    from go_game import WHITE
    from server.go_bot import GoBotDriver
    from server.go_room import GoRoom

    async def scenario():
        room = GoRoom("GO", "bot", size=19, human_side=WHITE)
        room.take_seat("An", "an", prefer=WHITE)
        driver = GoBotDriver(room, asyncio.get_running_loop(), lambda: None)
        try:
            for _ in range(4):
                driver.sync()           # bot bắt đầu tính nước đầu
                room.restart(WHITE)     # người bấm "Ván mới" ngay lúc đó
                driver.reset()
                stop = time.monotonic() + 10
                while not room.history:
                    assert time.monotonic() < stop, "bot cờ vây bị treo"
                    await asyncio.sleep(0.02)
                assert len(room.history) == 1  # đúng một nước, của ván mới
        finally:
            driver.close()

    asyncio.run(scenario())


def test_go_room_rejects_bad_komi():
    from server.go_room import GoRoom
    for komi in ("abc", "nan", "inf", 1000):
        with pytest.raises(GameError):
            GoRoom("GO", "pvp", size=9, komi=komi)
    assert GoRoom("GO", "pvp", size=9, komi="6.5").komi == 6.5


def test_caro_snapshot_names_its_game():
    assert Room("TEST", "pvp").snapshot()["game"] == "caro"


def test_go_bot_replies(client):
    with client.websocket_connect("/ws", headers=account(client, "go_player")) as ws:
        ws.send_json({"type": "create", "game": "go", "mode": "bot", "level": 0, "size": 9})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == 1
        ws.send_json({"type": "move", "r": 4, "c": 4})
        room = state_where(ws, lambda r: r["moves"] == 2)
        assert room["current"] == 1 and not room["botThinking"]


# ---------- Cờ tướng (Xiangqi) ----------
def test_xiangqi_room_mode_and_settings():
    from server.xiangqi_room import XiangqiRoom
    with pytest.raises(GameError):
        XiangqiRoom("XQ", "invalid")
    with pytest.raises(GameError):
        XiangqiRoom("XQ", "bot", level=99)
    with pytest.raises(GameError):
        XiangqiRoom("XQ", "bot", human_side=99)
    room = XiangqiRoom("XQ", "bot", level=0, human_side=1)
    assert room.snapshot()["game"] == "xiangqi"
    pvp = XiangqiRoom("XQ", "pvp")
    assert pvp.snapshot()["mode"] == "pvp" and not pvp.started


def test_xiangqi_bot_replies_over_websocket(client, monkeypatch):
    monkeypatch.setattr("xiangqi_game.XIANGQI_LEVELS", [("Dễ", 0.05), ("Vừa", 0.05), ("Khó", 0.05)])
    with client.websocket_connect("/ws", headers=account(client, "xq_red")) as ws:
        # Cầm Đỏ đi trước
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "bot", "level": 0, "side": 1})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == 1
        # Đi Pháo 2 bình 5: (7, 1) -> (7, 4)
        ws.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        room = state_where(ws, lambda r: r["moves"] == 2)
        assert room["current"] == 1 and not room["botThinking"]
        assert room["lastMove"] is not None

        # Hoàn tác
        ws.send_json({"type": "undo"})
        room = state_where(ws, lambda r: r["moves"] == 0)
        assert room["current"] == 1


def test_xiangqi_bot_moves_first_when_human_is_black(client, monkeypatch):
    monkeypatch.setattr("xiangqi_game.XIANGQI_LEVELS", [("Dễ", 0.05), ("Vừa", 0.05), ("Khó", 0.05)])
    with client.websocket_connect("/ws", headers=account(client, "xq_black")) as ws:
        # Cầm Đen (2) -> bot cầm Đỏ (1) tự đi nước đầu
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "bot", "level": 0, "side": 2})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == 2
        room = state_where(ws, lambda r: r["moves"] == 1)
        assert room["current"] == 2 and not room["botThinking"]


def test_xiangqi_rejects_bad_moves_and_bad_data(client):
    with client.websocket_connect("/ws", headers=account(client, "xq_err")) as ws:
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "bot", "level": 0, "side": 1})
        receive_until(ws, lambda m: m["type"] == "joined")

        # Nước sai luật (Xe nhảy chéo)
        ws.send_json({"type": "move_piece", "fr": 9, "fc": 0, "tr": 8, "tc": 1})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "Xe" in err or "không hợp lệ" in err

        # fr là chuỗi
        ws.send_json({"type": "move_piece", "fr": "7", "fc": 1, "tr": 7, "tc": 4})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "không hợp lệ" in err

        # Thiếu trường
        ws.send_json({"type": "move_piece", "fr": 7, "fc": 1})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "không hợp lệ" in err

        # Tin "move" kiểu caro gửi vào phòng cờ tướng
        ws.send_json({"type": "move", "r": 7, "c": 1})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "move_piece" in err or "cờ tướng" in err

        # Kết nối vẫn hoạt động bình thường sau lỗi
        ws.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        room = state_where(ws, lambda r: r["moves"] >= 1)
        assert room["moves"] >= 1


def test_xiangqi_rejects_invalid_mode(client):
    with client.websocket_connect("/ws", headers=account(client, "xq_inv")) as ws:
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "abc"})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "Chế độ chơi không hợp lệ" in err


def test_xiangqi_pvp_ready_and_turns(client):
    an = account(client, "an_xq")
    binh = account(client, "binh_xq")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        # Chưa sẵn sàng: đi bị lỗi
        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        err = receive_until(a, lambda m: m["type"] == "error")["message"]
        assert "Sẵn sàng" in err

        # Cả hai sẵn sàng -> ván bắt đầu
        room = start(a, b)
        assert room["started"] and room["current"] == 1

        # Đen đi sai lượt -> bị lỗi
        b.send_json({"type": "move_piece", "fr": 2, "fc": 1, "tr": 2, "tc": 4})
        err = receive_until(b, lambda m: m["type"] == "error")["message"]
        assert "Chưa đến lượt" in err

        # Đỏ đi hợp lệ -> thành công
        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        room = state_where(b, lambda r: r["moves"] == 1)
        assert room["current"] == 2 and room["lastMove"] == [7, 1, 7, 4]


def test_xiangqi_pvp_spectator(client):
    an = account(client, "an_spec")
    binh = account(client, "binh_spec")
    cuong = account(client, "cuong_spec")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b, \
            client.websocket_connect("/ws", headers=cuong) as c:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        start(a, b)

        # Cường vào phòng -> người xem (side = None)
        c.send_json({"type": "join", "room": code})
        assert receive_until(c, lambda m: m["type"] == "joined")["side"] is None

        # Người xem gửi nước đi -> bị lỗi
        c.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        err = receive_until(c, lambda m: m["type"] == "error")["message"]
        assert "đang xem" in err

        # Khi người chơi đi cờ, người xem vẫn nhận được state
        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        st = state_where(c, lambda r: r["moves"] == 1)
        assert st["moves"] == 1 and st["current"] == 2


def test_xiangqi_pvp_undo(client):
    an = account(client, "an_undo")
    binh = account(client, "binh_undo")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        start(a, b)

        # Đỏ đi (7, 1) -> (7, 4), Đen đi (2, 7) -> (2, 4)
        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        state_where(b, lambda r: r["moves"] == 1)
        b.send_json({"type": "move_piece", "fr": 2, "fc": 7, "tr": 2, "tc": 4})
        state_where(a, lambda r: r["moves"] == 2)

        # Đỏ xin đi lại
        a.send_json({"type": "undo"})
        req_room = state_where(b, lambda r: r["request"] is not None)
        assert req_room["request"]["kind"] == "undo" and req_room["request"]["side"] == 1

        # Đen từ chối -> bàn giữ nguyên 2 nước
        b.send_json({"type": "respond", "accept": False})
        room = state_where(a, lambda r: r["request"] is None)
        assert room["moves"] == 2 and "không đồng ý" in room["notice"]

        # Đỏ xin đi lại lần nữa
        a.send_json({"type": "undo"})
        state_where(b, lambda r: r["request"] is not None)

        # Đen đồng ý -> hoàn lại 2 nước (về trước nước của Đỏ)
        b.send_json({"type": "respond", "accept": True})
        room = state_where(a, lambda r: r["moves"] == 0)
        assert room["moves"] == 0 and room["current"] == 1


def test_xiangqi_pvp_checkmate_and_elo(client):
    from xiangqi_game import XiangqiBoard
    an = account(client, "an_elo")
    binh = account(client, "binh_elo")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        start(a, b)

        room = hub.rooms[code]
        # Dựng thế sắp chiếu bí: Xe Đỏ ở (9, 0), đi (0, 0) chiếu bí
        room.engine = XiangqiBoard("3ka4/3r5/9/9/9/9/9/9/9/R4K3 w")
        room.board = [row[:] for row in room.engine.board]

        a.send_json({"type": "move_piece", "fr": 9, "fc": 0, "tr": 0, "tc": 0})
        st = state_where(a, lambda r: r["winner"] != 0)
        assert st["winner"] == 1
        assert "chiếu bí" in st["notice"]

        p1_delta = st["players"]["1"]["eloDelta"]
        p2_delta = st["players"]["2"]["eloDelta"]
        assert p1_delta is not None and p2_delta is not None
        assert p1_delta > 0 and p1_delta == -p2_delta


def test_xiangqi_pvp_forfeit_and_timeout(client, monkeypatch):
    an = account(client, "an_ff")
    binh = account(client, "binh_ff")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        start(a, b)

        # An đi 1 nước
        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        state_where(b, lambda r: r["moves"] == 1)

        # An rời phòng giữa ván -> bị tính thua và mất elo
        a.send_json({"type": "leave"})
        room = state_where(b, lambda r: r["winner"] != 0)
        assert room["winner"] == 2
        assert "bị tính thua" in room["notice"]
        assert room["players"]["2"]["eloDelta"] > 0

    # Hết giờ lượt -> thua
    monkeypatch.setattr("server.game.TURN_SECONDS", 0.6)
    an2 = account(client, "an_to")
    binh2 = account(client, "binh_to")
    with client.websocket_connect("/ws", headers=an2) as a, \
            client.websocket_connect("/ws", headers=binh2) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        start(a, b)

        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        state_where(b, lambda r: r["moves"] == 1)

        # Binh không đánh -> hết giờ sau 0.6s
        room = state_where(a, lambda r: r["winner"] != 0)
        assert room["winner"] == 1
        assert "hết thời gian" in room["notice"]


def test_xiangqi_pvp_restart_swaps_sides(client):
    an = account(client, "an_swap")
    binh = account(client, "binh_swap")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        start(a, b)

        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        state_where(b, lambda r: r["moves"] == 1)

        # Bấm ván mới sau khi đã có nước đi -> đổi bên
        a.send_json({"type": "restart"})
        room_b = state_where(b, lambda r: r["moves"] == 0 and not r["started"])
        assert room_b["you"] == 1  # Binh giờ là Đỏ (1)
        room_a = state_where(a, lambda r: r["moves"] == 0 and not r["started"])
        assert room_a["you"] == 2  # An giờ là Đen (2)


def test_xiangqi_pvp_reconnect_keeps_seat(client):
    an = account(client, "an_reconn")
    # An tạo phòng pvp cầm Đỏ
    with client.websocket_connect("/ws", headers=an) as a:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]

    # Kết nối lại -> vào đúng ghế Đỏ (1)
    with client.websocket_connect("/ws", headers=an) as a2:
        a2.send_json({"type": "join", "room": code})
        assert receive_until(a2, lambda m: m["type"] == "joined")["side"] == 1


def test_xiangqi_bot_survives_reset_while_thinking():
    """Ván mới / hoàn tác trong lúc bot đang nghĩ (bot cầm Đỏ, đi trước): không treo."""
    from xiangqi_game import BLACK
    from server.xiangqi_room import XiangqiRoom
    from server.xiangqi_bot import XiangqiBotDriver

    async def scenario():
        room = XiangqiRoom("XQ", "bot", level=0, human_side=BLACK)
        room.take_seat("An", "an", prefer=BLACK)
        driver = XiangqiBotDriver(room, asyncio.get_running_loop(), lambda: None)
        try:
            for _ in range(4):
                driver.sync()
                room.restart(BLACK)
                driver.reset()
                stop = time.monotonic() + 10
                while not room.history:
                    assert time.monotonic() < stop, "bot cờ tướng bị treo"
                    await asyncio.sleep(0.02)
                assert len(room.history) == 1
        finally:
            driver.close()

    asyncio.run(scenario())


def test_xiangqi_checkmate_results_in_win(client):
    from xiangqi_game import XiangqiBoard
    with client.websocket_connect("/ws", headers=account(client, "xq_mate")) as ws:
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "bot", "level": 0, "side": 1})
        code = receive_until(ws, lambda m: m["type"] == "joined")["room"]
        room = hub.rooms[code]
        # Dựng thế sắp chiếu bí: Xe Đỏ ở (9, 0), đi (0, 0) chiếu bí
        room.engine = XiangqiBoard("3ka4/3r5/9/9/9/9/9/9/9/R4K3 w")
        room.board = [row[:] for row in room.engine.board]

        ws.send_json({"type": "move_piece", "fr": 9, "fc": 0, "tr": 0, "tc": 0})
        st = state_where(ws, lambda r: r["winner"] != 0)
        assert st["winner"] == 1
        assert "chiếu bí" in st["notice"] and "thắng" in st["notice"]


def test_xiangqi_room_list_includes_game(client):
    with client.websocket_connect("/ws", headers=account(client, "xq_list")) as ws:
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "bot", "level": 0, "side": 1})
        code = receive_until(ws, lambda m: m["type"] == "joined")["room"]
        res = client.get("/api/rooms", headers=account(client, "xq_viewer"))
        assert res.status_code == 200
        rooms = res.json()
        xq_rooms = [r for r in rooms if r["code"] == code]
        assert len(xq_rooms) == 1
        assert xq_rooms[0]["game"] == "xiangqi"


# ---------- Dò mìn (Minesweeper) ----------
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


