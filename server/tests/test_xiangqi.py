import asyncio
import time

import pytest

from server.app import hub
from server.game import GameError
from server.tests.conftest import account, receive_until, start, state_where


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

