#!/usr/bin/env python3
"""Apply SLH Mini App UX v1 patches in-place to mini_app.html.

Usage:
  python3 tools/apply_mini_app_ux_v1.py mini_app.html

Safe to re-run. Does not change API contracts or add seed UI.
Restore: branch backup/pre-ui-ux-2026-09-26
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "mini_app.html")
    text = path.read_text(encoding="utf-8")
    orig = text

    if 'class="slh-ds"' not in text:
        text = text.replace("<body>", '<body class="slh-ds">', 1)

    if "SLH Design System v1 overlay" not in text:
        extra_css = """
/* === SLH Design System v1 overlay === */
:root{--surface:#111827;--surface-2:#0d1422;--elevated:#1a2234;--border:#2a3548;--text-2:#cbd5e1;--ok:#34d399;--pending:#fbbf24;--info:#38bdf8;--accent-deep:#5b4bd8;--nav-h:64px}
body.slh-ds{padding-bottom:calc(var(--nav-h) + 20px)}
.slh-ds .nav{display:none !important}
.slh-ds .pill.ok{color:var(--ok);background:#10b98122}
.slh-ds .pill.pending{color:var(--pending);background:#f59e0b22}
.slh-ds .pill.danger{color:var(--danger);background:#fb718522}
.slh-ds .bottom{grid-template-columns:repeat(4,1fr);z-index:20;padding-bottom:max(8px,env(safe-area-inset-bottom));background:#090d16f2}
.slh-ds .bottom button{font-weight:600;border-radius:12px;padding:8px 4px}
.slh-ds .bottom button.active{background:#7c5cff22;color:#fff}
.slh-more-sheet{display:none;position:fixed;left:0;right:0;bottom:var(--nav-h);z-index:19;max-height:55vh;overflow:auto;padding:12px max(12px,calc((100vw - 720px)/2 + 12px));background:var(--elevated);border-top:1px solid var(--border);border-radius:20px 20px 0 0}
.slh-more-sheet.open{display:block}
.slh-more-sheet button{width:100%;text-align:right;margin-bottom:8px;padding:12px 14px;border-radius:14px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:14px;font-weight:700}
.slh-status-hint{margin-top:6px;font-size:12px;color:var(--text-2);line-height:1.55}
.slh-money-strip{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
.slh-money-strip .action{min-height:64px}
"""
        text = text.replace("</style>", extra_css + "</style>", 1)

    if "slh-money-strip" not in text:
        needle2 = '<div class="subtitle">Credits · יתרה פנימית</div></div><div class="grid">'
        money = (
            '\n<div class="slh-money-strip">\n'
            '<button class="action primary" onclick="show(\'wallet\');loadCombined();loadWalletBindings()">'
            '<b>💎 הפקדת TON</b><span>אימות ארנק ואז שליחה עם Memo</span></button>\n'
            '<button class="action primary" onclick="openAction(\'/pay\',\'קניית Credits\')">'
            '<b>⭐ קניית Credits</b><span>Telegram Stars · מיידי</span></button>\n'
            '</div>\n'
        )
        if needle2 in text:
            text = text.replace(
                needle2,
                '<div class="subtitle">Credits · יתרה פנימית</div></div>' + money + '<div class="grid">',
                1,
            )

    if "tonStatusHint" not in text:
        ton_n = '<div id="tonBindingAddress" class="muted" style="margin:6px 0"></div><div id="tonConnectButton"'
        ton_r = (
            '<div id="tonBindingAddress" class="muted" style="margin:6px 0"></div>\n'
            '<div id="tonStatusHint" class="slh-status-hint">'
            'לחץ «אמת ארנק TON», אשר ב-MyTonWallet/Tonkeeper (לא @wallet), ואז אשר חתימת Proof תוך כמה דקות.'
            '</div>\n'
            '<div id="tonConnectButton"'
        )
        if ton_n in text:
            text = text.replace(ton_n, ton_r, 1)

    if "slhBottomNav" not in text:
        new_bottom = '''<div class="bottom" id="slhBottomNav">
<button type="button" id="bh" onclick="show('home')">🏠<br>בית</button>
<button type="button" id="bw" onclick="show('wallet');loadCombined();loadWalletBindings()">👛<br>ארנק</button>
<button type="button" id="bm" onclick="show('market');loadStarsStore()">🛍<br>שוק</button>
<button type="button" id="bmore" onclick="toggleMoreSheet()">⋯<br>עוד</button>
</div>
<div class="slh-more-sheet" id="slhMoreSheet">
<button type="button" onclick="showFromMore('transfer')">💸 העברה</button>
<button type="button" onclick="showFromMore('buy')">💳 קנייה</button>
<button type="button" onclick="showFromMore('stake')">🔒 סטייקינג</button>
<button type="button" onclick="showFromMore('academy')">🎓 Academy</button>
<button type="button" onclick="showFromMore('exchange');loadBook()">🪙 בורסה</button>
<button type="button" onclick="showFromMore('alpha')">🚀 Alpha</button>
<button type="button" onclick="showFromMore('control');loadControl()">🧭 Control</button>
<button type="button" onclick="showFromMore('ai')">✨ AI</button>
<button type="button" onclick="showFromMore('system');loadSystem()">🖥 מערכת</button>
</div>
<div id="toast" class="toast"></div>'''
        bottom_re = re.compile(
            r'<div class="bottom">[\s\S]*?</div>\s*<div id="toast" class="toast"></div>|'
            r'<div class="bottom">[\s\S]*?</nav>\s*<div id="toast" class="toast"></div>|'
            r'<nav class="bottom"[\s\S]*?</nav>\s*<div id="toast" class="toast"></div>',
        )
        text2, n = bottom_re.subn(new_bottom, text, count=1)
        if n:
            text = text2
        else:
            print("WARN: bottom nav pattern not found", file=sys.stderr)

    if "function toggleMoreSheet" not in text and "function show(id){" in text:
        text = text.replace(
            "function show(id){",
            "function toggleMoreSheet(){const el=$('slhMoreSheet');if(!el)return;el.classList.toggle('open');$('bmore')?.classList.toggle('active',el.classList.contains('open'))}\n"
            "function showFromMore(id){$('slhMoreSheet')?.classList.remove('open');$('bmore')?.classList.remove('active');show(id)}\n"
            "function show(id){",
            1,
        )
        text = text.replace(
            "document.querySelectorAll('.nav button,.bottom button').forEach(x=>x.classList.remove('active'));",
            "document.querySelectorAll('.nav button,.bottom button').forEach(x=>x.classList.remove('active'));$('slhMoreSheet')?.classList.remove('open');",
            1,
        )
        text = text.replace(
            "const map={home:['nh','bh'],wallet:['nw','bw'],market:['nm']",
            "const map={home:['nh','bh'],wallet:['nw','bw'],market:['nm','bm']",
            1,
        )
        text = text.replace(
            "if(id==='market')loadStarsStore()}",
            "if(id==='market')loadStarsStore();if(id==='wallet'){loadCombined();loadWalletBindings()}}",
            1,
        )

    if "פג תוקף האימות" not in text:
        old2 = "setText('tonBindingStatus','❌ Proof נדחה');\n      toast('❌ TON: '+(e.message||e));"
        repl = (
            "const code=String(e.message||e||'');\n"
            "      const map={TON_CHALLENGE_EXPIRED:'פג תוקף האימות · לחץ שוב «אמת ארנק» ואשר תוך דקה',"
            "TON_CHALLENGE_MISMATCH:'אתגר לא תואם · התחל אימות מחדש',"
            "TON_PROOF_DOMAIN_MISMATCH:'דומיין לא מורשה · פתח מתוך Mini App בטלגרם',"
            "TON_STATE_INIT_REQUIRED:'הארנק לא שלח state init · נסה Tonkeeper/MyTonWallet',"
            "INVALID_TON_PROOF:'חתימה לא תקינה · אשר Proof בארנק',"
            "TON_WALLET_ALREADY_BOUND:'הארנק כבר מקושר למשתמש אחר',"
            "USER_ALREADY_HAS_TON_WALLET:'כבר יש ארנק TON מאומת לחשבון'};\n"
            "      const human=map[code]||code;\n"
            "      setText('tonBindingStatus','❌ '+code);\n"
            "      setText('tonStatusHint', human);\n"
            "      toast('❌ '+human);"
        )
        if old2 in text:
            text = text.replace(old2, repl, 1)

    if text == orig:
        print("No changes applied (already patched or patterns missed)")
        return 0

    path.write_text(text, encoding="utf-8")
    print(f"Patched {path} delta={len(text) - len(orig)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
