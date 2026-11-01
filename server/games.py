"""Sổ đăng ký trò chơi (Game registry)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from caro_game import X
from go_game import BLACK
from xiangqi_game import RED as XIANGQI_RED

from server.game import Room
from server.go_room import GoRoom
from server.xiangqi_room import XiangqiRoom
from server.battleship_room import BattleshipRoom

from server.bot import BotDriver
from server.go_bot import GoBotDriver
from server.xiangqi_bot import XiangqiBotDriver
from server.battleship_bot import BattleshipBotDriver


@dataclass
class GameSpec:
    name: str
    room_cls: type
    default_side: int
    make_room: Callable[[str, dict[str, Any]], Room]
    make_bot: Callable[[Any, Any, Any], Any] | None = None


def make_caro_room(code: str, msg: dict[str, Any]) -> Room:
    return Room(
        code,
        msg.get("mode"),
        msg.get("rows", 15),
        msg.get("cols", 15),
        msg.get("strict", False),
        msg.get("level", 1),
        msg.get("side", X),
    )


def make_go_room(code: str, msg: dict[str, Any]) -> GoRoom:
    return GoRoom(
        code,
        msg.get("mode"),
        size=msg.get("size", msg.get("rows", 19)),
        komi=msg.get("komi"),
        level=msg.get("level", 1),
        human_side=msg.get("side", BLACK),
    )


def make_xiangqi_room(code: str, msg: dict[str, Any]) -> XiangqiRoom:
    return XiangqiRoom(
        code,
        msg.get("mode"),
        level=msg.get("level", 1),
        human_side=msg.get("side", XIANGQI_RED),
    )


def make_battleship_room(code: str, msg: dict[str, Any]) -> BattleshipRoom:
    return BattleshipRoom(
        code,
        msg.get("mode"),
        level=msg.get("level", 1),
        human_side=msg.get("side", 1),
    )


GAMES: dict[str, GameSpec] = {
    "caro": GameSpec(
        name="caro",
        room_cls=Room,
        default_side=X,
        make_room=make_caro_room,
        make_bot=lambda room, loop, on_change: BotDriver(room, loop, on_change),
    ),
    "go": GameSpec(
        name="go",
        room_cls=GoRoom,
        default_side=BLACK,
        make_room=make_go_room,
        make_bot=lambda room, loop, on_change: GoBotDriver(room, loop, on_change),
    ),
    "xiangqi": GameSpec(
        name="xiangqi",
        room_cls=XiangqiRoom,
        default_side=XIANGQI_RED,
        make_room=make_xiangqi_room,
        make_bot=lambda room, loop, on_change: XiangqiBotDriver(room, loop, on_change),
    ),
    "battleship": GameSpec(
        name="battleship",
        room_cls=BattleshipRoom,
        default_side=1,
        make_room=make_battleship_room,
        make_bot=lambda room, loop, on_change: BattleshipBotDriver(room, loop, on_change),
    ),
}

