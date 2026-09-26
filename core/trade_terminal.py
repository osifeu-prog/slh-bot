"""SLH Trade Terminal: multilingual, non-custodial market UX.

This module provides token discovery, portfolio readout and DEX deeplinks.
It deliberately does not custody user keys or sign blockchain transactions.
Execution connectors can be added later behind an explicit feature flag.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import requests

SUPPORTED_CHAINS = {
    "ethereum": {"label": "Ethereum", "dex": "Uniswap"},
    "base": {"label": "Base", "dex": "Uniswap"},
    "arbitrum": {"label": "Arbitrum", "dex": "Uniswap"},
    "bsc": {"label": "BNB Chain", "dex": "PancakeSwap"},
    "solana": {"label": "Solana", "dex": "Jupiter"},
}

DEFAULT_EXECUTION_FEE_BPS = 0

_TEXT = {
    "he": {
        "title": "🚀 SLH TRADE TERMINAL",
        "subtitle": "מסוף מסחר רב־שרשרתי, לא משמורני.",
        "chains": "שרשראות: Ethereum · Base · Arbitrum · BNB Chain · Solana",
        "scanner": "📊 סורק טוקנים",
        "portfolio": "👛 פורטפוליו",
        "swap": "💱 Swap",
        "sniper": "🎯 Sniper",
        "orders": "📈 Limit / DCA",
        "bridge": "🌉 Bridge",
        "model": "💰 מודל הכנסות",
        "risk": "⚠️ סיכונים",
        "pro": "⭐ Trade Pro",
        "pro_status": "Trade Pro: {status}",
        "pro_active": "פעיל",
        "pro_locked": "לא פעיל",
        "scan_usage": "שימוש: /token <כתובת טוקן>",
        "swap_usage": "שימוש: /swap <ethereum|base|arbitrum|bsc|solana> <token_address>",
        "unsupported_chain": "שרשרת לא נתמכת כרגע.",
        "invalid_token": "כתובת טוקן לא תקינה.",
        "scan_error": "לא הצלחתי להביא נתוני שוק כרגע.",
        "no_pairs": "לא נמצאו זוגות מסחר לכתובת הזו.",
        "trade_link": "🔗 פתיחת מסחר דרך ה־DEX",
        "read_only": "🛡️ כרגע המסוף אינו מחזיק מפתחות ואינו חותם על עסקאות.",
        "sniper_safe": "🎯 Sniper זמין כממשק/תכנון בלבד; ביצוע אוטומטי לא מופעל.",
        "orders_safe": "📈 Limit/DCA זמינים כממשק בלבד; ביצוע אמיתי ייפתח רק אחרי חיבור execution מאומת.",
        "bridge_safe": "🌉 Bridge מוצג כשלב תכנון בלבד; אין חתימת bridge אוטומטית.",
        "model_text": (
            "💰 SLH TRADE — מודל הכנסות\\n\\n"
            "1) ⭐ Trade Pro — 199 Stars עבור גישה לפיצ'רים מתקדמים.\\n"
            "2) 💱 עמלת ביצוע — כרגע 0.00%; אין עמלה מוסתרת.\\n"
            "   כאשר execution connector יופעל, העמלה תוצג לפני אישור העסקה.\\n"
            "3) 🤝 הכנסות שותפים — רק כאשר קיימת שותפות מתועדת והגילוי מוצג למשתמש.\\n\\n"
            "❌ אין הבטחת רווח.\\n"
            "❌ SLH לא מחזיק כרגע מפתחות פרטיים של משתמשים במסוף הזה.\\n"
            "✅ אין זיכוי פנימי על סמך TX לא מאומת."
        ),
        "risk_text": (
            "⚠️ סיכונים\\n\\n"
            "מחיר, נזילות, Slippage, MEV וחוזים זדוניים עלולים לגרום להפסד.\\n"
            "נתוני סורק אינם audit ואינם המלצת קנייה/מכירה.\\n"
            "לפני חתימה יש לבדוק כתובת חוזה, שרשרת, סכום ויעד."
        ),
        "portfolio_error": "לא ניתן לטעון פורטפוליו כרגע.",
        "tradepro_text": "⭐ Trade Pro — 199 Stars\\nגישה לפיצ'רים מתקדמים של SLH Trade.",
        "commands": "פקודות: /trade · /token <address> · /swap <chain> <token> · /portfolio · /trade_model · /tradepro",
    },
    "en": {
        "title": "🚀 SLH TRADE TERMINAL",
        "subtitle": "Multichain, non-custodial trading surface.",
        "chains": "Chains: Ethereum · Base · Arbitrum · BNB Chain · Solana",
        "scanner": "📊 Token Scanner",
        "portfolio": "👛 Portfolio",
        "swap": "💱 Swap",
        "sniper": "🎯 Sniper",
        "orders": "📈 Limit / DCA",
        "bridge": "🌉 Bridge",
        "model": "💰 Revenue Model",
        "risk": "⚠️ Risks",
        "pro": "⭐ Trade Pro",
        "pro_status": "Trade Pro: {status}",
        "pro_active": "active",
        "pro_locked": "not active",
        "scan_usage": "Usage: /token <token address>",
        "swap_usage": "Usage: /swap <ethereum|base|arbitrum|bsc|solana> <token_address>",
        "unsupported_chain": "Chain is not supported yet.",
        "invalid_token": "Invalid token address.",
        "scan_error": "Market data is unavailable right now.",
        "no_pairs": "No trading pairs found for this address.",
        "trade_link": "🔗 Open trade on the DEX",
        "read_only": "🛡️ The terminal currently never holds keys or signs blockchain transactions.",
        "sniper_safe": "🎯 Sniper is UI/planning only; automated execution is not enabled.",
        "orders_safe": "📈 Limit/DCA are UI-only; live execution will open only after a verified execution connector is installed.",
        "bridge_safe": "🌉 Bridge is planning-only; no automated bridge signing is enabled.",
        "model_text": (
            "💰 SLH TRADE — Revenue Model\\n\\n"
            "1) ⭐ Trade Pro — 199 Stars for advanced features.\\n"
            "2) 💱 Execution fee — currently 0.00%; no hidden fee.\\n"
            "   When an execution connector is enabled, the fee will be shown before signing.\\n"
            "3) 🤝 Partner revenue — only where a documented partnership exists and disclosure is shown.\\n\\n"
            "❌ No profit guarantee.\\n"
            "❌ The terminal does not currently custody user private keys.\\n"
            "✅ Internal balances are never credited from an unverified TX."
        ),
        "risk_text": (
            "⚠️ RISKS\\n\\n"
            "Price, liquidity, slippage, MEV and malicious contracts can cause losses.\\n"
            "Scanner data is not an audit and is not a buy/sell recommendation.\\n"
            "Before signing, verify contract address, chain, amount and destination."
        ),
        "portfolio_error": "Unable to load portfolio right now.",
        "tradepro_text": "⭐ Trade Pro — 199 Stars\\nAccess advanced SLH Trade features.",
        "commands": "Commands: /trade · /token <address> · /swap <chain> <token> · /portfolio · /trade_model · /tradepro",
    },
    "ar": {
        "title": "🚀 منصة تداول SLH",
        "subtitle": "منصة متعددة الشبكات وغير وصائية.",
        "chains": "الشبكات: Ethereum · Base · Arbitrum · BNB Chain · Solana",
        "scanner": "📊 فحص العملات",
        "portfolio": "👛 المحفظة",
        "swap": "💱 مبادلة",
        "sniper": "🎯 Sniper",
        "orders": "📈 Limit / DCA",
        "bridge": "🌉 جسر",
        "model": "💰 نموذج الإيرادات",
        "risk": "⚠️ المخاطر",
        "pro": "⭐ Trade Pro",
        "pro_status": "Trade Pro: {status}",
        "pro_active": "نشط",
        "pro_locked": "غير نشط",
        "scan_usage": "الاستخدام: /token <عنوان العملة>",
        "swap_usage": "الاستخدام: /swap <ethereum|base|arbitrum|bsc|solana> <token_address>",
        "unsupported_chain": "الشبكة غير مدعومة حالياً.",
        "invalid_token": "عنوان العملة غير صالح.",
        "scan_error": "بيانات السوق غير متاحة الآن.",
        "no_pairs": "لم يتم العثور على أزواج تداول لهذا العنوان.",
        "trade_link": "🔗 فتح التداول عبر DEX",
        "read_only": "🛡️ المنصة لا تحتفظ بالمفاتيح ولا توقع المعاملات حالياً.",
        "sniper_safe": "🎯 Sniper متاح للواجهة/التخطيط فقط؛ التنفيذ الآلي غير مفعّل.",
        "orders_safe": "📈 Limit/DCA متاحان كواجهة فقط؛ التنفيذ الحقيقي يحتاج موصل تنفيذ موثّق.",
        "bridge_safe": "🌉 الجسر للعرض والتخطيط فقط؛ لا يوجد توقيع آلي.",
        "model_text": "💰 نموذج إيرادات SLH TRADE\\n\\n⭐ Trade Pro: 199 Stars.\\n💱 رسوم التنفيذ حالياً 0.00%، ولا توجد رسوم مخفية.\\n🤝 إيرادات الشركاء تُكشف عند وجود شراكة موثقة.\\n\\n❌ لا يوجد ضمان ربح.\\n✅ لا يتم احتساب رصيد داخلي من معاملة غير موثقة.",
        "risk_text": "⚠️ المخاطر\\n\\nالسعر والسيولة والانزلاق وMEV والعقود الخبيثة قد تسبب خسائر. بيانات الفحص ليست تدقيقاً ولا توصية شراء/بيع.",
        "portfolio_error": "تعذر تحميل المحفظة الآن.",
        "tradepro_text": "⭐ Trade Pro — 199 Stars\\nوصول إلى ميزات SLH Trade المتقدمة.",
        "commands": "الأوامر: /trade · /token <address> · /swap <chain> <token> · /portfolio · /trade_model · /tradepro",
    },
    "es": {
        "title": "🚀 TERMINAL DE TRADING SLH",
        "subtitle": "Terminal multichain y sin custodia.",
        "chains": "Cadenas: Ethereum · Base · Arbitrum · BNB Chain · Solana",
        "scanner": "📊 Scanner de tokens",
        "portfolio": "👛 Portafolio",
        "swap": "💱 Swap",
        "sniper": "🎯 Sniper",
        "orders": "📈 Limit / DCA",
        "bridge": "🌉 Bridge",
        "model": "💰 Modelo de ingresos",
        "risk": "⚠️ Riesgos",
        "pro": "⭐ Trade Pro",
        "pro_status": "Trade Pro: {status}",
        "pro_active": "activo",
        "pro_locked": "inactivo",
        "scan_usage": "Uso: /token <dirección del token>",
        "swap_usage": "Uso: /swap <ethereum|base|arbitrum|bsc|solana> <token_address>",
        "unsupported_chain": "Cadena no compatible todavía.",
        "invalid_token": "Dirección de token no válida.",
        "scan_error": "Los datos de mercado no están disponibles.",
        "no_pairs": "No se encontraron pares para esta dirección.",
        "trade_link": "🔗 Abrir trading en el DEX",
        "read_only": "🛡️ El terminal no guarda claves ni firma transacciones.",
        "sniper_safe": "🎯 Sniper es solo interfaz/planificación; la ejecución automática está desactivada.",
        "orders_safe": "📈 Limit/DCA son solo interfaz; la ejecución real requiere un conector verificado.",
        "bridge_safe": "🌉 Bridge es solo planificación; no hay firma automática.",
        "model_text": "💰 MODELO DE INGRESOS SLH TRADE\\n\\n⭐ Trade Pro — 199 Stars.\\n💱 Comisión de ejecución — 0,00% actualmente; sin costes ocultos.\\n🤝 Ingresos de socios — solo con divulgación.\\n\\n❌ Sin garantía de ganancias.\\n✅ Nunca se acredita saldo interno por una TX no verificada.",
        "risk_text": "⚠️ RIESGOS\\n\\nPrecio, liquidez, slippage, MEV y contratos maliciosos pueden causar pérdidas. El scanner no es una auditoría ni una recomendación.",
        "portfolio_error": "No se puede cargar el portafolio ahora.",
        "tradepro_text": "⭐ Trade Pro — 199 Stars\\nAcceso a funciones avanzadas de SLH Trade.",
        "commands": "Comandos: /trade · /token <address> · /swap <chain> <token> · /portfolio · /trade_model · /tradepro",
    },
    "ru": {
        "title": "🚀 SLH TRADE TERMINAL",
        "subtitle": "Мультичейн, некастодиальный терминал.",
        "chains": "Сети: Ethereum · Base · Arbitrum · BNB Chain · Solana",
        "scanner": "📊 Сканер токенов",
        "portfolio": "👛 Портфель",
        "swap": "💱 Swap",
        "sniper": "🎯 Sniper",
        "orders": "📈 Limit / DCA",
        "bridge": "🌉 Bridge",
        "model": "💰 Модель дохода",
        "risk": "⚠️ Риски",
        "pro": "⭐ Trade Pro",
        "pro_status": "Trade Pro: {status}",
        "pro_active": "активен",
        "pro_locked": "не активен",
        "scan_usage": "Использование: /token <адрес токена>",
        "swap_usage": "Использование: /swap <ethereum|base|arbitrum|bsc|solana> <token_address>",
        "unsupported_chain": "Сеть пока не поддерживается.",
        "invalid_token": "Неверный адрес токена.",
        "scan_error": "Данные рынка сейчас недоступны.",
        "no_pairs": "Торговые пары для этого адреса не найдены.",
        "trade_link": "🔗 Открыть торговлю в DEX",
        "read_only": "🛡️ Терминал не хранит ключи и не подписывает транзакции.",
        "sniper_safe": "🎯 Sniper пока только интерфейс/планирование; автоисполнение отключено.",
        "orders_safe": "📈 Limit/DCA пока только интерфейс; живое исполнение требует проверенного коннектора.",
        "bridge_safe": "🌉 Bridge пока только планирование; автоматической подписи нет.",
        "model_text": "💰 МОДЕЛЬ ДОХОДА SLH TRADE\\n\\n⭐ Trade Pro — 199 Stars.\\n💱 Комиссия исполнения — сейчас 0,00%, скрытых комиссий нет.\\n🤝 Партнёрские доходы раскрываются при наличии документированной партнёрской связи.\\n\\n❌ Гарантий прибыли нет.\\n✅ Неподтверждённая TX не создаёт внутренний баланс.",
        "risk_text": "⚠️ РИСКИ\\n\\nЦена, ликвидность, проскальзывание, MEV и вредоносные контракты могут привести к потерям. Сканер не является аудитом или рекомендацией.",
        "portfolio_error": "Не удалось загрузить портфель.",
        "tradepro_text": "⭐ Trade Pro — 199 Stars\\nДоступ к расширенным функциям SLH Trade.",
        "commands": "Команды: /trade · /token <address> · /swap <chain> <token> · /portfolio · /trade_model · /tradepro",
    },
    "pt": {
        "title": "🚀 SLH TRADE TERMINAL",
        "subtitle": "Terminal multichain e não custodial.",
        "chains": "Redes: Ethereum · Base · Arbitrum · BNB Chain · Solana",
        "scanner": "📊 Scanner de tokens",
        "portfolio": "👛 Portfólio",
        "swap": "💱 Swap",
        "sniper": "🎯 Sniper",
        "orders": "📈 Limit / DCA",
        "bridge": "🌉 Bridge",
        "model": "💰 Modelo de receita",
        "risk": "⚠️ Riscos",
        "pro": "⭐ Trade Pro",
        "pro_status": "Trade Pro: {status}",
        "pro_active": "ativo",
        "pro_locked": "inativo",
        "scan_usage": "Uso: /token <endereço do token>",
        "swap_usage": "Uso: /swap <ethereum|base|arbitrum|bsc|solana> <token_address>",
        "unsupported_chain": "Rede ainda não suportada.",
        "invalid_token": "Endereço de token inválido.",
        "scan_error": "Os dados de mercado não estão disponíveis agora.",
        "no_pairs": "Nenhum par de negociação encontrado para este endereço.",
        "trade_link": "🔗 Abrir negociação no DEX",
        "read_only": "🛡️ O terminal não guarda chaves nem assina transações.",
        "sniper_safe": "🎯 Sniper é apenas interface/planejamento; execução automática está desativada.",
        "orders_safe": "📈 Limit/DCA são apenas interface; execução real exige um conector verificado.",
        "bridge_safe": "🌉 Bridge é apenas planejamento; não há assinatura automática.",
        "model_text": "💰 MODELO DE RECEITA SLH TRADE\\n\\n⭐ Trade Pro — 199 Stars.\\n💱 Taxa de execução — atualmente 0,00%, sem taxas ocultas.\\n🤝 Receita de parceiros — somente com divulgação.\\n\\n❌ Sem garantia de lucro.\\n✅ TX não verificada nunca cria saldo interno.",
        "risk_text": "⚠️ RISCOS\\n\\nPreço, liquidez, slippage, MEV e contratos maliciosos podem causar perdas. O scanner não é auditoria nem recomendação.",
        "portfolio_error": "Não foi possível carregar o portfólio agora.",
        "tradepro_text": "⭐ Trade Pro — 199 Stars\\nAcesso aos recursos avançados do SLH Trade.",
        "commands": "Comandos: /trade · /token <address> · /swap <chain> <token> · /portfolio · /trade_model · /tradepro",
    },
}


# UI strings used by the Telegram handler outside the main text catalog.
_TEXT["he"].update({
    "ai_explain": "🧠 הסבר AI",
    "ai_explain_prompt": "הסבר למשתמש בעברית איך עובד SLH Trade Terminal, מה אפשר לעשות בו כרגע, מה לא פעיל, ומה הסיכונים. אל תיתן המלצת קנייה/מכירה ואל תבטיח רווח.",
    "execution_connector": "מחבר ביצוע",
    "execution_open": "פעיל",
    "execution_safe": "מצב בטוח",
    "execution_fee": "עמלת ביצוע מוגדרת: {fee:.2f}%",
    "verified": "מאומת",
    "not_verified": "לא אומת",
})
_TEXT["en"].update({
    "ai_explain": "🧠 AI Explanation",
    "ai_explain_prompt": "Explain to the user in English how the SLH Trade Terminal works, what is currently available, what is disabled, and the risks. Do not provide a buy/sell recommendation or profit guarantee.",
    "execution_connector": "Execution connector",
    "execution_open": "OPEN",
    "execution_safe": "SAFE MODE",
    "execution_fee": "Configured execution fee: {fee:.2f}%",
    "verified": "verified",
    "not_verified": "not verified",
})
_TEXT["ar"].update({
    "ai_explain": "🧠 شرح بالذكاء الاصطناعي",
    "ai_explain_prompt": "اشرح للمستخدم بالعربية كيف تعمل منصة SLH Trade، وما المتاح حالياً وما المعطل وما المخاطر. لا تقدم توصية شراء أو بيع ولا ضماناً للربح.",
    "execution_connector": "موصل التنفيذ",
    "execution_open": "مفتوح",
    "execution_safe": "الوضع الآمن",
    "execution_fee": "رسوم التنفيذ المحددة: {fee:.2f}%",
    "verified": "موثّق",
    "not_verified": "غير موثّق",
})
_TEXT["es"].update({
    "ai_explain": "🧠 Explicación de IA",
    "ai_explain_prompt": "Explica al usuario en español cómo funciona SLH Trade, qué está disponible ahora, qué está desactivado y los riesgos. No des recomendaciones de compra/venta ni garantías de ganancias.",
    "execution_connector": "Conector de ejecución",
    "execution_open": "ABIERTO",
    "execution_safe": "MODO SEGURO",
    "execution_fee": "Comisión de ejecución configurada: {fee:.2f}%",
    "verified": "verificado",
    "not_verified": "no verificado",
})
_TEXT["ru"].update({
    "ai_explain": "🧠 Объяснение ИИ",
    "ai_explain_prompt": "Объясни пользователю по-русски, как работает SLH Trade, что сейчас доступно, что отключено и какие есть риски. Не давай рекомендаций покупать/продавать и не обещай прибыль.",
    "execution_connector": "Коннектор исполнения",
    "execution_open": "ОТКРЫТ",
    "execution_safe": "БЕЗОПАСНЫЙ РЕЖИМ",
    "execution_fee": "Настроенная комиссия исполнения: {fee:.2f}%",
    "verified": "подтверждено",
    "not_verified": "не подтверждено",
})
_TEXT["pt"].update({
    "ai_explain": "🧠 Explicação por IA",
    "ai_explain_prompt": "Explique ao usuário em português como funciona o SLH Trade, o que está disponível agora, o que está desativado e os riscos. Não dê recomendação de compra/venda nem garantia de lucro.",
    "execution_connector": "Conector de execução",
    "execution_open": "ABERTO",
    "execution_safe": "MODO SEGURO",
    "execution_fee": "Taxa de execução configurada: {fee:.2f}%",
    "verified": "verificado",
    "not_verified": "não verificado",
})


def language_for(uid: str) -> str:
    try:
        from language_handler import get_lang
        lang = get_lang(str(uid))
    except Exception:
        lang = "he"
    return lang if lang in _TEXT else "en"


def t(key: str, uid: str, **kwargs) -> str:
    lang = language_for(uid)
    value = _TEXT.get(lang, _TEXT["en"]).get(key, _TEXT["en"].get(key, key))
    return str(value).format(**kwargs)


def execution_fee_bps() -> int:
    raw = os.getenv("SLH_TRADE_EXECUTION_FEE_BPS", str(DEFAULT_EXECUTION_FEE_BPS)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_EXECUTION_FEE_BPS
    return max(0, min(value, 1000))


def execution_enabled() -> bool:
    return os.getenv("SLH_TRADE_EXECUTION_ENABLED", "0").strip() == "1"


def tradepro_active(uid: str) -> bool:
    try:
        from core.profile_manager import get_user
        user = get_user(str(uid)) or {}
        perms = user.get("permissions", [])
        return "trade_pro" in perms
    except Exception:
        return False


def dex_url(chain: str, token_address: str) -> str:
    chain = str(chain).strip().lower()
    token = quote(str(token_address).strip(), safe="")
    if chain not in SUPPORTED_CHAINS:
        raise ValueError("UNSUPPORTED_CHAIN")
    if not token:
        raise ValueError("INVALID_TOKEN")
    if chain in {"ethereum", "base", "arbitrum"}:
        return f"https://app.uniswap.org/swap?chain={chain}&outputCurrency={token}"
    if chain == "bsc":
        return f"https://pancakeswap.finance/swap?chain=bsc&outputCurrency={token}"
    return f"https://jup.ag/swap/SOL-{token_address}"


def fetch_token_snapshot(token_address: str) -> dict:
    token_address = str(token_address or "").strip()
    if not token_address or len(token_address) > 120 or any(ch.isspace() for ch in token_address):
        raise ValueError("INVALID_TOKEN")
    url = "https://api.dexscreener.com/latest/dex/tokens/" + quote(token_address, safe="")
    response = requests.get(
        url,
        timeout=8,
        headers={"Accept": "application/json", "User-Agent": "SLH-Trade/1.0"},
    )
    response.raise_for_status()
    data = response.json() if response.content else {}
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("NO_PAIRS")
    pairs = [p for p in pairs if isinstance(p, dict)]
    pairs.sort(
        key=lambda p: float(((p.get("liquidity") or {}).get("usd") or 0)),
        reverse=True,
    )
    p = pairs[0]
    return {
        "chain": str(p.get("chainId") or ""),
        "dex": str(p.get("dexId") or ""),
        "pair": str(p.get("pairAddress") or ""),
        "base_symbol": str(((p.get("baseToken") or {}).get("symbol") or "")),
        "base_name": str(((p.get("baseToken") or {}).get("name") or "")),
        "price_usd": p.get("priceUsd"),
        "price_change_24h": ((p.get("priceChange") or {}).get("h24")),
        "liquidity_usd": ((p.get("liquidity") or {}).get("usd")),
        "volume_24h": ((p.get("volume") or {}).get("h24")),
        "pair_url": str(p.get("url") or ""),
    }
