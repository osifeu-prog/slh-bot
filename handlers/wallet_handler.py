from core import profile_manager
import os
from heb_convert import get_hebrew_date
import state_manager

TON_DEPOSITS_OPEN = os.getenv("TON_DEPOSITS_OPEN", "0").strip() == "1"



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

    @bot.message_handler(commands=["wallet_status", "wallet_ops"])
    def wallet_status(msg):
        """Read-only wallet/control status from the bot; no Mini App required."""
        uid = str(msg.from_user.id)
        try:
            from core.wallet_binding import get_binding
            from core.ton_wallet_binding import get_ton_binding
            from core.bnb_gate import bnb_readiness
            from core.ton_deposit_service import deposits_are_open, _settings
            from core.bsc_execution import policy_snapshot

            bnb_binding = get_binding(uid)
            ton_binding = get_ton_binding(uid)
            bnb = bnb_readiness()
            ton_wallet, ton_rate = _settings()
            try:
                execution = policy_snapshot()
            except Exception as exc:
                execution = {"error": type(exc).__name__, "message": str(exc)[:120]}

            bot.reply_to(
                msg,
                "🔐 SLH WALLET OPS — READ ONLY\\n\\n"
                f"👛 BNB wallet: {'✅ verified' if bnb_binding else '⛔ not verified'}\\n"
                f"💎 TON wallet: {'✅ verified' if ton_binding else '⛔ not verified'}\\n"
                f"🚪 BNB settlement: {'OPEN' if bnb['effective_open'] else 'CLOSED'}\\n"
                f"🚪 TON settlement: {'OPEN' if deposits_are_open() else 'CLOSED'}\\n"
                f"⚙️ BSC execution: {'ENABLED' if execution.get('enabled') else 'DISABLED'}\\n"
                f"📡 BSC network: {execution.get('network', '?')} / chain {execution.get('chain_id', '?')}\\n"
                f"✍️ Server signing: {'ENABLED' if execution.get('server_signing') else 'OFF'}\\n"
                "🔑 Key storage: external signer only\\n\\n"
                "Next BNB proof step:\\n"
                "/bnb_challenge <your BSC address>\\n"
                "Then obtain the wallet signature and send:\\n"
                "/bnb_verify <your BSC address> <signature>\\n\\n"
                "Prepare-only examples:\\n"
                "/bsc_prepare_bnb <recipient> <amount>\\n"
                "/bsc_prepare_slh <recipient> <amount>\\n"
                "/bsc_receipt <tx_hash>\\n\\n"
                "⚠️ No private key or seed is requested by these commands."
            )
        except Exception as exc:
            bot.reply_to(msg, f"❌ wallet status failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bnb_gate"])
    def bnb_gate_cmd(msg):
        """Read-only BNB settlement evidence."""
        try:
            from core.bnb_gate import bnb_readiness, bnb_opening_evidence
            r = bnb_readiness()
            e = bnb_opening_evidence()
            checks = ", ".join(f"{k}={v.get('status')}" for k, v in e.get("checks", {}).items())
            bot.reply_to(
                msg,
                "🚪 BNB GATE — READ ONLY\\n\\n"
                f"flag_open={r.get('flag_open')}\\n"
                f"ready={r.get('ready')}\\n"
                f"effective_open={r.get('effective_open')}\\n"
                f"chain={r.get('chain_id')} / {r.get('network')}\\n"
                f"checks: {checks}\\n"
                f"warnings: {', '.join(e.get('warnings', [])) or 'none'}\\n"
                f"next: {e.get('next_action', 'none')}"
            )
        except Exception as exc:
            bot.reply_to(msg, f"❌ BNB gate failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bsc_policy"])
    def bsc_policy_cmd(msg):
        """Read-only BSC execution policy."""
        try:
            from core.bsc_execution import policy_snapshot
            p = policy_snapshot()
            bot.reply_to(
                msg,
                "⚙️ BSC EXECUTION POLICY — READ ONLY\\n\\n"
                f"enabled={p.get('enabled')}\\n"
                f"network={p.get('network')}\\n"
                f"chain_id={p.get('chain_id')}\\n"
                f"mainnet_allowed={p.get('mainnet_allowed')}\\n"
                f"server_signing={p.get('server_signing')}\\n"
                f"server_signer_configured={p.get('server_signer_configured')}\\n"
                f"broadcast={p.get('broadcast')}\\n"
                f"custody={p.get('custody')}\\n"
                f"key_storage={p.get('key_storage')}"
            )
        except Exception as exc:
            bot.reply_to(msg, f"❌ BSC policy failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bsc_prepare_bnb"])
    def bsc_prepare_bnb_cmd(msg):
        """Prepare a user-signed BNB transaction; never signs or broadcasts."""
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /bsc_prepare_bnb <recipient> <amount_bnb>")
            return
        try:
            from core.bsc_execution import prepare_native_transfer
            result = prepare_native_transfer(str(msg.from_user.id), parts[1], parts[2])
            bot.reply_to(
                msg,
                "✅ BNB transaction prepared — NOT signed, NOT broadcast\\n\\n"
                f"from={result['from']}\\n"
                f"to={result['to']}\\n"
                f"amount={result['amount']} BNB\\n"
                f"gas={result['tx']['gas']}\\n"
                f"gasPrice={result['tx']['gasPrice']}\\n"
                f"nonce={result['tx']['nonce']}\\n"
                f"chainId={result['tx']['chainId']}\\n\\n"
                "חתום בארנק שלך בלבד. הבוט לא מחזיק את המפתח."
            )
        except ValueError as exc:
            bot.reply_to(msg, f"❌ BNB prepare: {exc}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ BNB prepare failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bsc_prepare_slh"])
    def bsc_prepare_slh_cmd(msg):
        """Prepare a user-signed SLH ERC-20 transfer; never signs or broadcasts."""
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /bsc_prepare_slh <recipient> <amount_slh>")
            return
        try:
            from core.binance_connector import get_bsc_config
            from core.bsc_execution import prepare_erc20_transfer
            cfg = get_bsc_config()
            token = cfg.get("token_contract")
            if not token:
                raise ValueError("SLH_TOKEN_NOT_CONFIGURED")
            result = prepare_erc20_transfer(
                str(msg.from_user.id), token, parts[1], parts[2], asset="SLH"
            )
            bot.reply_to(
                msg,
                "✅ SLH transaction prepared — NOT signed, NOT broadcast\\n\\n"
                f"token={result['token']}\\n"
                f"from={result['from']}\\n"
                f"recipient={result['to']}\\n"
                f"amount={result['amount']} SLH\\n"
                f"gas={result['tx']['gas']}\\n"
                f"gasPrice={result['tx']['gasPrice']}\\n"
                f"nonce={result['tx']['nonce']}\\n"
                f"chainId={result['tx']['chainId']}\\n\\n"
                "חתום בארנק שלך בלבד. הבוט לא מחזיק את המפתח."
            )
        except ValueError as exc:
            bot.reply_to(msg, f"❌ SLH prepare: {exc}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ SLH prepare failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bsc_receipt"])
    def bsc_receipt_cmd(msg):
        """Read-only receipt lookup for a user-signed transaction."""
        parts = msg.text.split()
        if len(parts) != 2:
            bot.reply_to(msg, "שימוש: /bsc_receipt <tx_hash>")
            return
        try:
            from core.bsc_execution import receipt_status
            r = receipt_status(parts[1])
            bot.reply_to(
                msg,
                "📡 BSC RECEIPT — READ ONLY\\n\\n"
                f"status={r.get('status')}\\n"
                f"succeeded={r.get('succeeded')}\\n"
                f"confirmed={r.get('confirmed')}\\n"
                f"block={r.get('block_number')}\\n"
                f"gas_used={r.get('gas_used')}"
            )
        except ValueError as exc:
            bot.reply_to(msg, f"❌ BSC receipt: {exc}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ BSC receipt failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bnb_sign"])
    def bnb_sign(msg):
        """Create a one-time external-browser signing link bound to one BSC address."""
        uid = str(msg.from_user.id)
        parts = msg.text.split()
        if len(parts) != 2:
            bot.reply_to(msg, "שימוש: /bnb_sign <כתובת BNB>")
            return
        try:
            from core.bnb_web_proof import issue_session
            session = issue_session(uid, parts[1])
            bot.reply_to(
                msg,
                "🔐 BNB WALLET PROOF — BOT FIRST\\n\\n"
                f"כתובת היעד לאימות: {session['address']}\\n"
                f"⏱️ הקישור בתוקף עד: {session['expires_at']}\\n\\n"
                "פתח את הקישור בדפדפן רגיל שבו MetaMask/Trust נגישים (לא Telegram Mini App):\\n"
                f"{session['url']}\\n\\n"
                "1. Connect MetaMask / Trust\\n"
                "2. ודא BSC Mainnet / chain 56\\n"
                "3. לחץ Sign ownership proof בלבד\\n"
                "4. אין שליחת BNB/SLH, אין Approve ואין Swap\\n\\n"
                "בסיום חזור לבוט והרץ /wallet_status."
            )
        except ValueError as exc:
            bot.reply_to(msg, f"❌ BNB signing session: {exc}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ BNB signing session failed: {type(exc).__name__}")

    @bot.message_handler(commands=["connect_bnb", "bnb_challenge"])
    def connect_bnb(msg):
        """Issue a short-lived BNB ownership challenge; no transaction is requested."""
        uid = str(msg.from_user.id)
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(
                msg,
                "🔐 חיבור BNB\n\n"
                "הדבק כתובת BNB כדי לקבל challenge חד־פעמי.\n\n"
                "/connect_bnb <כתובת BNB>\n\n"
                "לא שולחים BNB ולא חותמים על עסקה — רק חותמים על הודעת אימות."
            )
            return
        address = parts[1].strip().split()[0]
        try:
            from core.wallet_binding import issue_challenge
            challenge = issue_challenge(uid, address)
            bot.reply_to(
                msg,
                "🔐 BNB OWNERSHIP CHALLENGE\n\n"
                "חתום בארנק על ההודעה הבאה (Sign Message / personal_sign):\n\n"
                f"{challenge['message']}\n\n"
                "לא מדובר בעסקה ולא נשלח כסף.\n"
                "לאחר החתימה שלח:\n"
                "/connect_bnb_verify <הכתובת> <signature>"
            )
        except ValueError as exc:
            bot.reply_to(msg, f"❌ BNB challenge: {exc}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ BNB challenge failed: {type(exc).__name__}")

    @bot.message_handler(commands=["connect_bnb_verify", "bnb_verify"])
    def connect_bnb_verify(msg):
        """Verify the user's signed BNB ownership challenge."""
        uid = str(msg.from_user.id)
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(
                msg,
                "שימוש:\n/connect_bnb_verify <כתובת BNB> <signature>"
            )
            return
        address, signature = parts[1], parts[2]
        try:
            from core.wallet_binding import verify_signature
            binding = verify_signature(uid, address, signature)
            bot.reply_to(
                msg,
                "✅ BNB WALLET VERIFIED\n\n"
                f"Wallet: {binding['address']}\n"
                "הבעלות אומתה. כעת הפקדת BNB תיבדק server-side "
                "מול הכתובת הזו, ה־Treasury ו־15 confirmations."
            )
        except ValueError as exc:
            bot.reply_to(msg, f"❌ BNB verification: {exc}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ BNB verification failed: {type(exc).__name__}")

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
        ton_open = deposits_are_open() and TON_DEPOSITS_OPEN

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
            # Keep the ASCII logo monospace/aligned in Telegram on both
            # desktop and mobile. The body remains outside <pre> so normal
            # wallet text wrapping is preserved.
            bot.reply_to(
                msg,
                f"<pre>{logo}</pre>\n\n{text[len(logo) + 2:]}",
                parse_mode="HTML",
            )
        else:
            bot.reply_to(msg, text)

    print("wallet_handler loaded")
