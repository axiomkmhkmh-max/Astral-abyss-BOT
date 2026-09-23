# ============================================================
#  ASYNC_BRIDGE — پُلِ غیربلاک‌کننده رویِ سیستم‌های سینک
# ------------------------------------------------------------
#  مشکل: مونگو تویِ mongo_shim.py سینکه (pymongo خام). خیلی از
#  توابعِ عمومیِ فایل‌هایِ سیستمی (land_system.py, guild_system.py,
#  economy_engine.py, ...) مستقیم متدهایِ سینکِ _col() رو صدا
#  می‌زنن. وقتی این توابع مستقیم (بدونِ await) از داخلِ یه
#  async def هندلر صدا زده بشن، کوئری‌شون کلِ event loopِ ربات
#  (تلگرام + Gap، هر دوتا، برایِ *همه‌ی* کاربرا) رو برایِ مدتِ
#  رفت‌وبرگشت به دیتابیس فریز می‌کنه. زیرِ لود، این تجمیع می‌شه و
#  همون دیلیِ کلیِ ربات رو می‌سازه.
#
#  این فایل خودِ فایل‌هایِ سیستمی رو دست نمی‌زنه (صفر ریسکِ‌ شکستنِ
#  منطق). برایِ هر تابعِ عمومی‌ای که واقعاً (مستقیم یا از طریقِ
#  توابعِ دیگه‌ی همون فایل) یه کوئریِ سینکِ Mongo می‌زنه، یه wrapper
#  می‌سازه که با asyncio.to_thread توی یه ترد جدا اجراش می‌کنه —
#  یعنی همون کار رو می‌کنه ولی event loop رو بلاک نمی‌کنه.
#
#  استفاده تویِ هندلرها:
#      import async_bridge as bridge
#      ok, msg = await bridge.land_system.buy_land(uid, player, m, p)
#
#  امضا، آرگومان‌ها و مقدارِ برگشتیِ هر تابع دقیقاً همونیه که تویِ
#  فایلِ اصلی بود — فقط await می‌خواد.
#
#  ⚠️ توابعی که خودِ فایل‌هایِ سیستمی از همدیگه (نه از هندلر) صدا
#  می‌زنن (مثلاً guild_war_system.py که مستقیم guild_system.get_x
#  رو صدا می‌زنه) دست‌نخورده موندن — چون اون صدازدن از قبل داخلِ
#  یه ترد جدا (توسطِ همین bridge) داره اجرا می‌شه، پس بلاک‌کردنِ
#  event loop اصلاً مطرح نیست؛ فقط نقطه‌ی ورودی از هندلر مهمه.
# ============================================================
import asyncio
import functools

import land_system
import guild_system
import economy_engine
import farm_system
import group_system
import auction_system
import smuggling_contracts
import economy_ledger
import region_boss_system
import weekly_rewards
import referral_system
import house_system
import guild_war_system
import world_pulse
import seasonal_arc
import map_activity
import exchange_system
import convergence_system
import contract_system
import bounty_system
import black_market_dealers
import account_link
import weekly_challenge
import shop_system
import daily_wanted
import bank_system

def _wrap(fn):
    """تابعِ سینک رو تویِ یه ترد جدا اجرا می‌کنه — امضا/مقدارِ برگشتی دست‌نخورده."""
    @functools.wraps(fn)
    async def _wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return _wrapper


class _Namespace:
    """نگه‌دارنده‌ی نسخه‌هایِ awaitable توابعِ یه فایلِ سیستمی."""
    pass


def _build(module, names):
    ns = _Namespace()
    for name in names:
        setattr(ns, name, _wrap(getattr(module, name)))
    return ns



land_system = _build(land_system, ["list_plots", "get_my_land", "max_house_tier_for_player", "buy_land", "expand_land", "abandon_land", "list_for_sale", "cancel_listing", "list_for_sale_all", "buy_listed_land", "set_rent_price", "rent_land", "is_renting", "collect_rent_income", "land_summary_text"])
guild_system = _build(guild_system, ["get_guild_bonus_pct", "get_combat_bonus_pct", "get_trade_discount_pct", "get_forge_bonus_pct", "get_heal_bonus_pct", "get_loot_bonus_pct", "advance_quest", "do_guild_action", "add_war_points", "get_war_state", "war_status_text", "get_war_xp_buff", "get_guild_boss", "reset_guild_boss", "guild_boss_status_text", "guild_boss_attack", "get_treasury", "contribute_treasury", "get_rally_bonus_pct", "rally_ready", "start_rally", "treasury_top_contributors", "get_infra_level", "get_infra_bonus_pct", "infra_upgrade_ready", "buy_infra_upgrade"])
economy_engine = _build(economy_engine, ["trigger_market_event", "get_active_events_display", "maybe_spawn_random_event", "get_dynamic_price", "register_trade", "compute_sell_tax", "compute_buy_total", "deposit_tax_pool", "get_tax_pool", "withdraw_tax_pool", "get_market_overview"])
farm_system = _build(farm_system, ["ensure_farm", "plant_crop", "farm_status", "harvest_crop", "buy_animal", "barn_status", "feed_animal", "collect_produce", "sell_animal", "farm_summary_text"])
group_system = _build(group_system, ["get_group_boss", "save_group_boss", "mark_group_boss_killed", "group_boss_cooldown_remaining", "spawn_group_boss", "list_active_group_bosses", "touch_group_member", "get_group_member_ids", "known_group_chat_ids"])
auction_system = _build(auction_system, ["create_listing", "get_listing", "cancel_listing"])
smuggling_contracts = _build(smuggling_contracts, ["post_contract", "open_contracts", "my_contracts", "cancel_contract"])
economy_ledger = _build(economy_ledger, ["record_interest_paid", "record_loan_issued", "record_loan_repaid", "record_loan_default", "record_treasury_contribution", "record_house_income_paid", "record_house_upkeep", "record_robbery_attempt", "record_exchange_fee", "record_insurance_premium", "record_insurance_payout", "get_ledger", "record_transaction", "get_user_transactions", "get_recent_transactions", "get_large_transactions"])
region_boss_system = _build(region_boss_system, ["get_region_boss", "save_region_boss", "mark_region_boss_killed", "region_boss_cooldown_remaining", "spawn_region_boss", "list_active_region_bosses"])
weekly_rewards = _build(weekly_rewards, ["get_weekly_featured_boss_id"])
referral_system = _build(referral_system, ["track_referral", "group_invite_count", "top_inviting_groups"])
house_system = _build(house_system, ["get_insurance_pool", "buy_insurance", "attempt_robbery"])
guild_war_system = _build(guild_war_system, ["get_state", "war_map_text", "territory_detail_text", "raid_cooldown_remaining", "raid_territory", "garrison_territory", "get_player_perks"])
world_pulse = _build(world_pulse, ["get_chain_effect", "nemesis_spawn_boost", "underground_stake_bonus", "get_active_pulse", "get_pulse_target_map", "pulse_value", "pulse_loot_bonus_chance", "set_paused", "adjust_corruption", "clear_active", "pulse_status_text"])
seasonal_arc = _build(seasonal_arc, ["register_nemesis_kill", "progress", "buff_active", "xp_mult", "zen_mult", "progress_bar", "status_text"])
map_activity = _build(map_activity, ["log_event", "live_presence_badge", "daily_visitor_count", "hot_locations", "recent_feed_text"])
exchange_system = _build(exchange_system, ["get_prices", "get_price", "portfolio_value", "buy", "sell", "force_shock"])
convergence_system = _build(convergence_system, ["get_state", "is_active", "start_event", "contribute", "status_text", "get_top_contributors"])
contract_system = _build(contract_system, ["get_board", "get_contract", "accept_contract", "check_progress", "turn_in"])
bounty_system = _build(bounty_system, ["get_bounty", "place_bounty", "claim_bounty", "top_bounties"])
black_market_dealers = _build(black_market_dealers, ["active_dealers", "get_dealer", "buy_from_dealer"])
account_link = _build(account_link, ["generate_link_code", "is_linked", "link_status_text"])
weekly_challenge = _build(weekly_challenge, ["get_current_challenge", "ensure_baseline", "challenge_score", "leaderboard_text", "player_progress_text"])
shop_system = _build(shop_system, ["list_active_shops", "count_active_shops"])
daily_wanted = _build(daily_wanted, ["get_today_entries", "get_wanted_entry"])
bank_system = _build(bank_system, ["resolve_card_to_uid", "resolve_target"])
