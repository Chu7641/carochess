"""Máy chủ cờ caro qua mạng LAN: FastAPI + WebSocket, phục vụ luôn giao diện Vue.

Phải đăng nhập (cookie "session", xem /api/login) mới dùng được /ws và /api/rooms.
Ghế trong phòng gắn với tài khoản, nên tải lại trang hay đổi máy vẫn về đúng ghế.

Giao thức WebSocket (/ws), mọi tin nhắn là JSON có trường "type":
  client -> server
    create  {mode: "pvp"|"bot", rows, cols, strict, level, side}
    join    {room}
    move    {r, c}
    undo    {}                        đấu người: thành yêu cầu, chờ đối thủ đồng ý
    restart {}                        đấu người, ván đang dở: người bấm bị tính thua
    ready   {}                        đấu người: bật/tắt sẵn sàng; cả hai sẵn sàng thì ván bắt đầu
    respond {accept: bool}            đối thủ trả lời yêu cầu đi lại (room.request)
  Ván đấu người kết thúc (thắng, hòa, hết giờ, rời phòng, bỏ ván) thì tính elo (Hub.rate).
    leave   {}
  server -> client
    joined  {room, side}              side = null: người xem
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

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from caro_game import EMPTY, LEVELS, O, X

from . import auth
from .bot import BotDriver
from .game import MAX_SIZE, MIN_SIZE, GameError, Room, new_code

log = logging.getLogger("caro.server")

DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
EMPTY_ROOM_TTL = 600  # giây: phòng không còn ai kết nối sẽ bị xóa


class Client:
    def __init__(self, ws, username):
        self.ws = ws
        self.room: Room | None = None
        self.token = username  # khóa ghế trong phòng


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
        return self.join(client, room, prefer=msg.get("side", X))

    def join(self, client, room, prefer=None):
        self.leave(client)
        side = room.take_seat(client.token, client.token, prefer)
        client.room = room
        self.clients[room.code].add(client)
        if side is not None:
            room.seats[side].online += 1
            room.seats[side].elo = auth.elo_of(client.token)
        room.empty_since = None
        return side

    def leave(self, client, give_up=False):
        """give_up: người chơi bấm "Rời phòng" (nhả ghế); False: chỉ mất kết nối (giữ ghế)."""
        room = client.room
        if room is None:
            return
        self.clients.get(room.code, set()).discard(client)
        side = room.side_of(client.token)
        if side is not None:
            room.seats[side].online -= 1
            if give_up and room.mode == "pvp":
                room.forfeit(side, "rời phòng")  # tính elo trước khi nhả ghế
                self.rate(room)
                # Phòng thành "đang chờ": ai cũng vào được, kể cả người vừa rời.
                room.seats[side], room.request = None, None
                room.seat_freed(side)
        if not self.clients.get(room.code):
            room.empty_since = time.monotonic()
        client.room = None
        self.publish(room.code)

    def remove(self, code):
        self.rooms.pop(code, None)
        self.clients.pop(code, None)
        bot = self.bots.pop(code, None)
        if bot is not None:
            bot.close()

    def check_clocks(self):
        now = time.monotonic()
        for room in list(self.rooms.values()):
            if room.turn_deadline is not None and now >= room.turn_deadline:
                room.timeout()
                self.changed(room)

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
        room.sync_clock()
        for client in list(self.clients.get(code, ())):
            payload = {"type": "state", "room": room.snapshot(client.token, thinking)}
            asyncio.create_task(send(client.ws, payload))
        room.notice = ""

    def rate(self, room):
        """Ván đấu người vừa kết thúc (thắng, thua, hòa, xin thua): tính elo đúng một lần."""
        if room.mode != "pvp" or room.winner == EMPTY or room.rated:
            return
        room.rated = True
        x, o = room.seats[X], room.seats[O]
        if x is None or o is None:
            return
        score = 0.5 if room.winner == -1 else float(room.winner == X)
        result = auth.record_game(x.token, o.token, score)
        if result:
            x.elo, o.elo, x.elo_delta = result
            o.elo_delta = -x.elo_delta

    def changed(self, room, *, reset_bot=False):
        self.rate(room)
        bot = self.bots.get(room.code)
        if bot is not None:
            if reset_bot:
                bot.reset()
            else:
                bot.sync()
        self.publish(room.code)

    def room_list(self):
        """Mọi phòng còn người kết nối: đang chờ, đang chơi, hoặc đấu máy."""
        result = []
        for room in self.rooms.values():
            if not self.clients.get(room.code):
                continue  # phòng trống, sắp bị xóa
            status = "bot" if room.mode == "bot" else "waiting" if room.waiting else "playing"
            result.append({"code": room.code, "status": status, "rows": room.rows,
                           "cols": room.cols, "strict": room.strict, "moves": len(room.history),
                           "players": [s.name for s in room.seats.values() if s is not None],
                           "viewers": len(self.clients[room.code])})
        # Phòng đang chờ lên đầu để vào nhanh.
        result.sort(key=lambda r: (r["status"] != "waiting", r["code"]))
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
    auth.load_env()
    auth.init()

    async def cleanup_loop():
        while True:
            await asyncio.sleep(60)
            hub.cleanup()

    async def clock_loop():
        while True:
            await asyncio.sleep(0.5)
            hub.check_clocks()
    tasks = [asyncio.create_task(cleanup_loop()), asyncio.create_task(clock_loop())]
    yield
    for task in tasks:
        task.cancel()
    for code in list(hub.rooms):
        hub.remove(code)


app = FastAPI(title="Cờ caro LAN", lifespan=lifespan)
COOKIE = "session"


class Credentials(BaseModel):
    username: str
    password: str


def current_user(request: Request):
    user = auth.user_for(request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(401, "Bạn cần đăng nhập.")
    return user


def start_session(response, token, user):
    response.set_cookie(COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, samesite="lax")
    return user


@app.post("/api/register")
def register(body: Credentials):
    try:
        auth.register(body.username, body.password)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"pending": True}


@app.post("/api/login")
def login(body: Credentials, response: Response):
    try:
        return start_session(response, *auth.login(body.username, body.password))
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/logout")
def logout(request: Request, response: Response):
    auth.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE)
    return {}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


class PasswordChange(BaseModel):
    current: str
    new: str


@app.post("/api/password")
def change_password(body: PasswordChange, request: Request, user=Depends(current_user)):
    try:
        auth.change_password(user["id"], body.current, body.new, request.cookies.get(COOKIE))
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {}


def current_admin(user=Depends(current_user)):
    if not user["isAdmin"]:
        raise HTTPException(403, "Chỉ admin mới dùng được chức năng này.")
    return user


@app.get("/api/admin/users", dependencies=[Depends(current_admin)])
def admin_users():
    return auth.list_users()


ADMIN_ACTIONS = {"approve": auth.approve, "reject": auth.reject, "make-admin": auth.make_admin,
                 "reset-password": auth.reset_password, "delete": auth.delete_user,
                 "reset-elo": auth.reset_elo}


@app.post("/api/admin/users/{user_id}/{action}")
def admin_action(user_id: int, action: str, admin=Depends(current_admin)):
    if action not in ADMIN_ACTIONS:
        raise HTTPException(404, "Không có chức năng này.")
    if action == "delete" and user_id == admin["id"]:
        raise HTTPException(400, "Không thể tự xóa tài khoản của chính mình.")
    try:
        password = ADMIN_ACTIONS[action](user_id)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"password": password} if password else {}


@app.get("/api/info", dependencies=[Depends(current_user)])
def info():
    return {
        "lan": lan_addresses(),
        "levels": [{"id": i, "name": name, "seconds": seconds}
                   for i, (name, seconds, _depth, _limit) in enumerate(LEVELS)],
        "minSize": MIN_SIZE,
        "maxSize": MAX_SIZE,
    }


@app.get("/api/rooms", dependencies=[Depends(current_user)])
def rooms():
    return hub.room_list()


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    user = await asyncio.to_thread(auth.user_for, ws.cookies.get(COOKIE))
    if user is None:
        await ws.close(code=4401, reason="Bạn cần đăng nhập.")
        return
    client = Client(ws, user["username"])
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
        side = hub.create(client, msg)
        await joined(client, side)
        hub.changed(client.room)
        return
    if kind == "join":
        room = hub.rooms.get(str(msg.get("room", "")).strip().upper())
        if room is None:
            raise GameError("Không tìm thấy phòng. Kiểm tra lại mã phòng.")
        side = hub.join(client, room)
        await joined(client, side)
        hub.changed(room)
        return
    if kind == "leave":
        hub.leave(client, give_up=True)
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
        room.forfeit(side, "bỏ ván giữa chừng")  # đấu người, ván dở: thua trước, rồi mới ván mới
        hub.rate(room)
        room.restart(side)
        hub.changed(room, reset_bot=True)
    elif kind == "ready":
        room.toggle_ready(side)
        hub.changed(room)
    elif kind == "respond":
        room.respond(side, msg.get("accept") is True)
        hub.changed(room)
    else:
        raise GameError("Lệnh không hợp lệ.")


async def joined(client, side):
    await send(client.ws, {"type": "joined", "room": client.room.code, "side": side})


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
else:
    @app.get("/", response_class=HTMLResponse)
    def missing_build():
        return ("<h1>Chưa build giao diện</h1><p>Chạy <code>npm install</code> và "
                "<code>npm run build</code> trong thư mục <code>web</code>, hoặc dùng "
                "<code>npm run dev</code> khi phát triển.</p>")
