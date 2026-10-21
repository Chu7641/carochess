"""Chạy: python -m pytest server"""

import pytest
from fastapi.testclient import TestClient

from caro_game import EMPTY, O, X
from server.app import app, hub
from server.game import GameError, Room


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    for code in list(hub.rooms):
        hub.remove(code)


def receive_until(ws, predicate, limit=200):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("Không nhận được tin nhắn mong đợi")


def state_where(ws, predicate):
    return receive_until(ws, lambda m: m["type"] == "state" and predicate(m["room"]))["room"]


# ---------- luật trong phòng ----------
def test_room_rejects_bad_moves():
    room = Room("TEST", "pvp")
    room.take_seat("A")
    with pytest.raises(GameError):
        room.place(X, 7, 7)  # còn thiếu người thứ hai
    room.take_seat("B")
    room.place(X, 7, 7)
    for side, r, c in ((X, 7, 8), (O, 7, 7), (O, 99, 0), (O, True, 1), (None, 1, 1)):
        with pytest.raises(GameError):
            room.place(side, r, c)


def test_room_win_and_restart_swaps_sides():
    room = Room("TEST", "pvp")
    _, token_a = room.take_seat("A")
    room.take_seat("B")
    for n in range(4):
        room.place(X, 7, 3 + n)
        room.place(O, 9, 3 + n)
    room.place(X, 7, 7)
    assert room.winner == X and len(room.win_line) == 5
    with pytest.raises(GameError):
        room.place(O, 9, 7)
    room.restart(X)
    assert room.side_of(token_a) == O and room.history == [] and room.winner == EMPTY


def test_bot_room_undo_removes_bot_replies():
    room = Room("TEST", "bot", human_side=X)
    room.take_seat("A")
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
    room.take_seat("A", prefer=O)
    room.place(X, 7, 7)
    with pytest.raises(GameError):
        room.undo(O)


# ---------- WebSocket ----------
def test_pvp_over_websocket_and_reconnect(client):
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        a.send_json({"type": "create", "mode": "pvp", "name": "An", "rows": 9, "cols": 9})
        joined = receive_until(a, lambda m: m["type"] == "joined")
        assert joined["side"] == X
        code = joined["room"]
        assert client.get("/api/rooms").json()[0]["code"] == code

        b.send_json({"type": "join", "room": code.lower(), "name": "Bình"})
        joined_b = receive_until(b, lambda m: m["type"] == "joined")
        assert joined_b["side"] == O
        state_where(a, lambda r: not r["waiting"])
        assert client.get("/api/rooms").json() == []

        a.send_json({"type": "move", "r": 4, "c": 4})
        room = state_where(b, lambda r: r["moves"] == 1)
        assert room["board"][4][4] == X and room["current"] == O and room["you"] == O

        a.send_json({"type": "move", "r": 0, "c": 0})
        assert receive_until(a, lambda m: m["type"] == "error")["message"] == "Chưa đến lượt bạn."

    # Tải lại trang: token cũ lấy lại đúng ghế.
    with client.websocket_connect("/ws") as again:
        again.send_json({"type": "join", "room": code, "name": "Bình",
                         "token": joined_b["token"]})
        assert receive_until(again, lambda m: m["type"] == "joined")["side"] == O
        room = state_where(again, lambda r: True)
        assert room["players"][str(O)]["online"] and not room["players"][str(X)]["online"]


def test_bot_replies_over_websocket(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "create", "mode": "bot", "name": "An", "level": 0,
                      "side": X, "rows": 9, "cols": 9})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == X
        ws.send_json({"type": "move", "r": 4, "c": 4})
        room = state_where(ws, lambda r: r["moves"] == 2)
        assert room["current"] == X and not room["botThinking"]
        ws.send_json({"type": "undo"})
        room = state_where(ws, lambda r: r["moves"] == 0)
        assert room["current"] == X


def test_bot_moves_first_when_human_is_o(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "create", "mode": "bot", "name": "An", "level": 0,
                      "side": O, "rows": 9, "cols": 9})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == O
        room = state_where(ws, lambda r: r["moves"] == 1)
        assert room["current"] == O


def test_unknown_room_and_bad_settings(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "room": "ZZZZ", "name": "An"})
        assert receive_until(ws, lambda m: m["type"] == "error")
        ws.send_json({"type": "create", "mode": "pvp", "rows": 100})
        assert "Bàn cờ" in receive_until(ws, lambda m: m["type"] == "error")["message"]
