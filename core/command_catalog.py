"""Unified read-only Telegram command discovery/catalog.

Runtime registration remains the source of truth for command existence.
This module only provides presentation metadata and never grants permission.
"""

from collections import defaultdict


KNOWN = {
    "start": ("ACCOUNT", "בית / התחלה"),
    "join": ("ACCOUNT", "הרשמה"),
    "me": ("ACCOUNT", "פרופיל קצר"),
    "profile": ("ACCOUNT", "פרופיל וארנק"),
    "trade": ("TRADING", "מסוף מסחר חיצוני"),
    "token": ("TRADING", "סריקת טוקן"),
    "swap": ("TRADING", "קישור DEX חיצוני"),
    "portfolio": ("TRADING", "פורטפוליו"),
    "trade_model": ("TRADING", "מודל הכנסות שקוף"),
    "tradepro": ("TRADING", "Trade Pro"),
    "exchange": ("EXCHANGE", "מסחר פנימי SLH/Credits"),
    "buy_slh": ("EXCHANGE", "פקודת BUY"),
    "sell_slh": ("EXCHANGE", "פקודת SELL"),
    "orders": ("EXCHANGE", "הוראות פתוחות"),
    "trades": ("EXCHANGE", "עסקאות אחרונות"),
    "cancel": ("EXCHANGE", "ביטול הוראה"),
    "shop": ("MARKET", "קטלוג מוצרים"),
    "buy": ("MARKET", "רכישה ב-Credits"),
    "buystars": ("MARKET", "רכישה ב-Telegram Stars"),
    "pay": ("MARKET", "רכישת Credits"),
    "history": ("MARKET", "היסטוריית עסקאות"),
    "wallet": ("MONEY", "ארנק"),
    "balance": ("MONEY", "יתרת Credits"),
    "transfer": ("MONEY", "העברת Credits"),
    "p2p_slh": ("MONEY", "העברת SLH"),
    "stake": ("MONEY", "Staking"),
    "stake_lock": ("MONEY", "Staking לתקופה"),
    "positions": ("MONEY", "פוזיציות"),
    "unstake": ("MONEY", "שחרור פוזיציה"),
    "rewards": ("MONEY", "תגמולים"),
    "ton": ("CHAIN", "סטטוס TON"),
    "claim": ("CHAIN", "Claim BNB"),
    "academy": ("ACADEMY", "Academy"),
    "courses": ("ACADEMY", "קורסים"),
    "lesson": ("ACADEMY", "שיעור"),
    "finish": ("ACADEMY", "סיום שיעור"),
    "progress": ("ACADEMY", "התקדמות"),
    "map": ("ACADEMY", "מפת למידה"),
    "agents": ("AGENTS", "סוכנים"),
    "agent_create": ("AGENTS", "יצירת סוכן"),
    "agent_delete": ("AGENTS", "מחיקת סוכן"),
    "agentstate": ("AGENTS", "מצב סוכן"),
    "sendagent": ("AGENTS", "שליחה לסוכן"),
    "inbox": ("AGENTS", "תיבת סוכן"),
    "task": ("GOVERNANCE", "משימות"),
    "mission": ("GOVERNANCE", "משימות/מיסיות"),
    "complete": ("GOVERNANCE", "השלמת משימה"),
    "vote": ("GOVERNANCE", "הצבעה"),
    "propose": ("GOVERNANCE", "הצעה"),
    "tally": ("GOVERNANCE", "תוצאות"),
    "gov_status": ("GOVERNANCE", "סטטוס Governance"),
    "share": ("REFERRAL", "קישור הזמנה וסטטוס"),
    "refer": ("REFERRAL", "קיצור ל-Share"),
    "invite": ("REFERRAL", "קיצור ל-Share"),
    "status": ("SYSTEM", "סטטוס מערכת"),
    "health": ("SYSTEM", "בדיקת בריאות"),
    "doctor": ("SYSTEM", "אבחון"),
    "megadiag": ("SYSTEM", "אבחון מלא"),
    "check": ("SYSTEM", "בדיקת מערכת"),
    "check_money": ("SYSTEM", "בדיקת כלכלת המערכת"),
    "check_exchange": ("SYSTEM", "בדיקת Exchange"),
    "check_bnb": ("SYSTEM", "בדיקת BNB"),
    "check_ton": ("SYSTEM", "בדיקת TON"),
    "check_ux": ("SYSTEM", "בדיקת Mini App"),
    "biz": ("CONTROL", "תמונת עסק"),
    "biz_users": ("CONTROL", "כניסות משתמשים"),
    "biz_revenue": ("CONTROL", "הכנסות מאומתות"),
    "biz_ai": ("CONTROL", "מצב AI"),
    "biz_bots": ("CONTROL", "מלאי bots"),
    "bots": ("CONTROL", "מפת bots"),
    "execr": ("CONTROL", "בקשת ביצוע לאישור"),
    "bnb_smoke": ("CHAIN", "בדיקת BNB מבוקרת"),
    "bnb_reconcile": ("CHAIN", "בדיקת TX BNB קיים"),
    "bnb_reconcile_confirm": ("CHAIN", "אישור settlement TX BNB קיים"),
    "academy_progress": ("ACADEMY", "התקדמות בקורס"),
    "miniapp": ("UI", "Mini App"),
    "dashboard": ("UI", "Dashboard"),
    "settings": ("UI", "הגדרות"),
    "theme": ("UI", "ערכת תצוגה"),
    "ask": ("AI", "שאלת מערכת"),
    "faq": ("AI", "שאלות נפוצות"),
    "os": ("CONTROL", "SLH OS Control Center"),
    "e": ("CONTROL", "Control Plane / execution gateway"),
    "exec": ("CONTROL", "ביצוע פקודה"),
    "redeploy": ("CONTROL", "Redeploy"),
    "deploy": ("CONTROL", "Deploy"),
    "logs": ("CONTROL", "לוגים"),
    "releasecheck": ("CONTROL", "בדיקת release"),
    "vault": ("SECURITY", "Bot Vault"),
    "vault_verify": ("SECURITY", "אימות Vault"),
    "vault_health": ("SECURITY", "בריאות Vault"),
    "vault_log": ("SECURITY", "Audit Vault"),
    "alpha_status": ("ALPHA", "סטטוס Alpha"),
    "alpha_open": ("ALPHA", "פתיחת Alpha"),
    "alpha_state": ("ALPHA", "מצב Alpha"),
    "mcp_test": ("AUTOMATION", "בדיקת MCP"),
    "autonomy_test": ("AUTOMATION", "בדיקת autonomy"),
}


CATEGORY_ORDER = [
    "ACCOUNT",
    "TRADING",
    "EXCHANGE",
    "MARKET",
    "MONEY",
    "CHAIN",
    "ACADEMY",
    "AGENTS",
    "GOVERNANCE",
    "REFERRAL",
    "ALPHA",
    "AUTOMATION",
    "SYSTEM",
    "UI",
    "AI",
    "CONTROL",
    "SECURITY",
    "UNCLASSIFIED",
]


def _runtime_commands(bot_name="Me_ad_main"):
    try:
        from core.runtime_command_evidence import snapshot_runtime

        runtime = snapshot_runtime(bot_name)
        commands = runtime.get("commands") or []

        return sorted(
            {
                str(command).strip().lstrip("/")
                for command in commands
                if str(command).strip()
            }
        )
    except Exception:
        return []


def get_catalog(bot_name="Me_ad_main"):
    """Return runtime-backed command records.

    Runtime existence is authoritative. KNOWN only supplies presentation
    metadata and never changes permissions or dispatch.
    """
    result = []

    for command in _runtime_commands(bot_name):
        meta = KNOWN.get(command)

        if meta:
            category, description = meta
        else:
            category = "UNCLASSIFIED"
            description = "Runtime command — metadata pending"

        result.append(
            {
                "command": command,
                "category": category,
                "description": description,
                "known": bool(meta),
            }
        )

    return result


def render_help(bot_name="Me_ad_main", limit=60):
    """Render a Telegram-safe compact catalog."""
    full = get_catalog(bot_name)
    known = [item for item in full if item["known"]]
    unknown = [item for item in full if not item["known"]]
    catalog = known + unknown[: max(0, limit - len(known))]

    groups = defaultdict(list)

    for item in catalog:
        groups[item["category"]].append(item)

    lines = [
        "📘 SLH OS — Runtime Command Catalog",
        f"Runtime commands shown: {len(catalog)}",
    ]

    for category in CATEGORY_ORDER:
        items = groups.get(category)

        if not items:
            continue

        lines.append("")
        lines.append(f"━━ {category} ━━")

        for item in items:
            lines.append(
                f"/{item['command']} — {item['description']}"
            )

    hidden = len(full) - len(catalog)

    if hidden > 0:
        lines.append("")
        lines.append(f"… ועוד {hidden} פקודות runtime ללא מטא־דאטה")

    total = len(catalog)

    if not total:
        lines.append("")
        lines.append("⚠️ Runtime command evidence unavailable.")

    return "\n".join(lines)


def summary(bot_name="Me_ad_main"):
    catalog = get_catalog(bot_name)
    known = sum(1 for item in catalog if item["known"])

    return {
        "runtime_commands": len(catalog),
        "catalogued": known,
        "unclassified": len(catalog) - known,
    }


def render_compact(bot_name="Me_ad_main", limit=40):
    catalog = get_catalog(bot_name)

    lines = [
        f"📘 Runtime commands: {len(catalog)}",
        f"Catalogued: {sum(1 for item in catalog if item['known'])}",
        f"Unclassified: {sum(1 for item in catalog if not item['known'])}",
        "",
    ]

    lines.extend(
        f"/{item['command']} — {item['description']}"
        for item in catalog[:limit]
    )

    if len(catalog) > limit:
        lines.append(f"... +{len(catalog) - limit} more")

    return "\n".join(lines)
