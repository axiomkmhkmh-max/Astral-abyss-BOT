# ============================================================
#  ASTRAL ABYSS — 🩸 هندلرهای نفرین/دعا/آینه/طلسم (Telegram)
# ------------------------------------------------------------
#  «نفرین» و «دعا» باید ریپلایِ رویِ یه بازیکنِ دیگه باشن. «آینه» و
#  «طلسم» و «جدول نفرین» نیازی به ریپلای ندارن. منطقِ واقعی تو
#  curse_system.py — این فایل فقط UI و لیدربرده.
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.types import Message

from database import aget_player, asave_player, player_lock
from logger import log_sync
import curse_system as curses


def _target_from_reply(msg: Message) -> tuple[int | None, str | None, str | None]:
    """برمی‌گردونه (uid, name, error) — اگه ریپلای معتبر نباشه uid=None و error پر می‌شه."""
    r = msg.reply_to_message
    if not r or not r.from_user:
        return None, None, "برای این کار باید رویِ پیامِ یه بازیکنِ دیگه ریپلای کنی."
    if r.from_user.is_bot:
        return None, None, "رو من اثر نمی‌کنه 😼"
    if r.from_user.id == msg.from_user.id:
        return None, None, "رو خودت که نمی‌شه! یکی دیگه رو انتخاب کن."
    return r.from_user.id, r.from_user.first_name or "یه پیشی ناشناس", None


async def cmd_curse(msg: Message):
    uid = msg.from_user.id
    target_uid, target_name, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"🩸 {err}")
        return

    async with player_lock(uid):
        player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    async with player_lock(target_uid):
        target = await aget_player(target_uid)
        if not target:
            await msg.reply("🩸 این بازیکن هنوز بازی رو شروع نکرده.")
            return
        result = curses.apply_curse(target, by_uid=uid)
        await asave_player(target_uid, target)

    await curses.record_curse(msg.chat.id, uid, player.get("name", "—"), target_uid, target_name)
    await msg.reply(
        f"🩸 **نفرین!**\n\n{player.get('name','یکی')} یه نفرین فرستاد سمتِ {target_name}.\n"
        f"{result['flavor']}\n\n"
        f"✨ اثر: {result['label']} (تا {result['seconds']//60} دقیقه)\n"
        f"🪞 {target_name} می‌تونه بنویسه «آینه» تا شانس داشته باشه برش گردونه!"
    )
    log_sync(f"🩸 CURSE — {player.get('name')} ({uid}) → {target_name} ({target_uid})", "CURSE")


async def cmd_bless(msg: Message):
    uid = msg.from_user.id
    target_uid, target_name, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"🙏 {err}")
        return

    async with player_lock(uid):
        player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    async with player_lock(target_uid):
        target = await aget_player(target_uid)
        if not target:
            await msg.reply("🙏 این بازیکن هنوز بازی رو شروع نکرده.")
            return
        result = curses.apply_bless(target)
        await asave_player(target_uid, target)

    await curses.record_bless(msg.chat.id, uid, player.get("name", "—"), target_uid, target_name)
    await msg.reply(
        f"🙏 **دعا!**\n\n{player.get('name','یکی')} براش دعا کرد.\n"
        f"{result['flavor']}\n\n"
        f"✨ اثر: {result['label']} (تا {result['seconds']//60} دقیقه)"
    )
    log_sync(f"🙏 BLESS — {player.get('name')} ({uid}) → {target_name} ({target_uid})", "CURSE")


async def cmd_mirror(msg: Message):
    uid = msg.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
            return
        result = curses.try_mirror(player)
        if not result["ok"]:
            await msg.reply("🪞 الان هیچ نفرینی روت نیست که بخوای برگردونی.")
            return
        await asave_player(uid, player)

    original_uid = result.get("original_curser")

    if not result["bounced"]:
        await msg.reply(curses.FLAVOR_MIRROR_FAIL)
        return

    await msg.reply(curses.FLAVOR_MIRROR_SUCCESS)

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
    log_sync(f"🪞 MIRROR — {player.get('name')} ({uid}) bounced={result['bounced']}", "CURSE")


async def cmd_random_spell(msg: Message):
    uid = msg.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
            return
        result = curses.cast_random_spell(player)
        await asave_player(uid, player)

    await msg.reply(
        f"🔮 **طلسمِ شانسی**\n\n{result['flavor']}\n\n"
        f"{'✨' if result['good'] else '🫠'} اثر: {result['label']} (تا {result['seconds']//60} دقیقه)"
    )
    log_sync(f"🔮 SPELL — {player.get('name')} ({uid}) good={result['good']}", "CURSE")


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


def register_curse_handlers(dp, bot):
    dp.message.register(cmd_curse, F.text == "نفرین")
    dp.message.register(cmd_bless, F.text == "دعا")
    dp.message.register(cmd_mirror, F.text == "آینه")
    dp.message.register(cmd_random_spell, F.text == "طلسم")
    dp.message.register(cmd_curse_board, F.text == "جدول نفرین")
