from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BotCommand, BotCommandScopeChat, Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .bot import build_handlers
from .checker import ProxyChecker
from .config import Settings
from .jobs import JobManager

settings = Settings.from_env()
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

if settings.bot_token:
    bot = Bot(settings.bot_token)
else:
    # Keep module importable for local tooling; startup gives the useful error.
    bot = Bot("000000000:placeholder")

dispatcher = Dispatcher()
checker = ProxyChecker(settings)
jobs = JobManager(settings, checker)
handlers = build_handlers(bot, settings, jobs)
dispatcher.include_router(handlers.router)
_polling_task: asyncio.Task[None] | None = None


async def _set_commands() -> None:
    public_commands = [
        BotCommand(command="start", description="ᴏᴘᴇɴ ᴛʜᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇɴᴜ"),
        BotCommand(command="prxy", description="ᴄʜᴇᴄᴋ ᴘʀᴏxɪᴇs"),
    ]
    await bot.set_my_commands(public_commands)
    await bot.set_my_commands(
        [
            *public_commands,
            BotCommand(command="restart", description="ᴏᴡɴᴇʀ ǫᴜᴇᴜᴇ ʀᴇsᴇᴛ"),
        ],
        scope=BotCommandScopeChat(chat_id=settings.owner_id),
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _polling_task
    settings.validate()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await jobs.start()
    await _set_commands()

    if settings.telegram_webhook_url:
        LOGGER.info("starting Telegram webhook mode at %s", settings.telegram_webhook_url)
        await bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.webhook_secret or None,
            drop_pending_updates=True,
        )
    else:
        LOGGER.info("starting Telegram polling mode")
        await bot.delete_webhook(drop_pending_updates=True)
        _polling_task = asyncio.create_task(
            dispatcher.start_polling(bot, handle_signals=False, allowed_updates=dispatcher.resolve_used_update_types())
        )

    try:
        yield
    finally:
        if _polling_task:
            _polling_task.cancel()
            await asyncio.gather(_polling_task, return_exceptions=True)
            _polling_task = None
        else:
            try:
                await bot.delete_webhook()
            except TelegramNetworkError:
                LOGGER.warning("could not remove Telegram webhook during shutdown")
        await jobs.stop()
        await bot.session.close()


app = FastAPI(
    title="Advanced Proxy Checker Bot",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "ok"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="forbidden")
    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}
