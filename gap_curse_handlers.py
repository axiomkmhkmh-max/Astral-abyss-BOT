# ============================================================
#  ASTRAL ABYSS — 🩸 هندلرهای نفرین/دعا/آینه/طلسم (Gap dispatcher)
# ------------------------------------------------------------
#  پورتِ گپِ curse_handlers.py. منطق (curse_system.py) کاملاً مشترکه.
# ============================================================
from __future__ import annotations

from gap_types import Message
from gap_dispatcher import GapDispatcher

from database import aget_player, asave_player, player_lock
from logger import log_sync
import curse_system as curses


def _target_from_reply(msg: Message) -> tuple[int | None, str | None, str | None]:
    """⚠️ گپ (طبقِ چیزی که تا الان پورت شده) مفهومِ reply_to_message رو
    مثلِ تلگرام نمی‌ده؛ اگه/وقتی gap_types این رو اضافه کرد، همینجا
    `msg.reply_to_message` رو جایگزینِ این تابع کن. فعلاً برای اینکه
    فیچر کاملاً غیرفعال نمونه، یه حالتِ جایگزین داره: «نفرین @نام» —
    نیاز به نام/یوزرنیم به‌جایِ ریپلای.
    """
    return None, None, (
        "تو گپ هنوز ریپلای پشتیبانی نمی‌شه — فعلاً «آینه»، «طلسم» و "
        "«جدول نفرین» کار می‌کنن؛ «نفرین»/«دعا» منتظرِ پشتیبانیِ ریپلای تو گپن."
    )


async def cmd_curse(msg: Message):
    _, _, err = _target_from_reply(msg)
    await msg.answer(f"🩸 {err}")


async def cmd_bless(msg: Message):
    _, _, err = _target_from_reply(msg)
    await msg.answer(f"🙏 {err}")


async def cmd_mirror(msg: Message):
    uid = msg.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
            return
        result = curses.try_mirror(player)
        if not result["ok"]:
            await msg.answer("🪞 الان هیچ نفرینی روت نیست که بخوای برگردونی.")
            return
        await asave_player(uid, player)

    original_uid = result.get("original_curser")

    if not result["bounced"]:
        await msg.answer(curses.FLAVOR_MIRROR_FAIL)
        return

    await msg.answer(curses.FLAVOR_MIRROR_SUCCESS)

    if original_uid:
        async with player_lock(original_uid):
            original = await aget_player(original_uid)
            if original:
                back = curses.apply_curse(original, by_uid=uid)
                await asave_player(original_uid, original)
                await curses.record_mirror(
                    msg.chat.id, uid, player.get("name", "—"),
                    original_uid, original.get("name", "—"),
                )
        try:
            await msg.bot.send_message(
                original_uid,
                f"🪞 نفرینی که فرستاده بودی برگشت خورد تو خودت! ({back['label']})"
            )
        except Exception:
            pass
    log_sync(f"🪞 MIRROR (Gap) — {player.get('name')} ({uid}) bounced={result['bounced']}", "CURSE")


async def cmd_random_spell(msg: Message):
    uid = msg.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
            return
        result = curses.cast_random_spell(player)
        await asave_player(uid, player)

    await msg.answer(
        f"🔮 **طلسمِ شانسی**\n\n{result['flavor']}\n\n"
        f"{'✨' if result['good'] else '🫠'} اثر: {result['label']} (تا {result['seconds']//60} دقیقه)"
    )
    log_sync(f"🔮 SPELL (Gap) — {player.get('name')} ({uid}) good={result['good']}", "CURSE")


def _board_lines(rows: list[dict], field: str, emoji: str) -> list[str]:
    if not rows:
        return ["— هنوز کسی نیست —"]
    return [f"{emoji} {r.get('name','—')} — {r.get(field,0)}" for r in rows]


async def cmd_curse_board(msg: Message):
    board = await curses.get_leaderboard(msg.chat.id)
    text = (
        "📊 **جدولِ نفرین و دعا — همین گروه**\n\n"
        "🩸 **بیشترین نفرین‌شده:**\n" + "\n".join(_board_lines(board["most_cursed"], "been_cursed", "🩸")) + "\n\n"
        "😈 **بیشترین نفرین‌کننده:**\n" + "\n".join(_board_lines(board["most_cursers"], "cursed_others", "😈")) + "\n\n"
        "🪞 **بیشترین آینه‌کننده:**\n" + "\n".join(_board_lines(board["most_mirrors"], "mirror_bounces", "🪞"))
    )
    await msg.answer(text)


def register_gap_curse_handlers(dp: GapDispatcher):
    dp.register_message(cmd_curse, text="نفرین")
    dp.register_message(cmd_bless, text="دعا")
    dp.register_message(cmd_mirror, text="آینه")
    dp.register_message(cmd_random_spell, text="طلسم")
    dp.register_message(cmd_curse_board, text="جدول نفرین")
