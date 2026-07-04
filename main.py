"""
HYDRA — Multi-Camera Stream
Double-click main.py to install and run automatically.
"""

import sys, os, platform, socket, subprocess, threading

# ══════════════════════════════════════════════════════
#  CONFIGURATION  ★ edit only this section
# ══════════════════════════════════════════════════════

SERVER_URL         = "https://camdash.onrender.com"
DASHBOARD_PASSWORD = "changeme"

FRAME_WIDTH   = 960
FRAME_HEIGHT  = 540
TARGET_FPS    = 15
JPEG_QUALITY  = 55

# ══════════════════════════════════════════════════════

SCRIPT_PATH  = os.path.abspath(__file__)
SCRIPT_DIR   = os.path.dirname(SCRIPT_PATH)
PYTHON_EXE   = sys.executable
SYSTEM       = platform.system()
SVC_NAME     = "Hydra"
SVC_LABEL    = "com.user.hydra-camera"
MARKER       = os.path.join(SCRIPT_DIR, ".hydra_ready")
LOG          = os.path.join(SCRIPT_DIR, "hydra_error.log")

# ─────────────────────────────────────────────────────
#  ERROR HELPER  — silent normally, CMD popup on error
# ─────────────────────────────────────────────────────

def _silent_python():
    """pythonw.exe on Windows (no console flash), regular python elsewhere."""
    if SYSTEM != "Windows":
        return PYTHON_EXE
    pw = os.path.join(os.path.dirname(PYTHON_EXE), "pythonw.exe")
    return pw if os.path.exists(pw) else PYTHON_EXE

def show_error(msg):
    try:
        import datetime
        with open(LOG, "a") as f:
            f.write(f"\n[{datetime.datetime.now()}]\n{msg}\n")
    except Exception:
        pass
    if SYSTEM == "Windows":
        lines = msg.replace('"', "'")
        bat = os.path.join(SCRIPT_DIR, "_hydra_err.bat")
        with open(bat, "w") as f:
            f.write("@echo off\n")
            f.write("echo HYDRA ERROR\n")
            f.write("echo ============\n")
            for line in lines.split("\n"):
                if line.strip():
                    f.write(f"echo {line}\n")
                else:
                    f.write("echo.\n")
            f.write(f"echo.\necho Log: {LOG}\necho.\npause\n")
        subprocess.Popen(["cmd.exe", "/c", bat],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        print(f"ERROR: {msg}", file=sys.stderr)

# ─────────────────────────────────────────────────────
#  DASHBOARD HTML
# ─────────────────────────────────────────────────────

VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>Hydra</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#050508;--bg2:#0a0a12;
  --glass:rgba(255,255,255,.035);--glass2:rgba(255,255,255,.06);
  --bdr:rgba(255,255,255,.08);--bdr2:rgba(255,255,255,.15);
  --acc:#4ade80;--acc2:#22d3ee;--acc-soft:rgba(74,222,128,.14);
  --blue:#5b8dff;--blue-soft:rgba(91,141,255,.14);
  --red:#fb7185;--red-soft:rgba(251,113,133,.16);
  --txt:#f2f2f8;--txt2:#9696b0;--txt3:#48485c;
  --r-xl:22px;--r-lg:16px;--r-md:12px;--r-sm:9px
}
html,body{height:100%;overflow:hidden}
body{
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  background:var(--bg);color:var(--txt);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
body::before{
  content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background:
    radial-gradient(ellipse 70% 45% at 20% -8%,rgba(74,222,128,.09),transparent 60%),
    radial-gradient(ellipse 60% 45% at 100% 8%,rgba(34,211,238,.06),transparent 55%),
    radial-gradient(ellipse 50% 35% at 50% 110%,rgba(91,141,255,.05),transparent 55%);
}
::selection{background:rgba(74,222,128,.3)}

/* ═══════ SCROLL AREA ═══════ */
#main{position:fixed;inset:0;overflow-y:auto;-webkit-overflow-scrolling:touch;z-index:1}
#main::-webkit-scrollbar{width:5px}
#main::-webkit-scrollbar-track{background:transparent}
#main::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:6px}

/* ═══════ LOGIN ═══════ */
#login{
  position:fixed;inset:0;z-index:300;background:var(--bg);
  display:flex;align-items:center;justify-content:center;padding:24px;
}
#login.hide{display:none}
#login::before{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(circle at 50% 30%,rgba(74,222,128,.1),transparent 55%);
}
.lcard{
  position:relative;width:100%;max-width:368px;
  background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.02));
  border:1px solid rgba(255,255,255,.1);
  border-radius:28px;padding:46px 34px 38px;
  display:flex;flex-direction:column;align-items:center;
  box-shadow:0 0 0 1px rgba(74,222,128,.07),0 48px 90px rgba(0,0,0,.65),
             inset 0 1px 0 rgba(255,255,255,.08);
  backdrop-filter:blur(50px);
  animation:rise .5s cubic-bezier(.16,1,.3,1) both;
}
@keyframes rise{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:translateY(0) scale(1)}}
.lring{
  width:80px;height:80px;border-radius:24px;
  background:linear-gradient(135deg,rgba(74,222,128,.28),rgba(34,211,238,.1));
  border:1px solid rgba(74,222,128,.35);
  display:flex;align-items:center;justify-content:center;font-size:2.1rem;
  box-shadow:0 0 44px rgba(74,222,128,.2),0 0 90px rgba(74,222,128,.08),
             inset 0 1px 0 rgba(255,255,255,.15);
  margin-bottom:26px;
}
.ltit{
  font-size:1.28rem;font-weight:800;letter-spacing:-.01em;margin-bottom:8px;
  background:linear-gradient(135deg,#fff 20%,rgba(255,255,255,.5) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.lsub{font-size:.82rem;color:var(--txt2);margin-bottom:30px;letter-spacing:.005em}
.linput-wrap{position:relative;width:100%;margin-bottom:13px}
.linput{
  width:100%;padding:15px 18px;
  background:rgba(255,255,255,.055);
  border:1.5px solid rgba(255,255,255,.1);
  border-radius:var(--r-md);color:var(--txt);font-size:.95rem;
  font-family:'Inter',sans-serif;outline:none;
  transition:border-color .2s,box-shadow .2s,background .2s;
  letter-spacing:.03em;
}
.linput::placeholder{color:var(--txt3);letter-spacing:.01em}
.linput:focus{border-color:rgba(74,222,128,.55);box-shadow:0 0 0 4px rgba(74,222,128,.09);background:rgba(255,255,255,.07)}
.linput.shake{animation:sh .4s}
@keyframes sh{0%,100%{transform:translateX(0)}20%{transform:translateX(-9px)}40%{transform:translateX(7px)}60%{transform:translateX(-5px)}80%{transform:translateX(3px)}}
.lbtn{
  width:100%;padding:15px;border:none;border-radius:var(--r-md);
  background:linear-gradient(135deg,#4ade80,#22c55e);
  color:#04220f;font-size:.9rem;font-weight:700;font-family:'Inter',sans-serif;
  cursor:pointer;letter-spacing:.02em;
  box-shadow:0 6px 28px rgba(74,222,128,.35),inset 0 1px 0 rgba(255,255,255,.25);
  transition:opacity .2s,transform .15s,box-shadow .2s;
}
.lbtn:hover{box-shadow:0 8px 34px rgba(74,222,128,.45),inset 0 1px 0 rgba(255,255,255,.25)}
.lbtn:active{opacity:.88;transform:scale(.98)}
.lbtn:disabled{opacity:.5;cursor:not-allowed;box-shadow:none}
.lerr{font-size:.76rem;color:var(--red);text-align:center;margin-top:12px;min-height:16px;font-weight:500}

/* ═══════ TOPBAR ═══════ */
.topbar{
  position:sticky;top:0;z-index:50;
  background:rgba(5,5,8,.78);backdrop-filter:blur(28px) saturate(180%);
  border-bottom:1px solid rgba(255,255,255,.07);
  padding:0 20px;height:64px;
  display:flex;align-items:center;justify-content:space-between;
}
.tl{display:flex;align-items:center;gap:12px}
.tlogo{
  width:38px;height:38px;border-radius:11px;
  background:linear-gradient(135deg,rgba(74,222,128,.25),rgba(34,211,238,.13));
  border:1px solid rgba(74,222,128,.3);
  display:flex;align-items:center;justify-content:center;font-size:1.1rem;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.12);
}
.tname{font-size:.98rem;font-weight:800;letter-spacing:-.01em}
.tsub{font-size:.66rem;color:var(--txt3);margin-top:2px;font-family:'JetBrains Mono',monospace;letter-spacing:.01em}
.cpill{
  display:flex;align-items:center;gap:7px;
  padding:6px 14px 6px 10px;border-radius:999px;
  background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.09);
  font-size:.71rem;color:var(--txt2);font-weight:500;transition:all .3s;
}
.cpill.on{background:var(--acc-soft);border-color:rgba(74,222,128,.28);color:var(--acc)}
.cdot{width:7px;height:7px;border-radius:50%;background:var(--txt3);transition:background .3s}
.cpill.on .cdot{background:var(--acc);box-shadow:0 0 7px var(--acc);animation:dp 2.2s infinite}
@keyframes dp{0%,100%{opacity:1}50%{opacity:.35}}

/* ═══════ DASHBOARD ═══════ */
#dash{padding:22px 16px 44px;max-width:900px;margin:0 auto}
.sec{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;padding:0 2px}
.slbl{font-size:.66rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--txt3)}
.schip{
  font-size:.66rem;font-weight:500;font-family:'JetBrains Mono',monospace;
  padding:4px 11px;border-radius:999px;
  background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.08);
  color:var(--txt2);
}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px}

/* ═══════ CAMERA CARD ═══════ */
.card{
  background:var(--glass);border:1px solid var(--bdr);
  border-radius:var(--r-lg);overflow:hidden;cursor:pointer;
  transition:border-color .25s,box-shadow .25s,transform .18s cubic-bezier(.2,.8,.3,1);
  position:relative;animation:cin .38s cubic-bezier(.16,1,.3,1) both;
}
@keyframes cin{from{opacity:0;transform:translateY(16px) scale(.97)}to{opacity:1;transform:translateY(0) scale(1)}}
.card::after{content:'';position:absolute;inset:0;border-radius:var(--r-lg);box-shadow:inset 0 1px 0 rgba(255,255,255,.08);pointer-events:none}
.card:active{transform:scale(.955)}
.card:hover{border-color:rgba(255,255,255,.16);transform:translateY(-2px)}

.thumb{width:100%;aspect-ratio:16/9;background:#08080e;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.tph{font-size:1.9rem;opacity:.12;z-index:1}
.thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .45s ease}
.thumb img.ok{opacity:1}
.tgrad{position:absolute;inset:0;z-index:2;background:linear-gradient(to top,rgba(5,5,8,.92) 0%,rgba(5,5,8,.15) 45%,transparent 70%)}

.lbadge{
  position:absolute;top:9px;left:9px;z-index:4;display:none;align-items:center;gap:5px;
  padding:4px 9px;border-radius:8px;background:rgba(0,0,0,.6);backdrop-filter:blur(10px);
  border:1px solid rgba(251,113,133,.5);font-size:.58rem;font-weight:700;letter-spacing:.09em;color:#fff;
}
.card.live .lbadge{display:flex}
.rdot{width:6px;height:6px;border-radius:50%;background:var(--red);box-shadow:0 0 6px var(--red);animation:rp 1.15s infinite}
@keyframes rp{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.78)}}

.ci{padding:11px 13px 13px}
.cn{font-size:.83rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.005em}
.cs{display:flex;align-items:center;gap:6px;font-size:.68rem;margin-top:4px;color:var(--txt3);font-weight:500}
.spip{width:6px;height:6px;border-radius:50%;background:var(--txt3);flex-shrink:0;transition:all .3s}

.card.online .spip{background:var(--blue);box-shadow:0 0 6px rgba(91,141,255,.65);animation:op 2.6s infinite}
.card.online .cs{color:#8fb0ff}
.card.online{border-color:rgba(91,141,255,.2)}
@keyframes op{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}

.card.lit .spip{background:var(--acc);box-shadow:0 0 9px rgba(74,222,128,.75);animation:sp 1.4s infinite}
.card.lit .cs{color:var(--acc)}
.card.lit{border-color:rgba(74,222,128,.4);box-shadow:0 0 0 1px rgba(74,222,128,.14),0 14px 40px rgba(0,0,0,.5)}
@keyframes sp{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.72)}}

/* ═══════ EMPTY STATE ═══════ */
.empty{grid-column:1/-1;display:flex;flex-direction:column;align-items:center;padding:76px 24px;gap:16px;text-align:center}
.ebox{
  width:76px;height:76px;border-radius:22px;
  background:linear-gradient(160deg,rgba(255,255,255,.05),rgba(255,255,255,.015));
  border:1px solid rgba(255,255,255,.08);
  display:flex;align-items:center;justify-content:center;font-size:2.1rem;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07);
}
.empty h3{font-size:.94rem;font-weight:700;color:var(--txt2)}
.empty p{font-size:.79rem;color:var(--txt3);line-height:1.65}
.empty code{
  font-family:'JetBrains Mono',monospace;font-size:.74rem;
  color:var(--acc);background:var(--acc-soft);padding:2px 8px;border-radius:6px;
}

/* ═══════ FULLSCREEN VIEWER ═══════ */
#vw{display:none;position:fixed;inset:0;z-index:200;background:#000;flex-direction:column}
#vw.open{display:flex}
#vimg{position:absolute;inset:0;display:none;width:100%;height:100%;object-fit:contain;background:#000}
#vimg.show{display:block;animation:fadein .3s ease}
@keyframes fadein{from{opacity:0}to{opacity:1}}
#vph{position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:rgba(255,255,255,.16)}
#vph .vi{font-size:3.2rem;opacity:.35}
#vph p{font-size:.82rem;font-weight:500}
#vph.hide{display:none}

#vtop{
  position:absolute;top:0;left:0;right:0;z-index:10;
  background:linear-gradient(to bottom,rgba(0,0,0,.82) 0%,rgba(0,0,0,.3) 60%,transparent 100%);
  padding:calc(env(safe-area-inset-top,16px) + 6px) 16px 36px;
  display:flex;align-items:center;gap:13px;
}
#vback{
  width:40px;height:40px;border-radius:13px;border:1px solid rgba(255,255,255,.16);
  background:rgba(255,255,255,.1);backdrop-filter:blur(14px);
  color:#fff;font-size:1.15rem;cursor:pointer;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  -webkit-tap-highlight-color:transparent;transition:background .2s;
}
#vback:active{background:rgba(255,255,255,.2)}
#vnm{font-size:.98rem;font-weight:700;text-shadow:0 2px 8px rgba(0,0,0,.6);letter-spacing:-.005em}
#vbg{
  margin-left:auto;font-size:.66rem;font-weight:700;
  padding:5px 12px;border-radius:999px;
  background:rgba(0,0,0,.55);color:rgba(255,255,255,.5);
  border:1px solid rgba(255,255,255,.14);
  backdrop-filter:blur(10px);white-space:nowrap;letter-spacing:.04em;
}
#vbg.live{background:rgba(251,113,133,.24);color:var(--red);border-color:rgba(251,113,133,.45)}

#vsw{
  position:absolute;bottom:0;left:0;right:0;z-index:10;
  background:linear-gradient(to top,rgba(0,0,0,.88) 0%,rgba(0,0,0,.35) 60%,transparent 100%);
  padding:34px 16px calc(env(safe-area-inset-bottom,18px) + 4px);
  display:flex;gap:9px;overflow-x:auto;scrollbar-width:none;
}
#vsw::-webkit-scrollbar{display:none}
.sb{
  flex-shrink:0;display:flex;align-items:center;gap:7px;
  padding:8px 16px;border-radius:999px;
  border:1px solid rgba(255,255,255,.14);
  background:rgba(255,255,255,.09);backdrop-filter:blur(14px);
  color:rgba(255,255,255,.6);font-size:.76rem;font-weight:500;
  font-family:'Inter',sans-serif;cursor:pointer;white-space:nowrap;
  -webkit-tap-highlight-color:transparent;transition:all .2s;
}
.sbd{width:6px;height:6px;border-radius:50%;background:var(--acc)}
.sb.cur{border-color:rgba(74,222,128,.5);color:var(--acc);background:rgba(74,222,128,.15)}
</style>
</head>
<body>

<!-- LOGIN -->
<div id="login" class="NEEDS_AUTH">
  <div class="lcard">
    <div class="lring">📷</div>
    <div class="ltit">Hydra</div>
    <div class="lsub">Enter your password to view cameras</div>
    <div class="linput-wrap">
      <input class="linput" id="pw" type="password" placeholder="Password" autocomplete="current-password"/>
    </div>
    <button class="lbtn" id="lbtn">Unlock Dashboard</button>
    <div class="lerr" id="lerr"></div>
  </div>
</div>

<div id="main">
<div class="topbar">
  <div class="tl">
    <div class="tlogo">📷</div>
    <div>
      <div class="tname">Hydra</div>
      <div class="tsub" id="tcnt">Connecting…</div>
    </div>
  </div>
  <div class="cpill" id="pill"><span class="cdot"></span><span id="tst">Connecting</span></div>
</div>

<div id="dash">
  <div class="sec">
    <div class="slbl">Live Cameras</div>
    <div class="schip" id="chip">0 online</div>
  </div>
  <div class="grid" id="grid">
    <div class="empty">
      <div class="ebox">🎥</div>
      <h3>No cameras online</h3>
      <p>Run <code>python main.py</code><br>on a laptop to begin.</p>
    </div>
  </div>
</div>
</div><!-- /main -->

<div id="vw">
  <img id="vimg" alt=""/>
  <div id="vph"><div class="vi">🎥</div><p id="vpm">Waiting for stream…</p></div>
  <div id="vtop">
    <button id="vback">&#8592;</button>
    <span id="vnm"></span>
    <span id="vbg">Connecting…</span>
  </div>
  <div id="vsw"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
<script>
var cams={},cur=null,thumbs={},authed=false;
var needsAuth=(document.getElementById('login').className.indexOf('hide')===-1);
authed=!needsAuth;
function E(id){return document.getElementById(id);}
var loginEl=E('login'),pwEl=E('pw'),lbtn=E('lbtn'),lerr=E('lerr');
var tcnt=E('tcnt'),pill=E('pill'),tst=E('tst'),chip=E('chip'),grid=E('grid');
var vw=E('vw'),vimg=E('vimg'),vph=E('vph'),vpm=E('vpm');
var vback=E('vback'),vnm=E('vnm'),vbg=E('vbg'),vsw=E('vsw');

var socket=io({transports:['websocket','polling']});

socket.on('connect',function(){
  pill.className='cpill on'; tst.textContent='Online';
  if(authed) socket.emit('viewer_join');
});
socket.on('disconnect',function(){
  pill.className='cpill'; tst.textContent='Offline'; tcnt.textContent='Disconnected';
});
socket.on('auth_ok',function(){ authed=true; loginEl.className='hide'; socket.emit('viewer_join'); });
socket.on('auth_fail',function(){
  lerr.textContent='Incorrect password.';
  pwEl.className='linput shake'; lbtn.disabled=false; lbtn.textContent='Unlock Dashboard';
  setTimeout(function(){pwEl.className='linput';},400);
});
socket.on('camera_list',function(list){
  cams={};
  for(var i=0;i<list.length;i++) cams[list[i].id]=list[i];
  var n=list.length;
  tcnt.textContent=n?n+' camera'+(n>1?'s':'')+' online':'No cameras online';
  chip.textContent=n+' online';
  renderGrid(); renderSw();
  if(cur&&!cams[cur]){cur=null;showPh('Camera went offline');}
});
socket.on('frame',function(data){
  var id=data.id,b64=data.frame;
  thumbs[id]=b64;
  var img=E('t'+id);
  if(img){img.src='data:image/jpeg;base64,'+b64;img.className='ok';}
  var card=E('c'+id);
  if(card&&id===cur) card.className='card online lit live';
  if(id!==cur) return;
  vimg.src='data:image/jpeg;base64,'+b64;
  if(!vimg.classList.contains('show')){vimg.classList.add('show');vph.className='hide';}
  vbg.className='live'; vbg.textContent='● LIVE';
});

lbtn.onclick=doLogin;
pwEl.onkeydown=function(e){if(e.key==='Enter')doLogin();};
function doLogin(){
  var pw=pwEl.value.trim(); if(!pw) return;
  lbtn.disabled=true; lbtn.textContent='Verifying…'; lerr.textContent='';
  socket.emit('authenticate',pw);
}
function xe(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function renderGrid(){
  grid.innerHTML='';
  var ids=Object.keys(cams);
  if(!ids.length){
    grid.innerHTML='<div class="empty"><div class="ebox">🎥</div><h3>No cameras online</h3><p>Run <code>python main.py</code><br>on a laptop to begin.</p></div>';
    return;
  }
  for(var i=0;i<ids.length;i++){
    var id=ids[i],c=cams[id],th=thumbs[id];
    var live=(id===cur);
    var lit =(c.viewers&&c.viewers>0)||live;
    var cls ='card online'+(lit?' lit':'')+(live?' live':'');

    var statusTxt;
    if(live){ statusTxt='● Viewing now'; }
    else if(lit){ var v=c.viewers||1; statusTxt='● Live — '+v+' viewer'+(v>1?'s':''); }
    else { statusTxt='● Online'; }

    var d=document.createElement('div');
    d.className=cls; d.id='c'+id;
    d.style.animationDelay=(i*.055)+'s';
    d.innerHTML=
      '<div class="thumb">'+
        '<div class="tph">📷</div>'+
        '<img id="t'+id+'"'+(th?' src="data:image/jpeg;base64,'+th+'" class="ok"':'')+' alt=""/>'+
        '<div class="tgrad"></div>'+
        '<div class="lbadge"><span class="rdot"></span>LIVE</div>'+
      '</div>'+
      '<div class="ci">'+
        '<div class="cn">'+xe(c.name)+'</div>'+
        '<div class="cs"><span class="spip"></span>'+statusTxt+'</div>'+
      '</div>';
    d.onclick=(function(cid){return function(){openViewer(cid);};})(id);
    grid.appendChild(d);
  }
}

function openViewer(id){
  cur=id; socket.emit('viewer_watch',id);
  vnm.textContent=cams[id]?cams[id].name:id;
  vbg.className=''; vbg.textContent='Connecting…';
  if(thumbs[id]){
    vimg.src='data:image/jpeg;base64,'+thumbs[id];
    vimg.classList.add('show'); vph.className='hide';
  } else {
    vimg.classList.remove('show'); vph.className=''; vpm.textContent='Waiting for stream…';
  }
  vw.classList.add('open'); renderGrid(); renderSw();
}
function closeViewer(){
  if(cur) socket.emit('viewer_stop');
  cur=null; vw.classList.remove('open'); vimg.classList.remove('show'); renderGrid();
}
function showPh(m){vimg.classList.remove('show');vph.className='';vpm.textContent=m;}
vback.onclick=function(){closeViewer();};
var ty=0;
vw.addEventListener('touchstart',function(e){ty=e.touches[0].clientY;},{passive:true});
vw.addEventListener('touchend',function(e){if(e.changedTouches[0].clientY-ty>80)closeViewer();},{passive:true});

function renderSw(){
  vsw.innerHTML='';
  var ids=Object.keys(cams);
  for(var i=0;i<ids.length;i++){
    var id=ids[i],b=document.createElement('button');
    b.className='sb'+(id===cur?' cur':'');
    b.innerHTML='<span class="sbd"></span>'+xe(cams[id].name);
    b.onclick=(function(cid){return function(){openViewer(cid);};})(id);
    vsw.appendChild(b);
  }
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────
#  SERVER  (Render)
# ─────────────────────────────────────────────────────

def run_server():
    try:
        import eventlet; eventlet.monkey_patch()
        from flask import Flask, request as req
        from flask_socketio import SocketIO, emit
    except ImportError:
        print("pip install flask flask-socketio eventlet"); sys.exit(1)

    import hashlib
    PWD = hashlib.sha256(DASHBOARD_PASSWORD.encode()).hexdigest() if DASHBOARD_PASSWORD else ""

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "hydra-2024"
    sio = SocketIO(app, cors_allowed_origins="*",
                   max_http_buffer_size=10*1024*1024,
                   async_mode="eventlet", ping_timeout=60, ping_interval=25)

    cams         = {}   # sid → {id, name}
    authed       = set()
    watching     = {}   # viewer_sid → cam_id currently watching
    watch_counts = {}   # cam_id → number of active viewers
    cam_to_sid   = {}   # cam_id → laptop sid (for targeted start/stop)

    def cam_list():
        return [
            {"id": v["id"], "name": v["name"],
             "viewers": watch_counts.get(v["id"], 0)}
            for v in cams.values()
        ]

    @app.route("/")
    def index():
        return VIEWER_HTML.replace("NEEDS_AUTH", "" if not PWD else "hide")

    @app.route("/health")
    def health():
        return "OK"

    @sio.on("authenticate")
    def on_auth(pw):
        import hashlib as h
        if h.sha256(pw.encode()).hexdigest() == PWD:
            authed.add(req.sid); emit("auth_ok")
        else:
            emit("auth_fail")

    @sio.on("register_camera")
    def on_reg(data):
        cid  = data.get("id",   req.sid[:6])
        name = data.get("name", f"Camera {cid}")
        cams[req.sid]  = {"id": cid, "name": name}
        cam_to_sid[cid] = req.sid
        print(f"📹 Online: {name}")
        sio.emit("camera_list", cam_list())

    @sio.on("frame")
    def on_frame(data):
        cid   = data.get("id")
        frame = data.get("frame")
        if cid and frame:
            # Use server-level emit — most reliable broadcast in eventlet
            sio.emit("frame", {"id": cid, "frame": frame})

    @sio.on("viewer_join")
    def on_join():
        if (not PWD) or req.sid in authed:
            emit("camera_list", cam_list())

    def _viewer_start(cam_id):
        """Tell laptop to start streaming when first viewer joins."""
        watch_counts[cam_id] = watch_counts.get(cam_id, 0) + 1
        if watch_counts[cam_id] == 1:
            lsid = cam_to_sid.get(cam_id)
            if lsid:
                sio.emit("start_stream", to=lsid)
                print(f"▶  Stream ON:  {cam_id}")
        sio.emit("camera_list", cam_list())

    def _viewer_stop(cam_id):
        """Tell laptop to stop streaming when last viewer leaves."""
        watch_counts[cam_id] = max(0, watch_counts.get(cam_id, 0) - 1)
        if watch_counts[cam_id] == 0:
            lsid = cam_to_sid.get(cam_id)
            if lsid:
                sio.emit("stop_stream", to=lsid)
                print(f"⏸  Stream OFF: {cam_id}")
        sio.emit("camera_list", cam_list())

    @sio.on("viewer_watch")
    def on_watch(cam_id):
        sid = req.sid
        if PWD and sid not in authed:
            return
        old = watching.get(sid)
        if old == cam_id:
            return   # already watching this camera
        if old:
            _viewer_stop(old)
        watching[sid] = cam_id
        _viewer_start(cam_id)

    @sio.on("viewer_stop")
    def on_viewer_stop():
        sid = req.sid
        old = watching.pop(sid, None)
        if old:
            _viewer_stop(old)

    @sio.on("disconnect")
    def on_disc():
        sid = req.sid
        authed.discard(sid)
        old = watching.pop(sid, None)
        if old:
            _viewer_stop(old)
        if sid in cams:
            info = cams.pop(sid)
            cam_to_sid.pop(info["id"], None)
            watch_counts.pop(info["id"], None)
            print(f"📴 Offline: {info['name']}")
            sio.emit("camera_list", cam_list())

    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Hydra server on port {port}")
    sio.run(app, host="0.0.0.0", port=port)

# ─────────────────────────────────────────────────────
#  LAPTOP STREAMING
# ─────────────────────────────────────────────────────

def run_laptop():
    try:
        import cv2, base64, time
        import socketio as sc
    except ImportError as e:
        show_error(f"Missing package: {e}\nRun: pip install opencv-python python-socketio[client] websocket-client")
        sys.exit(1)

    name = socket.gethostname()
    cid  = name.lower().replace(" ", "_").replace("-", "_")
    sio  = sc.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=3)

    # Camera state — None when nobody watching (LED OFF), open when watching (LED ON)
    cap_holder    = [None]           # [cv2.VideoCapture or None]
    stop_flag     = [False]          # signals stream thread to stop
    stream_thread = [None]

    # ── Pre-detect camera index at startup (without opening it) ──
    if SYSTEM == "Windows":
        os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

    found_idx = [-1]   # -1 = not found yet
    print("🔍 Finding camera (not opening it yet)...")
    for idx in range(5):
        try:
            backend = cv2.CAP_DSHOW if SYSTEM == "Windows" else cv2.CAP_ANY
            t = cv2.VideoCapture(idx, backend)
            if not t.isOpened(): t.release(); continue
            ok, frm = t.read()
            t.release()     # ← release immediately — LED stays OFF
            if ok and frm is not None and frm.size > 0:
                found_idx[0] = idx
                print(f"✅ Camera #{idx} detected — LED is OFF (waiting for viewer)")
                break
        except Exception:
            pass

    if found_idx[0] == -1:
        show_error("No camera found.\nPlug in a camera and close any app using it (Zoom, Teams).")
        sys.exit(1)

    # ── Stream thread: opens camera, sends frames, closes on stop ──
    def _stream_loop():
        import cv2 as _cv2, base64 as _b64, time as _t
        idx     = found_idx[0]
        backend = _cv2.CAP_DSHOW if SYSTEM == "Windows" else _cv2.CAP_ANY

        print(f"📷 Camera ON  — opening camera #{idx} (LED lights up)")
        cap = _cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            print("❌ Failed to open camera")
            return
        cap_holder[0] = cap

        cap.set(_cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
        cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(_cv2.CAP_PROP_FPS,          TARGET_FPS)

        # Warmup — clears blue/dark init frames
        for _ in range(30): cap.read()

        enc   = [_cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        delay = 1.0 / TARGET_FPS

        while not stop_flag[0]:
            t0 = _t.monotonic()
            ok, frame = cap.read()
            if not ok or frame is None: _t.sleep(0.1); continue
            if _cv2.mean(frame)[0] < 5: _t.sleep(0.05); continue

            _, buf  = _cv2.imencode(".jpg", frame, enc)
            payload = _b64.b64encode(buf).decode("ascii")
            if sio.connected:
                sio.emit("frame", {"id": cid, "frame": payload})

            wait = delay - (_t.monotonic() - t0)
            if wait > 0: _t.sleep(wait)

        # Release camera — physical LED turns OFF
        cap.release()
        cap_holder[0] = None
        print(f"🔒 Camera OFF — LED is off (no viewers)")

    # ── Socket events ─────────────────────────────────────────
    @sio.event
    def connect():
        print(f"✅ Connected as '{name}'")
        print(f"   📱 Dashboard : {SERVER_URL}")
        print(f"   🔒 LED is OFF — turns ON only when viewed on dashboard\n")
        sio.emit("register_camera", {"id": cid, "name": name})

    @sio.event
    def disconnect():
        # Signal the stream thread to stop; it releases its own camera
        # handle at the end of its loop — avoids a race where disconnect()
        # releases cap while _stream_loop is still mid cap.read().
        stop_flag[0] = True
        print("🔌 Reconnecting...")

    @sio.event
    def connect_error(data):
        show_error(f"Cannot connect to {SERVER_URL}\n{data}")

    @sio.on("start_stream")
    def on_start():
        """Server says someone is watching — open camera (LED ON) and start streaming."""
        if stream_thread[0] and stream_thread[0].is_alive():
            return  # already streaming
        stop_flag[0] = False
        t = threading.Thread(target=_stream_loop, daemon=True)
        stream_thread[0] = t
        t.start()

    @sio.on("stop_stream")
    def on_stop():
        """Server says nobody watching — stop streaming and release camera (LED OFF)."""
        stop_flag[0] = True
        stream_thread[0] = None

    try:
        sio.connect(SERVER_URL, transports=["websocket", "polling"])
    except Exception as e:
        show_error(f"Cannot connect to {SERVER_URL}\n{e}")
        sys.exit(1)

    try:
        import time as _tm
        while True:
            _tm.sleep(1)   # keep main thread alive, streaming in _stream_loop thread
    except KeyboardInterrupt:
        print("⏹  Stopped.")
        stop_flag[0] = True
        if cap_holder[0]:
            cap_holder[0].release()
    finally:
        sio.disconnect()


# ─────────────────────────────────────────────────────
#  WINDOWS SERVICE  (self-removes when stopped = uninstall)
# ─────────────────────────────────────────────────────

if SYSTEM == "Windows":
    try:
        import win32serviceutil as _wsu
        import win32service    as _wsc
        import win32event      as _wev
        import servicemanager  as _smg

        class HydraService(_wsu.ServiceFramework):
            _svc_name_         = "Hydra"
            _svc_display_name_ = "Hydra Camera Stream"
            _svc_description_  = "diri ak maaram"

            def __init__(self, args):
                _wsu.ServiceFramework.__init__(self, args)
                self._stop = _wev.CreateEvent(None, 0, 0, None)

            def SvcStop(self):
                """Stop streaming AND remove service — so Stop = Uninstall."""
                self.ReportServiceStatus(_wsc.SERVICE_STOP_PENDING)
                _wev.SetEvent(self._stop)
                # Self-uninstall: remove service when stopped from Task Manager
                try:
                    _wsu.RemoveService("Hydra")
                    # Delete marker so next run reinstalls
                    if os.path.exists(MARKER):
                        os.remove(MARKER)
                except Exception:
                    pass

            def SvcDoRun(self):
                _smg.LogMsg(_smg.EVENTLOG_INFORMATION_TYPE,
                            _smg.PYS_SERVICE_STARTED, (self._svc_name_,""))
                t = threading.Thread(target=run_laptop, daemon=True)
                t.start()
                _wev.WaitForSingleObject(self._stop, _wev.INFINITE)

    except ImportError:
        HydraService = None
else:
    HydraService = None

# ─────────────────────────────────────────────────────
#  INSTALL / UNINSTALL
# ─────────────────────────────────────────────────────

def _cmd(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0: show_error(r.stderr.strip())
    return r

def install_startup():
    if SYSTEM == "Windows":
        global HydraService

        if HydraService is None:
            # Install pywin32 silently
            r = subprocess.run([PYTHON_EXE,"-m","pip","install","pywin32","-q"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                show_error("Failed to install pywin32:\n"+r.stderr)
                return
            scripts = os.path.join(os.path.dirname(PYTHON_EXE),"Scripts")
            hook    = os.path.join(scripts,"pywin32_postinstall.py")
            if os.path.exists(hook):
                subprocess.run([PYTHON_EXE,hook,"-install"], capture_output=True)
            # Relaunch silently to define HydraService class — no window
            subprocess.Popen([_silent_python(), SCRIPT_PATH, "--install"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            sys.exit(0)

        try:
            import win32serviceutil as wsu, win32service as wsc
            for fn in ("StopService","RemoveService"):
                try: getattr(wsu,fn)("Hydra")
                except Exception: pass

            old = sys.argv[:]
            sys.argv = [SCRIPT_PATH,"--startup","auto","install"]
            wsu.HandleCommandLine(HydraService)
            sys.argv = old
            wsu.StartService("Hydra")
            print("✅ Hydra running → Task Manager → Services → Hydra")
            print("   Stop it there to uninstall automatically.")
        except Exception as e:
            show_error(f"Service install failed:\n{e}\n\nTry running as Administrator.")

    elif SYSTEM == "Darwin":
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened(): cap.read(); cap.release()
        except Exception: pass
        pdir = os.path.expanduser("~/Library/LaunchAgents")
        ppath= os.path.join(pdir, f"{SVC_LABEL}.plist")
        os.makedirs(pdir, exist_ok=True)
        with open(ppath,"w") as f:
            f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{SVC_LABEL}</string>
<key>ProgramArguments</key><array><string>{PYTHON_EXE}</string><string>{SCRIPT_PATH}</string></array>
<key>WorkingDirectory</key><string>{SCRIPT_DIR}</string>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>{LOG}</string>
<key>StandardErrorPath</key><string>{LOG}</string>
</dict></plist>""")
        uid = subprocess.run(["id","-u"],capture_output=True,text=True).stdout.strip()
        r   = _cmd(f"launchctl bootstrap gui/{uid} '{ppath}'", check=False)
        if r.returncode != 0: _cmd(f"launchctl load -w '{ppath}'")
        print("✅ Hydra installed — starts on every login")

    elif SYSTEM == "Linux":
        sdir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir,f"{SVC_NAME}.service"),"w") as f:
            f.write(f"""[Unit]
Description=Hydra Camera Stream
After=network-online.target
[Service]
ExecStart={PYTHON_EXE} {SCRIPT_PATH}
WorkingDirectory={SCRIPT_DIR}
Restart=always
RestartSec=5
StandardOutput=append:{LOG}
StandardError=append:{LOG}
[Install]
WantedBy=default.target
""")
        _cmd("systemctl --user daemon-reload")
        _cmd(f"systemctl --user enable {SVC_NAME}")
        _cmd(f"systemctl --user start  {SVC_NAME}")
        username = os.environ.get("USER","")
        if username: _cmd(f"loginctl enable-linger {username}", check=False)
        print("✅ Hydra service started")

def uninstall_startup():
    if SYSTEM == "Windows":
        try:
            import win32serviceutil as wsu
            try: wsu.StopService("Hydra")
            except Exception: pass
            wsu.RemoveService("Hydra")
        except Exception:
            _cmd("sc stop Hydra",   check=False)
            _cmd("sc delete Hydra", check=False)
        if os.path.exists(MARKER): os.remove(MARKER)
        print("✅ Hydra removed")

    elif SYSTEM == "Darwin":
        ppath = os.path.expanduser(f"~/Library/LaunchAgents/{SVC_LABEL}.plist")
        uid   = subprocess.run(["id","-u"],capture_output=True,text=True).stdout.strip()
        _cmd(f"launchctl bootout gui/{uid} '{ppath}'", check=False)
        _cmd(f"launchctl unload '{ppath}'", check=False)
        if os.path.exists(ppath): os.remove(ppath)
        if os.path.exists(MARKER): os.remove(MARKER)
        print("✅ Hydra removed")

    elif SYSTEM == "Linux":
        _cmd(f"systemctl --user stop    {SVC_NAME}", check=False)
        _cmd(f"systemctl --user disable {SVC_NAME}", check=False)
        svc = os.path.expanduser(f"~/.config/systemd/user/{SVC_NAME}.service")
        if os.path.exists(svc): os.remove(svc)
        _cmd("systemctl --user daemon-reload", check=False)
        if os.path.exists(MARKER): os.remove(MARKER)
        print("✅ Hydra removed")

# ─────────────────────────────────────────────────────
#  AUTO-INSTALL PACKAGES  (silent)
# ─────────────────────────────────────────────────────

def auto_install():
    pkgs = [("cv2","opencv-python"),
            ("socketio","python-socketio[client]"),
            ("websocket","websocket-client")]
    for mod, pkg in pkgs:
        try:
            __import__(mod)
        except ImportError:
            r = subprocess.run([PYTHON_EXE,"-m","pip","install",pkg,"-q"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                show_error(f"Failed to install {pkg}:\n{r.stderr}")

# ─────────────────────────────────────────────────────
#  FIRST-RUN SETUP  (runs once, fully silent)
# ─────────────────────────────────────────────────────

def first_run():
    if os.path.exists(MARKER): return

    auto_install()
    install_startup()

    try: open(MARKER,"w").write("ready")
    except Exception: pass

    if SYSTEM == "Windows":
        # Service is now running — close this installer window
        import time; time.sleep(2)
        sys.exit(0)

# ─────────────────────────────────────────────────────
#  UAC ELEVATION  (Windows: auto-popup on double-click)
# ─────────────────────────────────────────────────────

def ensure_admin():
    if SYSTEM != "Windows": return
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin(): return
        params = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", _silent_python(), params, SCRIPT_DIR, 0)
        sys.exit(0)
    except Exception: pass

# ─────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_admin()
    args = sys.argv[1:]
    if   "--server"    in args: run_server()
    elif "--install"   in args: install_startup()
    elif "--uninstall" in args: uninstall_startup()
    elif "--reset"     in args:
        if os.path.exists(MARKER): os.remove(MARKER)
        print("Reset. Double-click main.py to reinstall.")
    elif "--check"     in args:
        try:
            import cv2
            if SYSTEM=="Windows": os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"]="0"
            found=[]
            for i in range(4):
                b = cv2.CAP_DSHOW if SYSTEM=="Windows" else cv2.CAP_ANY
                t = cv2.VideoCapture(i,b)
                if t.isOpened():
                    ok,_=t.read()
                    if ok: found.append(i)
                t.release()
            if found: print(f"✅ Cameras found: {found}")
            else: print("❌ No cameras found")
        except Exception as e: print(f"❌ {e}")
    else:
        first_run()
        # On Windows, the Hydra Service owns the camera loop once installed.
        # Running it again here would create a duplicate connection with
        # the same camera id, so just confirm status and exit.
        if SYSTEM == "Windows" and os.path.exists(MARKER):
            print("✅ Hydra is running in the background.")
            print("   View it: Task Manager → Services tab → Hydra")
        else:
            run_laptop()
