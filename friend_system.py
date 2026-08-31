# ============================================================
#  ASTRAL ABYSS RPG — Friend System (core)
#  (friend_system.py)
# ============================================================
# سیستمِ دوستی: درخواست/تایید/حذف، لیستِ دوستان با وضعیتِ آنلاین،
# هدیه‌ی روزانه‌ی Zen به هرکدوم (سقف‌دار — نه یه راهِ دورزدنِ اقتصاد)،
# و مقایسه‌ی استتِ دو بازیکن کنارِ هم.
#
# همه‌ی عملیاتِ دوطرفه (افزودن/حذف/هدیه) زیرِ player_lock_pair
# می‌رن تا اتمیک باشن — دقیقاً همون الگوی bank_system.py.
# ============================================================
import time

from database import aget_player, asave_player, player_lock, player_lock_pair, all_players

MAX_FRIENDS = 50
GIFT_AMOUNT = 1000              # مقدارِ ثابتِ هر هدیه
GIFT_COOLDOWN = 24 * 3600        # هر جفت‌دوست، هر ۲۴ ساعت یه‌بار
DAILY_GIFT_CAP = 10              # حداکثر چندتا هدیه در روز (ضدِ فارمِ Zen بینِ چند اکانت)


def _friends(player: dict) -> list[int]:
    return player.setdefault("friends", [])


def is_friend(player: dict, other_uid: int) -> bool:
    return other_uid in _friends(player)


def resolve_player_target(arg: str, requester_uid: int) -> int | None:
    """ورودی می‌تونه @username، user_id یا اسمِ بازیکن باشه."""
    from pvp_handlers import _resolve_track_target
    return _resolve_track_target(arg, requester_uid)


# ─── درخواستِ دوستی ──────────────────────────────────────────
async def send_request(sender_uid: int, target_uid: int) -> dict:
    if sender_uid == target_uid:
        return {"ok": False, "msg": "❌ نمی‌تونی به خودت درخواست بدی!"}

    async with player_lock_pair(sender_uid, target_uid):
        sender = await aget_player(sender_uid)
        target = await aget_player(target_uid)
        if not sender or not target:
            return {"ok": False, "msg": "❌ بازیکن پیدا نشد."}

        if is_friend(sender, target_uid):
            return {"ok": False, "msg": "❌ قبلاً باهم دوستین."}
        if len(_friends(sender)) >= MAX_FRIENDS:
            return {"ok": False, "msg": f"❌ لیستِ دوستات پره (سقف {MAX_FRIENDS} نفر)."}
        if len(_friends(target)) >= MAX_FRIENDS:
            return {"ok": False, "msg": "❌ لیستِ دوستانِ اون بازیکن پره."}

        out = sender.setdefault("friend_requests_out", [])
        inn = target.setdefault("friend_requests_in", [])

        if target_uid in out:
            return {"ok": False, "msg": "❌ قبلاً بهش درخواست دادی — منتظرِ جوابش باش."}

        # اگه طرف از قبل به ما درخواست داده بود، این یعنی قبولِ متقابل

        if sender_uid in target.get("friend_requests_out", []):
            # طرف خودش قبلاً به ما درخواست داده بود → مستقیم دوست می‌شیم
            target["friend_requests_out"].remove(sender_uid)
            sender.setdefault("friend_requests_in", [])
            if sender_uid in sender["friend_requests_in"]:
                sender["friend_requests_in"].remove(sender_uid)
            _friends(sender).append(target_uid)
            _friends(target).append(sender_uid)
            await asave_player(sender_uid, sender)
            await asave_player(target_uid, target)
            return {"ok": True, "mutual": True, "target_name": target.get("name", "—")}

        out.append(target_uid)
        inn.append(sender_uid)
        await asave_player(sender_uid, sender)
        await asave_player(target_uid, target)
        return {"ok": True, "mutual": False, "target_name": target.get("name", "—")}


async def accept_request(uid: int, requester_uid: int) -> dict:
    async with player_lock_pair(uid, requester_uid):
        player = await aget_player(uid)
        requester = await aget_player(requester_uid)
        if not player or not requester:
            return {"ok": False, "msg": "❌ بازیکن پیدا نشد."}

        inn = player.setdefault("friend_requests_in", [])
        if requester_uid not in inn:
            return {"ok": False, "msg": "❌ همچین درخواستی نداری."}

        inn.remove(requester_uid)
        req_out = requester.setdefault("friend_requests_out", [])
        if uid in req_out:
            req_out.remove(uid)

        if not is_friend(player, requester_uid):
            _friends(player).append(requester_uid)
        if not is_friend(requester, uid):
            _friends(requester).append(uid)

        await asave_player(uid, player)
        await asave_player(requester_uid, requester)
        return {"ok": True, "name": requester.get("name", "—")}


async def decline_request(uid: int, requester_uid: int) -> dict:
    async with player_lock_pair(uid, requester_uid):
        player = await aget_player(uid)
        requester = await aget_player(requester_uid)
        if not player:
            return {"ok": False, "msg": "❌ بازیکن پیدا نشد."}

        inn = player.setdefault("friend_requests_in", [])
        if requester_uid in inn:
            inn.remove(requester_uid)
        await asave_player(uid, player)

        if requester:
            req_out = requester.setdefault("friend_requests_out", [])
            if uid in req_out:
                req_out.remove(uid)
            await asave_player(requester_uid, requester)

        return {"ok": True}


async def remove_friend(uid: int, other_uid: int) -> dict:
    async with player_lock_pair(uid, other_uid):
        player = await aget_player(uid)
        other = await aget_player(other_uid)
        if not player:
            return {"ok": False, "msg": "❌ بازیکن پیدا نشد."}

        if other_uid in _friends(player):
            _friends(player).remove(other_uid)
        await asave_player(uid, player)

        if other:
            if uid in _friends(other):
                _friends(other).remove(uid)
            await asave_player(other_uid, other)

        return {"ok": True}


# ─── هدیه ─────────────────────────────────────────────────────
def _today_gift_count(player: dict) -> int:
    """چندتا هدیه امروز فرستاده (بر اساسِ friend_gift_sent_at)."""
    sent_at = player.get("friend_gift_sent_at", {})
    cutoff = time.time() - 24 * 3600
    return sum(1 for ts in sent_at.values() if ts >= cutoff)


def gift_cooldown_remaining(player: dict, target_uid: int) -> int:
    sent_at = player.get("friend_gift_sent_at", {})
    last = sent_at.get(str(target_uid), 0)
    remain = int(last + GIFT_COOLDOWN - time.time())
    return max(0, remain)


async def send_gift(sender_uid: int, target_uid: int) -> dict:
    async with player_lock_pair(sender_uid, target_uid):
        sender = await aget_player(sender_uid)
        target = await aget_player(target_uid)
        if not sender or not target:
            return {"ok": False, "msg": "❌ بازیکن پیدا نشد."}

        if not is_friend(sender, target_uid):
            return {"ok": False, "msg": "❌ فقط به دوستات می‌تونی هدیه بدی."}

        remain = gift_cooldown_remaining(sender, target_uid)
        if remain > 0:
            h = remain // 3600
            m = (remain % 3600) // 60
            return {"ok": False, "msg": f"⏳ برای این دوست باید {h} ساعت و {m} دقیقه‌ی دیگه صبر کنی."}

        if _today_gift_count(sender) >= DAILY_GIFT_CAP:
            return {"ok": False, "msg": f"❌ سقفِ هدیه‌ی امروزت پر شده (حداکثر {DAILY_GIFT_CAP} هدیه در روز)."}

        if sender.get("zen", 0) < GIFT_AMOUNT:
            return {"ok": False, "msg": f"❌ Zen کافی نداری (هدیه {GIFT_AMOUNT:,}ه)."}

        sender["zen"] = sender.get("zen", 0) - GIFT_AMOUNT
        target["zen"] = target.get("zen", 0) + GIFT_AMOUNT
        sender.setdefault("friend_gift_sent_at", {})[str(target_uid)] = time.time()
        sender["friend_gifts_sent_total"] = sender.get("friend_gifts_sent_total", 0) + 1

        await asave_player(sender_uid, sender)
        await asave_player(target_uid, target)
        return {"ok": True, "amount": GIFT_AMOUNT, "target_name": target.get("name", "—")}


# ─── نمایش ────────────────────────────────────────────────────
def friends_list_text(player: dict) -> str:
    friends = _friends(player)
    inn = player.get("friend_requests_in", [])
    out = player.get("friend_requests_out", [])

    lines = [f"👥 **دوستانِ تو ({len(friends)}/{MAX_FRIENDS})**\n"]
    if not friends:
        lines.append("هنوز هیچ دوستی اضافه نکردی.\n")
    else:
        all_p = all_players()
        for fid in friends:
            fp = all_p.get(str(fid))
            if not fp:
                continue
            try:
                from bot import is_online
                online = "🟢" if is_online(fid) else "🔴"
            except Exception:
                online = "⚪️"
            lines.append(
                f"{online} **{fp.get('name','—')}** — Lv.{fp.get('level',1)} "
                f"{_class_emoji(fp.get('class'))}\n"
            )

    if inn:
        lines.append(f"\n📥 {len(inn)} درخواستِ دوستیِ جدید — «📥 درخواست‌ها» رو بزن.")
    if out:
        lines.append(f"📤 {len(out)} درخواستِ درحالِ انتظار.")

    return "".join(lines)


def _class_emoji(cls: str | None) -> str:
    return {"wizard": "🧙", "adventurer": "🗡", "merchant": "💰", "healer": "✨"}.get(cls or "", "❔")


def requests_list_text(player: dict) -> str:
    inn = player.get("friend_requests_in", [])
    if not inn:
        return "📥 هیچ درخواستِ دوستیِ جدیدی نداری."
    all_p = all_players()
    lines = ["📥 **درخواست‌های دوستی:**\n"]
    for rid in inn:
        rp = all_p.get(str(rid))
        if rp:
            lines.append(f"• **{rp.get('name','—')}** — Lv.{rp.get('level',1)} {_class_emoji(rp.get('class'))}\n")
    return "".join(lines)


def compare_text(player: dict, other: dict) -> str:
    s1, s2 = player.get("stats", {}), other.get("stats", {})

    def row(label, v1, v2, unit=""):
        return f"{label}: **{v1:,}**{unit}  در مقابل  **{v2:,}**{unit}"

    lines = [
        f"📊 **مقایسه: {player.get('name','—')} در مقابل {other.get('name','—')}**\n",
        row("📈 سطح", player.get("level", 1), other.get("level", 1)),
        row("❤️ HP", s1.get("max_hp", 0), s2.get("max_hp", 0)),
        row("⚔️ حمله", s1.get("atk", 0), s2.get("atk", 0)),
        row("🛡 دفاع", s1.get("def", 0), s2.get("def", 0)),
        row("💰 Zen", player.get("zen", 0), other.get("zen", 0)),
        row("🆚 بردِ PvP", player.get("pvp_wins", 0), other.get("pvp_wins", 0)),
    ]
    return "\n".join(lines)
