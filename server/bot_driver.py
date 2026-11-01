"""Lớp cơ sở điều phối bot chạy ở luồng nền (worker thread) cho các trò chơi."""

from __future__ import annotations

import logging
import threading
import traceback
from typing import Any

log = logging.getLogger("bot.driver")


class ThreadedBotDriver:
    """Lớp điều phối bot dùng chung chạy ở luồng nền."""

    name: str = "bot"
    log: logging.Logger = log

    def __init__(self, room, loop, on_change):
        self.room = room
        self.loop = loop
        self.on_change = on_change
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.failed = False
        self._is_thinking = False

    @property
    def thinking(self) -> bool:
        room = self.room
        return (
            not self.failed
            and room.winner == 0
            and room.current == room.bot_side
            and self._is_thinking
            and self.can_think()
        )

    def can_think(self) -> bool:
        """Điều kiện riêng ngoài các điều kiện chung để bot được phép tính."""
        return True

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
        if self.failed or room.winner != 0 or room.waiting or not self.can_think():
            self.cancel()
            return
        if room.current != room.bot_side:
            self.cancel()
            return
        if self.worker is not None and self.worker.is_alive():
            return  # Đang suy nghĩ dở

        self.cancel_event = threading.Event()
        self._is_thinking = True
        data = self.make_input()

        self.worker = threading.Thread(
            target=self._worker_main,
            args=(data, self.cancel_event),
            daemon=True,
        )
        self.worker.start()

    def make_input(self) -> Any:
        """Dữ liệu đưa cho luồng nền (copy của bàn cờ / góc nhìn bot)."""
        raise NotImplementedError

    def compute(self, data: Any, cancel_event: threading.Event) -> Any:
        """Chạy ở luồng nền: gọi engine tính nước đi."""
        raise NotImplementedError

    def apply(self, result: Any):
        """Chạy trên event loop: thực hiện nước đi và cập nhật stats."""
        raise NotImplementedError

    def _worker_main(self, data: Any, cancel_event: threading.Event):
        try:
            res = self.compute(data, cancel_event)
            if not cancel_event.is_set():
                self.loop.call_soon_threadsafe(self._on_done, res, cancel_event)
        except Exception:
            self.loop.call_soon_threadsafe(self._on_error, traceback.format_exc())
        finally:
            self.loop.call_soon_threadsafe(self._worker_exited, threading.current_thread())

    def _worker_exited(self, thread: threading.Thread):
        # join để is_alive() chắc chắn False rồi sync lại: nếu có ván mới/hoàn tác
        # trong lúc luồng cũ đang chạy, sync() lúc đó đã bỏ qua và bot sẽ treo.
        thread.join()
        if thread is self.worker:
            self._is_thinking = False
            self.sync()

    def _on_done(self, res: Any, cancel_event: threading.Event):
        room = self.room
        if cancel_event is not self.cancel_event or cancel_event.is_set():
            return  # kết quả của lượt tính đã bị hủy (ván cũ, trước khi hoàn tác)
        if room.winner != 0 or room.current != room.bot_side or not self.can_think():
            return

        self.apply(res)
        self.on_change()
        self.sync()

    def _on_error(self, text: str):
        self.log.error("Bot %s gặp lỗi ở phòng %s:\n%s", self.name, self.room.code, text)
        self.failed = True
        self._is_thinking = False
        self.room.notice = f"Bot {self.name} gặp lỗi; hãy mở ván mới."
        self.on_change()

