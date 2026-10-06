"""User-facing SLH wallet entrypoint.

The bot is the simple UX layer. It never signs or broadcasts an on-chain
transaction; the Mini App and the user's BSC wallet perform the actual
user-signed transfer through the existing SLH distribution authority.
"""

import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode, urlsplit

from telebot import types
from web3 import Web3

from core.bsc_wallet_read_model import read_bsc_wallet
from core.distribution_wallet_registry import get_secondary_distribution_wallet
from core.identity import OWNER_TELEGRAM_ID
from core.slh_quick_send import get_quick_send_config
from core.wallet_binding import get_binding
from core.wallet_handoff import create_handoff


_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_AMOUNT_RE = re.compile(r"^\d+(?:\.\d{1,15})?$")


def _mini_app_url(**params):
    base = (
        os.getenv("SLH_MINI_APP_URL")
        or "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"
    ).strip()
    query = urlencode({k: v for k, v in params.items() if v not in (None, "")})
    return f"{base}?{query}" if query else base

def _public_origin():
    base = (
        os.getenv("SLH_MINI_APP_URL")
        or "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"
    ).strip()
    parts = urlsplit(base)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return "https://slh-cloud-bot-production.up.railway.app"


def _trust_wallet_smoke_url(uid):
    handoff = create_handoff(uid)
    target = (
        f"{_public_origin()}/wallet-handoff?"
        f"code={quote(str(handoff['token']), safe='')}&next=/slh-smoke"
    )
    return (
        "https://link.trustwallet.com/open_url?coin_id=20000714&url="
        + quote(target, safe="")
    )


def _owner_slh_browser_send_url(uid):
    if str(uid) != str(OWNER_TELEGRAM_ID):
        raise PermissionError("OWNER_ONLY")
    handoff = create_handoff(uid)
    return (
        f"{_public_origin()}/wallet-handoff?"
        f"code={quote(str(handoff['token']), safe='')}&next=/slh-browser-send"
    )



def _format_amount(value):
    try:
        return f"{Decimal(str(value)):,.15f}".rstrip("0").rstrip(".")
    except (InvalidOperation, TypeError, ValueError):
        return str(value)


def _parse_amount(raw):
    value = str(raw or "").strip()
    if not _AMOUNT_RE.fullmatch(value):
        raise ValueError("INVALID_SLH_AMOUNT")
    amount = Decimal(value)
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_SLH_AMOUNT")
    return value


def _status(uid):
    binding = get_binding(uid)
    registry = get_secondary_distribution_wallet(uid)
    live = read_bsc_wallet(uid)

    if not binding:
        return (
            """🪙 SLH OS

ארנק BNB: ⛔ לא מאומת
SLH on-chain: לא זמין עד לאימות ארנק BSC.

פתח /slh כדי לקבל את מסלול החיבור."""
            , binding, registry, live
        )

    wallet = str(binding.get("address") or "")
    assets = (live.get("assets") or {}) if isinstance(live, dict) else {}
    slh = assets.get("SLH") or {}
    bnb = assets.get("BNB") or {}
    slh_amount = slh.get("amount")
    bnb_amount = bnb.get("amount")

    lines = [
        "🪙 SLH OS",
        "",
        f"🔐 BSC: ✅ מאומת",
        f"📍 {wallet}",
        f"🪙 SLH on-chain: {_format_amount(slh_amount if slh_amount is not None else 0)}",
        f"⛽ BNB gas: {_format_amount(bnb_amount if bnb_amount is not None else 0)}",
    ]
    if registry and str(registry.get("status")) == "active":
        lines.extend([
            "",
            "⚡ שליחה מאומתת: ✅ פעילה",
            f"• Per-tx: {registry.get('per_tx_limit_slh')} SLH",
            f"• Daily: {registry.get('daily_limit_slh')} SLH",
            "• חתימה/שידור: מהארנק בלבד",
        ])
    else:
        lines.extend([
            "",
            "ℹ️ שליחת SLH דרך מסלול ההפצה אינה מופעלת עבור הארנק הזה.",
            "המערכת לא תאפשר עקיפה של הרשאת distribution.",
        ])
    return "\n".join(lines), binding, registry, live


def _menu(uid, *, include_test=False):
    text, binding, registry, live = _status(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)

    send_url = _mini_app_url(screen="wallet", slh_route="send")
    markup.add(
        types.InlineKeyboardButton("🪙 שליחת SLH", web_app=types.WebAppInfo(url=send_url)),
        types.InlineKeyboardButton("🔎 רענן יתרה", callback_data="slh_menu_refresh"),
    )

    if binding:
        markup.add(
            types.InlineKeyboardButton("📥 קבלת SLH", callback_data="slh_menu_receive"),
        )
    else:
        markup.add(
            types.InlineKeyboardButton("🔐 אימות BNB", callback_data="slh_menu_connect"),
        )

    if str(uid) == str(OWNER_TELEGRAM_ID):
        try:
            quick = get_quick_send_config(uid, "owner_to_tzvika_1")
            browser_url = _owner_slh_browser_send_url(uid)
            markup.add(
                types.InlineKeyboardButton(
                    f"⚡ שלח 1 SLH ל{quick.get('label', 'איש קשר')} · Trezor",
                    url=browser_url,
                )
            )
        except (PermissionError, ValueError) as exc:
            print("[SLH] quick send unavailable:", str(exc))

    active = bool(registry and str(registry.get("status")) == "active")
    if include_test and active:
        owner_binding = get_binding(str(OWNER_TELEGRAM_ID))
        owner_address = owner_binding.get("address") if owner_binding else None
        if owner_address:
            try:
                smoke_url = _trust_wallet_smoke_url(uid)
                markup.add(
                    types.InlineKeyboardButton(
                        "🧪 שלח 1 SLH אל אוסיף",
                        url=smoke_url,
                    )
                )
            except Exception as exc:
                print("[SLH] smoke link error:", type(exc).__name__)
                markup.add(
                    types.InlineKeyboardButton(
                        "🧪 בדיקת 1 SLH",
                        web_app=types.WebAppInfo(
                            url=_mini_app_url(
                                screen="wallet",
                                slh_route="smoke",
                                slh_smoke="1",
                                recipient=owner_address,
                                amount="1",
                            )
                        ),
                    )
                )
    return text, markup


def register(bot):
    @bot.message_handler(commands=["slh"])
    def slh_menu(message):
        uid = str(message.from_user.id)
        text, markup = _menu(uid, include_test=True)
        bot.reply_to(message, text, reply_markup=markup)

    @bot.message_handler(commands=["slh_send"])
    def slh_send(message):
        """Open the real user-signed SLH transfer flow with optional prefill."""
        parts = (message.text or "").split()
        if len(parts) not in {1, 3}:
            bot.reply_to(
                message,
                "שימוש פשוט:\n"
                "/slh_send — פתיחת מסלול שליחת SLH\n"
                "/slh_send <BSC_ADDRESS> <AMOUNT> — פתיחה עם מילוי מראש",
            )
            return

        params = {"screen": "wallet", "slh_route": "send"}
        if len(parts) == 3:
            recipient = parts[1].strip()
            if not _ADDRESS_RE.fullmatch(recipient):
                bot.reply_to(message, "❌ כתובת BSC לא תקינה.")
                return
            try:
                amount = _parse_amount(parts[2])
            except ValueError:
                bot.reply_to(message, "❌ כמות SLH לא תקינה. עד 15 ספרות עשרוניות.")
                return
            params.update({"recipient": Web3.to_checksum_address(recipient), "amount": amount})

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "🪙 פתח שליחת SLH",
                web_app=types.WebAppInfo(url=_mini_app_url(**params)),
            )
        )
        bot.reply_to(
            message,
            "🪙 שליחת SLH\n\n"
            "העסקה תיבדק במערכת ותאושר/תשודר רק מהארנק שלך.\n"
            "המערכת אינה מחזיקה מפתח פרטי.",
            reply_markup=markup,
        )

    @bot.message_handler(commands=["slh_test"])
    def slh_test(message):
        """Open the controlled 1-SLH smoke flow for an active distribution wallet."""
        uid = str(message.from_user.id)
        registry = get_secondary_distribution_wallet(uid)
        if not registry or str(registry.get("status")) != "active":
            bot.reply_to(
                message,
                "⛔ מסלול בדיקת 1 SLH זמין רק לארנק Distribution מאומת ופעיל.",
            )
            return

        owner_binding = get_binding(str(OWNER_TELEGRAM_ID))
        if not owner_binding:
            bot.reply_to(
                message,
                "⛔ לא נמצא BSC wallet binding של OWNER ליעד הבדיקה.",
            )
            return

        target = owner_binding.get("address")
        markup = types.InlineKeyboardMarkup()
        try:
            smoke_url = _trust_wallet_smoke_url(uid)
            markup.add(
                types.InlineKeyboardButton(
                    "🧪 פתח Trust Wallet ושלח 1 SLH",
                    url=smoke_url,
                )
            )
        except Exception as exc:
            print("[SLH] smoke link error:", type(exc).__name__)
            markup.add(
                types.InlineKeyboardButton(
                    "🧪 פתח בדיקת 1 SLH",
                    web_app=types.WebAppInfo(
                        url=_mini_app_url(
                            screen="wallet",
                            slh_route="smoke",
                            slh_smoke="1",
                            recipient=target,
                            amount="1",
                        )
                    ),
                )
            )
        bot.reply_to(
            message,
            "🧪 SLH ON-CHAIN SMOKE\n\n"
            "1 SLH → ארנק ה־OWNER המאומת\n"
            "BSC / Chain 56 · BNB הוא gas בלבד\n"
            "המערכת לא שולחת BNB ליעד.\n\n"
            "לאחר החתימה נדרש TX hash + אימות on-chain.",
            reply_markup=markup,
        )

    @bot.callback_query_handler(func=lambda call: call.data in {
        "slh_menu_refresh",
        "slh_menu_receive",
        "slh_menu_connect",
    })
    def slh_menu_callback(call):
        uid = str(call.from_user.id)
        action = call.data

        if action == "slh_menu_receive":
            binding = get_binding(uid)
            if not binding:
                bot.answer_callback_query(call.id, "צריך לאמת קודם BNB", show_alert=True)
                return
            address = binding.get("address")
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "🔎 BscScan",
                    url=f"https://bscscan.com/address/{quote(str(address), safe='')}",
                )
            )
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "📥 קבלת SLH\n\n"
                "כתובת BSC המאומתת שלך:\n"
                f"<code>{address}</code>\n\n"
                "קבל SLH רק לכתובת שבדקת בעצמך.",
                parse_mode="HTML",
                reply_markup=markup,
            )
            return

        if action == "slh_menu_connect":
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "🔐 אימות BNB\n\n"
                "פתח את SLH OS → Wallet → חיבור BNB, או השתמש:\n"
                "/connect_bnb <כתובת BSC>",
            )
            return

        text, markup = _menu(uid, include_test=True)
        bot.answer_callback_query(call.id, "✅ עודכן")
        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
            )
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)

    print("✅ slh handler loaded")
