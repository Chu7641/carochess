"""Quản lý bot hải chiến chạy ở luồng nền cho một phòng BattleshipRoom."""

from __future__ import annotations

import logging
import threading
import traceback

from battleship_game import BATTLESHIP_LEVELS, BattleshipBot
from server.battleship_room import BattleshipRoom

log = logging.getLogger("battleship.bot")


class BattleshipBotDriver:
    """Điều phối bot hải chiến ở luồng nền cho BattleshipRoom."""

    def __init__(self, room: BattleshipRoom, loop, on_change):
        self.room = room
        self.loop = loop
        self.on_change = on_change
        self.engine = BattleshipBot(level=room.level)
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.failed = False
        self._is_thinking = False

    @property
    def thinking(self) -> bool:
        room = self.room
        return not self.failed and room.winner == 0 and room.current == room.bot_side and self._is_thinking

    def cancel(self):
        self.cancel_event.set()
        self._is_thinking = False

    def reset(self):
        self.cancel()
        self.failed = False
        self.sync()

    def close(self):
        self.cancel()
        self.failed = True

    def sync(self):
        room = self.room
        if self.failed or room.winner != 0 or room.waiting:
            self.cancel()
            return
        if getattr(room, "phase", "") != "playing" or not room.started:
            self.cancel()
            return
        if room.current != room.bot_side:
            self.cancel()
            return
        if self.worker is not None and self.worker.is_alive():
            return  # Đang suy nghĩ dở

        self.cancel_event = threading.Event()
        self._is_thinking = True
        view = room.bot_view()

        self.worker = threading.Thread(
            target=self._worker_main,
            args=(view, self.cancel_event),
            daemon=True,
        )
        self.worker.start()

    def _worker_main(self, view: dict, cancel_event: threading.Event):
        try:
            move = self.engine.choose(view, cancel_event)
            delay = BATTLESHIP_LEVELS[self.room.level][1]
            if not cancel_event.is_set():
                cancel_event.wait(delay)
            if not cancel_event.is_set():
                self.loop.call_soon_threadsafe(self._on_done, move, cancel_event)
        except Exception:
            self.loop.call_soon_threadsafe(self._on_error, traceback.format_exc())
        finally:
            self.loop.call_soon_threadsafe(self._worker_exited, threading.current_thread())

    def _worker_exited(self, thread: threading.Thread):
        thread.join()
        if thread is self.worker:
            self._is_thinking = False
            self.sync()

    def _on_done(self, move: tuple[int, int], cancel_event: threading.Event):
        room = self.room
        if cancel_event is not self.cancel_event or cancel_event.is_set():
            return  # Kết quả đã bị hủy (ván mới, restart)
        if room.winner != 0 or room.current != room.bot_side or getattr(room, "phase", "") != "playing":
            return

        r, c = move
        try:
            room.fire(room.bot_side, r, c)
        except Exception as exc:
            log.warning("Bot hải chiến bắn không hợp lệ: %s", exc)

        self.on_change()
        self.sync()

    def _on_error(self, text: str):
        log.error("Bot hải chiến gặp lỗi ở phòng %s:\n%s", self.room.code, text)
        self.failed = True
        self._is_thinking = False
        self.room.notice = "Bot hải chiến gặp lỗi; hãy mở ván mới."
        self.on_change()
