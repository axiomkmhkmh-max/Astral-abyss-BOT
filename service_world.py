"""The single global world boss (one shared HP bar for every group and private chat), group registry."""
import random
import time
import uuid

from pymongo import ReturnDocument

from data_bosses import BOSSES, BOSS_BY_ID
from data_crafting import tagged_name
from data_items import ALL, EVO_BY_RARITY
from data_weapons import ELEMENTS, RARITIES
from data_world import boss_gap_seconds, boss_hp_scale, day_id, season_pts_boss
import engine as E
from database import bump_counter, col, game_settings, try_cooldown
from service_combat import build_player
from service_economy import inv_add, roll_drop
from service_player import add_coins, add_xp, bump_quest, get_char
from service_worldcore import (WS_ID, active_levels, active_players, chronicle, get_world, invalidate, is_new_account,
                               season_add, world_adjust)


# ---- groups -------------------------------------------------------------------------
async def note_group(chat_id: int, title: str, level: int = None, lang: str = "fa"):
    now = int(time.time())
    upd = {"$set": {"title": (title or "")[:60], "last_active": now, "blocked": False},
           "$setOnInsert": {"chat_id": chat_id, "lang": lang, "auto_lang": lang}}
    if level:
        upd["$push"] = {"levels": {"$each": [int(level)], "$slice": -20}}
    await col("groups").update_one({"chat_id": chat_id}, upd, upsert=True)


async def group_doc(chat_id: int) -> dict:
    return await col("groups").find_one({"chat_id": chat_id}) or {"chat_id": chat_id, "lang": "fa"}


async def set_group_lang(chat_id: int, lang: str):
    await col("groups").update_one({"chat_id": chat_id}, {"$set": {"lang": lang, "lang_set": True}, "$setOnInsert": {"chat_id": chat_id}}, upsert=True)


def pick_boss(levels: list) -> dict:
    target = sorted(levels)[len(levels) // 2] if levels else 3
    return min(BOSSES, key=lambda b: abs(b["level"] - target))


# ---- boss lifecycle (one global boss) ---------------------------------------------------------------------------
async def active_boss(chat_id: int = None):
    """The one living global boss (chat_id is ignored; kept for old call sites)."""
    return await col("boss_sessions").find_one({"scope": "global", "active": True})


async def spawn_boss(chat_id: int = None, boss_id: str = None):
    """Spawn the global boss. Atomic: only one can exist (claimed through world_state.boss_id)."""
    st = await game_settings()
    ws, _ = await get_world(force=True)
    sid = uuid.uuid4().hex[:10]
    claim = await col("world_state").update_one(
        {"_id": WS_ID, "$or": [{"boss_id": None}, {"boss_id": {"$exists": False}}]}, {"$set": {"boss_id": sid}})
    if not claim.modified_count:
        return None
    try:
        levels = await active_levels()
        b = BOSS_BY_ID.get(boss_id) if boss_id else pick_boss(levels)
        scale = boss_hp_scale(await active_players(), ws.get("threat", 20), st)
        hp = max(1, int(b["hp"] * scale * float(st["boss_hp_mult"])))
        now = int(time.time())
        doc = {"_id": sid, "scope": "global", "boss_id": b["_id"], "name_fa": b["name_fa"], "name_en": b["name_en"], "level": b["level"],
               "hp": hp, "max_hp": hp, "trait": b["trait"], "active": True, "spawn_at": now, "scale": round(scale, 2),
               "expires_at": now + int(st["boss_duration_minutes"]) * 60, "contrib": {}, "nm": {}, "hits": 0, "last_hitter": None,
               "edit_at": 0, "msgs": {}, "refresh_at": now, "combo": 0, "last_at": 0, "feed": []}
        await col("boss_sessions").insert_one(doc)
    except Exception:
        await col("world_state").update_one({"_id": WS_ID, "boss_id": sid}, {"$set": {"boss_id": None}})
        raise
    invalidate()
    return doc


async def _end_global(doc: dict):
    """Free the boss slot and schedule the next spawn (threat shortens the gap)."""
    if doc.get("scope") != "global":
        return
    st = await game_settings()
    ws, _ = await get_world(force=True)
    gap = boss_gap_seconds(st, ws.get("threat", 20), random)
    await col("world_state").update_one({"_id": WS_ID, "boss_id": doc["_id"]}, {"$set": {"boss_id": None, "next_boss_at": int(time.time()) + gap}})
    invalidate()


def phase(doc: dict) -> int:
    f = doc["hp"] / doc["max_hp"]
    return 1 if f > 0.6 else 2 if f > 0.3 else 3


async def boss_hit(uid: int, sid: str):
    st = await game_settings()
    ch = await get_char(uid)
    if not ch:
        return "noreg", None
    if ch["level"] < int(st["boss_min_level"]):
        return "level", int(st["boss_min_level"])
    sess = await col("boss_sessions").find_one({"_id": sid, "active": True})
    if not sess or sess["expires_at"] <= time.time() or sess["hp"] <= 0:
        return "gone", None
    trait = sess.get("trait")
    wait = await try_cooldown(f"bosshit:{uid}", int(int(st["boss_hit_cooldown"]) * (1.5 if trait == "burn" else 1)))
    if wait:
        return "cool", wait
    b = BOSS_BY_ID[sess["boss_id"]]
    rng = random.Random()
    if trait == "dodge" and rng.random() < 0.40:  # (was hits % 5, but hits only grows on a landed hit -> evaded forever)
        return "evade", 0
    if trait == "illusion" and rng.random() < 0.30:
        return "evade", 0
    player = await build_player(ch)
    boss = E.new_fighter("Boss", b["level"], {"zanjutsu": 1, "kido": 1, "hakuda": b["defense"] * 2, "hoho": 1, "reiatsu": 1}, 10 ** 9, 100,
                         {"attack": 1, "element": ELEMENTS[sum(map(ord, b["_id"])) % 8], "skills": [], "weapon_type": "melee"}, armor=0)
    state = {"a": player, "b": boss, "turn": 1, "cur": "a", "first": "a", "done": False, "winner": None}
    ev = []
    E._deal(state, "a", 1.0, rng, ev, "atk")
    dmg = sum(e.get("n", 0) for e in ev if e["k"] == "hit")
    crit = any(e.get("c") for e in ev if e["k"] == "hit")
    if dmg <= 0:
        return "miss", 0
    # signature mechanics (the trait is chosen per boss in data_bosses)
    mult = 1.0
    if trait == "armor":
        mult = 0.80        # hierro-like hide
    elif trait == "decay":
        mult = 0.90        # withering aura
    elif trait == "poison":
        mult = 0.88
    elif trait == "enrage" and sess["hp"] <= sess["max_hp"] * 0.30:
        mult = 0.80        # cornered: hardens in the last phase
    elif trait == "bleed" and crit:
        mult = 1.50        # open wounds: crits hurt more
    # bigger, more satisfying numbers: base multiplier + team combo + occasional signature strike
    now = time.time()
    combo = min(int(st["boss_combo_cap"]), int(sess.get("combo", 0)) + 1) if now - float(sess.get("last_at", 0)) <= float(st["boss_combo_window"]) else 0
    special = rng.random() < float(st["boss_special_chance"])
    dmg = dmg * mult * float(st["boss_dmg_mult"]) * (1 + float(st["boss_combo_step"]) * combo) * (float(st["boss_special_mult"]) if special else 1.0)
    dmg = max(1, int(dmg))
    heal = int(sess["max_hp"] * 0.004) if trait == "regen" and sess["hp"] < sess["max_hp"] * 0.99 else 0
    heal = 0 if sess["hp"] - dmg <= 0 else min(heal, dmg // 2)  # regen can never undo a killing blow or stall the last 1%
    pname = tagged_name(ch, ALL)
    entry = {"n": pname, "d": dmg, "c": bool(crit), "s": bool(special), "r": ch["race"]}
    doc = await col("boss_sessions").find_one_and_update(
        {"_id": sid, "active": True, "hp": {"$gt": 0}},
        {"$inc": {"hp": -dmg + heal, f"contrib.{uid}": dmg, "hits": 1},
         "$set": {"last_hitter": uid, f"nm.{uid}": pname, "combo": combo, "last_at": now},
         "$push": {"feed": {"$each": [entry], "$slice": -4}}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        return "gone", None
    phase_up = phase(doc) if phase(doc) > phase(sess) else 0
    await bump_quest(uid, "boss_hit", 1)
    from service_worldstate import on_action
    await on_action(uid, "boss_hit", ch["location"])
    return "hit", {"dmg": dmg, "crit": crit, "doc": doc, "combo": combo, "special": special, "phase_up": phase_up, "race": ch["race"]}


async def settle_boss(sid: str):
    """Pay out a killed boss exactly once. Returns summary or None."""
    doc = await col("boss_sessions").find_one_and_update(
        {"_id": sid, "active": True, "hp": {"$lte": 0}}, {"$set": {"active": False, "killed": True, "ended_at": int(time.time())}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        return None
    try:
        summary = await _pay(doc, killed=True)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("boss payout failed: %s", sid)
        summary = {"rows": [], "drops": {}, "evo_drops": {}, "killed": True, "enraged": False, "n": 0}
    finally:
        await _end_global(doc)  # always free the boss slot, otherwise no new boss ever spawns
    return summary


async def expire_bosses():
    out = []
    now = int(time.time())
    while True:
        doc = await col("boss_sessions").find_one_and_update(
            {"active": True, "expires_at": {"$lte": now}}, {"$set": {"active": False, "escaped": True, "ended_at": now}},
            return_document=ReturnDocument.AFTER)
        if not doc:
            break
        summary = await _pay(doc, killed=False)
        await _end_global(doc)
        out.append((doc, summary))
    return out


async def _pay(doc: dict, killed: bool):
    st = await game_settings()
    lvl = doc["level"]
    contrib = {int(k): v for k, v in doc.get("contrib", {}).items()}
    total = sum(contrib.values()) or 1
    n = len(contrib)
    pool_mult = (min(n, int(st["boss_pool_cap"])) ** 0.7) if n > 1 else 1.0  # more fighters, bigger prize pool
    xp_pool = int(300 * lvl ** 1.3 + 500) * (1.0 if killed else 0.3) * pool_mult
    coin_pool = int((120 * lvl ** 1.2 + 300) * float(st["coin_rate"])) * (1.0 if killed else 0.3) * pool_mult
    enraged = doc["hp"] <= 0 and doc["max_hp"] > 0 and killed
    if enraged:
        xp_pool *= 1.3
    rows, drops, evo_drops = [], {}, {}
    ranked = sorted(contrib.items(), key=lambda x: -x[1])
    day = day_id()
    for rank, (uid, dmg) in enumerate(ranked):
        ch = await get_char(uid)
        if not ch:
            continue
        share = dmg / total
        paid = (not is_new_account(ch, st)) and await bump_counter(f"bosspaid:{uid}:{day}", 1, int(st["boss_daily_paid"]))
        main = dmg >= float(st["boss_main_share"]) * doc["max_hp"]
        xp = (xp_pool * share if main else xp_pool * 0.01) if paid else 0
        coins = (coin_pool * share if main else 0) if paid else 0
        last = killed and uid == doc.get("last_hitter")
        if last and paid:
            xp += xp_pool * 0.10
            coins += coin_pool * 0.10
        if xp:
            await add_xp(uid, int(xp), "boss", apply_rate=True)
        if coins:
            await add_coins(uid, int(coins), "boss")
        # boss loot is a reward for the kill: never silently lost to a full bag (force), and a failure for one
        # player must not abort the payout of everyone else
        try:
            if killed and paid and (last or rank < 3):
                iid = await roll_drop(uid, source_mult=2.0, weapon_chance=0.2)
                if await inv_add(uid, iid, 1, force=True):
                    drops[uid] = iid
            if killed and paid and rank < 5 and random.random() < 0.30:
                pool = EVO_BY_RARITY[RARITIES[min(3, lvl // 25)]] or EVO_BY_RARITY["Common"]
                eid = random.choice(pool)
                if await inv_add(uid, eid, 1, force=True):
                    evo_drops[uid] = eid
        except Exception:
            import logging
            logging.getLogger(__name__).exception("boss loot failed for uid=%s", uid)
        if killed:
            await bump_quest(uid, "boss_kill", 1)
        await season_add(uid, season_pts_boss(share, killed) + (3 if paid else 0), ch["name"])
        rows.append({"uid": uid, "name": (doc.get("nm") or {}).get(str(uid)) or ch["name"], "dmg": dmg, "share": share,
                     "xp": int(xp), "last": last, "paid": bool(paid)})
    if doc.get("scope") == "global":
        if killed:
            await world_adjust(threat=-float(st["world_threat_boss_kill"]), stability=1.5)
            last_name = next((r["name"] for r in rows if r["last"]), rows[0]["name"] if rows else "?")
            await chronicle("boss_kill", name=last_name, boss_fa=doc["name_fa"], boss_en=doc["name_en"], n=n)
        else:
            await world_adjust(threat=float(st["world_threat_boss_flee"]), stability=-2.0)
            await chronicle("boss_flee", boss_fa=doc["name_fa"], boss_en=doc["name_en"])
    return {"rows": rows, "drops": drops, "evo_drops": evo_drops, "killed": killed, "enraged": enraged, "n": n}


async def herald_due(window: int) -> int:
    """Minutes until the next world boss, the first time that boss slot enters the herald window; 0 otherwise.
    Atomic: the slot is marked with `herald_for` in the same update, so it is announced exactly once."""
    ws, _ = await get_world(force=True)
    nxt, now = int(ws.get("next_boss_at", 0) or 0), int(time.time())
    if ws.get("boss_id") or nxt <= now or nxt - now > window:
        return 0
    res = await col("world_state").update_one({"_id": WS_ID, "herald_for": {"$ne": nxt}}, {"$set": {"herald_for": nxt}})
    return max(1, round((nxt - now) / 60)) if res.modified_count else 0


async def boss_due() -> bool:
    ws, _ = await get_world(force=True)
    return not ws.get("boss_id") and ws.get("next_boss_at", 0) <= int(time.time())


async def broadcast_groups(limit: int = 300) -> list:
    """Groups that get world announcements (recently active, not blocked)."""
    now = int(time.time())
    return await col("groups").find({"blocked": {"$ne": True}, "last_active": {"$gte": now - 7 * 86400}}).sort("last_active", -1).limit(limit).to_list(limit)
