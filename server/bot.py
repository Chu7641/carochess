"""Chạy CaroBot ở luồng nền cho một phòng, có nghĩ trước như bản desktop.

Mọi phương thức (trừ _worker_main) chạy trên event loop của asyncio;
luồng nền chỉ báo kết quả về qua loop.call_soon_threadsafe.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import traceback

from caro_game import EMPTY, LEVELS, WIN_LENGTH, BotJob, CaroBot, Clock

log = logging.getLogger("caro.bot")


class BotDriver:
    def __init__(self, room, loop, on_change, ponder=True):
        self.room, self.loop, self.on_change = room, loop, on_change
        self.ponder = ponder
        _, seconds, depth, limit = LEVELS[room.level]
        self.engine = CaroBot(depth=depth, time_budget=seconds, move_limit=limit,
                              win_length=WIN_LENGTH, strict=room.strict)
        self.job = None
        self.worker = None
        self.failed = False

    @property
    def thinking(self):
        room = self.room
        return not self.failed and room.winner == EMPTY and room.current == room.bot_side

    def cancel(self):
        if self.job is not None:
            self.job.cancel.set()
            self.job = None

    def reset(self):
        """Sau hoàn tác hoặc ván mới: bỏ kết quả cũ rồi tính lại."""
        self.cancel()
        self.failed = False
        self.sync()

    def close(self):
        self.cancel()
        self.failed = True

    # ---------- luồng nền ----------
    def _worker_main(self, job, snapshot, side):
        try:
            if job.kind == "ponder":
                guess = self.engine.predict(snapshot, 3 - side, job.cancel)
                if guess is None or job.cancel.is_set():
                    return
                snapshot[guess[0]][guess[1]] = 3 - side
                job.search_started = time.perf_counter()
                job.predicted = guess

            def progress(result):
                self.loop.call_soon_threadsafe(self._on_progress, job, result)
            result = self.engine.choose(snapshot, side, job.cancel, progress, job.clock)
            if not job.cancel.is_set():
                self.loop.call_soon_threadsafe(self._on_done, job, result)
        except Exception:
            self.loop.call_soon_threadsafe(self._on_error, job, traceback.format_exc())
        finally:
            self.loop.call_soon_threadsafe(self.sync)  # có thể đang chờ worker cũ thoát

    # ---------- event loop ----------
    def _on_progress(self, job, result):
        if job is self.job and job.kind == "search":
            self.room.stats = result
            self.on_change()

    def _on_done(self, job, result):
        if job is self.job:
            job.result = result
            self.sync()

    def _on_error(self, job, text):
        if job is self.job:
            log.error("Bot lỗi ở phòng %s:\n%s", self.room.code, text)
            self.job, self.failed = None, True
            self.room.notice = "Bot gặp lỗi; hãy mở ván mới."
            self.on_change()

    def _start(self, kind):
        # Mỗi thời điểm chỉ một worker dùng engine; worker cũ thoát khi thấy cancel.
        if self.worker is not None and self.worker.is_alive():
            return
        now = time.perf_counter()
        clock = Clock(math.inf if kind == "ponder" else now + self.engine.time_budget)
        job = BotJob(kind, threading.Event(), clock, len(self.room.history))
        job.thread = threading.Thread(
            target=self._worker_main,
            args=(job, [row[:] for row in self.room.board], self.room.bot_side),
            daemon=True,
        )
        self.job, self.worker = job, job.thread
        job.thread.start()

    def _ponder_hit(self, job):
        history = self.room.history
        return (job.kind == "ponder" and job.predicted is not None
                and len(history) == job.base_moves + 1
                and job.predicted == history[-1][:2])

    def sync(self):
        """Gọi sau mỗi thay đổi bàn cờ: bắt đầu, chuyển, hủy hoặc áp dụng kết quả."""
        room = self.room
        if self.failed or room.winner != EMPTY or room.waiting:
            self.cancel()
            return
        job = self.job
        if room.current != room.bot_side:
            if job is not None and job.kind == "search":
                self.cancel()
                job = None
            if job is None and self.ponder and room.history:
                self._start("ponder")
            return
        if job is not None and job.kind == "ponder":
            if self._ponder_hit(job):
                # Đoán trúng: chỉ cần thêm phần còn thiếu của ngân sách.
                job.kind = "search"
                now, budget = time.perf_counter(), self.engine.time_budget
                job.clock.deadline = now + max(budget * 0.25,
                                               budget - (now - job.search_started))
            else:
                self.cancel()
                job = None
        if job is None:
            room.stats = type(room.stats)(None)
            self._start("search")
            return
        if job.result is not None:
            self.job = None
            room.stats = job.result
            if job.result.move is not None:
                room.place(room.bot_side, *job.result.move)
            self.on_change()
            self.sync()  # bắt đầu nghĩ trước cho lượt người
