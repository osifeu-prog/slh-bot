from core import profile_manager
import os
from heb_convert import get_hebrew_date
import state_manager



def _fetch_api_wallet(uid):
    """Fetch on-chain + multi-token balances via shared slh_api_client."""
    from core import slh_api_client
    return slh_api_client.get_balances(uid)


def register(bot):

    def referral_link(uid):
        try:
            username = getattr(bot.get_me(), "username", None)
            if username:
                return f"https://t.me/{str(username).lstrip('@')}?start=ref_{uid}"
        except Exception:
            pass
        return None

    @bot.message_handler(commands=["connect_bnb"])
    def connect_bnb(msg):
        """Open the external Mini App wallet screen for BNB ownership binding."""
        url = "https://slh-nft.com/mini-app?screen=wallet&external=1"
        try:
            from telebot import types
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🦊 התחבר ואמת BNB", url=url))
            bot.reply_to(
                msg,
                "🔐 חיבור BNB\n\n"
                "פתח את מסך Wallet בדפדפן כדי לבצע challenge + חתימה "
                "ולהוכיח בעלות על ארנק BNB.\n"
                "אין לשלוח כספים לצורך האימות.",
                reply_markup=markup,
            )
        except Exception:
            bot.reply_to(
                msg,
                "🔐 חיבור BNB:\n"
                f"{url}\n\n"
                "פתח בדפדפן כדי לאמת בעלות על הארנק. אין לשלוח כספים לצורך האימות.",
            )

    @bot.message_handler(commands=["wallet"])
    def wallet(msg):
        uid = str(msg.from_user.id)

        user = profile_manager.get_user(uid)
        wallet = user.get("wallet", {})
        referral = user.get("referral", {})
        gamification = user.get("gamification", {})

        credits = wallet.get("credits", 0)
        staked = wallet.get("staked", 0)
        token_balance = wallet.get("token_balance", 0)
        live_token_balance = wallet.get("live_token_balance", 0)
        points = gamification.get("points", 0)
        level = gamification.get("level", 1)
        referral_count = referral.get("count", 0)

        # Canonical referral commission source of truth is the top-level
        # commissions ledger, updated atomically by the economy service.
        db = state_manager.load_db()
        commission = db.get("commissions", {}).get(uid, 0)
        invite = referral_link(uid)

        text = (
            "[בס\"ד]\n\n"
            "💰 SLH Wallet\n\n"
            f"📅 {get_hebrew_date()}\n"
            f"💳 Credits: {credits}\n"
            f"🔒 Staked: {staked}\n"
            f"🪙 SLH Live (מגובה): {live_token_balance}\n"
            f"⭐ Points: {points} (Level {level})\n"
            f"👥 Referrals: {referral_count}\n"
            f"💎 Referral commission: {commission}\n\n"
        )
        try:
            legacy_unbacked = float(token_balance or 0) - float(live_token_balance or 0)
        except (TypeError, ValueError):
            legacy_unbacked = 0
        if legacy_unbacked > 0:
            text += (
                f"⚠️ SLH פנימי לא מגובה/Legacy: {legacy_unbacked:g}\n"
                "   היתרה הזו אינה זמינה למסחר Live עד להפקדת SLH on-chain מאומתת.\n\n"
            )

        # On-chain / multi-token view from slh-api (separate ledger — never merged)
        api_data = _fetch_api_wallet(uid)
        if api_data and api_data.get("balances"):
            b = api_data["balances"]
            text += "━━━━━━━━━━━━━━\n"
            text += "🌐 ארנק on-chain (slh-api):\n"
            text += f"   SLH: {b.get('SLH', 0)}\n"
            if b.get('ZVK'): text += f"   ZVK: {b.get('ZVK', 0)}\n"
            if b.get('MNH'): text += f"   MNH: {b.get('MNH', 0)}\n"
            if b.get('REP'): text += f"   REP: {b.get('REP', 0)}\n"
            if b.get('ZUZ'): text += f"   ZUZ: {b.get('ZUZ', 0)}\n"
            text += f"   ₪ סה\"כ: {api_data.get('total_value_ils', 0)}\n\n"

        if invite:
            text += f"🔗 קישור ההזמנה האישי שלך:\n{invite}\n\n"

        from core.wallet_binding import get_binding
        from core.ton_deposit_service import _settings, deposits_are_open
        from core.ton_wallet_binding import get_ton_binding

        bnb_binding = get_binding(uid)
        ton_binding = get_ton_binding(uid)
        ton_treasury, ton_rate = _settings()
        ton_open = deposits_are_open()

        text += (
            "📤 העברת Credits: /transfer <uid> <amount>\n"
            "🎁 מתנת Credits: /gift <uid> <amount>\n"
            "🎁 מרכז מתנות ו-Airdrop: /gifts\n"
            "⭐ רכישת Credits: /pay\n"
            "📜 היסטוריית תשלומים: /history\n\n"
            "🔐 Wallet binding:\n"
            f"   BNB: {'✅ מאומת' if bnb_binding else '⚪️ לא מאומת'}"
            + (f" — {bnb_binding.get('address')}" if bnb_binding else "")
            + "\n"
            f"   TON: {'✅ מאומת' if ton_binding else '⚪️ לא מאומת'}"
            + (f" — {ton_binding.get('address')}" if ton_binding else "")
            + "\n"
            + (
                f"   TON deposits: ✅ OPEN · 1 TON = {ton_rate:g} Credits\n"
                if ton_open and ton_rate
                else "   TON deposits: ⛔ CLOSED\n"
            )
            + "המערכת מזכה הפקדות רק לאחר binding מאומת ובדיקת sender/recipient/memo. TX לבדו אינו מספיק."
        )

        try:
            from datetime import datetime
            with open("branding/SLH_LOGO.txt", "r", encoding="utf-8") as f:
                logo_lines = f.read().strip().splitlines()
            today = datetime.now().strftime("%Y-%m-%d")
            logo_lines = [
                f"Updated: {today}" if line.startswith("Updated:") else line
                for line in logo_lines
            ]
            logo = "\n".join(logo_lines)
        except Exception:
            logo = ""
        if logo:
            text = logo + "\n\n" + text

        bot.reply_to(msg, text)

    print("wallet_handler loaded")
