from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

OWNER_URL = "https://t.me/WhoEvenYori"


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⌁ ʜᴇʟᴘ", callback_data="menu:help"),
                InlineKeyboardButton(text="⌘ ᴄᴍᴅs", callback_data="menu:cmds"),
            ],
            [InlineKeyboardButton(text="♢ ᴏᴡɴᴇʀ", url=OWNER_URL)],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="← ʙᴀᴄᴋ", callback_data="menu:back")]]
    )


def cancel_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⊘ ᴄᴀɴᴄᴇʟ", callback_data=f"job:cancel:{job_id}")]
        ]
    )
