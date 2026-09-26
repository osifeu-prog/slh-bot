"""Telegram UI for the SLH Trade Terminal MVP."""

from telebot import types

from core import trade_terminal as trade


def _prepare_locale(message):
    uid = str(message.from_user.id)
    try:
        from language_handler import ensure_user_language
        ensure_user_language(uid, getattr(message.from_user, "language_code", None))
    except Exception:
        pass
    return uid


def _send_portfolio(bot, chat_id, uid):
    try:
        from core.profile_manager import get_user
        from core.wallet_binding import get_binding
        from core.ton_wallet_binding import get_ton_binding
        from core import slh_api_client

        user = get_user(uid) or {}
        wallet = user.get("wallet", {}) or {}
        bnb = get_binding(uid)
        ton = get_ton_binding(uid)
        api = slh_api_client.get_balances(uid) or {}
        balances = api.get("balances", {}) if isinstance(api, dict) else {}

        lines = [
            f"👛 {trade.t('portfolio', uid)}",
            f"💰 Credits: {wallet.get('credits', 0)}",
            f"🔒 Staked: {wallet.get('staked', 0)}",
            f"🌐 SLH on-chain: {balances.get('SLH', 0)}",
            f"BNB: {'✅ ' + trade.t('verified', uid) if bnb else '⚪️ ' + trade.t('not_verified', uid)}",
            f"TON: {'✅ ' + trade.t('verified', uid) if ton else '⚪️ ' + trade.t('not_verified', uid)}",
        ]
        bot.send_message(chat_id, "\n".join(lines))
    except Exception as exc:
        print("[TRADE] portfolio:", type(exc).__name__)
        bot.send_message(chat_id, trade.t("portfolio_error", uid))


def _send_trade_model(bot, chat_id, uid):
    fee = trade.execution_fee_bps() / 100
    execution = trade.t("execution_open", uid) if trade.execution_enabled() else trade.t("execution_safe", uid)
    bot.send_message(
        chat_id,
        trade.t("model_text", uid)
        + f"\n\n{trade.t('execution_connector', uid)}: {execution}"
        + f"\n{trade.t('execution_fee', uid, fee=fee)}",
    )


def _send_tradepro(bot, chat_id, uid):
    if trade.tradepro_active(uid):
        bot.send_message(
            chat_id,
            trade.t("pro_status", uid, status=trade.t("pro_active", uid)),
        )
        return
    bot.send_message(
        chat_id,
        trade.t("tradepro_text", uid) + "\n\nUse: /buystars trade_pro",
    )


def _trade_menu(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(trade.t("scanner", uid), callback_data="trade:scanner"),
        types.InlineKeyboardButton(trade.t("portfolio", uid), callback_data="trade:portfolio"),
    )
    markup.add(
        types.InlineKeyboardButton(trade.t("swap", uid), callback_data="trade:swap"),
        types.InlineKeyboardButton(trade.t("sniper", uid), callback_data="trade:sniper"),
    )
    markup.add(
        types.InlineKeyboardButton(trade.t("orders", uid), callback_data="trade:orders"),
        types.InlineKeyboardButton(trade.t("bridge", uid), callback_data="trade:bridge"),
    )
    markup.add(
        types.InlineKeyboardButton(trade.t("model", uid), callback_data="trade:model"),
        types.InlineKeyboardButton(trade.t("risk", uid), callback_data="trade:risk"),
    )
    markup.add(types.InlineKeyboardButton(trade.t("pro", uid), callback_data="trade:pro"))
    markup.add(types.InlineKeyboardButton(trade.t("ai_explain", uid), callback_data="trade:ai"))
    return markup


def register(bot):
    @bot.message_handler(commands=["trade", "trading", "terminal"])
    def trade_command(message):
        uid = _prepare_locale(message)
        text = (
            f"{trade.t('title', uid)}\n\n"
            f"{trade.t('subtitle', uid)}\n"
            f"{trade.t('chains', uid)}\n\n"
            f"{trade.t('read_only', uid)}\n\n"
            f"{trade.t('commands', uid)}"
        )
        bot.send_message(message.chat.id, text, reply_markup=_trade_menu(uid))

    @bot.message_handler(commands=["token", "scan"])
    def token_command(message):
        uid = _prepare_locale(message)
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            bot.reply_to(message, trade.t("scan_usage", uid))
            return
        try:
            snapshot = trade.fetch_token_snapshot(parts[1].strip())
        except ValueError as exc:
            code = str(exc)
            if code == "INVALID_TOKEN":
                msg = trade.t("invalid_token", uid)
            elif code == "NO_PAIRS":
                msg = trade.t("no_pairs", uid)
            else:
                msg = trade.t("scan_error", uid)
            bot.reply_to(message, msg)
            return
        except Exception as exc:
            print("[TRADE] token scan:", type(exc).__name__)
            bot.reply_to(message, trade.t("scan_error", uid))
            return

        lines = [
            f"📊 {snapshot['base_symbol'] or snapshot['base_name'] or 'TOKEN'}",
            f"Chain: {snapshot['chain'] or '—'} · DEX: {snapshot['dex'] or '—'}",
            f"Price USD: {snapshot['price_usd'] or '—'}",
            f"24h change: {snapshot['price_change_24h'] if snapshot['price_change_24h'] is not None else '—'}%",
            f"Liquidity USD: {snapshot['liquidity_usd'] if snapshot['liquidity_usd'] is not None else '—'}",
            f"Volume 24h USD: {snapshot['volume_24h'] if snapshot['volume_24h'] is not None else '—'}",
            "",
            "ℹ️ Scanner data is market data, not a contract audit or trading recommendation.",
        ]
        markup = types.InlineKeyboardMarkup(row_width=2)
        chain = snapshot["chain"].lower()
        token = parts[1].strip()
        if chain in trade.SUPPORTED_CHAINS:
            markup.add(
                types.InlineKeyboardButton(
                    trade.t("trade_link", uid),
                    url=trade.dex_url(chain, token),
                )
            )
        bot.send_message(message.chat.id, "\n".join(lines), reply_markup=markup)

    @bot.message_handler(commands=["portfolio"])
    def portfolio_command(message):
        uid = _prepare_locale(message)
        _send_portfolio(bot, message.chat.id, uid)

    @bot.message_handler(commands=["swap"])
    def swap_command(message):
        uid = _prepare_locale(message)
        parts = (message.text or "").split()
        if len(parts) != 3:
            bot.reply_to(message, trade.t("swap_usage", uid))
            return
        chain, token = parts[1].strip().lower(), parts[2].strip()
        if chain not in trade.SUPPORTED_CHAINS:
            bot.reply_to(message, trade.t("unsupported_chain", uid))
            return
        if not token:
            bot.reply_to(message, trade.t("invalid_token", uid))
            return
        try:
            url = trade.dex_url(chain, token)
        except ValueError:
            bot.reply_to(message, trade.t("invalid_token", uid))
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(trade.t("trade_link", uid), url=url))
        bot.send_message(
            message.chat.id,
            f"💱 {trade.SUPPORTED_CHAINS[chain]['label']}\n"
            f"<code>{token}</code>\n\n{trade.t('read_only', uid)}",
            reply_markup=markup,
            parse_mode="HTML",
        )

    @bot.message_handler(commands=["trade_model", "tradefees"])
    def trade_model_command(message):
        uid = _prepare_locale(message)
        _send_trade_model(bot, message.chat.id, uid)

    @bot.message_handler(commands=["tradepro"])
    def tradepro_command(message):
        uid = _prepare_locale(message)
        _send_tradepro(bot, message.chat.id, uid)

    @bot.callback_query_handler(func=lambda call: str(call.data).startswith("trade:"))
    def trade_callback(call):
        uid = str(call.from_user.id)
        try:
            from language_handler import ensure_user_language
            ensure_user_language(uid, getattr(call.from_user, "language_code", None))
        except Exception:
            pass

        action = str(call.data).split(":", 1)[1]
        bot.answer_callback_query(call.id)
        if action == "scanner":
            bot.send_message(call.message.chat.id, trade.t("scan_usage", uid))
        elif action == "portfolio":
            _send_portfolio(bot, call.message.chat.id, uid)
        elif action == "swap":
            bot.send_message(call.message.chat.id, trade.t("swap_usage", uid))
        elif action == "sniper":
            bot.send_message(call.message.chat.id, trade.t("sniper_safe", uid))
        elif action == "orders":
            bot.send_message(call.message.chat.id, trade.t("orders_safe", uid))
        elif action == "bridge":
            bot.send_message(call.message.chat.id, trade.t("bridge_safe", uid))
        elif action == "model":
            _send_trade_model(bot, call.message.chat.id, uid)
        elif action == "risk":
            bot.send_message(call.message.chat.id, trade.t("risk_text", uid))
        elif action == "pro":
            _send_tradepro(bot, call.message.chat.id, uid)
        elif action == "ai":
            try:
                from core.ask_router import route
                bot.send_chat_action(call.message.chat.id, "typing")
                answer = route(trade.t("ai_explain_prompt", uid), uid)
                bot.send_message(call.message.chat.id, str(answer or "לא התקבלה תשובת AI כרגע.")[:4000])
            except Exception as exc:
                print("[TRADE] AI explanation:", type(exc).__name__)
                bot.send_message(call.message.chat.id, "🧠 מנוע ה-AI אינו זמין כרגע.")

    print("✅ trade terminal handler registered")
