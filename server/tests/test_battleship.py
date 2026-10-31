import asyncio

import pytest

from server.game import GameError
from server.tests.conftest import account, receive_until, state_where


def test_battleship_room_mode_and_settings():
    from server.battleship_room import BattleshipRoom
    with pytest.raises(GameError):
        BattleshipRoom("BS", "invalid")
    with pytest.raises(GameError):
        BattleshipRoom("BS", "bot", level=99)
    with pytest.raises(GameError):
        BattleshipRoom("BS", "bot", human_side=99)

    room_pvp = BattleshipRoom("BS_PVP", "pvp")
    assert room_pvp.mode == "pvp"
    assert room_pvp.bot_side is None

    room = BattleshipRoom("BS", "bot", level=1, human_side=1)
    snap = room.snapshot()
    assert snap["game"] == "battleship"
    assert snap["phase"] == "placing"
    assert snap["rows"] == 10 and snap["cols"] == 10
    assert not snap["started"]


def test_battleship_place_ships_validation():
    from server.battleship_room import BattleshipRoom
    room = BattleshipRoom("BS", "bot", level=0, human_side=1)

    # Thiếu tàu (< 5 tàu)
    with pytest.raises(GameError) as exc:
        room.place_ships(1, [{"r": 0, "c": 0, "len": 5, "vertical": False}])
    assert "đúng 5 tàu" in str(exc.value)

    # Tàu ra ngoài bàn
    bad_oob = [
        {"r": 0, "c": 8, "len": 5, "vertical": False},  # 8+5 = 13 > 10
        {"r": 1, "c": 0, "len": 4, "vertical": False},
        {"r": 2, "c": 0, "len": 3, "vertical": False},
        {"r": 3, "c": 0, "len": 3, "vertical": False},
        {"r": 4, "c": 0, "len": 2, "vertical": False},
    ]
    with pytest.raises(GameError) as exc:
        room.place_ships(1, bad_oob)
    assert "ngoài" in str(exc.value)

    # Tàu chồng lên nhau
    bad_overlap = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},
        {"r": 0, "c": 2, "len": 4, "vertical": False},  # đè lên (0, 2)
        {"r": 2, "c": 0, "len": 3, "vertical": False},
        {"r": 3, "c": 0, "len": 3, "vertical": False},
        {"r": 4, "c": 0, "len": 2, "vertical": False},
    ]
    with pytest.raises(GameError) as exc:
        room.place_ships(1, bad_overlap)
    assert "chồng" in str(exc.value)

    # Tàu nằm kề sát nhau (hợp lệ theo luật tự do!)
    adjacent_ships = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},
        {"r": 1, "c": 0, "len": 4, "vertical": False},
        {"r": 2, "c": 0, "len": 3, "vertical": False},
        {"r": 3, "c": 0, "len": 3, "vertical": False},
        {"r": 4, "c": 0, "len": 2, "vertical": False},
    ]
    room.place_ships(1, adjacent_ships)
    assert room.phase == "playing"
    assert room.started
    assert room.fleets[1] is not None


def test_battleship_bot_flow_over_websocket(client, monkeypatch):
    monkeypatch.setattr("battleship_game.BATTLESHIP_LEVELS", [("Dễ", 0.05), ("Vừa", 0.05), ("Khó", 0.05)])
    monkeypatch.setattr("server.battleship_bot.BATTLESHIP_LEVELS", [("Dễ", 0.05), ("Vừa", 0.05), ("Khó", 0.05)])
    with client.websocket_connect("/ws", headers=account(client, "bs_user1")) as ws:
        # Tạo phòng với người bắn trước (side 1)
        ws.send_json({"type": "create", "game": "battleship", "mode": "bot", "level": 0, "side": 1})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == 1

        # Xếp tàu ngẫu nhiên
        ws.send_json({"type": "place_ships", "random": True})
        room = state_where(ws, lambda r: r["phase"] == "playing")
        assert room["started"]
        assert room["current"] == 1
        assert room["myFleet"] is not None
        assert len(room["myFleet"]["ships"]) == 5
        # Không lộ tàu chưa chìm của bot!
        assert room["opponentBoard"]["revealedShips"] == []

        # Bắn 1 phát vào (0, 0)
        ws.send_json({"type": "fire", "r": 0, "c": 0})
        room = state_where(ws, lambda r: r["moves"] >= 1)
        assert len(room["opponentBoard"]["hits"]) + len(room["opponentBoard"]["misses"]) >= 1


def test_battleship_bot_shoots_first_when_side_2(client, monkeypatch):
    monkeypatch.setattr("battleship_game.BATTLESHIP_LEVELS", [("Dễ", 0.05), ("Vừa", 0.05), ("Khó", 0.05)])
    monkeypatch.setattr("server.battleship_bot.BATTLESHIP_LEVELS", [("Dễ", 0.05), ("Vừa", 0.05), ("Khó", 0.05)])
    with client.websocket_connect("/ws", headers=account(client, "bs_side2")) as ws:
        ws.send_json({"type": "create", "game": "battleship", "mode": "bot", "level": 0, "side": 2})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == 2

        # Người xếp tàu ngẫu nhiên
        ws.send_json({"type": "place_ships", "random": True})

        # Do người là side 2, bot là side 1 (đi trước). Bot sẽ tự khai hỏa nước đầu tiên!
        room = state_where(ws, lambda r: r["moves"] >= 1)
        assert room["moves"] >= 1


def test_battleship_anti_cheat_and_win(client):
    from server.battleship_room import BattleshipRoom
    from battleship_game import Fleet

    room = BattleshipRoom("BS_TEST", "bot", level=0, human_side=1)
    human_ships = [
        {"name": "Tàu sân bay", "len": 5, "r": 0, "c": 0, "vertical": False},
        {"name": "Thiết giáp hạm", "len": 4, "r": 1, "c": 0, "vertical": False},
        {"name": "Tuần dương hạm", "len": 3, "r": 2, "c": 0, "vertical": False},
        {"name": "Tàu ngầm", "len": 3, "r": 3, "c": 0, "vertical": False},
        {"name": "Khu trục hạm", "len": 2, "r": 4, "c": 0, "vertical": False},
    ]
    bot_ships = [
        {"name": "Tàu sân bay", "len": 5, "r": 5, "c": 0, "vertical": False},
        {"name": "Thiết giáp hạm", "len": 4, "r": 6, "c": 0, "vertical": False},
        {"name": "Tuần dương hạm", "len": 3, "r": 7, "c": 0, "vertical": False},
        {"name": "Tàu ngầm", "len": 3, "r": 8, "c": 0, "vertical": False},
        {"name": "Khu trục hạm", "len": 2, "r": 9, "c": 0, "vertical": False},
    ]
    room.fleets[1] = Fleet(human_ships)
    room.fleets[2] = Fleet(bot_ships)
    room.take_seat("Human", "user_token", prefer=1)
    room.phase = "playing"
    room.started = True
    room.current = 1

    # Kiểm tra anti-cheat snapshot:
    snap = room.snapshot("user_token")
    # Tàu đối thủ chưa chìm KHÔNG ĐƯỢC xuất hiện
    assert snap["opponentBoard"]["revealedShips"] == []
    assert len(snap["opponentBoard"]["sunkShips"]) == 0

    # Bắn chìm Tàu sân bay của bot: (5, 0..4)
    for c in range(4):
        room.fire(1, 5, c)
        assert room.current == 1  # Bắn trúng được bắn tiếp!
    room.fire(1, 5, 4)  # Đánh chìm tàu sân bay

    snap = room.snapshot("user_token")
    assert len(snap["opponentBoard"]["sunkShips"]) == 1
    assert snap["opponentBoard"]["sunkShips"][0]["name"] == "Tàu sân bay"
    assert snap["opponentBoard"]["revealedShips"] == []  # Ván chưa kết thúc, vẫn chưa lộ toàn bộ tàu

    # Bắn chìm toàn bộ các tàu còn lại của bot
    for r, count in [(6, 4), (7, 3), (8, 3), (9, 2)]:
        for c in range(count):
            room.fire(1, r, c)

    assert room.winner == 1
    assert room.phase == "ended"
    final_snap = room.snapshot("user_token")
    # Khi đã thắng, toàn bộ vị trí tàu đối thủ mới được lộ ra
    assert len(final_snap["opponentBoard"]["revealedShips"]) == 5


def test_battleship_rejects_bad_requests(client):
    with client.websocket_connect("/ws", headers=account(client, "bs_err")) as ws:
        ws.send_json({"type": "create", "game": "battleship", "mode": "bot", "level": 0, "side": 1})
        receive_until(ws, lambda m: m["type"] == "joined")

        # Bắn khi chưa xếp tàu
        ws.send_json({"type": "fire", "r": 0, "c": 0})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "Chưa đến giai đoạn bắn tàu" in err

        # Lệnh move cờ caro gửi vào
        ws.send_json({"type": "move", "r": 0, "c": 0})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "fire" in err or "hải chiến" in err

        # Lệnh undo
        ws.send_json({"type": "undo"})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "không có đi lại" in err

        # Xếp tàu ngẫu nhiên để vào giai đoạn bắn
        ws.send_json({"type": "place_ships", "random": True})
        state_where(ws, lambda r: r["phase"] == "playing")

        # Tọa độ ngoài bàn
        ws.send_json({"type": "fire", "r": 15, "c": 0})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "không hợp lệ" in err

        # Tọa độ không phải số nguyên
        ws.send_json({"type": "fire", "r": "0", "c": 0})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "không hợp lệ" in err


def test_battleship_bot_survives_reset_while_thinking():
    from server.battleship_bot import BattleshipBotDriver
    from server.battleship_room import BattleshipRoom

    async def scenario():
        room = BattleshipRoom("BS_RESET", "bot", level=0, human_side=2)
        room.take_seat("An", "an", prefer=2)
        driver = BattleshipBotDriver(room, asyncio.get_running_loop(), lambda: None)
        try:
            for _ in range(4):
                # Bot cầm side 1 đi trước khi human xếp tàu xong
                room.place_ships(2, None)
                driver.sync()
                room.restart(2)
                driver.reset()
                assert not driver.failed
        finally:
            driver.close()

    asyncio.run(scenario())


def test_battleship_room_list_includes_game(client):
    h = account(client, "bs_lister")
    with client.websocket_connect("/ws", headers=h) as ws:
        ws.send_json({"type": "create", "game": "battleship", "mode": "bot", "level": 1, "side": 1})
        receive_until(ws, lambda m: m["type"] == "joined")

        res = client.get("/api/rooms", headers=h)
        assert res.status_code == 200
        rooms = res.json()
        assert any(r.get("game") == "battleship" for r in rooms)


def test_battleship_rejects_invalid_mode(client):
    with client.websocket_connect("/ws", headers=account(client, "bs_inv")) as ws:
        ws.send_json({"type": "create", "game": "battleship", "mode": "abc"})
        err = receive_until(ws, lambda m: m["type"] == "error")["message"]
        assert "Chế độ chơi không hợp lệ" in err


def test_battleship_pvp_placing_and_turns(client):
    an = account(client, "an_bspvp")
    binh = account(client, "binh_bspvp")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        # Bắn khi chưa xếp tàu -> lỗi
        a.send_json({"type": "fire", "r": 0, "c": 0})
        err = receive_until(a, lambda m: m["type"] == "error")["message"]
        assert "chưa đến giai đoạn bắn" in err.lower()

        # An xếp tàu
        a.send_json({"type": "place_ships", "random": True})
        st_b = state_where(b, lambda r: 1 in r.get("placed", []))
        # Đối thủ (Bình) không được nhìn thấy tàu của An
        assert st_b["phase"] == "placing"
        assert st_b["opponentBoard"]["hits"] == []
        assert "ships" not in st_b["opponentBoard"]

        # An thử xếp tàu lần nữa -> lỗi đã xếp
        a.send_json({"type": "place_ships", "random": True})
        err = receive_until(a, lambda m: m["type"] == "error")["message"]
        assert "đang chờ đối thủ" in err

        # Bình xếp tàu -> cả 2 đã xếp, ván bắt đầu
        b.send_json({"type": "place_ships", "random": True})
        st_a = state_where(a, lambda r: r["phase"] == "playing")
        assert st_a["started"] is True
        assert st_a["current"] == 1

        # Bình bắn sai lượt -> lỗi
        b.send_json({"type": "fire", "r": 0, "c": 0})
        err = receive_until(b, lambda m: m["type"] == "error")["message"]
        assert "Chưa đến lượt" in err

        # An bắn hợp lệ -> thành công
        a.send_json({"type": "fire", "r": 0, "c": 0})
        st_b2 = state_where(b, lambda r: r.get("myFleet") and len(r["myFleet"]["hits"]) + len(r["myFleet"]["misses"]) > 0)
        assert len(st_b2["myFleet"]["hits"]) + len(st_b2["myFleet"]["misses"]) == 1


def test_battleship_pvp_turns_and_hit_repeat(client):
    an = account(client, "an_repeat")
    binh = account(client, "binh_repeat")
    fleet = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},  # (0,0)..(0,4)
        {"r": 2, "c": 0, "len": 4, "vertical": False},  # (2,0)..(2,3)
        {"r": 4, "c": 0, "len": 3, "vertical": False},  # (4,0)..(4,2)
        {"r": 6, "c": 0, "len": 3, "vertical": False},  # (6,0)..(6,2)
        {"r": 8, "c": 0, "len": 2, "vertical": False},  # (8,0)..(8,1)
    ]
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        a.send_json({"type": "place_ships", "ships": fleet})
        b.send_json({"type": "place_ships", "ships": fleet})
        state_where(a, lambda r: r["phase"] == "playing")

        # An bắn trúng ô (0, 0) của Bình
        a.send_json({"type": "fire", "r": 0, "c": 0})
        st = state_where(a, lambda r: [0, 0] in r["opponentBoard"]["hits"])
        # Bắn trúng -> An giữ lượt
        assert st["current"] == 1

        # An bắn hụt vào ô (9, 9)
        a.send_json({"type": "fire", "r": 9, "c": 9})
        st = state_where(a, lambda r: [9, 9] in r["opponentBoard"]["misses"])
        # Bắn hụt -> chuyển lượt sang Bình (2)
        assert st["current"] == 2


def test_battleship_pvp_spectator(client):
    an = account(client, "an_bspec")
    binh = account(client, "binh_bspec")
    cuong = account(client, "cuong_bspec")
    fleet = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},
        {"r": 2, "c": 0, "len": 4, "vertical": False},
        {"r": 4, "c": 0, "len": 3, "vertical": False},
        {"r": 6, "c": 0, "len": 3, "vertical": False},
        {"r": 8, "c": 0, "len": 2, "vertical": False},
    ]
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b, \
            client.websocket_connect("/ws", headers=cuong) as c:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        # Cường vào xem
        c.send_json({"type": "join", "room": code})
        joined_c = receive_until(c, lambda m: m["type"] == "joined")
        assert joined_c["side"] is None

        # Cả 2 xếp tàu
        a.send_json({"type": "place_ships", "ships": fleet})
        b.send_json({"type": "place_ships", "ships": fleet})

        st_c = state_where(c, lambda r: r["phase"] == "playing")
        assert st_c["you"] is None
        assert "boards" in st_c
        # Chống gian lận: khán giả chưa thấy tàu chưa chìm
        assert st_c["boards"]["1"]["sunkShips"] == []
        assert "ships" not in st_c["boards"]["1"]
        assert "ships" not in st_c["boards"]["2"]

        # Khán giả bắn -> bị lỗi
        c.send_json({"type": "fire", "r": 0, "c": 0})
        err = receive_until(c, lambda m: m["type"] == "error")["message"]
        assert "đang xem" in err or "khán giả" in err

        # An bắn trúng -> Cường nhận được cập nhật
        a.send_json({"type": "fire", "r": 0, "c": 0})
        st_c2 = state_where(c, lambda r: [0, 0] in r["boards"]["2"]["hits"])
        assert [0, 0] in st_c2["boards"]["2"]["hits"]


def test_battleship_pvp_win_and_elo(client):
    an = account(client, "an_bselo")
    binh = account(client, "binh_bselo")
    fleet = [
        {"r": 0, "c": 0, "len": 5, "vertical": False},  # (0,0)..(0,4)
        {"r": 2, "c": 0, "len": 4, "vertical": False},  # (2,0)..(2,3)
        {"r": 4, "c": 0, "len": 3, "vertical": False},  # (4,0)..(4,2)
        {"r": 6, "c": 0, "len": 3, "vertical": False},  # (6,0)..(6,2)
        {"r": 8, "c": 0, "len": 2, "vertical": False},  # (8,0)..(8,1)
    ]
    target_cells = [
        (0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
        (2, 0), (2, 1), (2, 2), (2, 3),
        (4, 0), (4, 1), (4, 2),
        (6, 0), (6, 1), (6, 2),
        (8, 0), (8, 1),
    ]
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        a.send_json({"type": "place_ships", "ships": fleet})
        b.send_json({"type": "place_ships", "ships": fleet})
        state_where(a, lambda r: r["phase"] == "playing")

        # An bắn liên tiếp trúng hết 17 ô của Bình
        for r, c in target_cells:
            a.send_json({"type": "fire", "r": r, "c": c})

        st = state_where(a, lambda r: r["winner"] != 0)
        assert st["winner"] == 1
        assert "thắng" in st["notice"].lower()
        assert len(st["opponentBoard"]["sunkShips"]) == 5

        # Elo được cập nhật
        p1_delta = st["players"]["1"]["eloDelta"]
        p2_delta = st["players"]["2"]["eloDelta"]
        assert p1_delta is not None and p2_delta is not None
        assert p1_delta > 0 and p1_delta == -p2_delta


def test_battleship_pvp_forfeit_and_timeout(client, monkeypatch):
    an = account(client, "an_bsff")
    binh = account(client, "binh_bsff")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        # An xếp tàu trước, sau đó An rời phòng khi đang xếp tàu -> không bị tính thua, chỉ reset ghế
        a.send_json({"type": "place_ships", "random": True})
        state_where(b, lambda r: 1 in r.get("placed", []))
        a.send_json({"type": "leave"})
        st_b = state_where(b, lambda r: r["waiting"] is True)
        assert st_b["winner"] == 0
        assert 1 not in st_b.get("placed", [])

    # Bây giờ chơi ván mới: rời phòng khi đang bắn -> bị tính thua
    an2 = account(client, "an_bsff2")
    binh2 = account(client, "binh_bsff2")
    with client.websocket_connect("/ws", headers=an2) as a, \
            client.websocket_connect("/ws", headers=binh2) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        a.send_json({"type": "place_ships", "random": True})
        b.send_json({"type": "place_ships", "random": True})
        state_where(a, lambda r: r["phase"] == "playing")

        # An bắn 1 phát
        a.send_json({"type": "fire", "r": 0, "c": 0})
        state_where(b, lambda r: r.get("myFleet") and len(r["myFleet"]["hits"]) + len(r["myFleet"]["misses"]) > 0)

        # An rời phòng giữa ván -> bị tính thua và tính Elo
        a.send_json({"type": "leave"})
        st = state_where(b, lambda r: r["winner"] != 0)
        assert st["winner"] == 2
        assert "bị tính thua" in st["notice"]
        assert st["players"]["2"]["eloDelta"] > 0

    # Hết giờ lượt -> thua
    monkeypatch.setattr("server.game.TURN_SECONDS", 0.6)
    an3 = account(client, "an_bsto")
    binh3 = account(client, "binh_bsto")
    with client.websocket_connect("/ws", headers=an3) as a, \
            client.websocket_connect("/ws", headers=binh3) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp"})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        a.send_json({"type": "place_ships", "random": True})
        b.send_json({"type": "place_ships", "random": True})
        state_where(a, lambda r: r["phase"] == "playing")

        # An không bắn -> hết giờ sau 0.6s
        room = state_where(b, lambda r: r["winner"] != 0)
        assert room["winner"] == 2
        assert "hết thời gian" in room["notice"]


def test_battleship_pvp_restart_swaps_sides(client):
    an = account(client, "an_bsswap")
    binh = account(client, "binh_bsswap")
    with client.websocket_connect("/ws", headers=an) as a, \
            client.websocket_connect("/ws", headers=binh) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])

        a.send_json({"type": "place_ships", "random": True})
        b.send_json({"type": "place_ships", "random": True})
        state_where(a, lambda r: r["phase"] == "playing")

        a.send_json({"type": "fire", "r": 0, "c": 0})
        state_where(b, lambda r: r.get("myFleet") and len(r["myFleet"]["hits"]) + len(r["myFleet"]["misses"]) > 0)

        # Bấm ván mới sau khi đã có phát bắn -> đổi bên
        a.send_json({"type": "restart"})
        room_b = state_where(b, lambda r: r["phase"] == "placing" and not r["started"])
        assert room_b["you"] == 1  # Bình giờ là Bên 1
        room_a = state_where(a, lambda r: r["phase"] == "placing" and not r["started"])
        assert room_a["you"] == 2  # An giờ là Bên 2


def test_battleship_pvp_reconnect_keeps_seat(client):
    an = account(client, "an_bsreconn")
    with client.websocket_connect("/ws", headers=an) as a:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp", "side": 1})
        code = receive_until(a, lambda m: m["type"] == "joined")["room"]
        a.send_json({"type": "place_ships", "random": True})
        state_where(a, lambda r: 1 in r.get("placed", []))

    # An kết nối lại -> vẫn ở ghế 1 và đội tàu đã xếp vẫn còn
    with client.websocket_connect("/ws", headers=an) as a2:
        a2.send_json({"type": "join", "room": code})
        joined = receive_until(a2, lambda m: m["type"] == "joined")
        assert joined["side"] == 1
        st = state_where(a2, lambda r: r.get("phase") == "placing")
        assert 1 in st.get("placed", [])
        assert st.get("myFleet") is not None
        assert len(st["myFleet"]["ships"]) == 5

