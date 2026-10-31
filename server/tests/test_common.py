from caro_game import X
from server.tests.conftest import account, receive_until, state_where


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

