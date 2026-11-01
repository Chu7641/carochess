"""Kiểm tra hợp đồng snapshot (snapshot contract) và ThreadedBotDriver."""

import asyncio
import threading
import time

from battleship_game import Fleet
from caro_game import O, X
from go_game import BLACK, WHITE
from server.app import hub
from server.battleship_bot import BattleshipBotDriver
from server.battleship_room import BattleshipRoom
from server.game import Room
from server.go_bot import GoBotDriver
from server.go_room import GoRoom
from server.tests.conftest import account, start, state_where
from server.xiangqi_bot import XiangqiBotDriver
from server.xiangqi_room import RED as XIANGQI_RED, XiangqiRoom
from xiangqi_game import BLACK as XIANGQI_BLACK

CARO_KEYS = {
    "board", "botThinking", "code", "cols", "current", "game", "lastMove",
    "level", "levelName", "mode", "moves", "notice", "players", "ready",
    "request", "rows", "started", "stats", "strict", "turnLeft", "turnSeconds",
    "waiting", "winLength", "winLine", "winner", "you",
}

GO_KEYS = {
    "board", "botThinking", "captured", "code", "cols", "current", "game",
    "komi", "lastAction", "lastMove", "level", "levelName", "mode", "moves",
    "notice", "players", "ready", "request", "rows", "score", "size", "started",
    "stats", "turnLeft", "turnSeconds", "waiting", "winLine", "winner", "you",
}

XIANGQI_KEYS = {
    "board", "botThinking", "code", "cols", "current", "game", "inCheck",
    "lastMove", "legalMoves", "level", "levelName", "mode", "moves", "notice",
    "players", "ready", "request", "rows", "started", "stats", "turnLeft",
    "turnSeconds", "waiting", "winLine", "winner", "you",
}

BATTLESHIP_KEYS = {
    "boards", "botThinking", "code", "cols", "current", "game", "lastShot",
    "level", "levelName", "mode", "moves", "myFleet", "notice", "opponentBoard",
    "phase", "placed", "players", "ready", "request", "rows", "shipsLeft",
    "started", "turnLeft", "turnSeconds", "waiting", "winLine", "winner", "you",
}


def test_snapshot_contract_caro(client):
    # Caro bot
    with client.websocket_connect("/ws", headers=account(client, "sc_caro_bot")) as ws:
        ws.send_json({"type": "create", "mode": "bot", "level": 0, "side": X, "rows": 9, "cols": 9})
        st = state_where(ws, lambda r: r["moves"] == 0)
        room = hub.rooms[st["code"]]
        assert set(room.snapshot("sc_caro_bot").keys()) == CARO_KEYS
        assert set(room.snapshot(None).keys()) == CARO_KEYS

        ws.send_json({"type": "move", "r": 4, "c": 4})
        state_where(ws, lambda r: r["moves"] >= 1)
        assert set(room.snapshot("sc_caro_bot").keys()) == CARO_KEYS
        assert set(room.snapshot(None).keys()) == CARO_KEYS

    # Caro pvp
    a_h = account(client, "sc_caro_a")
    b_h = account(client, "sc_caro_b")
    with client.websocket_connect("/ws", headers=a_h) as a, \
            client.websocket_connect("/ws", headers=b_h) as b:
        a.send_json({"type": "create", "mode": "pvp", "rows": 9, "cols": 9})
        code = state_where(a, lambda r: True)["code"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        start(a, b)
        a.send_json({"type": "move", "r": 4, "c": 4})
        state_where(b, lambda r: r["moves"] == 1)
        room = hub.rooms[code]
        assert set(room.snapshot("sc_caro_a").keys()) == CARO_KEYS
        assert set(room.snapshot(None).keys()) == CARO_KEYS


def test_snapshot_contract_go(client):
    # Go bot
    with client.websocket_connect("/ws", headers=account(client, "sc_go_bot")) as ws:
        ws.send_json({"type": "create", "game": "go", "mode": "bot", "level": 0, "size": 9})
        st = state_where(ws, lambda r: r["moves"] == 0)
        room = hub.rooms[st["code"]]
        assert set(room.snapshot("sc_go_bot").keys()) == GO_KEYS
        assert set(room.snapshot(None).keys()) == GO_KEYS

        ws.send_json({"type": "move", "r": 4, "c": 4})
        state_where(ws, lambda r: r["moves"] >= 1)
        assert set(room.snapshot("sc_go_bot").keys()) == GO_KEYS
        assert set(room.snapshot(None).keys()) == GO_KEYS

    # Go pvp
    a_h = account(client, "sc_go_a")
    b_h = account(client, "sc_go_b")
    with client.websocket_connect("/ws", headers=a_h) as a, \
            client.websocket_connect("/ws", headers=b_h) as b:
        a.send_json({"type": "create", "game": "go", "mode": "pvp", "size": 9})
        code = state_where(a, lambda r: True)["code"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        start(a, b)
        a.send_json({"type": "move", "r": 0, "c": 0})
        state_where(b, lambda r: r["moves"] == 1)
        room = hub.rooms[code]
        assert set(room.snapshot("sc_go_a").keys()) == GO_KEYS
        assert set(room.snapshot(None).keys()) == GO_KEYS


def test_snapshot_contract_xiangqi(client):
    # Xiangqi bot
    with client.websocket_connect("/ws", headers=account(client, "sc_xq_bot")) as ws:
        ws.send_json({"type": "create", "game": "xiangqi", "mode": "bot", "level": 0, "side": 1})
        st = state_where(ws, lambda r: r["moves"] == 0)
        room = hub.rooms[st["code"]]
        assert set(room.snapshot("sc_xq_bot").keys()) == XIANGQI_KEYS
        assert set(room.snapshot(None).keys()) == XIANGQI_KEYS

        ws.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        state_where(ws, lambda r: r["moves"] >= 1)
        assert set(room.snapshot("sc_xq_bot").keys()) == XIANGQI_KEYS
        assert set(room.snapshot(None).keys()) == XIANGQI_KEYS

    # Xiangqi pvp
    a_h = account(client, "sc_xq_a")
    b_h = account(client, "sc_xq_b")
    with client.websocket_connect("/ws", headers=a_h) as a, \
            client.websocket_connect("/ws", headers=b_h) as b:
        a.send_json({"type": "create", "game": "xiangqi", "mode": "pvp", "side": 1})
        code = state_where(a, lambda r: True)["code"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        start(a, b)
        a.send_json({"type": "move_piece", "fr": 7, "fc": 1, "tr": 7, "tc": 4})
        state_where(b, lambda r: r["moves"] == 1)
        room = hub.rooms[code]
        assert set(room.snapshot("sc_xq_a").keys()) == XIANGQI_KEYS
        assert set(room.snapshot(None).keys()) == XIANGQI_KEYS


def test_snapshot_contract_battleship(client):
    # Battleship bot
    with client.websocket_connect("/ws", headers=account(client, "sc_bs_bot")) as ws:
        ws.send_json({"type": "create", "game": "battleship", "mode": "bot", "level": 0, "side": 1})
        st = state_where(ws, lambda r: r["moves"] == 0)
        room = hub.rooms[st["code"]]
        assert set(room.snapshot("sc_bs_bot").keys()) == BATTLESHIP_KEYS
        assert set(room.snapshot(None).keys()) == BATTLESHIP_KEYS

        ws.send_json({"type": "place_ships", "random": True})
        state_where(ws, lambda r: r["phase"] == "playing")
        ws.send_json({"type": "fire", "r": 0, "c": 0})
        state_where(ws, lambda r: r["moves"] >= 1)
        assert set(room.snapshot("sc_bs_bot").keys()) == BATTLESHIP_KEYS
        assert set(room.snapshot(None).keys()) == BATTLESHIP_KEYS

    # Battleship pvp
    a_h = account(client, "sc_bs_a")
    b_h = account(client, "sc_bs_b")
    with client.websocket_connect("/ws", headers=a_h) as a, \
            client.websocket_connect("/ws", headers=b_h) as b:
        a.send_json({"type": "create", "game": "battleship", "mode": "pvp", "side": 1})
        code = state_where(a, lambda r: True)["code"]
        b.send_json({"type": "join", "room": code})
        state_where(a, lambda r: not r["waiting"])
        a.send_json({"type": "place_ships", "random": True})
        b.send_json({"type": "place_ships", "random": True})
        state_where(a, lambda r: r["phase"] == "playing")
        a.send_json({"type": "fire", "r": 0, "c": 0})
        state_where(b, lambda r: r["moves"] == 1)
        room = hub.rooms[code]
        assert set(room.snapshot("sc_bs_a").keys()) == BATTLESHIP_KEYS
        assert set(room.snapshot(None).keys()) == BATTLESHIP_KEYS


def test_threaded_bot_driver_reset_while_thinking_go():
    async def scenario():
        room = GoRoom("GO_TEST", "bot", size=9, human_side=WHITE)
        room.take_seat("An", "an", prefer=WHITE)
        driver = GoBotDriver(room, asyncio.get_running_loop(), lambda: None)
        try:
            for _ in range(3):
                driver.sync()
                room.restart(WHITE)
                driver.reset()
                stop = time.monotonic() + 10
                while not room.history:
                    assert time.monotonic() < stop, "Bot cờ vây bị treo"
                    await asyncio.sleep(0.02)
                assert len(room.history) == 1
        finally:
            driver.close()

    asyncio.run(scenario())


def test_threaded_bot_driver_reset_while_thinking_xiangqi():
    async def scenario():
        room = XiangqiRoom("XQ_TEST", "bot", level=0, human_side=XIANGQI_BLACK)
        room.take_seat("An", "an", prefer=XIANGQI_BLACK)
        driver = XiangqiBotDriver(room, asyncio.get_running_loop(), lambda: None)
        try:
            for _ in range(3):
                driver.sync()
                room.restart(XIANGQI_BLACK)
                driver.reset()
                stop = time.monotonic() + 10
                while not room.history:
                    assert time.monotonic() < stop, "Bot cờ tướng bị treo"
                    await asyncio.sleep(0.02)
                assert len(room.history) == 1
        finally:
            driver.close()

    asyncio.run(scenario())


def test_threaded_bot_driver_reset_while_thinking_battleship():
    async def scenario():
        room = BattleshipRoom("BS_TEST", "bot", level=0, human_side=2)
        room.take_seat("An", "an", prefer=2)
        driver = BattleshipBotDriver(room, asyncio.get_running_loop(), lambda: None)
        try:
            for _ in range(3):
                room.place_ships(2, None)
                driver.sync()
                room.restart(2)
                driver.reset()
                assert not driver.failed
        finally:
            driver.close()

    asyncio.run(scenario())


def test_threaded_bot_driver_discards_cancelled_result():
    room = GoRoom("GO_DISCARD", "bot", size=9, human_side=WHITE)
    loop = asyncio.new_event_loop()
    driver = GoBotDriver(room, loop, lambda: None)
    old_event = threading.Event()
    old_event.set()  # Đã bị hủy

    class FakeResult:
        nodes = 999
        elapsed = 9.9
        is_pass = False
        move = (0, 0)

    # _on_done với event đã hủy -> không được áp kết quả
    driver._on_done(FakeResult(), old_event)
    assert len(room.history) == 0
    assert room.stats_nodes == 0
    loop.close()
