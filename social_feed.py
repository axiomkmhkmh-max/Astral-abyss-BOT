# ============================================================
#  ASTRAL ABYSS RPG — Social Feed (live achievement broadcast)
#  (social_feed.py)
# ============================================================
# وقتی یه اتفاقِ «بزرگ» می‌افته (ارتقای کلاس، قهرمانِ چالشِ هفته،
# قهرمانِ فصلِ PvP، کشتنِ تکی‌ی یه باسِ جهانی)، این ماژول خبرش رو
# به همه‌ی گروه‌هایی که ربات توشون فعاله پخش می‌کنه — از همون
# known_group_chat_ids تو group_system.py که برای /gbroadcast هم
# استفاده می‌شه. هدف: بازیکن‌ها همدیگه رو تو گروه ببینن و بهم
# انگیزه/رقابت بدن، نه فقط تنها بازی کنن.
#
# طراحی عمداً fire-and-forget و بی‌سروصداست: اگه یه گروه ربات رو
# بلاک کرده یا خطای دیگه‌ای بده، بی‌خیالِ همون یکی می‌شه و ادامه می‌ده.
# ============================================================
import asyncio

_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def broadcast_achievement(text: str, max_groups: int = 200):
    """متنِ دستاورد رو به آخرین max_groups گروهِ فعال می‌فرسته."""
    if _bot is None:
        return
    try:
        from group_system import known_group_chat_ids
        chat_ids = await asyncio.to_thread(known_group_chat_ids)
    except Exception:
        return

    for cid in chat_ids[:max_groups]:
        try:
            await _bot.send_message(cid, text, disable_web_page_preview=True)
        except Exception:
            pass
        await asyncio.sleep(0.05)  # رعایتِ ریت‌لیمیتِ تلگرام


def broadcast_achievement_sync(text: str):
    """معادلِ sync — برای جاهایی که تو یه تابعِ async نیستیم (هم‌الگو با logger.log_sync)."""
    if _bot is None:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast_achievement(text))
        else:
            loop.run_until_complete(broadcast_achievement(text))
    except Exception:
        pass
