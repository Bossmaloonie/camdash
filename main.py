"""
╔══════════════════════════════════════════════════════════════╗
║               HYDRA — MULTI-CAMERA STREAM                    ║
║                                                              ║
║  Just double-click main.py — setup runs automatically        ║
║                                                              ║
║  python main.py              → First-time setup + stream     ║
║  python main.py --server     → Deploy to Render              ║
║  python main.py --install    → Re-run auto-startup           ║
║  python main.py --uninstall  → Remove auto-start             ║
║  python main.py --check      → Verify setup                  ║
║  python main.py --reset      → Redo first-time setup         ║
╚══════════════════════════════════════════════════════════════╝

Laptop requirements:
    pip install opencv-python "python-socketio[client]" websocket-client

Server requirements (Render only):
    pip install flask flask-socketio eventlet
"""

import sys
import os
import platform
import socket
import subprocess

# ══════════════════════════════════════════════════════════════
#  ★  CONFIGURATION  — only edit this section
# ══════════════════════════════════════════════════════════════

SERVER_URL         = "https://camdash.onrender.com"
DASHBOARD_PASSWORD = "changeme"   # set "" to disable password

# Camera settings
CAMERA_INDEX  = 0     # 0 = auto-detect, ignored when auto-scan finds camera
FRAME_WIDTH   = 1280
FRAME_HEIGHT  = 720
TARGET_FPS    = 20
JPEG_QUALITY  = 65    # 0-100

# ══════════════════════════════════════════════════════════════

SCRIPT_PATH   = os.path.abspath(__file__)
SCRIPT_DIR    = os.path.dirname(SCRIPT_PATH)
PYTHON_EXE    = sys.executable
SYSTEM        = platform.system()
SERVICE_NAME  = "Hydra"
SERVICE_LABEL = "com.user.hydra-camera"
MARKER_FILE   = os.path.join(SCRIPT_DIR, ".camdash_ready")

# ─────────────────────────────────────────────────────────────
#  DASHBOARD HTML  (served to phone browser)
# ─────────────────────────────────────────────────────────────

VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>CamDash</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#08080f;--card:#111118;--border:#1c1c28;
  --accent:#4ade80;--red:#f87171;
  --text:#eeeeee;--muted:#555570;
}
body{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif;min-height:100dvh}

/* ── LOGIN ── */
#login{position:fixed;inset:0;z-index:200;background:var(--bg);
  display:flex;align-items:center;justify-content:center;padding:24px}
#login.hide{display:none}
.lcard{width:100%;max-width:340px;background:var(--card);border:1px solid var(--border);
  border-radius:20px;padding:36px 28px;display:flex;flex-direction:column;align-items:center;gap:16px}
.licon{font-size:2.8rem}
.ltitle{font-size:1.05rem;font-weight:700;letter-spacing:.06em}
.lsub{font-size:.78rem;color:var(--muted);text-align:center}
#pw{width:100%;padding:13px 16px;background:rgba(255,255,255,.05);
  border:1px solid var(--border);border-radius:12px;
  color:var(--text);font-size:1rem;outline:none}
#pw:focus{border-color:rgba(74,222,128,.5)}
#pw.shake{animation:sh .35s}
@keyframes sh{0%,100%{transform:translateX(0)}25%{transform:translateX(-8px)}75%{transform:translateX(8px)}}
#lbtn{width:100%;padding:13px;border:none;border-radius:12px;
  background:var(--accent);color:#052e16;font-size:.9rem;font-weight:700;cursor:pointer}
#lerr{font-size:.76rem;color:var(--red);min-height:16px;text-align:center}

/* ── TOPBAR ── */
.topbar{position:sticky;top:0;z-index:50;background:rgba(8,8,15,.9);
  backdrop-filter:blur(16px);border-bottom:1px solid var(--border);
  padding:14px 16px;display:flex;align-items:center;justify-content:space-between}
.tlogo{font-size:1.1rem;font-weight:700;letter-spacing:.06em}
.tsub{font-size:.68rem;color:var(--muted);margin-top:2px}
.tpill{display:flex;align-items:center;gap:6px;padding:4px 12px 4px 8px;
  border-radius:999px;background:rgba(255,255,255,.04);border:1px solid var(--border);
  font-size:.7rem;color:var(--muted)}
.tpill.on{background:rgba(74,222,128,.1);border-color:rgba(74,222,128,.3);color:var(--accent)}
.tdot{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.tpill.on .tdot{background:var(--accent);animation:pd 2s infinite}
@keyframes pd{0%,100%{opacity:1}50%{opacity:.3}}

/* ── DASHBOARD ── */
#dash{padding:16px}
.dlabel{font-size:.65rem;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}

/* ── CAMERA CARD ── */
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;
  overflow:hidden;cursor:pointer;transition:border-color .2s,transform .15s}
.card:active{transform:scale(.96)}
.card:hover{border-color:#303040}
.thumb{width:100%;aspect-ratio:16/9;background:#0c0c18;position:relative;
  display:flex;align-items:center;justify-content:center;font-size:1.8rem;overflow:hidden}
.thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none}
.thumb img.ok{display:block}
.livebadge{position:absolute;top:7px;left:7px;display:none;align-items:center;gap:5px;
  padding:2px 8px;border-radius:6px;background:rgba(0,0,0,.7);
  border:1px solid rgba(248,113,113,.5);font-size:.58rem;font-weight:700;letter-spacing:.08em}
.card.live .livebadge{display:flex}
.rdot{width:6px;height:6px;border-radius:50%;background:var(--red);animation:ld 1s infinite}
@keyframes ld{0%,100%{opacity:1}50%{opacity:.3}}
.cinfo{padding:9px 12px 11px}
.cname{font-size:.82rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cstatus{font-size:.67rem;margin-top:3px;display:flex;align-items:center;gap:5px;color:var(--muted)}
.sdot{width:6px;height:6px;border-radius:50%;background:var(--muted);flex-shrink:0}
.card.online .sdot{background:var(--accent)}
.card.online .cstatus{color:var(--accent)}

/* ── EMPTY STATE ── */
.empty{grid-column:1/-1;display:flex;flex-direction:column;align-items:center;
  padding:60px 20px;gap:12px;color:var(--muted);text-align:center}
.empty .eicon{font-size:2.5rem;opacity:.3}
.empty p{font-size:.8rem;line-height:1.6}
.empty code{color:var(--accent);font-family:monospace;
  background:rgba(74,222,128,.08);padding:1px 6px;border-radius:4px}

/* ── FULLSCREEN VIEWER ── */
#viewer{display:none;position:fixed;inset:0;z-index:100;background:#000;flex-direction:column}
#viewer.open{display:flex}
#vtop{position:absolute;top:0;left:0;right:0;z-index:10;
  background:linear-gradient(to bottom,rgba(0,0,0,.8),transparent);
  padding:env(safe-area-inset-top,16px) 16px 32px;
  display:flex;align-items:center;gap:12px}
#vback{width:38px;height:38px;border-radius:11px;border:1px solid rgba(255,255,255,.15);
  background:rgba(255,255,255,.1);color:#fff;font-size:1.1rem;
  cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;
  -webkit-tap-highlight-color:transparent}
#vname{font-size:.95rem;font-weight:600}
#vbadge{margin-left:auto;font-size:.65rem;padding:3px 10px;border-radius:999px;
  background:rgba(0,0,0,.5);color:rgba(255,255,255,.5);
  border:1px solid rgba(255,255,255,.12);white-space:nowrap}
#vbadge.live{background:rgba(248,113,113,.2);color:var(--red);border-color:rgba(248,113,113,.4)}
#vfeed{position:absolute;inset:0;display:none;width:100%;height:100%;object-fit:contain}
#vfeed.show{display:block}
#vph{position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:12px;color:rgba(255,255,255,.2)}
#vph .vi{font-size:3rem;opacity:.3}
#vph.hide{display:none}
#vsw{position:absolute;bottom:0;left:0;right:0;z-index:10;
  background:linear-gradient(to top,rgba(0,0,0,.85),transparent);
  padding:32px 16px env(safe-area-inset-bottom,16px);
  display:flex;gap:8px;overflow-x:auto;scrollbar-width:none}
#vsw::-webkit-scrollbar{display:none}
.swbtn{flex-shrink:0;display:flex;align-items:center;gap:6px;padding:7px 14px;
  border-radius:999px;border:1px solid rgba(255,255,255,.15);
  background:rgba(255,255,255,.08);color:rgba(255,255,255,.6);
  font-size:.75rem;cursor:pointer;white-space:nowrap;
  -webkit-tap-highlight-color:transparent}
.swbtn .sd{width:6px;height:6px;border-radius:50%;background:var(--accent)}
.swbtn.cur{border-color:rgba(74,222,128,.5);color:var(--accent);background:rgba(74,222,128,.12)}
</style>
</head>
<body>

<!-- LOGIN -->
<div id="login" class="NEEDS_AUTH_CLASS">
  <div class="lcard">
    <div class="licon">📷</div>
    <div class="ltitle">CAMDASH</div>
    <div class="lsub">Enter password to view cameras</div>
    <input id="pw" type="password" placeholder="Password" autocomplete="current-password"/>
    <button id="lbtn">Unlock</button>
    <div id="lerr"></div>
  </div>
</div>

<!-- TOPBAR -->
<div class="topbar">
  <div>
    <div class="tlogo">📷 CamDash</div>
    <div class="tsub" id="tcount">Connecting...</div>
  </div>
  <div class="tpill" id="tpill">
    <span class="tdot"></span>
    <span id="tstat">Connecting</span>
  </div>
</div>

<!-- DASHBOARD -->
<div id="dash">
  <div class="dlabel">Live Cameras</div>
  <div class="grid" id="grid">
    <div class="empty">
      <div class="eicon">🎥</div>
      <p>No cameras online.<br/>Run <code>python main.py</code> on a laptop.</p>
    </div>
  </div>
</div>

<!-- FULLSCREEN VIEWER -->
<div id="viewer">
  <img id="vfeed" alt=""/>
  <div id="vph"><div class="vi">🎥</div><p id="vpmsg">Waiting...</p></div>
  <div id="vtop">
    <button id="vback">&#8592;</button>
    <span id="vname"></span>
    <span id="vbadge">Connecting...</span>
  </div>
  <div id="vsw"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
<script>
var cams={}, cur=null, thumbs={}, authed=false, needsAuth=false;
needsAuth = document.getElementById('login').className.indexOf('hide') === -1;
authed    = !needsAuth;

var loginEl=document.getElementById('login');
var pwEl=document.getElementById('pw');
var lbtn=document.getElementById('lbtn');
var lerr=document.getElementById('lerr');
var tcount=document.getElementById('tcount');
var tpill=document.getElementById('tpill');
var tstat=document.getElementById('tstat');
var grid=document.getElementById('grid');
var viewer=document.getElementById('viewer');
var vfeed=document.getElementById('vfeed');
var vph=document.getElementById('vph');
var vpmsg=document.getElementById('vpmsg');
var vback=document.getElementById('vback');
var vname=document.getElementById('vname');
var vbadge=document.getElementById('vbadge');
var vsw=document.getElementById('vsw');

var socket=io({transports:['websocket','polling']});

socket.on('connect',function(){
  tpill.className='tpill on'; tstat.textContent='Online';
  if(authed) socket.emit('viewer_join');
});
socket.on('disconnect',function(){
  tpill.className='tpill'; tstat.textContent='Offline';
  tcount.textContent='Disconnected';
});
socket.on('auth_ok',function(){
  authed=true; loginEl.className='hide';
  socket.emit('viewer_join');
});
socket.on('auth_fail',function(){
  lerr.textContent='Wrong password.';
  pwEl.className='shake'; lbtn.disabled=false; lbtn.textContent='Unlock';
  setTimeout(function(){pwEl.className='';},400);
});
socket.on('camera_list',function(list){
  cams={};
  for(var i=0;i<list.length;i++) cams[list[i].id]=list[i];
  var n=list.length;
  tcount.textContent=n?n+' camera'+(n>1?'s':'')+' online':'No cameras online';
  renderGrid(); renderSw();
  if(cur&&!cams[cur]){
    cur=null; vbadge.className=''; vbadge.textContent='Offline';
    showPh('Camera went offline');
  }
});
socket.on('frame',function(b64){
  if(!cur) return;
  vfeed.src='data:image/jpeg;base64,'+b64;
  if(!vfeed.classList.contains('show')){
    vfeed.classList.add('show'); vph.className='hide';
  }
  vbadge.className='live'; vbadge.textContent='● LIVE';
  thumbs[cur]=b64;
  var img=document.getElementById('t'+cur);
  if(img){img.src='data:image/jpeg;base64,'+b64; img.className='ok';}
  var card=document.getElementById('c'+cur);
  if(card) card.className='card online live';
});

lbtn.onclick=doLogin;
pwEl.onkeydown=function(e){if(e.key==='Enter') doLogin();};
function doLogin(){
  var pw=pwEl.value.trim(); if(!pw) return;
  lbtn.disabled=true; lbtn.textContent='...'; lerr.textContent='';
  socket.emit('authenticate',pw);
}

function esc(s){
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderGrid(){
  grid.innerHTML='';
  var ids=Object.keys(cams);
  if(!ids.length){
    grid.innerHTML='<div class="empty"><div class="eicon">🎥</div><p>No cameras online.<br/>Run <code>python main.py</code> on a laptop.</p></div>';
    return;
  }
  for(var i=0;i<ids.length;i++){
    var id=ids[i], c=cams[id], th=thumbs[id], isLive=(id===cur);
    var d=document.createElement('div');
    d.className='card online'+(isLive?' live':''); d.id='c'+id;
    d.innerHTML=
      '<div class="thumb"><span>📷</span>'+
      '<img id="t'+id+'"'+(th?' src="data:image/jpeg;base64,'+th+'" class="ok"':'')+' alt=""/>'+
      '<div class="livebadge"><span class="rdot"></span>LIVE</div></div>'+
      '<div class="cinfo"><div class="cname">'+esc(c.name)+'</div>'+
      '<div class="cstatus"><span class="sdot"></span>'+(isLive?'Streaming':'Online')+'</div></div>';
    d.onclick=(function(cid){return function(){openViewer(cid);};})(id);
    grid.appendChild(d);
  }
}

function openViewer(id){
  if(cur&&cur!==id) socket.emit('viewer_leave_cam',cur);
  cur=id; socket.emit('viewer_watch',id);
  vname.textContent=cams[id]?cams[id].name:id;
  vbadge.className=''; vbadge.textContent='Connecting...';
  if(thumbs[id]){
    vfeed.src='data:image/jpeg;base64,'+thumbs[id];
    vfeed.classList.add('show'); vph.className='hide';
  } else {
    vfeed.classList.remove('show'); vph.className='';
    vpmsg.textContent='Waiting for stream...';
  }
  viewer.classList.add('open');
  renderGrid(); renderSw();
}

function closeViewer(){
  if(cur) socket.emit('viewer_leave_cam',cur);
  cur=null; viewer.classList.remove('open');
  vfeed.classList.remove('show'); renderGrid();
}

function showPh(msg){
  vfeed.classList.remove('show'); vph.className=''; vpmsg.textContent=msg;
}

vback.onclick=function(){closeViewer();};

var ty=0;
viewer.addEventListener('touchstart',function(e){ty=e.touches[0].clientY;},{passive:true});
viewer.addEventListener('touchend',function(e){
  if(e.changedTouches[0].clientY-ty>80) closeViewer();
},{passive:true});

function renderSw(){
  vsw.innerHTML='';
  var ids=Object.keys(cams);
  for(var i=0;i<ids.length;i++){
    var id=ids[i], b=document.createElement('button');
    b.className='swbtn'+(id===cur?' cur':'');
    b.innerHTML='<span class="sd"></span>'+esc(cams[id].name);
    b.onclick=(function(cid){return function(){openViewer(cid);};})(id);
    vsw.appendChild(b);
  }
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
#  SERVER MODE  (deploy on Render)
# ─────────────────────────────────────────────────────────────

def run_server():
    try:
        import eventlet
        eventlet.monkey_patch()
        from flask import Flask, request as flask_request
        from flask_socketio import SocketIO, emit, join_room, leave_room
    except ImportError:
        print("❌  pip install flask flask-socketio eventlet")
        sys.exit(1)

    import hashlib
    PASSWORD_HASH = (
        hashlib.sha256(DASHBOARD_PASSWORD.encode()).hexdigest()
        if DASHBOARD_PASSWORD else ""
    )

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "hydra-cam-2024"
    sio = SocketIO(
        app, cors_allowed_origins="*",
        max_http_buffer_size=10 * 1024 * 1024,
        async_mode="eventlet", ping_timeout=60, ping_interval=25,
    )

    cameras_by_sid   = {}   # sid → {id, name}
    authed_sids      = set()
    viewers_watching = {}   # viewer sid → cam_id

    def get_camera_list():
        return [{"id": v["id"], "name": v["name"]} for v in cameras_by_sid.values()]

    def is_authed(sid):
        return (not PASSWORD_HASH) or (sid in authed_sids)

    @app.route("/")
    def index():
        return VIEWER_HTML.replace(
            "NEEDS_AUTH_CLASS",
            "" if not PASSWORD_HASH else "hide"
        )

    @app.route("/health")
    def health():
        return "OK"

    @sio.on("authenticate")
    def on_authenticate(password):
        import hashlib as _hl
        h = _hl.sha256(password.encode()).hexdigest()
        if h == PASSWORD_HASH:
            authed_sids.add(flask_request.sid)
            emit("auth_ok")
        else:
            emit("auth_fail")

    @sio.on("register_camera")
    def on_register(data):
        cam_id   = data.get("id",   flask_request.sid[:6])
        cam_name = data.get("name", f"Camera {cam_id}")
        cameras_by_sid[flask_request.sid] = {"id": cam_id, "name": cam_name}
        print(f"📹 Online:  {cam_name}")
        emit("camera_list", get_camera_list(), broadcast=True)

    @sio.on("frame")
    def on_frame(data):
        cam_id = data.get("id")
        frame  = data.get("frame")
        if cam_id and frame:
            emit("frame", frame, to=f"viewers_{cam_id}")

    @sio.on("viewer_join")
    def on_viewer_join():
        if is_authed(flask_request.sid):
            emit("camera_list", get_camera_list())

    @sio.on("viewer_watch")
    def on_viewer_watch(cam_id):
        sid = flask_request.sid
        if not is_authed(sid):
            return
        old = viewers_watching.get(sid)
        if old and old != cam_id:
            leave_room(f"viewers_{old}")
        viewers_watching[sid] = cam_id
        join_room(f"viewers_{cam_id}")
        print(f"▶  Watching: {cam_id}")

    @sio.on("viewer_leave_cam")
    def on_viewer_leave(cam_id):
        leave_room(f"viewers_{cam_id}")
        if viewers_watching.get(flask_request.sid) == cam_id:
            viewers_watching.pop(flask_request.sid, None)

    @sio.on("disconnect")
    def on_disconnect():
        sid = flask_request.sid
        authed_sids.discard(sid)
        viewers_watching.pop(sid, None)
        if sid in cameras_by_sid:
            info = cameras_by_sid.pop(sid)
            print(f"📴 Offline: {info['name']}")
            emit("camera_list", get_camera_list(), broadcast=True)

    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Hydra server running on port {port}")
    sio.run(app, host="0.0.0.0", port=port)


# ─────────────────────────────────────────────────────────────
#  LAPTOP MODE  (stream this laptop's camera)
# ─────────────────────────────────────────────────────────────

def run_laptop():
    try:
        import cv2, base64, time, threading
        import socketio as sio_lib
    except ImportError:
        print('❌  pip install opencv-python "python-socketio[client]" websocket-client')
        sys.exit(1)

    cam_name = socket.gethostname()
    cam_id   = cam_name.lower().replace(" ", "_").replace("-", "_")

    sio = sio_lib.Client(
        reconnection=True, reconnection_attempts=0, reconnection_delay=2,
    )

    @sio.event
    def connect():
        print(f"✅ Connected as '{cam_name}'")
        print(f"   📱 Dashboard : {SERVER_URL}")
        print(f"   🎥 Open dashboard on phone and tap this camera\n")
        sio.emit("register_camera", {"id": cam_id, "name": cam_name})

    @sio.event
    def disconnect():
        print("🔌 Disconnected — reconnecting automatically...")

    @sio.event
    def connect_error(data):
        print(f"⚠️  Connection error: {data}")

    print(f"🔌 Connecting to {SERVER_URL} as '{cam_name}'...")
    sio.connect(SERVER_URL, transports=["websocket", "polling"])

    # ── Auto-detect first working camera ─────────────────────
    cap = None
    found_index = -1

    # Windows: disable MSMF (buggy) and force DirectShow
    if SYSTEM == "Windows":
        os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

    print("🔍 Scanning for cameras...")
    for idx in range(4):
        try:
            if SYSTEM == "Windows":
                test = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            else:
                test = cv2.VideoCapture(idx)
            if not test.isOpened():
                test.release(); continue
            # Read a few frames to wake up the camera
            for _ in range(5):
                test.read()
            ret, frame = test.read()
            if ret and frame is not None and frame.size > 0:
                cap = test
                found_index = idx
                print(f"✅  Camera found at index {idx}")
                break
            test.release()
        except Exception:
            pass

    if cap is None or not cap.isOpened():
        print("\n❌  No camera found (checked indices 0-3).")
        print("    • Make sure the camera is plugged in")
        print("    • Close Zoom / Teams / any app using the camera")
        sio.disconnect(); sys.exit(1)

    # ── Set resolution and warm up ────────────────────────────
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS,          TARGET_FPS)

    # Warmup: discard frames while auto-exposure settles (avoids blue frames)
    print("⏳ Warming up camera...")
    for _ in range(30):
        cap.read()

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"✅ Camera #{found_index}: {w}×{h} @ {TARGET_FPS}fps — streaming now\n")

    encode_params  = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    frame_interval = 1.0 / TARGET_FPS

    # Keepalive: prevents Render free tier from sleeping
    def _keepalive():
        while True:
            time.sleep(20)
            try:
                if sio.connected:
                    sio.emit("ping_keepalive", {})
            except Exception:
                pass

    threading.Thread(target=_keepalive, daemon=True).start()

    try:
        while True:
            t0 = time.monotonic()
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.1); continue

            # Skip frames with near-zero brightness (camera not ready yet)
            if cv2.mean(frame)[0] < 5:
                time.sleep(0.05); continue

            _, buf  = cv2.imencode(".jpg", frame, encode_params)
            payload = base64.b64encode(buf).decode("ascii")
            if sio.connected:
                sio.emit("frame", {"id": cam_id, "frame": payload})
            wait = frame_interval - (time.monotonic() - t0)
            if wait > 0:
                time.sleep(wait)
    except KeyboardInterrupt:
        print(f"\n⏹  Stopped.")
    finally:
        cap.release(); sio.disconnect()


# ─────────────────────────────────────────────────────────────
#  CHECK MODE
# ─────────────────────────────────────────────────────────────

def run_check():
    print("\n🔍 Checking setup...\n")
    ok = True

    # Server URL
    if "YOUR-APP-NAME" in SERVER_URL:
        print("❌  SERVER_URL not set"); ok = False
    else:
        print(f"✅  SERVER_URL: {SERVER_URL}")

    # Packages
    for pkg, mod in [("opencv-python",          "cv2"),
                     ("python-socketio[client]", "socketio"),
                     ("websocket-client",        "websocket")]:
        try:
            __import__(mod); print(f"✅  {pkg}")
        except ImportError:
            print(f"❌  {pkg} not installed  →  pip install \"{pkg}\""); ok = False

    # Camera scan (uses DirectShow on Windows — avoids MSMF errors)
    try:
        import cv2
        if SYSTEM == "Windows":
            os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
        found = []
        for idx in range(4):
            try:
                if SYSTEM == "Windows":
                    test = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                else:
                    test = cv2.VideoCapture(idx)
                if test.isOpened():
                    ret, _ = test.read()
                    if ret:
                        w = int(test.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(test.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        label = "built-in" if idx == 0 else "external"
                        found.append((idx, w, h, label))
                test.release()
            except Exception:
                pass
        if found:
            for idx, w, h, label in found:
                print(f"✅  Camera #{idx} ({w}×{h}) — {label}")
        else:
            print("❌  No cameras found"); ok = False
    except Exception as e:
        print(f"❌  Camera scan error: {e}"); ok = False

    # Name + password
    print(f"✅  Camera name: '{socket.gethostname()}'")
    if DASHBOARD_PASSWORD:
        print(f"✅  Password protection: ON")
    else:
        print(f"⚠️  Password protection: OFF")

    print(f"\n{'✅  All good!' if ok else '⚠️  Fix issues above first.'}\n")


# ─────────────────────────────────────────────────────────────
#  WINDOWS SERVICE CLASS  (visible in Task Manager → Services)
# ─────────────────────────────────────────────────────────────

if SYSTEM == "Windows":
    try:
        import win32serviceutil as _wsutil
        import win32service    as _winsvc
        import win32event      as _wevt
        import servicemanager  as _smgr

        class HydraService(_wsutil.ServiceFramework):
            _svc_name_         = "Hydra"
            _svc_display_name_ = "Hydra Camera Stream"
            _svc_description_  = "diri ak maaram"

            def __init__(self, args):
                _wsutil.ServiceFramework.__init__(self, args)
                self._stop = _wevt.CreateEvent(None, 0, 0, None)

            def SvcStop(self):
                self.ReportServiceStatus(_winsvc.SERVICE_STOP_PENDING)
                _wevt.SetEvent(self._stop)

            def SvcDoRun(self):
                import threading
                _smgr.LogMsg(
                    _smgr.EVENTLOG_INFORMATION_TYPE,
                    _smgr.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""))
                t = threading.Thread(target=run_laptop, daemon=True)
                t.start()
                _wevt.WaitForSingleObject(self._stop, _wevt.INFINITE)

    except ImportError:
        HydraService = None   # pywin32 not installed yet


# ─────────────────────────────────────────────────────────────
#  INSTALL / UNINSTALL
# ─────────────────────────────────────────────────────────────

def _run_cmd(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"⚠️  {r.stderr.strip()}")
    return r

def _grant_camera_permission_macos():
    """Trigger macOS camera permission dialog once."""
    print("📸 Opening camera to trigger macOS permission dialog...")
    print("   If a popup appears — click OK / Allow.\n")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.read()
            cap.release()
            print("✅  Camera permission granted.\n")
            return True
        else:
            print("⚠️  Camera did not open.")
            print(f"   Go to: System Settings → Privacy & Security → Camera → Python ✓\n")
            return False
    except ImportError:
        print("❌  opencv-python not installed. Run:  pip install opencv-python")
        return False

def install_startup():
    print(f"\n⚙️  Installing Hydra service on {SYSTEM}...\n")

    # ── macOS ─────────────────────────────────────────────────
    if SYSTEM == "Darwin":
        _grant_camera_permission_macos()
        plist_dir  = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(plist_dir, f"{SERVICE_LABEL}.plist")
        log_path   = os.path.join(SCRIPT_DIR, "hydra.log")
        os.makedirs(plist_dir, exist_ok=True)

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key>             <string>{SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON_EXE}</string>
        <string>{SCRIPT_PATH}</string>
    </array>
    <key>WorkingDirectory</key>  <string>{SCRIPT_DIR}</string>
    <key>RunAtLoad</key>         <true/>
    <key>KeepAlive</key>         <true/>
    <key>StandardOutPath</key>   <string>{log_path}</string>
    <key>StandardErrorPath</key> <string>{log_path}</string>
</dict></plist>"""

        with open(plist_path, "w") as f:
            f.write(plist)

        uid = subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip()
        r = _run_cmd(f"launchctl bootstrap gui/{uid} '{plist_path}'", check=False)
        if r.returncode != 0:
            r = _run_cmd(f"launchctl load -w '{plist_path}'")

        if r.returncode == 0:
            print(f"✅  Hydra installed — starts on every login.")
            print(f"ℹ️   Logs: tail -f {log_path}")
        else:
            print("❌  Failed to install launchd agent.")

    # ── Windows ───────────────────────────────────────────────
    elif SYSTEM == "Windows":
        print("  Installing Hydra as a Windows Service...\n")
        global HydraService

        # Install pywin32 if missing
        if HydraService is None:
            print("  📦 Installing pywin32...")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pywin32", "-q"],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                print("  ❌ pip install failed — try running as Administrator")
                return
            scripts = os.path.join(os.path.dirname(sys.executable), "Scripts")
            hook    = os.path.join(scripts, "pywin32_postinstall.py")
            if os.path.exists(hook):
                subprocess.run([sys.executable, hook, "-install"],
                               capture_output=True)
            print("  ✅ pywin32 installed.")
            print("  🔄 Restarting to apply — please double-click main.py again.")
            # Relaunch so HydraService class gets defined
            subprocess.Popen([sys.executable, SCRIPT_PATH, "--install"])
            sys.exit(0)

        # Remove old service if exists
        try:
            import win32serviceutil
            import win32service
            for action in ("StopService", "RemoveService"):
                try: getattr(win32serviceutil, action)("Hydra")
                except Exception: pass

            # Install and start
            old_argv = sys.argv[:]
            sys.argv = [SCRIPT_PATH, "--startup", "auto", "install"]
            win32serviceutil.HandleCommandLine(HydraService)
            sys.argv = old_argv
            win32serviceutil.StartService("Hydra")
            print("  ✅ Hydra service installed and running!")
            print()
            print("  📋 View:      Task Manager → Services tab → Hydra")
            print("  ⏹  Stop:      Right-click Hydra → Stop")
            print("  🗑  Uninstall: python main.py --uninstall  (as Administrator)")
        except Exception as e:
            print(f"  ❌ {e}")
            print("  Try: Right-click terminal → Run as administrator")
        print()

    # ── Linux ─────────────────────────────────────────────────
    elif SYSTEM == "Linux":
        svc_dir  = os.path.expanduser("~/.config/systemd/user")
        svc_path = os.path.join(svc_dir, f"{SERVICE_NAME}.service")
        log_path = os.path.join(SCRIPT_DIR, "hydra.log")
        os.makedirs(svc_dir, exist_ok=True)

        with open(svc_path, "w") as f:
            f.write(f"""[Unit]
Description=Hydra Camera Stream
After=network-online.target
Wants=network-online.target

[Service]
ExecStart={PYTHON_EXE} {SCRIPT_PATH}
WorkingDirectory={SCRIPT_DIR}
Restart=always
RestartSec=5
StandardOutput=append:{log_path}
StandardError=append:{log_path}

[Install]
WantedBy=default.target
""")

        _run_cmd("systemctl --user daemon-reload")
        _run_cmd(f"systemctl --user enable {SERVICE_NAME}")
        r = _run_cmd(f"systemctl --user start {SERVICE_NAME}")
        username = os.environ.get("USER", "")
        if username:
            _run_cmd(f"loginctl enable-linger {username}", check=False)

        if r.returncode == 0:
            print(f"✅  Hydra service installed — starts on every boot.")
            print(f"ℹ️   Logs: journalctl --user -u {SERVICE_NAME} -f")
        else:
            print(f"❌  Failed. Check: journalctl --user -u {SERVICE_NAME}")
    else:
        print(f"❌  Unsupported OS: {SYSTEM}")
    print()


def uninstall_startup():
    print(f"\n🗑  Removing Hydra on {SYSTEM}...\n")
    if SYSTEM == "Windows":
        try:
            import win32serviceutil
            try: win32serviceutil.StopService("Hydra")
            except Exception: pass
            win32serviceutil.RemoveService("Hydra")
            print("  ✅ Hydra removed from Windows Services.")
        except ImportError:
            _run_cmd("sc stop Hydra",   check=False)
            _run_cmd("sc delete Hydra", check=False)
            print("  ✅ Hydra removed via sc.exe")
        except Exception as e:
            print(f"  ❌ {e}")
            print("  Try running as Administrator.")
    elif SYSTEM == "Darwin":
        plist_path = os.path.expanduser(
            f"~/Library/LaunchAgents/{SERVICE_LABEL}.plist")
        uid = subprocess.run(["id", "-u"],
                             capture_output=True, text=True).stdout.strip()
        _run_cmd(f"launchctl bootout gui/{uid} '{plist_path}'", check=False)
        _run_cmd(f"launchctl unload '{plist_path}'", check=False)
        if os.path.exists(plist_path):
            os.remove(plist_path)
        print(f"✅  Removed Hydra launchd agent.")
    elif SYSTEM == "Linux":
        _run_cmd(f"systemctl --user stop {SERVICE_NAME}",    check=False)
        _run_cmd(f"systemctl --user disable {SERVICE_NAME}", check=False)
        svc_path = os.path.expanduser(
            f"~/.config/systemd/user/{SERVICE_NAME}.service")
        if os.path.exists(svc_path): os.remove(svc_path)
        _run_cmd("systemctl --user daemon-reload", check=False)
        print(f"✅  Removed Hydra systemd service.")
    print()


# ─────────────────────────────────────────────────────────────
#  AUTO-INSTALL PACKAGES
# ─────────────────────────────────────────────────────────────

def auto_install_packages():
    packages = [
        ("cv2",       "opencv-python"),
        ("socketio",  "python-socketio[client]"),
        ("websocket", "websocket-client"),
    ]
    all_ok = True
    for mod, pkg in packages:
        try:
            __import__(mod)
        except ImportError:
            all_ok = False
            print(f"   📦 Installing {pkg}...")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                print(f"   ✅ {pkg} installed")
            else:
                print(f"   ❌ Failed — run manually:  pip install \"{pkg}\"")
    if all_ok:
        print("   ✅ All packages ready")


# ─────────────────────────────────────────────────────────────
#  FIRST-RUN SETUP  (runs once, skipped forever after)
# ─────────────────────────────────────────────────────────────

def first_run_setup():
    if os.path.exists(MARKER_FILE):
        return  # Already set up — skip silently

    print("""
╔══════════════════════════════════════════════════════╗
║         HYDRA — FIRST TIME SETUP                     ║
║         (This only runs once)                        ║
╚══════════════════════════════════════════════════════╝
""")
    print("  [1/2] Installing packages...")
    auto_install_packages()
    print()
    print("  [2/2] Installing auto-startup...")
    install_startup()

    try:
        open(MARKER_FILE, "w").write("ready")
    except Exception:
        pass

    print()
    print("  " + "─" * 50)
    print("  ✅  Setup complete! Starting camera stream...")
    print("  " + "─" * 50 + "\n")


# ─────────────────────────────────────────────────────────────
#  UAC AUTO-ELEVATION (Windows — triggers on double-click)
# ─────────────────────────────────────────────────────────────

def _ensure_admin():
    if SYSTEM != "Windows":
        return
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return  # already admin
        params = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, SCRIPT_DIR, 1)
        sys.exit(0)
    except Exception:
        pass  # if elevation fails, continue anyway


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

def print_help():
    print("""
╔══════════════════════════════════════════════════════════╗
║            HYDRA — USAGE                                 ║
╠══════════════════════════════════════════════════════════╣
║  python main.py              First-time setup + stream   ║
║  python main.py --server     Run relay server (Render)   ║
║  python main.py --install    Re-install auto-startup     ║
║  python main.py --uninstall  Remove auto-startup         ║
║  python main.py --check      Verify everything is ready  ║
║  python main.py --reset      Redo first-time setup       ║
║  python main.py --help       Show this message           ║
╚══════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    _ensure_admin()   # Windows: auto-UAC popup on double-click

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print_help()
    elif "--server" in args:
        run_server()
    elif "--install" in args:
        install_startup()
    elif "--uninstall" in args:
        uninstall_startup()
    elif "--check" in args:
        run_check()
    elif "--reset" in args:
        if os.path.exists(MARKER_FILE):
            os.remove(MARKER_FILE)
            print("🔄  Reset done — double-click main.py to redo setup.")
        else:
            print("ℹ️   Already fresh.")
    else:
        first_run_setup()
        run_laptop()
