from __future__ import annotations

from .models import JobStats


WELCOME_TEXT = """✦ ᴘʀᴏxʏ ᴄʜᴇᴄᴋᴇʀ

ᴀ ᴘʀᴏғᴇssɪᴏɴᴀʟ ᴀsʏɴᴄ ᴘʀᴏxʏ ᴠᴀʟɪᴅᴀᴛᴏʀ.

→ sᴇɴᴅ ᴏɴᴇ ᴘʀᴏxʏ, ᴍᴜʟᴛɪᴘʟᴇ ʟɪɴᴇs, ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴛᴇxᴛ ғɪʟᴇ ᴡɪᴛʜ /prxy.
→ ᴏɴʟʏ ᴡᴏʀᴋɪɴɢ ᴘʀᴏxɪᴇs ᴀʀᴇ ʀᴇᴛᴜʀɴᴇᴅ.

✧ ᴜsᴇ ᴛʜᴇ ᴍᴇɴᴜ ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ."""


HELP_TEXT = """⌁ ʜᴏᴡ ᴛᴏ ᴜsᴇ

◆ ʟɪɴᴇ ᴄʜᴇᴄᴋ
sᴇɴᴅ:
/prxy 1.2.3.4:8080

◆ ᴍᴜʟᴛɪᴘʟᴇ ᴄʜᴇᴄᴋ
sᴇɴᴅ /prxy ғᴏʟʟᴏᴡᴇᴅ ʙʏ ᴍᴜʟᴛɪᴘʟᴇ ᴘʀᴏxʏ ʟɪɴᴇs.

◆ ғɪʟᴇ ᴄʜᴇᴄᴋ
ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴛᴇxᴛ ғɪʟᴇ ᴡɪᴛʜ /prxy.
ᴍᴀxɪᴍᴜᴍ ғɪʟᴇ sɪᴢᴇ: 20 ᴍʙ.

◆ ғᴏʀᴍᴀᴛs
ɪᴘ:ᴘᴏʀᴛ, ʜᴛᴛᴘ://ɪᴘ:ᴘᴏʀᴛ, sᴏᴄᴋs4://ɪᴘ:ᴘᴏʀᴛ,
sᴏᴄᴋs5://ɪᴘ:ᴘᴏʀᴛ, ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛᴇᴅ ᴀɴᴅ ɪᴘᴠ6 ᴘʀᴏxɪᴇs.

⌁ ᴘʀᴏɢʀᴇss ᴄʜᴇᴄᴋs ᴄᴀɴ ʙᴇ sᴛᴏᴘᴘᴇᴅ ᴜsɪɴɢ ᴛʜᴇ ᴄᴀɴᴄᴇʟ ʙᴜᴛᴛᴏɴ."""


COMMANDS_TEXT = """⌘ ᴄᴏᴍᴍᴀɴᴅs

/prxy — ᴄʜᴇᴄᴋ ᴏɴᴇ ᴏʀ ᴍᴜʟᴛɪᴘʟᴇ ᴘʀᴏxɪᴇs
/start — ᴏᴘᴇɴ ᴛʜᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇɴᴜ

✦ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴛᴇxᴛ ғɪʟᴇ ᴡɪᴛʜ /prxy ᴛᴏ ᴄʜᴇᴄᴋ ᴛʜᴇ ᴇɴᴛɪʀᴇ ғɪʟᴇ.
✦ ᴛʜᴇ ᴄᴀɴᴄᴇʟ ᴄᴏɴᴛʀᴏʟ ᴀᴘᴘᴇᴀʀs ᴏɴʟʏ ᴡʜɪʟᴇ ᴀ ᴊᴏʙ ɪs ʀᴜɴɴɪɴɢ."""


INVALID_INPUT = "⊘ ɴᴏ ᴠᴀʟɪᴅ ᴘʀᴏxʏ ᴇɴᴛʀɪᴇs ᴡᴇʀᴇ ғᴏᴜɴᴅ."
FILE_TOO_LARGE = "⊘ ᴛʜɪs ғɪʟᴇ ɪs ʟᴀʀɢᴇʀ ᴛʜᴀɴ 20 ᴍʙ."
NEED_INPUT = "⊘ sᴇɴᴅ ᴀ ᴘʀᴏxʏ ʟɪɴᴇ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴛᴇxᴛ ғɪʟᴇ ᴡɪᴛʜ /prxy."
BUSY = "⊘ ʏᴏᴜʀ ᴊᴏʙ ǫᴜᴇᴜᴇ ɪs ғᴜʟʟ. ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ᴀ ᴊᴏʙ ᴛᴏ ғɪɴɪsʜ."


def queued_text(total: int) -> str:
    return f"⌁ ᴊᴏʙ ǫᴜᴇᴜᴇᴅ\n\n→ ᴠᴀʟɪᴅ ᴘʀᴏxɪᴇs: {total}\n→ ᴛʜᴇ ᴄʜᴇᴄᴋ ᴡɪʟʟ sᴛᴀʀᴛ sʜᴏʀᴛʟʏ."


def progress_text(stats: JobStats) -> str:
    return f"""⌁ ᴘʀᴏxʏ ᴄʜᴇᴄᴋɪɴɢ sᴛᴀʀᴛᴇᴅ

━━━━━━━━━━━━━━
ᴛᴏᴛᴀʟ: {stats.valid_entries:,}
ᴄʜᴇᴄᴋᴇᴅ: {stats.checked:,}
ᴡᴏʀᴋɪɴɢ: {stats.working:,}
ʀᴇᴍᴀɪɴɪɴɢ: {stats.remaining:,}
━━━━━━━━━━━━━━

→ ᴄᴏɴᴄᴜʀʀᴇɴᴛ ᴄʜᴇᴄᴋs ᴀʀᴇ ʀᴜɴɴɪɴɢ."""


def final_text(stats: JobStats, cancelled: bool = False) -> str:
    title = "⊘ ᴄʜᴇᴄᴋɪɴɢ ᴄᴀɴᴄᴇʟʟᴇᴅ" if cancelled else "✓ ᴄʜᴇᴄᴋɪɴɢ ᴄᴏᴍᴘʟᴇᴛᴇᴅ"
    attachment_line = (
        "✦ ᴏɴʟʏ ᴡᴏʀᴋɪɴɢ ᴘʀᴏxɪᴇs ᴡɪʟʟ ʙᴇ ᴀᴛᴛᴀᴄʜᴇᴅ."
        if stats.working
        else "⊘ ɴᴏ ᴡᴏʀᴋɪɴɢ ᴘʀᴏxʏ ғɪʟᴇ ᴡᴀs ғᴏᴜɴᴅ."
    )
    return f"""{title}

━━━━━━━━━━━━━━
✦ ʀᴇᴄᴇɪᴠᴇᴅ: {stats.received_lines:,}
◆ ᴠᴀʟɪᴅ ᴇɴᴛʀɪᴇs: {stats.valid_entries:,}
✓ ᴄʜᴇᴄᴋᴇᴅ: {stats.checked:,}
✓ ᴡᴏʀᴋɪɴɢ: {stats.working:,}
⊘ ɴᴏᴛ ᴡᴏʀᴋɪɴɢ: {stats.failed:,}
→ ᴛɪᴍᴇ ᴛᴀᴋᴇɴ: {stats.elapsed_seconds:.1f} s
━━━━━━━━━━━━━━

{attachment_line}"""


def error_text(detail: str) -> str:
    return f"⊘ {detail}"
