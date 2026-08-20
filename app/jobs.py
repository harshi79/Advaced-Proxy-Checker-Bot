from __future__ import annotations

import asyncio
import logging
import secrets
from collections import deque
from time import monotonic
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.types import BufferedInputFile

from .checker import ProxyChecker
from .config import Settings
from .models import JobStats, ParseResult, ProxyCandidate, ProxyCheckResult
from .texts import final_text, progress_text, queued_text
from .ui import cancel_keyboard

LOGGER = logging.getLogger(__name__)


class ProxyJob:
    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        checker: ProxyChecker,
        check_gate: asyncio.Semaphore,
        chat_id: int,
        user_id: int,
        parse_result: ParseResult,
        progress_message_id: int,
        source_name: str = "proxies.txt",
    ) -> None:
        self.id = secrets.token_hex(5)
        self.bot = bot
        self.settings = settings
        self.checker = checker
        self.check_gate = check_gate
        self.chat_id = chat_id
        self.user_id = user_id
        self.proxies: list[ProxyCandidate] = parse_result.valid_entries
        self.stats = JobStats(
            received_lines=parse_result.received_lines,
            valid_entries=len(parse_result.valid_entries),
            invalid_lines=parse_result.invalid_lines,
            duplicate_lines=parse_result.duplicate_lines,
        )
        self.progress_message_id = progress_message_id
        self.source_name = source_name or "proxies.txt"
        self.results: list[ProxyCheckResult] = []
        self.cancel_event = asyncio.Event()
        self.progress_deleted = False
        self.status = "queued"
        self._finished = asyncio.Event()

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_queued(self) -> bool:
        return self.status == "queued"

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def mark_progress_deleted(self) -> None:
        self.progress_deleted = True

    async def run(self) -> None:
        self.status = "active"
        self.stats.started_at = monotonic()
        try:
            await self._edit_progress(progress_text(self.stats), cancel_keyboard(self.id))
            progress_task = asyncio.create_task(self._progress_loop())
            try:
                await self._check_all()
            finally:
                progress_task.cancel()
                await asyncio.gather(progress_task, return_exceptions=True)
        except asyncio.CancelledError:
            # The queue manager does not cancel active jobs during a normal
            # owner queue reset. This is only a process-shutdown safeguard.
            self.request_cancel()
            raise
        except Exception:  # noqa: BLE001 - report a clean Telegram message
            LOGGER.exception("job %s failed", self.id)
            self.status = "failed"
        finally:
            self.stats.finished_at = monotonic()
            cancelled = self.cancel_event.is_set()
            if cancelled and self.status != "failed":
                self.status = "cancelled"
            elif self.status != "failed":
                self.status = "completed"
            await self._finish(cancelled=cancelled)
            self._finished.set()

    async def _check_all(self) -> None:
        pending: asyncio.Queue[ProxyCandidate] = asyncio.Queue()
        for proxy in self.proxies:
            pending.put_nowait(proxy)

        worker_count = min(self.settings.check_concurrency, max(len(self.proxies), 1))

        async def worker() -> None:
            while not self.cancel_event.is_set():
                try:
                    proxy = pending.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    async with self.check_gate:
                        # A worker may have been waiting for the global gate
                        # when cancellation was requested. Do not start a new
                        # network request after the cancel action.
                        if self.cancel_event.is_set():
                            return
                        try:
                            result = await self.checker.check(proxy)
                        except Exception as exc:  # noqa: BLE001
                            result = ProxyCheckResult(
                                proxy=proxy,
                                working=False,
                                error=exc.__class__.__name__.lower(),
                            )
                    self.results.append(result)
                    self.stats.checked += 1
                    if result.working:
                        self.stats.working += 1
                finally:
                    pending.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        await asyncio.gather(*workers)

    async def _progress_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.progress_update_seconds)
            if self.progress_deleted:
                return
            await self._edit_progress(progress_text(self.stats), cancel_keyboard(self.id))

    async def _edit_progress(self, text: str, reply_markup=None) -> None:
        if self.progress_deleted:
            return
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.progress_message_id,
                text=text,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as exc:
            # A user may have deleted the message manually or tapped cancel
            # while an update was in flight. Do not keep retrying a dead ID.
            if "not modified" not in str(exc).lower():
                self.progress_deleted = True
        except TelegramNetworkError:
            LOGGER.warning("temporary Telegram update failure for job %s", self.id)

    async def delete_progress(self) -> None:
        if self.progress_deleted:
            return
        self.progress_deleted = True
        try:
            await self.bot.delete_message(self.chat_id, self.progress_message_id)
        except TelegramBadRequest:
            pass
        except TelegramNetworkError:
            LOGGER.warning("could not delete progress message for job %s", self.id)

    async def _finish(self, *, cancelled: bool) -> None:
        summary = final_text(self.stats, cancelled=cancelled)
        if self.status == "failed":
            summary = "⊘ ᴛʜᴇ ᴊᴏʙ ᴇɴᴅᴇᴅ ᴜɴᴇxᴘᴇᴄᴛᴇᴅʟʏ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ."

        if not self.progress_deleted:
            await self._edit_progress(summary)

        working = [result for result in self.results if result.working and result.checked_scheme]
        if not working:
            if self.progress_deleted:
                await self._send_message(summary)
            return

        lines = [result.proxy.display(result.checked_scheme) for result in working]
        payload = ("\n".join(lines) + "\n").encode("utf-8")
        filename = f"working_proxies_{self.id}.txt"
        caption = (
            summary
            if self.progress_deleted
            else (
                "✓ ᴡᴏʀᴋɪɴɢ ᴘʀᴏxɪᴇs\n"
                f"→ {len(lines):,} ᴇɴᴛʀɪᴇs\n"
                "→ ᴅᴇᴀᴅ ᴘʀᴏxɪᴇs ᴀʀᴇ ɴᴏᴛ ɪɴᴄʟᴜᴅᴇᴅ."
            )
        )[:1024]
        try:
            await self.bot.send_document(
                chat_id=self.chat_id,
                document=BufferedInputFile(payload, filename=filename),
                caption=caption,
            )
        except TelegramNetworkError:
            LOGGER.warning("could not send result file for job %s", self.id)
            await self._send_message("⊘ ᴛʜᴇ ʀᴇsᴜʟᴛ ғɪʟᴇ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ sᴇɴᴛ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")

    async def _send_message(self, text: str) -> None:
        try:
            await self.bot.send_message(self.chat_id, text)
        except TelegramNetworkError:
            LOGGER.warning("could not send Telegram message for job %s", self.id)


class JobManager:
    def __init__(self, settings: Settings, checker: ProxyChecker) -> None:
        self.settings = settings
        self.checker = checker
        self.check_gate = asyncio.Semaphore(settings.check_concurrency)
        self._queue: deque[ProxyJob] = deque()
        self._queued: dict[str, ProxyJob] = {}
        self._active: dict[str, ProxyJob] = {}
        self._jobs: dict[str, ProxyJob] = {}
        self._condition = asyncio.Condition()
        self._workers: list[asyncio.Task[None]] = []
        self._stopping = False

    async def start(self) -> None:
        self._stopping = False
        self._workers = [asyncio.create_task(self._worker_loop(i)) for i in range(self.settings.worker_count)]

    async def stop(self) -> None:
        self._stopping = True
        async with self._condition:
            self._condition.notify_all()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def submit(self, job: ProxyJob) -> tuple[bool, str]:
        async with self._condition:
            user_jobs = sum(1 for item in self._jobs.values() if item.user_id == job.user_id)
            if user_jobs >= 3:
                return False, "ᴜᴘ ᴛᴏ 3 ᴊᴏʙs ᴘᴇʀ ᴜsᴇʀ ᴄᴀɴ ʙᴇ ᴀᴄᴛɪᴠᴇ ᴏʀ ǫᴜᴇᴜᴇᴅ."
            self._queue.append(job)
            self._queued[job.id] = job
            self._jobs[job.id] = job
            self._condition.notify()
            return True, ""

    async def _worker_loop(self, worker_number: int) -> None:
        while not self._stopping:
            async with self._condition:
                await self._condition.wait_for(lambda: bool(self._queue) or self._stopping)
                if self._stopping:
                    return
                job = self._queue.popleft()
                self._queued.pop(job.id, None)
                self._active[job.id] = job
                job.status = "active"
            try:
                await job.run()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                LOGGER.exception("worker %s failed for job %s", worker_number, job.id)
            finally:
                async with self._condition:
                    self._active.pop(job.id, None)
                    self._jobs.pop(job.id, None)

    async def cancel(self, job_id: str, user_id: int) -> tuple[bool, bool]:
        """Request cancellation. Returns (found, was_active)."""
        async with self._condition:
            job = self._jobs.get(job_id)
            if job is None or job.user_id != user_id:
                return False, False
            was_active = job.id in self._active
            if not was_active:
                try:
                    self._queue.remove(job)
                except ValueError:
                    pass
                self._queued.pop(job.id, None)
                self._jobs.pop(job.id, None)
                job.status = "cancelled"
            job.request_cancel()
            self._condition.notify_all()
            return True, was_active

    async def clear_queued(self) -> int:
        async with self._condition:
            jobs = list(self._queue)
            self._queue.clear()
            for job in jobs:
                self._queued.pop(job.id, None)
                self._jobs.pop(job.id, None)
                job.status = "cancelled"
                job.request_cancel()
            self._condition.notify_all()
        for job in jobs:
            await job.delete_progress()
        return len(jobs)

    async def get(self, job_id: str) -> Optional[ProxyJob]:
        async with self._condition:
            return self._jobs.get(job_id)

    async def queued_count(self) -> int:
        async with self._condition:
            return len(self._queue)

    async def active_count(self) -> int:
        async with self._condition:
            return len(self._active)
