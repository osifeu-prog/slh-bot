const $=id=>document.getElementById(id);
const tg=window.Telegram?.WebApp;
if(tg){tg.ready();tg.expand();}
function headers(){const h={"Accept":"application/json"};if(tg?.initData)h["X-Telegram-Init-Data"]=tg.initData;return h}
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function statusClass(s){return s==="SUCCESS"||s==="PASS"?"ok":"bad"}
async function load(){
  $("banner").textContent="טוען מפת מערכת ובדיקות…";
  try{
    const r=await fetch("/api/system-map",{headers:headers()});
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||("HTTP "+r.status));
    const v=d.verification||{};
    $("banner").textContent=v.status==="PASS"?"🟢 המערכת עברה את כל בדיקות ה-read-only":"🔴 נמצאו כשלים — פתח את הרשימה למטה";
    $("banner").className="banner "+statusClass(v.status);
    $("timestamp").textContent=d.timestamp||"";
    $("summary").textContent=`${v.passed||0}/${v.total||0} PASS`;
    const infra=d.infrastructure||{};
    $("stats").innerHTML=[
      ["👤 Users",d.users?.count||0],["🤖 Agents",d.agents?.count||0],["🟢 Active",d.agents?.active||0],
      ["🏗️ Projects",infra.projects||0],["⚙️ Services",infra.services||0]
    ].map(x=>`<div class="stat"><span class="muted">${x[0]}</span><b>${esc(x[1])}</b></div>`).join("");
    const nodes=[
      ["🧠 SLH OS","Gateway + runtime"],["🌐 Mini App","/mini-app"],["🖥️ Control Plane","/dashboard"],
      ["🤖 Agents",`${d.agents?.count||0} registered`],["🏭 Bot Factory","Registry + deploy binding"],
      ["🎓 Academy","User learning flow"],["💳 Economy","Credits / ledger"],["🚀 Alpha",d.verification?.checks?.find(x=>x.name==="alpha")?.detail||"unknown"],
      ["🔗 Git",d.deployment?.branch||"unknown"],["🚂 Railway",d.deployment?.environment||"unknown"]
    ];
    $("map").innerHTML=nodes.map(n=>`<div class="node"><b><span class="dot"></span>${esc(n[0])}</b><small>${esc(n[1])}</small></div>`).join("");
    $("checks").innerHTML=(v.checks||[]).map(c=>`<div class="check"><span>${c.status==="PASS"?"🟢":"🔴"} ${esc(c.name)}</span><span class="${c.status==="PASS"?"pass":"fail"}">${esc(c.detail)}</span></div>`).join("");
    const dep=d.deployment||{};
    $("deployment").innerHTML=[["Commit",dep.commit],["Branch",dep.branch],["Environment",dep.environment],["Deployment",dep.deployment_id],["Schema",infra.schema_version],["Verified",infra.verified_date_utc]].map(x=>`<div class="detail"><span class="muted">${esc(x[0])}</span><br><b>${esc(x[1]||"—")}</b></div>`).join("");
    $("runtime").innerHTML=[["Agents",d.agents?.count||0],["Active",d.agents?.active||0],["AI",JSON.stringify(d.ai||{})],["Bots",((d.bots||{}).count??"registry metadata")],["Users",d.users?.count||0],["Scope","READ ONLY"]].map(x=>`<div class="detail"><span class="muted">${esc(x[0])}</span><br><b>${esc(x[1])}</b></div>`).join("");
    const rows=infra.services_inventory||[];
    $("railway").innerHTML=rows.length?`<table class="railway-table"><thead><tr><th>Project</th><th>Service</th><th>Repo</th><th>Status</th><th>Class</th></tr></thead><tbody>${rows.map(s=>`<tr><td>${esc(s.project)}</td><td>${esc(s.service)}</td><td>${esc(s.repo)}</td><td><span class="pill ${statusClass(s.status)}">${esc(s.status||"unknown")}</span></td><td>${esc(s.class)}</td></tr>`).join("")}</tbody></table>`:"אין inventory זמין";
  }catch(e){$("banner").textContent="🔐 "+e.message;$("banner").className="banner bad"}
}
$("refresh").onclick=load;load();
