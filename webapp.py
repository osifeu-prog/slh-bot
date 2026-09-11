from flask import Flask, jsonify, send_from_directory, request, make_response
import json
from pathlib import Path

from core.telegram_webapp_auth import validate_init_data
from core.investor_read_model import get_investor_snapshot
from core.wallet_binding import issue_challenge, verify_signature, get_binding

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state" / "db.json"

app = Flask(__name__)


def load_db():
    if not DB_PATH.exists():
        return {}
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def authenticated_uid():
    """Return the Telegram UID authenticated by server-validated initData."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    try:
        return validate_init_data(init_data)["uid"]
    except (ValueError, RuntimeError):
        return None


def require_auth():
    """Require a valid Telegram Mini App identity for non-user-scoped APIs."""
    if authenticated_uid() is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    return None


def require_self(uid):
    authenticated = authenticated_uid()
    if authenticated is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    if str(uid) != authenticated:
        return jsonify({"error": "FORBIDDEN_USER_MISMATCH"}), 403
    return None


@app.route("/health")
def health():
    return "OK", 200


@app.route("/market")
def market():
    return jsonify({
        "status": "SLH Market UP",
        "time": "2026-08-11"
    }), 200


@app.route("/mini-app")
def mini_app():
    """Serve the Mini App and inject the authenticated BNB ownership UI."""
    html_path = BASE_DIR / "mini_app.html"
    html = html_path.read_text(encoding="utf-8")
    shim = """
<style>
#slh-bnb-binding{margin-top:12px}
#slh-bnb-binding .wallet-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}
#slh-bnb-binding .wallet-actions button{background:#ffffff08;border:1px solid #ffffff12;color:#fff;border-radius:15px;padding:13px;text-align:right;min-height:64px}
#slh-bnb-binding .wallet-actions .primary{background:linear-gradient(135deg,#7c5cff,#5b4bd8);border-color:transparent}
#slh-bnb-binding .bnb-address{direction:ltr;text-align:left;font-family:monospace;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
<script>
(function(){
  const tg=window.Telegram&&window.Telegram.WebApp;
  const initData=tg?tg.initData:"";
  const headers=initData?{"X-Telegram-Init-Data":initData,"Content-Type":"application/json"}:{"Content-Type":"application/json"};
  const walletMarkup=`<div id="slh-bnb-binding" class="card"><div class="section-title" style="margin-top:0">🔐 BNB Wallet</div><div id="slh-bnb-status" class="muted">בודק מצב…</div><div id="slh-bnb-address" class="bnb-address" style="margin-top:7px"></div><div class="wallet-actions"><button id="slh-bnb-connect" class="primary"><b>🔗 חיבור ואימות</b><span>חבר ארנק BSC וחתום על הודעת בעלות</span></button><button id="slh-bnb-refresh"><b>↻ בדיקת סטטוס</b><span>בדיקת הארנק המאומת</span></button></div><details class="guide"><summary>📘 איך האימות עובד?</summary><p>המערכת יוצרת הודעת challenge חד־פעמית. הארנק חותם עליה בלבד; החתימה אינה מאשרת העברת כספים. לאחר אימות, /claim מקבל זיכוי רק עבור TX שהשולח שלו הוא אותו ארנק מאומת.</p></details></div>`;

  function install(){
    const wallet=document.getElementById('wallet');
    if(!wallet || document.getElementById('slh-bnb-binding')) return !!wallet;
    wallet.insertAdjacentHTML('beforeend',walletMarkup);
    document.getElementById('slh-bnb-connect').addEventListener('click',connectAndVerify);
    document.getElementById('slh-bnb-refresh').addEventListener('click',loadBinding);
    loadBinding();
    return true;
  }

  function status(text){const e=document.getElementById('slh-bnb-status');if(e)e.textContent=text}
  function address(text){const e=document.getElementById('slh-bnb-address');if(e)e.textContent=text||''}
  function ethereum(){return window.ethereum||null}
  function short(a){return a?a.slice(0,8)+'…'+a.slice(-6):''}

  async function loadBinding(){
    if(!install()) return;
    try{
      const r=await fetch('/api/wallet/bnb',{headers});
      const d=await r.json();
      if(!r.ok) throw new Error(d.error||'BNB_STATUS_FAILED');
      if(d.binding){status('✅ ארנק BNB מאומת');address(d.binding.address+' · '+short(d.binding.address));}
      else {status('לא קיים ארנק BNB מאומת');address('');}
    }catch(e){status('⚠️ לא ניתן לקרוא סטטוס BNB: '+e.message)}
  }

  async function connectAndVerify(){
    const eth=ethereum();
    if(!eth){status('הארנק אינו זמין בתוך ה־Mini App. פתח את ה־Mini App בסביבה עם EIP-1193 wallet, למשל ארנק התומך בחיבור DApp.');return}
    const button=document.getElementById('slh-bnb-connect');
    if(button) button.disabled=true;
    try{
      const accounts=await eth.request({method:'eth_requestAccounts'});
      const addressValue=accounts&&accounts[0];
      if(!addressValue) throw new Error('NO_WALLET_ACCOUNT');
      status('יוצר הודעת אימות…');address(addressValue);
      const challengeResponse=await fetch('/api/wallet/bnb/challenge',{method:'POST',headers,body:JSON.stringify({address:addressValue})});
      const challenge=await challengeResponse.json();
      if(!challengeResponse.ok) throw new Error(challenge.error||'CHALLENGE_FAILED');
      status('חתום על הודעת הבעלות בארנק. אין כאן העברת כספים.');
      let signature;
      try{
        signature=await eth.request({method:'personal_sign',params:[challenge.message,addressValue]});
      }catch(signError){
        signature=await eth.request({method:'personal_sign',params:[addressValue,challenge.message]});
      }
      status('מאמת חתימה…');
      const verifyResponse=await fetch('/api/wallet/bnb/verify',{method:'POST',headers,body:JSON.stringify({address:addressValue,signature})});
      const verified=await verifyResponse.json();
      if(!verifyResponse.ok) throw new Error(verified.error||'VERIFY_FAILED');
      status('✅ ארנק BNB אומת בהצלחה');
      address(verified.binding&&verified.binding.address||addressValue);
    }catch(e){status('⛔ אימות BNB נכשל: '+(e.message||e));}
    finally{if(button)button.disabled=false;}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install); else install();
})();
</script>
<script>
function showGuide(id){
  const el=document.getElementById(id);
  if(!el){return;}
  if(el.tagName.toLowerCase()==='details'){
    el.open=true;
    el.scrollIntoView({behavior:'smooth',block:'center'});
  }
}
</script>
"""
    if "id=\"slh-bnb-binding\"" not in html:
        html = html.replace("</body>", shim + "</body>")
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.route("/api/v1/me")
def investor_me():
    """Return the read-only investor snapshot for the authenticated Telegram user."""
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401

    try:
        return jsonify(get_investor_snapshot(uid)), 200
    except ValueError as exc:
        if str(exc) == "USER_NOT_FOUND":
            return jsonify({"error": "USER_NOT_FOUND"}), 404
        raise


@app.route("/api/wallet/<uid>")
def get_wallet(uid):
    denied = require_self(uid)
    if denied:
        return denied

    db = load_db()
    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {})

    return jsonify({
        "name": user.get("name", str(uid)),
        "credits": wallet.get("credits", 0),
        "staked": wallet.get("staked", 0),
        "token_balance": wallet.get("token_balance", 0),
        "ton_wallet": user.get("ton_wallet")
    })


@app.route("/api/wallet/bnb/challenge", methods=["POST"])
def bnb_wallet_challenge():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        result = issue_challenge(uid, payload.get("address"))
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/wallet/bnb/verify", methods=["POST"])
def bnb_wallet_verify():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        binding = verify_signature(uid, payload.get("address"), payload.get("signature"))
        return jsonify({"status": "verified", "binding": binding}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/wallet/bnb")
def bnb_wallet_binding():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    return jsonify({"binding": get_binding(uid)}), 200


@app.route("/api/tasks/<uid>")
def get_tasks(uid):
    denied = require_self(uid)
    if denied:
        return denied

    db = load_db()
    tasks = db.get("tasks", {})

    result = []

    for tid, task in tasks.items():
        if str(task.get('owner_id', '')) not in ('', str(uid)):
            continue
        done_by = task.get("done_by", [])

        result.append({
            "id": tid,
            "title": task.get("title", "?"),
            "reward": task.get("reward", 0),
            "status": (
                "done"
                if str(uid) in [str(x) for x in done_by]
                else task.get("status", "open")
            ),
            "agent": task.get("agent", "unassigned")
        })

    return jsonify(result)


@app.route("/api/stats")
def stats():
    denied = require_auth()
    if denied:
        return denied

    db = load_db()
    users = db.get("users", {})
    agents = db.get("agents", {})
    tasks = db.get("tasks", {})
    total_credits = 0

    if isinstance(users, dict):
        for user in users.values():
            if isinstance(user, dict):
                wallet = user.get("wallet", {})
                if isinstance(wallet, dict):
                    credits = wallet.get("credits", 0)
                    if isinstance(credits, (int, float)):
                        total_credits += credits

    return jsonify({
        "users": len(users) if isinstance(users, dict) else 0,
        "agents": len(agents) if isinstance(agents, dict) else 0,
        "tasks": len(tasks) if isinstance(tasks, dict) else 0,
        "credits": total_credits,
    })


@app.route("/api/leaderboard")
def api_leaderboard():
    denied = require_auth()
    if denied:
        return denied

    try:
        from plugins.leaderboard import LeaderboardPlugin

        lb = LeaderboardPlugin(str(DB_PATH))
        top = lb.get_top(10)

        result = []

        for uid, data in top:
            result.append({
                "uid": str(uid),
                "name": data.get("name", f"User{uid}"),
                "points": (data.get("gamification") or {}).get("points", 0)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/api/v1/leaderboard")
def api_v1_leaderboard():
    return api_leaderboard()


@app.route("/api/onchain/status")
def onchain_status():
    denied = require_auth()
    if denied:
        return denied

    from core.deposit_monitor import get_onchain_status
    return jsonify(get_onchain_status())


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )
