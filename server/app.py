"""Máy chủ cờ caro qua mạng LAN: FastAPI + WebSocket, phục vụ luôn giao diện Vue.

Giao thức WebSocket (/ws), mọi tin nhắn là JSON có trường "type":
  client -> server
    create  {mode: "pvp"|"bot", name, rows, cols, strict, level, side}
    join    {room, name, token?}      token cũ giữ lại ghế khi tải lại trang
    move    {r, c}
    undo    {}                        chỉ khi đấu máy
    restart {}
    leave   {}
  server -> client
    joined  {room, side, token}       side = null: người xem
    state   {room: <Room.snapshot>}
    error   {message}
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from caro_game import LEVELS, X

from .bot import BotDriver
from .game import MAX_SIZE, MIN_SIZE, GameError, Room, new_code

log = logging.getLogger("caro.server")

DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
EMPTY_ROOM_TTL = 600  # giây: phòng không còn ai kết nối sẽ bị xóa


class Client:
    def __init__(self, ws):
        self.ws = ws
        self.room: Room | None = None
        self.token: str | None = None


class Hub:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.clients: dict[str, set[Client]] = {}
        self.bots: dict[str, BotDriver] = {}

    # ---------- phòng ----------
    def create(self, client, msg):
        loop = asyncio.get_running_loop()
        code = new_code(self.rooms)
        room = Room(code, msg.get("mode"), msg.get("rows", 15), msg.get("cols", 15),
                    msg.get("strict", False), msg.get("level", 1), msg.get("side", X))
        self.rooms[code] = room
        self.clients[code] = set()
        if room.mode == "bot":
            self.bots[code] = BotDriver(room, loop, lambda: self.publish(code))
        return self.join(client, room, msg.get("name"), None, prefer=msg.get("side", X))

    def join(self, client, room, name, token, prefer=None):
        self.leave(client)
        side, token = room.take_seat(name, token, prefer)
        client.room, client.token = room, token
        self.clients[room.code].add(client)
        if side is not None:
            room.seats[side].online += 1
        room.empty_since = None
        return side, token

    def leave(self, client):
        room = client.room
        if room is None:
            return
        self.clients.get(room.code, set()).discard(client)
        side = room.side_of(client.token)
        if side is not None:
            room.seats[side].online -= 1
        if not self.clients.get(room.code):
            room.empty_since = time.monotonic()
        client.room = client.token = None
        self.publish(room.code)

    def remove(self, code):
        self.rooms.pop(code, None)
        self.clients.pop(code, None)
        bot = self.bots.pop(code, None)
        if bot is not None:
            bot.close()

    def cleanup(self):
        now = time.monotonic()
        for code, room in list(self.rooms.items()):
            if room.empty_since is not None and now - room.empty_since > EMPTY_ROOM_TTL:
                self.remove(code)

    # ---------- gửi trạng thái ----------
    def publish(self, code):
        """Gửi trạng thái mới cho mọi người trong phòng (gọi từ event loop)."""
        room = self.rooms.get(code)
        if room is None:
            return
        bot = self.bots.get(code)
        thinking = bot.thinking if bot else False
        for client in list(self.clients.get(code, ())):
            payload = {"type": "state", "room": room.snapshot(client.token, thinking)}
            asyncio.create_task(send(client.ws, payload))
        room.notice = ""

    def changed(self, room, *, reset_bot=False):
        bot = self.bots.get(room.code)
        if bot is not None:
            if reset_bot:
                bot.reset()
            else:
                bot.sync()
        self.publish(room.code)

    def open_rooms(self):
        result = []
        for room in self.rooms.values():
            if room.waiting and self.clients.get(room.code):
                host = next(s for s in room.seats.values() if s is not None)
                result.append({"code": room.code, "host": host.name, "rows": room.rows,
                               "cols": room.cols, "strict": room.strict})
        return result


async def send(ws, payload):
    try:
        await ws.send_json(payload)
    except Exception:
        pass  # kết nối đã đóng; vòng nhận tin sẽ dọn dẹp


def lan_addresses():
    """Địa chỉ IPv4 trong mạng LAN; card mạng chính (có route ra ngoài) đứng đầu."""
    primary = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))  # UDP connect: không gửi gói tin nào
            primary = probe.getsockname()[0]
    except OSError:
        pass
    found = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    # Card ảo (WSL, Hyper-V, Docker) thường ở 172.16-31.x; xếp sau 192.168.x và 10.x.
    rank = lambda ip: (ip != primary, not ip.startswith(("192.168.", "10.")), ip)
    return sorted((ip for ip in found | {primary} if ip and not ip.startswith("127.")),
                  key=rank)


hub = Hub()


@asynccontextmanager
async def lifespan(_app):
    async def cleanup_loop():
        while True:
            await asyncio.sleep(60)
            hub.cleanup()
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    for code in list(hub.rooms):
        hub.remove(code)


app = FastAPI(title="Cờ caro LAN", lifespan=lifespan)


@app.get("/api/info")
def info():
    return {
        "lan": lan_addresses(),
        "levels": [{"id": i, "name": name, "seconds": seconds}
                   for i, (name, seconds, _depth, _limit) in enumerate(LEVELS)],
        "minSize": MIN_SIZE,
        "maxSize": MAX_SIZE,
    }


@app.get("/api/rooms")
def rooms():
    return hub.open_rooms()


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    client = Client(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if not isinstance(msg, dict):
                continue
            try:
                await handle(client, msg)
            except GameError as exc:
                await send(ws, {"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("Lỗi kết nối WebSocket")
    finally:
        hub.leave(client)


async def handle(client, msg):
    kind = msg.get("type")
    if kind == "create":
        side, token = hub.create(client, msg)
        await joined(client, side, token)
        hub.changed(client.room)
        return
    if kind == "join":
        room = hub.rooms.get(str(msg.get("room", "")).strip().upper())
        if room is None:
            raise GameError("Không tìm thấy phòng. Kiểm tra lại mã phòng.")
        side, token = hub.join(client, room, msg.get("name"), msg.get("token"))
        await joined(client, side, token)
        hub.changed(room)
        return
    if kind == "leave":
        hub.leave(client)
        return
    room = client.room
    if room is None:
        raise GameError("Bạn chưa vào phòng nào.")
    side = room.side_of(client.token)
    if kind == "move":
        room.place(side, msg.get("r"), msg.get("c"))
        hub.changed(room)
    elif kind == "undo":
        room.undo(side)
        hub.changed(room, reset_bot=True)
    elif kind == "restart":
        room.restart(side)
        hub.changed(room, reset_bot=True)
    else:
        raise GameError("Lệnh không hợp lệ.")


async def joined(client, side, token):
    await send(client.ws, {"type": "joined", "room": client.room.code,
                           "side": side, "token": token})


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
else:
    @app.get("/", response_class=HTMLResponse)
    def missing_build():
        return ("<h1>Chưa build giao diện</h1><p>Chạy <code>npm install</code> và "
                "<code>npm run build</code> trong thư mục <code>web</code>, hoặc dùng "
                "<code>npm run dev</code> khi phát triển.</p>")
