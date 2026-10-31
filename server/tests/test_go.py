import asyncio
import time

import pytest

from server.game import GameError
from server.tests.conftest import account, receive_until, start, state_where


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


def test_go_bot_replies(client):
    with client.websocket_connect("/ws", headers=account(client, "go_player")) as ws:
        ws.send_json({"type": "create", "game": "go", "mode": "bot", "level": 0, "size": 9})
        assert receive_until(ws, lambda m: m["type"] == "joined")["side"] == 1
        ws.send_json({"type": "move", "r": 4, "c": 4})
        room = state_where(ws, lambda r: r["moves"] == 2)
        assert room["current"] == 1 and not room["botThinking"]

