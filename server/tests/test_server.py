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
