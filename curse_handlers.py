# ============================================================
#  ASTRAL ABYSS — 🩸 هندلرهای نفرین/دعا/آینه/طلسم (Telegram)
# ------------------------------------------------------------
#  «نفرین» و «دعا» باید ریپلایِ رویِ یه بازیکنِ دیگه باشن. «آینه» و
#  «طلسم» و «جدول نفرین» نیازی به ریپلای ندارن. منطقِ واقعی تو
#  curse_system.py — این فایل فقط UI و لیدربرده.
#
#  ⏳ ضد‌اسپم (همه‌ی عددها تو curse_system.COOLDOWNS):
#   • کولداونِ شخصی: نفرین ۱۰ دقیقه، دعا ۵ دقیقه، طلسم ۲۰ دقیقه
#   • هدف تا وقتی نفرینه یا تا ۱۰ دقیقه بعدش، نفرینِ تازه نمی‌گیره؛ تا وقتی دعا فعاله دعای تازه نمی‌گیره
#   • آینه برای هر نفرین فقط یه‌بار
#   • پیامِ «کولداون داری» حداکثر هر ۲۰ ثانیه یه‌بار میاد؛ تلاش‌های پشتِ‌هم بی‌صدا نادیده گرفته می‌شن
#   • «جدول نفرین» هر گروه حداکثر هر ۳۰ ثانیه یه‌بار
#   • نفرین/دعا/جدول فقط تو گروه معنی دارن؛ تو پیوی یه پیامِ کوتاه می‌گیرن
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


async def _soft_reply(msg: Message, uid: int, key: str, text: str) -> None:
    """پیامِ هشدار — ولی فقط گهگاه، تا خودِ هشدار اسپم نشه."""
    if curses.should_warn(uid, key):
        await msg.reply(text)


async def _refund(uid: int, action: str) -> None:
    """اگه عملیات به هدف نرسید، کولداونِ مصرف‌شده برمی‌گرده."""
    async with player_lock(uid):
        p = await aget_player(uid)
        if p:
            curses.clear_cooldown(p, action)
            await asave_player(uid, p)


async def _take_cooldown(msg: Message, uid: int, action: str, verb: str):
    """چکِ کولداون + مصرفش، زیرِ قفلِ خودِ بازیکن (تا پیام‌های هم‌زمان رد نشن).
    برمی‌گردونه player یا None (و خودش پیامِ مناسب رو می‌فرسته)."""
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await _soft_reply(msg, uid, "nostart", "❌ اول باید بازی رو شروع کنی: /start")
            return None
        left = curses.cooldown_left(player, action)
        if left > 0:
            await _soft_reply(msg, uid, action, f"⏳ تا {curses.fmt_wait(left)} دیگه نمی‌تونی {verb}.")
            return None
        curses.start_cooldown(player, action)
        await asave_player(uid, player)
        return player


async def _group_only(msg: Message) -> bool:
    """True یعنی تو پیوی‌ایم و کار نباید ادامه پیدا کنه."""
    if msg.chat.type == "private":
        await _soft_reply(msg, msg.from_user.id, "grouponly", "👥 این یکی فقط تو گروه کار می‌کنه.")
        return True
    return False


async def cmd_curse(msg: Message):
    uid = msg.from_user.id
    if await _group_only(msg):
        return
    target_uid, target_name, err = _target_from_reply(msg)
    if err:
        await _soft_reply(msg, uid, "curse_err", f"🩸 {err}")
        return

    player = await _take_cooldown(msg, uid, "نفرین", "نفرین کنی")
    if not player:
        return

    async with player_lock(target_uid):
        target = await aget_player(target_uid)
        if not target:
            refund, why = True, "🩸 این بازیکن هنوز بازی رو شروع نکرده."
        else:
            ok, wait = curses.can_receive_curse(target)
            if not ok:
                refund, why = True, f"🛡 {target_name} الان نفرینه یا تازه نفرین شده — تا {curses.fmt_wait(wait)} دیگه روش اثر نمی‌کنه."
            else:
                refund, why = False, ""
                result = curses.apply_curse(target, by_uid=uid)
                await asave_player(target_uid, target)

    if refund:
        await _refund(uid, "نفرین")
        await _soft_reply(msg, uid, "curse_deny", why)
        return

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
    if await _group_only(msg):
        return
    target_uid, target_name, err = _target_from_reply(msg)
    if err:
        await _soft_reply(msg, uid, "bless_err", f"🙏 {err}")
        return

    player = await _take_cooldown(msg, uid, "دعا", "دعا کنی")
    if not player:
        return

    async with player_lock(target_uid):
        target = await aget_player(target_uid)
        if not target:
            refund, why = True, "🙏 این بازیکن هنوز بازی رو شروع نکرده."
        else:
            ok, wait = curses.can_receive_bless(target)
            if not ok:
                refund, why = True, f"✨ {target_name} الان دعای فعال داره — تا {curses.fmt_wait(wait)} دیگه."
            else:
                refund, why = False, ""
                result = curses.apply_bless(target)
                await asave_player(target_uid, target)

    if refund:
        await _refund(uid, "دعا")
        await _soft_reply(msg, uid, "bless_deny", why)
        return

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
            await _soft_reply(msg, uid, "nostart", "❌ اول باید بازی رو شروع کنی: /start")
            return
        result = curses.try_mirror(player)
        if not result["ok"]:
            reason = result.get("reason")
            await _soft_reply(
                msg, uid, "mirror_no",
                "🪞 برای این نفرین قبلاً آینه رو امتحان کردی." if reason == "already_tried"
                else "🪞 الان هیچ نفرینی روت نیست که بخوای برگردونی.",
            )
            return
        await asave_player(uid, player)

    original_uid = result.get("original_curser")

    if not result["bounced"]:
        await msg.reply(curses.FLAVOR_MIRROR_FAIL)
        return

    await msg.reply(curses.FLAVOR_MIRROR_SUCCESS)

    if original_uid:
        back = None
        async with player_lock(original_uid):
            original = await aget_player(original_uid)
            if original:
                back = curses.apply_curse(original, by_uid=uid)
                await asave_player(original_uid, original)
                await curses.record_mirror(
                    msg.chat.id, uid, player.get("name", "—"),
                    original_uid, original.get("name", "—"),
                )
        if back:
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
    player = await _take_cooldown(msg, uid, "طلسم", "طلسم کنی")
    if not player:
        return
    async with player_lock(uid):
        player = await aget_player(uid)
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
    if await _group_only(msg):
        return
    # هر گروه حداکثر هر ۳۰ ثانیه یه‌بار؛ تکراری‌ها بی‌صدا نادیده گرفته می‌شن
    if not curses.mem_gate(("board", msg.chat.id), curses.BOARD_THROTTLE_SEC):
        return
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
