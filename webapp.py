from flask import Flask, jsonify, send_from_directory, request, make_response
import json
from pathlib import Path

from core.telegram_webapp_auth import validate_init_data
from core.investor_read_model import get_investor_snapshot
from core.alpha_control_plane import alpha_state
from core.wallet_binding import issue_challenge, verify_signature, get_binding
from core.profile_manager import get_user
from core import staking_service

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
    """Serve the Mini App with a compatibility and staking UX shim."""
    html_path = BASE_DIR / "mini_app.html"
    html = html_path.read_text(encoding="utf-8")
    shim = """
<script>
function showGuide(id){
  const el=document.getElementById(id);
  if(!el){return;}
  if(el.tagName.toLowerCase()==='details'){
    el.open=true;
    el.scrollIntoView({behavior:'smooth',block:'center'});
  }
}
(function(){
  function installStakingUi(){
    const stake=document.getElementById('stake');
    if(!stake || document.getElementById('miniapp-staking-box')) return;
    const box=document.createElement('div');
    box.id='miniapp-staking-box';
    box.className='card';
    box.innerHTML=`
      <b>🔒 הפעלת Staking</b>
      <p class="muted">Staking פנימי של Credits · נעילה ל־30 יום.</p>
      <div class="wallet-row"><span class="muted">Credits זמינים</span><strong id="stakeAvailable">—</strong></div>
      <label class="form-label" for="miniStakeAmount">סכום Credits לנעילה</label>
      <input id="miniStakeAmount" class="form-input" inputmode="numeric" type="number" min="1" step="1" placeholder="לדוגמה: 250">
      <div class="wallet-row"><span class="muted">לאחר הפעולה</span><span id="stakePreview">—</span></div>
      <button id="miniStakeConfirm" class="action primary" style="width:100%;margin-top:10px;min-height:56px"><b>אישור נעילת 30 יום</b><span>יצירת Position בפועל</span></button>
      <div id="miniStakeStatus" class="muted" style="margin-top:9px"></div>
      <p class="muted" style="margin-top:10px">זהו מנגנון פנימי של SLH ואינו העברת נכס on-chain.</p>`;
    stake.prepend(box);

    const amountEl=document.getElementById('miniStakeAmount');
    const availableEl=document.getElementById('stakeAvailable');
    const previewEl=document.getElementById('stakePreview');
    const statusEl=document.getElementById('miniStakeStatus');
    const confirmEl=document.getElementById('miniStakeConfirm');

    function currentCredits(){
      const raw=(document.getElementById('credits')||{}).textContent || '';
      const n=Number(String(raw).replace(/[^0-9.-]/g,''));
      return Number.isFinite(n) ? n : 0;
    }
    function renderPreview(){
      const available=currentCredits();
      const amount=Number(amountEl.value||0);
      availableEl.textContent=available;
      if(amount>0 && amount<=available){
        previewEl.textContent=`Credits: ${available-amount} · Staked: +${amount}`;
        confirmEl.disabled=false;
      } else {
        previewEl.textContent=amount>available ? 'אין מספיק Credits' : 'בחר סכום';
        confirmEl.disabled=true;
      }
    }
    amountEl.addEventListener('input',renderPreview);
    confirmEl.addEventListener('click',async function(){
      const amount=Number(amountEl.value||0);
      const available=currentCredits();
      if(!Number.isInteger(amount) || amount<=0){
        statusEl.textContent='יש להזין סכום שלם וחיובי.';
        return;
      }
      if(amount>available){
        statusEl.textContent='אין מספיק Credits זמינים.';
        return;
      }
      if(!window.Telegram || !Telegram.WebApp || !Telegram.WebApp.initData){
        statusEl.textContent='נדרשת פתיחה מתוך Telegram Mini App.';
        return;
      }
      confirmEl.disabled=true;
      statusEl.textContent='מאשר ומעדכן את ה־Position…';
      try{
        const res=await fetch('/api/v1/staking',{
          method:'POST',
          headers:{'Content-Type':'application/json','X-Telegram-Init-Data':Telegram.WebApp.initData},
          body:JSON.stringify({amount})
        });
        const data=await res.json().catch(()=>({}));
        if(!res.ok){
          if(data.error==='INSUFFICIENT_CREDITS') throw new Error('אין מספיק Credits זמינים.');
          if(res.status===401) throw new Error('יש לפתוח את הממשק מתוך Telegram.');
          throw new Error('לא ניתן ליצור Position כרגע.');
        }
        statusEl.textContent=`✓ Staking פעיל · ${data.amount} Credits ננעלו · Position ${data.position.id}`;
        amountEl.value='';
        if(typeof refreshAll==='function') await refreshAll();
        renderPreview();
      }catch(err){
        statusEl.textContent=err.message || 'אירעה שגיאה.';
        confirmEl.disabled=false;
      }
    });
    renderPreview();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',installStakingUi);
  else installStakingUi();
  window.installStakingUi=installStakingUi;
})();
</script>
"""
    if "function showGuide(" not in html:
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
        snapshot = get_investor_snapshot(uid)
        global_alpha = alpha_state()
        if isinstance(snapshot.get("alpha"), dict):
            alpha = snapshot["alpha"]
            alpha["readiness_status"] = alpha.get("status", "review")
            alpha["global_status"] = global_alpha.get("status", "CLOSED")
            if alpha["global_status"] == "OPEN":
                alpha["status"] = "OPEN"
        snapshot["alpha_global"] = global_alpha
        return jsonify(snapshot), 200
    except ValueError as exc:
        if str(exc) == "USER_NOT_FOUND":
            return jsonify({"error": "USER_NOT_FOUND"}), 404
        raise


@app.route("/api/v1/staking", methods=["POST"])
def create_staking_position():
    """Public Mini App staking mutation is disabled; expose read-only status only."""
    return jsonify({
        "error": "STAKING_MUTATION_DISABLED",
        "message": "Staking actions are not enabled through the public Mini App.",
    }), 403
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


# Read-only adapter over the existing exchange state. No order placement or settlement.
@app.route("/api/v1/exchange/markets")
def exchange_markets():
    return jsonify({"markets": [{"base": "SLH", "quote": "CREDITS", "symbol": "SLH/CREDITS"}]})


@app.route("/api/v1/exchange/orderbook")
def exchange_orderbook():
    db = load_db()
    raw = db.get("exchange_orders", {})
    orders = list(raw.values()) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    rows = []
    for order in orders:
        if not isinstance(order, dict) or order.get("status") != "open":
            continue
        rows.append({
            "id": order.get("id"),
            "side": order.get("side"),
            "amount": order.get("remaining_amount", order.get("original_amount")),
            "price": order.get("limit_price"),
            "created_at": order.get("created_at"),
        })
    rows.sort(key=lambda x: (x.get("created_at") or ""))
    return jsonify({"symbol": "SLH/CREDITS", "orders": rows})


@app.route("/api/v1/exchange/trades")
def exchange_trades():
    db = load_db()
    raw = db.get("exchange_trades", [])
    trades = raw if isinstance(raw, list) else []
    public_trades = []
    for trade in trades[-100:]:
        public_trades.append({
            "slh_amount": trade.get("slh_amount"),
            "price": trade.get("price"),
            "credits_value": trade.get("credits_value"),
            "timestamp": trade.get("timestamp"),
        })
    return jsonify({"symbol": "SLH/CREDITS", "trades": public_trades})


@app.route("/api/v1/exchange/ticker")
def exchange_ticker():
    db = load_db()
    raw = db.get("exchange_trades", [])
    trades = raw if isinstance(raw, list) else []
    if not trades:
        return jsonify({"symbol": "SLH/CREDITS", "has_data": False, "last_price": None})
    last = trades[-1]
    return jsonify({
        "symbol": "SLH/CREDITS",
        "has_data": True,
        "last_price": last.get("price"),
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )