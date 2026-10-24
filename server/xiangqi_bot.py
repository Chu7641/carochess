"""Quản lý bot cờ tướng chạy ở luồng nền cho một phòng XiangqiRoom."""

from __future__ import annotations

import logging
import threading
import traceback

from xiangqi_game import XiangqiBot
from server.xiangqi_room import XiangqiRoom

log = logging.getLogger("xiangqi.bot")


class XiangqiBotDriver:
    """Điều phối bot cờ tướng ở luồng nền cho XiangqiRoom."""

    def __init__(self, room: XiangqiRoom, loop, on_change):
        self.room = room
        self.loop = loop
        self.on_change = on_change
        self.engine = XiangqiBot(level=room.level)
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
        if room.current != room.bot_side:
            self.cancel()
            return
        if self.worker is not None and self.worker.is_alive():
            return  # Đang suy nghĩ dở

        self.cancel_event = threading.Event()
        self._is_thinking = True
        board_copy = room.engine.copy()

        self.worker = threading.Thread(
            target=self._worker_main,
            args=(board_copy, self.cancel_event),
            daemon=True,
        )
        self.worker.start()

    def _worker_main(self, board, cancel_event):
        try:
            res = self.engine.choose(board, cancel_event)
            if not cancel_event.is_set():
                self.loop.call_soon_threadsafe(self._on_done, res, cancel_event)
        except Exception:
            self.loop.call_soon_threadsafe(self._on_error, traceback.format_exc())
        finally:
            self.loop.call_soon_threadsafe(self._worker_exited, threading.current_thread())

    def _worker_exited(self, thread):
        # join để is_alive() chắc chắn False rồi sync lại: nếu có ván mới/hoàn tác
        # trong lúc luồng cũ đang chạy, sync() lúc đó đã bỏ qua và bot sẽ treo.
        thread.join()
        if thread is self.worker:
            self._is_thinking = False
            self.sync()

    def _on_done(self, res, cancel_event):
        room = self.room
        if cancel_event is not self.cancel_event or cancel_event.is_set():
            return  # kết quả của lượt tính đã bị hủy (ván cũ, trước khi hoàn tác)
        if room.winner != 0 or room.current != room.bot_side:
            return

        room.stats_nodes = res.nodes
        room.stats_elapsed = res.elapsed
        room.stats_depth = res.depth
        room.stats_score = res.score

        if res.move is None:
            log.warning("Bot cờ tướng không tìm được nước đi (hết nước).")
        else:
            try:
                room.move(room.bot_side, *res.move)
            except Exception as exc:
                log.warning("Bot cờ tướng đánh nước không hợp lệ: %s", exc)

        self.on_change()
        self.sync()

    def _on_error(self, text):
        log.error("Bot cờ tướng gặp lỗi ở phòng %s:\n%s", self.room.code, text)
        self.failed = True
        self._is_thinking = False
        self.room.notice = "Bot cờ tướng gặp lỗi; hãy mở ván mới."
        self.on_change()

