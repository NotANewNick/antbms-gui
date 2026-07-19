# -*- coding: utf-8 -*-
"""Embedded single-page dashboard (served by webui.py). No external assets."""

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ANT BMS Dashboard</title>
<style>
  :root{
    --bg:#0c1018; --panel:#151b27; --panel2:#1b2333; --line:#26303f;
    --txt:#e7ecf3; --mut:#8a98ad; --acc:#39d98a; --acc2:#3aa0ff;
    --warn:#ffb020; --bad:#ff5d5d; --chg:#39d98a; --dis:#3aa0ff;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{display:flex;align-items:center;gap:16px;padding:14px 20px;
    background:linear-gradient(180deg,#11161f,#0c1018);border-bottom:1px solid var(--line);
    position:sticky;top:0;z-index:5}
  header h1{font-size:16px;margin:0;letter-spacing:.5px;font-weight:600}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--bad);box-shadow:0 0 8px var(--bad)}
  .dot.ok{background:var(--acc);box-shadow:0 0 8px var(--acc)}
  .pill{font-size:12px;color:var(--mut);padding:3px 10px;border:1px solid var(--line);border-radius:20px}
  .spacer{flex:1}
  .tabs{display:flex;gap:6px}
  .tab{padding:6px 14px;border:1px solid var(--line);border-radius:8px;cursor:pointer;color:var(--mut);background:var(--panel)}
  .tab.active{color:var(--txt);border-color:var(--acc2);background:var(--panel2)}
  main{padding:20px;max-width:1200px;margin:0 auto}
  .grid{display:grid;gap:16px}
  .g4{grid-template-columns:repeat(4,1fr)}
  .g3{grid-template-columns:repeat(3,1fr)}
  .g2{grid-template-columns:2fr 1fr}
  @media(max-width:900px){.g4,.g3,.g2{grid-template-columns:1fr 1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
  .card h2{margin:0 0 12px;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);font-weight:600}
  .stat{display:flex;flex-direction:column;gap:4px}
  .stat .v{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums}
  .stat .u{font-size:13px;color:var(--mut)}
  .stat .l{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px}
  .ring{display:flex;align-items:center;gap:18px}
  .ring svg{transform:rotate(-90deg)}
  .big{font-size:40px;font-weight:800}
  .cells{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}
  .cell{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px;position:relative;overflow:hidden}
  .cell .n{font-size:11px;color:var(--mut)}
  .cell .mv{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
  .cell .bar{height:6px;border-radius:4px;background:#2a3547;margin-top:8px;overflow:hidden}
  .cell .bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--acc2),var(--acc))}
  .cell.max{border-color:var(--acc)} .cell.min{border-color:var(--warn)}
  .cell.bal::after{content:"BAL";position:absolute;top:8px;right:8px;font-size:9px;color:#0c1018;
    background:var(--acc);padding:1px 5px;border-radius:4px;font-weight:700}
  .tag{display:inline-block;padding:3px 9px;border-radius:7px;font-size:12px;margin:3px 4px 0 0}
  .tag.ok{background:rgba(57,217,138,.14);color:var(--acc);border:1px solid rgba(57,217,138,.3)}
  .tag.warn{background:rgba(255,176,32,.14);color:var(--warn);border:1px solid rgba(255,176,32,.35)}
  .tag.bad{background:rgba(255,93,93,.14);color:var(--bad);border:1px solid rgba(255,93,93,.35)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
  th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
  td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
  input[type=number],input[type=text]{background:var(--bg);border:1px solid var(--line);color:var(--txt);
    border-radius:7px;padding:6px 8px;width:110px;font-variant-numeric:tabular-nums}
  button{background:var(--acc2);color:#031018;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer}
  button.ghost{background:var(--panel2);color:var(--txt);border:1px solid var(--line)}
  button.danger{background:var(--bad);color:#220606}
  button:disabled{opacity:.5;cursor:default}
  .cmdgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
  .cmdgrid button{width:100%;text-align:left;padding:11px 14px}
  .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .muted{color:var(--mut)}
  .hidden{display:none}
  .flash{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:var(--panel2);
    border:1px solid var(--line);padding:10px 16px;border-radius:10px;opacity:0;transition:.3s;pointer-events:none}
  .flash.show{opacity:1}
  .connbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 20px;
    background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:53px;z-index:4}
  .connbar input,.connbar select{background:var(--bg);border:1px solid var(--line);color:var(--txt);
    border-radius:7px;padding:7px 9px}
  .connbar input#addrInput{width:230px}
  .hint{padding:40px;text-align:center;color:var(--mut)}
  .temps{display:flex;gap:12px;flex-wrap:wrap}
  .temps .t{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 14px;text-align:center}
  .temps .t .v{font-size:20px;font-weight:700}
</style>
</head>
<body>
<header>
  <span class="dot" id="dot"></span>
  <h1>ANT&nbsp;BMS</h1>
  <span class="pill" id="addr">—</span>
  <span class="pill" id="status">connecting…</span>
  <div class="spacer"></div>
  <div class="tabs">
    <div class="tab active" data-tab="live">Live</div>
    <div class="tab" data-tab="settings">Settings</div>
    <div class="tab" data-tab="controls">Controls</div>
  </div>
</header>

<div class="connbar">
  <button id="scanBtn">Scan</button>
  <input id="addrInput" list="devlist" placeholder="device address (or Scan)" autocomplete="off">
  <datalist id="devlist"></datalist>
  <input id="pwInput" type="text" placeholder="unlock password (optional)" value="12345678" style="width:170px">
  <button id="connectBtn">Connect</button>
  <button class="ghost" id="demoBtn">Demo</button>
  <button class="ghost" id="disconnectBtn">Disconnect</button>
  <span class="muted" id="connMsg"></span>
</div>

<main>
  <!-- LIVE -->
  <section id="tab-live">
    <div class="hint hidden" id="liveHint">Not connected. Use <b>Scan</b> → pick a device → <b>Connect</b>, or click <b>Demo</b>.</div>
    <div class="grid g4" style="margin-bottom:16px">
      <div class="card"><div class="ring">
        <svg width="92" height="92" viewBox="0 0 92 92">
          <circle cx="46" cy="46" r="40" stroke="#26303f" stroke-width="8" fill="none"/>
          <circle id="socArc" cx="46" cy="46" r="40" stroke="var(--acc)" stroke-width="8"
                  fill="none" stroke-linecap="round" stroke-dasharray="251" stroke-dashoffset="251"/>
        </svg>
        <div><div class="big" id="soc">—</div><div class="u">% SOC · SOH <span id="soh">—</span>%</div></div>
      </div></div>
      <div class="card stat"><div class="l">Pack Voltage</div><div class="v"><span id="vpack">—</span> <span class="u">V</span></div><div class="u" id="vavg">avg —</div></div>
      <div class="card stat"><div class="l">Current</div><div class="v"><span id="cur">—</span> <span class="u">A</span></div><div class="u" id="flow">—</div></div>
      <div class="card stat"><div class="l">Power</div><div class="v"><span id="pwr">—</span> <span class="u">W</span></div><div class="u" id="state">—</div></div>
    </div>

    <div class="grid g2" style="margin-bottom:16px">
      <div class="card">
        <h2>Cells <span class="muted" id="cellinfo"></span></h2>
        <div class="cells" id="cells"></div>
      </div>
      <div class="card">
        <h2>Capacity & Runtime</h2>
        <table>
          <tr><td>Remaining</td><td class="r"><span id="remah">—</span> Ah</td></tr>
          <tr><td>Physical</td><td class="r"><span id="physah">—</span> Ah</td></tr>
          <tr><td>Total cycled</td><td class="r"><span id="cycah">—</span> Ah</td></tr>
          <tr><td>Cell Δ (max−min)</td><td class="r"><span id="vdiff">—</span> V</td></tr>
          <tr><td>Max / Min cell</td><td class="r"><span id="vmaxmin">—</span></td></tr>
          <tr><td>Runtime</td><td class="r"><span id="runtime">—</span></td></tr>
        </table>
      </div>
    </div>

    <div class="grid g3">
      <div class="card">
        <h2>Temperatures</h2>
        <div class="temps" id="temps"></div>
      </div>
      <div class="card">
        <h2>MOS &amp; Balance</h2>
        <table>
          <tr><td>Charge MOS</td><td class="r"><span class="tag" id="chmos">—</span></td></tr>
          <tr><td>Discharge MOS</td><td class="r"><span class="tag" id="dismos">—</span></td></tr>
          <tr><td>Balance</td><td class="r"><span class="tag" id="bal">—</span></td></tr>
        </table>
      </div>
      <div class="card">
        <h2>Protections &amp; Warnings</h2>
        <div id="alarms"><span class="tag ok">all clear</span></div>
      </div>
    </div>
  </section>

  <!-- SETTINGS -->
  <section id="tab-settings" class="hidden">
    <div class="card" style="margin-bottom:16px">
      <div class="row">
        <button id="loadBtn">Load settings</button>
        <button class="ghost" id="saveFlash">Save to flash</button>
        <span style="width:20px"></span>
        <input id="backupPath" type="text" style="width:220px" value="antbms_backup.json">
        <button class="ghost" id="backupBtn">Backup</button>
        <button class="ghost" id="restoreBtn">Restore</button>
        <label class="muted"><input type="checkbox" id="restoreSave" checked> save after restore</label>
        <div class="spacer"></div>
        <span class="muted" id="setInfo"></span>
      </div>
    </div>
    <div class="row" id="groupTabs" style="margin-bottom:14px"></div>
    <div id="groups"><div class="card muted">Click “Load settings”.</div></div>
  </section>

  <!-- CONTROLS -->
  <section id="tab-controls" class="hidden">
    <div class="card" style="margin-bottom:16px">
      <span class="muted">Action buttons mirror the app's <b>BMS Control</b> page. Destructive
      actions ask for confirmation. These send commands to the BMS
      (function 0x51); writes may require the unlock password.</span>
    </div>
    <div id="cmdGroups"></div>
  </section>
</main>
<div class="flash" id="flash"></div>

<script>
const $ = s => document.querySelector(s);
const fmt = (v,d=2)=> v==null||isNaN(v) ? "—" : Number(v).toFixed(d);
function flash(msg,bad){const f=$("#flash");f.textContent=msg;f.style.borderColor=bad?"var(--bad)":"var(--line)";
  f.classList.add("show");setTimeout(()=>f.classList.remove("show"),2200);}
function hms(s){if(s==null)return "—";s=Math.floor(s);const d=Math.floor(s/86400);s%=86400;
  const h=Math.floor(s/3600);s%=3600;const m=Math.floor(s/60);return (d?d+"d ":"")+h+"h "+m+"m";}

const TABS=["live","settings","controls"];
document.querySelectorAll("header .tab").forEach(t=>t.onclick=()=>{
  document.querySelectorAll("header .tab").forEach(x=>x.classList.remove("active"));
  t.classList.add("active");
  const sel=t.dataset.tab;
  TABS.forEach(name=>$("#tab-"+name).classList.toggle("hidden",name!==sel));
  if(sel==="controls" && !CMDS_LOADED) loadCommands();
});

function renderCells(t){
  const box=$("#cells");box.innerHTML="";
  const lo=3.0, hi=3.65;
  (t.cells||[]).forEach((v,i)=>{
    const pos=i+1;
    const pct=Math.max(2,Math.min(100,(v-lo)/(hi-lo)*100));
    const cls=["cell"];
    if(pos===t.cell_v_max_pos)cls.push("max");
    if(pos===t.cell_v_min_pos)cls.push("min");
    if((t.balancing_cells||[]).includes(pos))cls.push("bal");
    const d=document.createElement("div");d.className=cls.join(" ");
    d.innerHTML=`<div class="n">Cell ${pos}</div><div class="mv">${fmt(v,3)}<span class="u"> V</span></div>
      <div class="bar"><i style="width:${pct}%"></i></div>`;
    box.appendChild(d);
  });
  $("#cellinfo").textContent=`· ${t.cell_count} series`;
}
function renderTemps(t){
  const box=$("#temps");box.innerHTML="";
  const add=(lbl,v)=>{const e=document.createElement("div");e.className="t";
    e.innerHTML=`<div class="muted">${lbl}</div><div class="v">${v==null?"—":v+"°"}</div>`;box.appendChild(e);};
  (t.temperatures||[]).forEach((v,i)=>add("T"+(i+1),v));
  add("MOS",t.temp_mos); add("Bal",t.temp_balance);
}
function renderAlarms(t){
  const box=$("#alarms");box.innerHTML="";
  const items=[...(t.protections||[]).map(x=>["bad",x]),...(t.warnings||[]).map(x=>["warn",x])];
  if(!items.length){box.innerHTML='<span class="tag ok">all clear</span>';return;}
  items.forEach(([c,x])=>{const s=document.createElement("span");s.className="tag "+c;s.textContent=x;box.appendChild(s);});
}
function mos(el,label,code){
  el.textContent=label||"—";
  el.className="tag "+(code===1?"ok":code===0?"":"bad");
}
function render(t){
  $("#soc").textContent=t.soc??"—";
  $("#soh").textContent=t.soh??"—";
  $("#socArc").style.strokeDashoffset = 251-(251*(t.soc||0)/100);
  $("#vpack").textContent=fmt(t.pack_voltage,2);
  $("#vavg").textContent="avg "+fmt(t.cell_v_avg,3)+" V";
  $("#cur").textContent=fmt(t.current,2);
  const flowing = t.current>0.05?"charging":t.current<-0.05?"discharging":"idle";
  $("#flow").textContent=flowing;
  $("#cur").style.color = t.current>0.05?"var(--chg)":t.current<-0.05?"var(--dis)":"var(--txt)";
  $("#pwr").textContent=t.power??"—";
  $("#state").textContent=t.state||"—";
  $("#remah").textContent=fmt(t.remaining_capacity_ah,2);
  $("#physah").textContent=fmt(t.physical_capacity_ah,1);
  $("#cycah").textContent=fmt(t.cycle_capacity_ah,2);
  $("#vdiff").textContent=fmt(t.cell_v_diff,3);
  $("#vmaxmin").textContent=`${fmt(t.cell_v_max,3)} (#${t.cell_v_max_pos}) / ${fmt(t.cell_v_min,3)} (#${t.cell_v_min_pos})`;
  $("#runtime").textContent=hms(t.runtime_s);
  renderCells(t);renderTemps(t);renderAlarms(t);
  mos($("#chmos"),t.charge_mos,t.charge_mos_code);
  mos($("#dismos"),t.discharge_mos,t.discharge_mos_code);
  $("#bal").textContent=t.balance||"—";
  $("#bal").className="tag "+(t.balance_code?"warn":"");
}

let MODE="idle";
async function poll(){
  try{
    const r=await fetch("/api/state");const s=await r.json();
    MODE=s.mode||"idle";
    const ok=s.connected && s.telemetry;
    $("#dot").classList.toggle("ok",ok);
    $("#addr").textContent = s.address || "—";
    let st;
    if(s.mode==="demo") st="demo "+(s.age!=null?"· "+s.age.toFixed(1)+"s":"");
    else if(s.mode==="live") st=ok?("live · "+(s.age!=null?s.age.toFixed(1)+"s":"")):(s.error||"connecting…");
    else st="not connected";
    $("#status").textContent=st;
    $("#disconnectBtn").style.display = s.mode==="idle" ? "none":"";
    $("#liveHint").classList.toggle("hidden", s.mode!=="idle");
    if(s.telemetry) render(s.telemetry);
  }catch(e){$("#dot").classList.remove("ok");$("#status").textContent="server offline";}
  setTimeout(poll,1000);
}
poll();

// ---- connection controls ----
function conn(msg,bad){const e=$("#connMsg");e.textContent=msg;e.style.color=bad?"var(--bad)":"var(--mut)";}
$("#scanBtn").onclick=async()=>{
  const b=$("#scanBtn");b.disabled=true;conn("scanning…");
  try{
    const r=await fetch("/api/scan",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({timeout:6})});
    const j=await r.json();
    if(j.error){conn(j.error,true);}
    else{
      const dl=$("#devlist");dl.innerHTML="";
      (j.devices||[]).forEach(d=>{const o=document.createElement("option");
        o.value=d.address;o.label=`${d.name||"?"}  (rssi ${d.rssi})`;dl.appendChild(o);});
      if(j.devices&&j.devices.length){$("#addrInput").value=j.devices[0].address;
        conn(`found ${j.devices.length} device(s)`);}
      else conn("no ANT devices found",true);
    }
  }catch(e){conn("scan failed",true);}
  b.disabled=false;
};
$("#connectBtn").onclick=async()=>{
  const address=$("#addrInput").value.trim();
  if(!address){conn("enter or scan a device address",true);return;}
  $("#connectBtn").disabled=true;conn("connecting…");
  try{
    const r=await fetch("/api/connect",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({address,password:$("#pwInput").value})});
    const j=await r.json();
    conn(j.error?j.error:("connected to "+address),!!j.error);
    if(!j.error){SETTINGS={};CMDS_LOADED=false;CURGROUP=null;}
  }catch(e){conn("connect failed",true);}
  $("#connectBtn").disabled=false;
};
$("#demoBtn").onclick=async()=>{
  conn("starting demo…");
  try{await fetch("/api/connect",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({demo:true})});conn("demo running");
    SETTINGS={};CMDS_LOADED=false;CURGROUP=null;}
  catch(e){conn("demo failed",true);}
};
$("#disconnectBtn").onclick=async()=>{
  await fetch("/api/disconnect",{method:"POST"});conn("disconnected");
  SETTINGS={};CMDS_LOADED=false;
};

// ---- settings (grouped by the app's pages) ----
let SETTINGS={}, GROUPS=[], CURGROUP=null;
async function loadSettings(){
  $("#setInfo").textContent="reading…";
  try{
    const r=await fetch("/api/settings");const j=await r.json();
    if(j.error){flash(j.error,true);$("#setInfo").textContent="error";return;}
    SETTINGS=j.settings; GROUPS=j.groups||[];
    renderGroupTabs(); renderSettings();
    $("#setInfo").textContent=Object.keys(SETTINGS).length+" settings";
  }catch(e){flash("read failed",true);$("#setInfo").textContent="error";}
}
function groupCount(gk){return Object.values(SETTINGS).filter(v=>v.group===gk).length;}
function renderGroupTabs(){
  const present=GROUPS.filter(g=>groupCount(g.key)>0);
  if(CURGROUP===null && present.length) CURGROUP=present[0].key;
  const box=$("#groupTabs");box.innerHTML="";
  present.forEach(g=>{
    const t=document.createElement("div");
    t.className="tab"+(g.key===CURGROUP?" active":"");
    t.innerHTML=`${g.label} <span class="muted">${groupCount(g.key)}</span>`;
    t.onclick=()=>{CURGROUP=g.key;renderGroupTabs();renderSettings();};
    box.appendChild(t);
  });
}
function renderSettings(){
  const wrap=$("#groups");wrap.innerHTML="";
  const g=GROUPS.find(x=>x.key===CURGROUP);
  if(!g)return;
  const rows=Object.entries(SETTINGS).filter(([k,v])=>v.group===CURGROUP)
    .sort((a,c)=>a[1].address-c[1].address);
  const card=document.createElement("div");card.className="card";
  card.innerHTML=`<h2>${g.label} <span class="muted">· ${g.desc} · ${rows.length} settings</span></h2>
    <table><thead><tr><th>Setting</th><th class="r">Value</th><th>Unit</th>
      <th class="r">New value</th><th></th></tr></thead><tbody></tbody></table>`;
  const body=card.querySelector("tbody");
  rows.forEach(([k,v])=>{
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${v.name}<div class="muted" style="font-size:11px">${k} · @${v.address}</div></td>
      <td class="r">${v.value}</td><td class="muted">${v.unit||""}</td>
      <td class="r"><input type="number" step="any" data-k="${k}" placeholder="${v.value}"></td>
      <td><button class="ghost" data-set="${k}">Set</button></td>`;
    body.appendChild(tr);
  });
  wrap.appendChild(card);
  body.querySelectorAll("button[data-set]").forEach(btn=>btn.onclick=async()=>{
    const k=btn.dataset.set;const inp=body.querySelector(`input[data-k="${k}"]`);
    if(inp.value==="")return;
    btn.disabled=true;
    try{
      const r=await fetch("/api/set",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({key:k,value:parseFloat(inp.value),save:false})});
      const j=await r.json();
      if(j.ok){flash("set "+k+" = "+inp.value+" (remember to Save to flash)");
        SETTINGS[k].value=parseFloat(inp.value);renderSettings();}
      else flash(j.error||"failed",true);
    }catch(e){flash("failed",true);}
    btn.disabled=false;
  });
}
$("#loadBtn").onclick=loadSettings;
$("#saveFlash").onclick=async()=>{const r=await fetch("/api/save",{method:"POST"});
  const j=await r.json();flash(j.ok?"saved to flash":(j.error||"failed"),!j.ok);};
$("#backupBtn").onclick=async()=>{
  const r=await fetch("/api/backup",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({path:$("#backupPath").value})});
  const j=await r.json();flash(j.ok?("backed up → "+j.path):(j.error||"failed"),!j.ok);};
$("#restoreBtn").onclick=async()=>{
  const path=$("#backupPath").value;
  const vr=await fetch("/api/verify_restore",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({path:path})});
  const v=await vr.json();
  if(!v.ok){flash(v.error||"verify failed",true);return;}
  const rep=v.report;
  let msg="Restore from "+path+"?\n"
    +"items: backup "+rep.backup_count+" / device "+rep.device_count
    +"   names matched: "+(rep.backup_count-rep.name_mismatches.length)+"\n"
    +rep.differences.length+" value(s) will change, "+rep.identical+" identical";
  const warn=[];
  if(rep.address_match===false)warn.push("backup is from a DIFFERENT device ("+rep.backup_address+")");
  if(rep.only_in_backup.length)warn.push(rep.only_in_backup.length+" item(s) only in backup");
  if(rep.only_on_device.length)warn.push(rep.only_on_device.length+" item(s) missing from backup");
  if(rep.name_mismatches.length)warn.push(rep.name_mismatches.length+" name mismatch(es)");
  if(rep.inconsistent_with_chunks.length)warn.push("file edited: "+rep.inconsistent_with_chunks.join(", ")+" (raw data wins)");
  if(warn.length)msg+="\n\nWARNING:\n- "+warn.join("\n- ");
  msg+="\n\nSettings are written, read back and verified; save-to-flash only happens if the read-back matches.";
  if(!confirm(msg))return;
  const r=await fetch("/api/restore",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({path:path,save:$("#restoreSave").checked})});
  const j=await r.json();
  if(!j.ok)flash(j.error||"failed",true);
  else if(!j.verified){
    let m="restore failed: ";
    if(j.error)m+=j.error+" — ";
    if(j.mismatches&&j.mismatches.length)m+=j.mismatches.length+" register(s) failed read-back — ";
    m+=(j.rollback_ok?"previous settings restored":"ROLLBACK INCOMPLETE, restart the BMS to revert")+"; flash unchanged";
    flash(m,true);}
  else flash("restored "+j.registers+" registers, read-back verified"+(j.saved?", saved to flash":""),false);
  if(j.ok)loadSettings();};

// ---- controls (BMS action buttons, mirrors the app's BMS Control page) ----
let CMDS_LOADED=false;
async function loadCommands(){
  try{
    const r=await fetch("/api/commands");const j=await r.json();
    const wrap=$("#cmdGroups");wrap.innerHTML="";
    j.groups.forEach(g=>{
      const items=j.commands.filter(c=>c.group===g.key);
      if(!items.length)return;
      const card=document.createElement("div");card.className="card";card.style.marginBottom="16px";
      card.innerHTML=`<h2>${g.label}</h2><div class="cmdgrid"></div>`;
      const grid=card.querySelector(".cmdgrid");
      items.forEach(c=>{
        const b=document.createElement("button");
        b.className=c.confirm?"danger":"ghost";
        b.textContent=c.label;
        b.onclick=()=>sendCommand(c,b);
        grid.appendChild(b);
      });
      wrap.appendChild(card);
    });
    CMDS_LOADED=true;
  }catch(e){flash("could not load commands",true);}
}
async function sendCommand(c,btn){
  if(c.confirm && !confirm(`Send command “${c.label}” to the BMS?\\n\\nThis can change BMS behaviour.`))return;
  btn.disabled=true;
  try{
    const r=await fetch("/api/command",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({command:c.id})});
    const j=await r.json();
    flash(j.ok?("sent: "+(j.label||c.label)):(j.error||"failed"),!j.ok);
  }catch(e){flash("failed",true);}
  setTimeout(()=>btn.disabled=false,400);
}
</script>
</body>
</html>
"""
