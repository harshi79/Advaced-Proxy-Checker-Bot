from __future__ import annotations

import io
import logging
import re
from collections import defaultdict, deque
from time import monotonic
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, FSInputFile, Message

from .config import Settings
from .jobs import JobManager, ProxyJob
from .parser import decode_text, parse_proxy_text
from .texts import (
    BUSY,
    COMMANDS_TEXT,
    FILE_TOO_LARGE,
    HELP_TEXT,
    INVALID_INPUT,
    NEED_INPUT,
    WELCOME_TEXT,
    error_text,
    queued_text,
)
from .ui import back_keyboard, cancel_keyboard, main_keyboard

LOGGER = logging.getLogger(__name__)
_PRXY_CAPTION = re.compile(r"^/prxy(?:@\w+)?(?:\s|$)", re.IGNORECASE)


class BotHandlers:
    def __init__(self, bot: Bot, settings: Settings, jobs: JobManager) -> None:
        self.bot = bot
        self.settings = settings
        self.jobs = jobs
        self.router = Router(name="proxy-checker")
        self._requests: dict[int, deque[float]] = defaultdict(deque)
        self._register()

    def _register(self) -> None:
        self.router.message.register(self.start, Command("start"))
        self.router.message.register(self.proxy_command, Command("prxy"))
        self.router.message.register(self.restart, Command("restart"))
        self.router.message.register(self.document_command, F.document)
        self.router.callback_query.register(self.menu_help, F.data == "menu:help")
        self.router.callback_query.register(self.menu_commands, F.data == "menu:cmds")
        self.router.callback_query.register(self.menu_back, F.data == "menu:back")
        self.router.callback_query.register(self.cancel_job, F.data.startswith("job:cancel:"))

    async def start(self, message: Message) -> None:
        if not message.from_user:
            return
        if self.settings.welcome_image.exists():
            await message.answer_photo(
                photo=FSInputFile(self.settings.welcome_image),
                caption=WELCOME_TEXT,
                reply_markup=main_keyboard(),
            )
        else:
            await message.answer(WELCOME_TEXT, reply_markup=main_keyboard())

    async def menu_help(self, query: CallbackQuery) -> None:
        await query.answer()
        if not query.message:
            return
        await self._edit_menu(query.message, HELP_TEXT, back_keyboard())

    async def menu_commands(self, query: CallbackQuery) -> None:
        await query.answer()
        if not query.message:
            return
        await self._edit_menu(query.message, COMMANDS_TEXT, back_keyboard())

    async def menu_back(self, query: CallbackQuery) -> None:
        await query.answer()
        if not query.message:
            return
        await self._edit_menu(query.message, WELCOME_TEXT, main_keyboard())

    async def _edit_menu(self, message: Message, text: str, keyboard) -> None:
        try:
            if message.photo:
                await message.edit_caption(caption=text, reply_markup=keyboard)
            else:
                await message.edit_text(text=text, reply_markup=keyboard)
        except TelegramBadRequest:
            # The user may have opened the menu from an old/deleted message.
            LOGGER.debug("menu message could not be edited", exc_info=True)

    async def proxy_command(self, message: Message, command: CommandObject) -> None:
        document = None
        source_name = "proxies.txt"
        text: Optional[str] = None

        if message.reply_to_message and message.reply_to_message.document:
            document = message.reply_to_message.document
            source_name = document.file_name or source_name
        elif message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
        elif command.args and command.args.strip():
            text = command.args

        await self._start_proxy_job(message, text=text, document=document, source_name=source_name)

    async def document_command(self, message: Message) -> None:
        caption = message.caption or ""
        if not _PRXY_CAPTION.match(caption):
            return
        await self._start_proxy_job(
            message,
            text=None,
            document=message.document,
            source_name=message.document.file_name if message.document else "proxies.txt",
        )

    async def _start_proxy_job(
        self,
        message: Message,
        *,
        text: Optional[str],
        document,
        source_name: str,
    ) -> None:
        if not message.from_user:
            return
        user_id = message.from_user.id
        if self._rate_limited(user_id):
            await message.answer("⊘ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ʙᴇғᴏʀᴇ sᴜʙᴍɪᴛᴛɪɴɢ ᴀɴᴏᴛʜᴇʀ ᴊᴏʙ.")
            return

        try:
            if document is not None:
                text = await self._download_text(document)
            if not text or not text.strip():
                await message.answer(NEED_INPUT)
                return
            parsed = parse_proxy_text(text)
        except ValueError as exc:
            await message.answer(error_text(str(exc)))
            return
        except Exception:  # noqa: BLE001
            LOGGER.exception("input processing failed for user %s", user_id)
            await message.answer("⊘ ᴛʜᴇ ɪɴᴘᴜᴛ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ ʀᴇᴀᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀ ᴛᴇxᴛ ғɪʟᴇ.")
            return

        if not parsed.valid_entries:
            await message.answer(
                f"{INVALID_INPUT}\n\n→ ʀᴇᴄᴇɪᴠᴇᴅ: {parsed.received_lines:,}\n→ ɪɴᴠᴀʟɪᴅ: {parsed.invalid_lines:,}"
            )
            return

        # Generate the short ID before sending the status message so its
        # inline cancel button is valid from the first frame.
        temporary_job = ProxyJob(
            bot=self.bot,
            settings=self.settings,
            checker=self.jobs.checker,
            check_gate=self.jobs.check_gate,
            chat_id=message.chat.id,
            user_id=user_id,
            parse_result=parsed,
            progress_message_id=0,
            source_name=source_name,
        )
        status_message = await message.answer(
            queued_text(len(parsed.valid_entries)),
            reply_markup=cancel_keyboard(temporary_job.id),
        )
        temporary_job.progress_message_id = status_message.message_id
        accepted, reason = await self.jobs.submit(temporary_job)
        if not accepted:
            await temporary_job.delete_progress()
            await message.answer(f"{BUSY}\n\n→ {reason}")

    async def _download_text(self, document) -> str:
        if document.file_size and document.file_size > self.settings.max_file_bytes:
            raise ValueError(FILE_TOO_LARGE.replace("⊘ ", ""))
        buffer = io.BytesIO()
        await self.bot.download(document, destination=buffer)
        data = buffer.getvalue()
        if len(data) > self.settings.max_file_bytes:
            raise ValueError(FILE_TOO_LARGE.replace("⊘ ", ""))
        return decode_text(data)

    def _rate_limited(self, user_id: int) -> bool:
        now = monotonic()
        history = self._requests[user_id]
        while history and now - history[0] > 60:
            history.popleft()
        if len(history) >= 3:
            return True
        history.append(now)
        return False

    async def restart(self, message: Message) -> None:
        if not message.from_user or message.from_user.id != self.settings.owner_id:
            await message.answer("⊘ ᴏᴡɴᴇʀ ᴏɴʟʏ.")
            return
        cleared = await self.jobs.clear_queued()
        active = await self.jobs.active_count()
        await message.answer(
            "✓ ǫᴜᴇᴜᴇ ʀᴇғʀᴇsʜᴇᴅ\n\n"
            f"→ ǫᴜᴇᴜᴇᴅ ᴊᴏʙs ᴄʟᴇᴀʀᴇᴅ: {cleared:,}\n"
            f"→ ᴀᴄᴛɪᴠᴇ sᴇssɪᴏɴs ᴜɴᴛᴏᴜᴄʜᴇᴅ: {active:,}"
        )

    async def cancel_job(self, query: CallbackQuery) -> None:
        if not query.message or not query.from_user:
            await query.answer()
            return
        job_id = (query.data or "").split(":")[-1]
        job = await self.jobs.get(job_id)
        if job is None or job.user_id != query.from_user.id:
            await query.answer("ᴛʜɪs ᴊᴏʙ ɪs ɴᴏᴛ ʏᴏᴜʀs.", show_alert=True)
            return

        job.mark_progress_deleted()
        found, was_active = await self.jobs.cancel(job_id, query.from_user.id)
        if not found:
            await query.answer("ᴛʜɪs ᴊᴏʙ ʜᴀs ᴀʟʀᴇᴀᴅʏ ғɪɴɪsʜᴇᴅ.")
            return
        try:
            await query.message.delete()
        except TelegramBadRequest:
            pass
        if was_active:
            await query.answer("ᴄᴀɴᴄᴇʟʟɪɴɢ — ᴄᴜʀʀᴇɴᴛ ᴄʜᴇᴄᴋs ᴡɪʟʟ ғɪɴɪsʜ.")
        else:
            await query.answer("ǫᴜᴇᴜᴇᴅ ᴊᴏʙ ᴄᴀɴᴄᴇʟʟᴇᴅ.")


def build_handlers(bot: Bot, settings: Settings, jobs: JobManager) -> BotHandlers:
    return BotHandlers(bot, settings, jobs)
