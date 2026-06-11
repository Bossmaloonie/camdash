"""
╔══════════════════════════════════════════════════════════════╗
║           ALL-IN-ONE MULTI-CAMERA STREAM                     ║
║                                                              ║
║  python main.py              → Stream this laptop's camera   ║
║  python main.py --server     → Deploy this to Render         ║
║  python main.py --install    → One-time setup + permissions  ║
║  python main.py --uninstall  → Remove auto-start             ║
║  python main.py --check      → Verify setup is correct       ║
╚══════════════════════════════════════════════════════════════╝

Requirements (laptop):
    pip install opencv-python "python-socketio[client]" websocket-client

Requirements (server / Render):
    pip install flask flask-socketio gevent gevent-websocket
"""

import sys
import os
import platform
import socket
import subprocess

# ══════════════════════════════════════════════════════════════
#  ★  CONFIGURATION  — edit this section only
# ══════════════════════════════════════════════════════════════

# Your Render relay URL (set after deploying with --server)
SERVER_URL = "https://camdash.onrender.com"

# Dashboard password — viewers must enter this to see cameras.
# Set to "" (empty string) to disable password protection.
DASHBOARD_PASSWORD = "changeme"

# Camera name is taken automatically from the computer's hostname.
# e.g. "Johns-MacBook", "DESKTOP-AB12CD", "ubuntu-pc" — no setup needed.

# Camera settings
CAMERA_INDEX  = 0     # 0 = built-in, 1/2 = external webcam
FRAME_WIDTH   = 1280
FRAME_HEIGHT  = 720
TARGET_FPS    = 20
JPEG_QUALITY  = 65    # 0-100

# ══════════════════════════════════════════════════════════════

SCRIPT_PATH   = os.path.abspath(__file__)
SCRIPT_DIR    = os.path.dirname(SCRIPT_PATH)
PYTHON_EXE    = sys.executable
SYSTEM        = platform.system()   # "Windows" | "Darwin" | "Linux"
SERVICE_NAME  = "camera-stream"
SERVICE_LABEL = "com.user.camera-stream"

def _pythonw():
    """Return pythonw.exe on Windows (no console window), python elsewhere."""
    if SYSTEM != "Windows":
        return PYTHON_EXE
    pw = os.path.join(os.path.dirname(PYTHON_EXE), "pythonw.exe")
    return pw if os.path.exists(pw) else PYTHON_EXE

# ─────────────────────────────────────────────────────────────
#  SERVER MODE  (deploy on Render)
# ─────────────────────────────────────────────────────────────

def run_server():
    try:
        import eventlet
        eventlet.monkey_patch()
        from flask import Flask, render_template_string, request as flask_request
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
    app.config["SECRET_KEY"] = "multi-cam-2024"
    sio = SocketIO(
        app, cors_allowed_origins="*",
        max_http_buffer_size=10 * 1024 * 1024,
        async_mode="eventlet", ping_timeout=60, ping_interval=25,
    )

    cameras_by_sid   = {}   # sid → {id, name}
    authed_sids      = set() # authenticated viewer sids
    viewers_watching = {}   # viewer sid → cam_id being watched

    def get_camera_list():
        return [{"id": v["id"], "name": v["name"]} for v in cameras_by_sid.values()]

    def is_authed(sid):
        return (not PASSWORD_HASH) or (sid in authed_sids)

    # ── Phone Dashboard HTML ──────────────────────────────────
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

/* viewer top bar — standalone, no overlay parent */
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

/* feed */
#vfeed{position:absolute;inset:0;display:none;width:100%;height:100%;object-fit:contain}
#vfeed.show{display:block}
#vph{position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:12px;color:rgba(255,255,255,.2)}
#vph .vi{font-size:3rem;opacity:.3}
#vph.hide{display:none}

/* viewer bottom switcher — standalone, no overlay parent */
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
    <span class="tdot" id="tdot"></span>
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
// ── state ──────────────────────────────────────────────────────
var cams = {}, cur = null, thumbs = {}, authed = false, needsAuth = false;

// read needs_auth from html class
needsAuth = document.getElementById('login').className.indexOf('hide') === -1;
authed    = !needsAuth;

// ── elements ───────────────────────────────────────────────────
var loginEl = document.getElementById('login');
var pwEl    = document.getElementById('pw');
var lbtn    = document.getElementById('lbtn');
var lerr    = document.getElementById('lerr');
var tcount  = document.getElementById('tcount');
var tpill   = document.getElementById('tpill');
var tstat   = document.getElementById('tstat');
var grid    = document.getElementById('grid');
var viewer  = document.getElementById('viewer');
var vfeed   = document.getElementById('vfeed');
var vph     = document.getElementById('vph');
var vpmsg   = document.getElementById('vpmsg');
var vback   = document.getElementById('vback');
var vname   = document.getElementById('vname');
var vbadge  = document.getElementById('vbadge');
var vsw     = document.getElementById('vsw');

// ── socket ─────────────────────────────────────────────────────
var socket = io({transports:['websocket','polling']});

socket.on('connect', function(){
  tpill.className = 'tpill on';
  tstat.textContent = 'Online';
  if(authed) socket.emit('viewer_join');
});

socket.on('disconnect', function(){
  tpill.className = 'tpill';
  tstat.textContent = 'Offline';
  tcount.textContent = 'Disconnected';
});

socket.on('auth_ok', function(){
  authed = true;
  loginEl.className = 'hide';
  socket.emit('viewer_join');
});

socket.on('auth_fail', function(){
  lerr.textContent = 'Wrong password.';
  pwEl.className = 'shake';
  lbtn.disabled = false;
  lbtn.textContent = 'Unlock';
  setTimeout(function(){ pwEl.className = ''; }, 400);
});

socket.on('camera_list', function(list){
  cams = {};
  for(var i=0;i<list.length;i++) cams[list[i].id] = list[i];
  var n = list.length;
  tcount.textContent = n ? n+' camera'+(n>1?'s':'')+' online' : 'No cameras online';
  renderGrid();
  renderSw();
  if(cur && !cams[cur]){
    cur = null;
    vbadge.className = 'viewer-badge';
    vbadge.textContent = 'Offline';
    showPh('Camera went offline');
  }
});

socket.on('frame', function(b64){
  if(!cur) return;
  vfeed.src = 'data:image/jpeg;base64,'+b64;
  if(!vfeed.classList.contains('show')){
    vfeed.classList.add('show');
    vph.className = 'hide';
  }
  vbadge.className = 'live';
  vbadge.textContent = '● LIVE';
  thumbs[cur] = b64;
  var img = document.getElementById('t'+cur);
  if(img){ img.src='data:image/jpeg;base64,'+b64; img.className='ok'; }
  var card = document.getElementById('c'+cur);
  if(card) card.className = 'card online live';
});

// ── login ───────────────────────────────────────────────────────
lbtn.onclick = doLogin;
pwEl.onkeydown = function(e){ if(e.key==='Enter') doLogin(); };
function doLogin(){
  var pw = pwEl.value.trim();
  if(!pw) return;
  lbtn.disabled=true; lbtn.textContent='...'; lerr.textContent='';
  socket.emit('authenticate', pw);
}

// ── grid ────────────────────────────────────────────────────────
function renderGrid(){
  grid.innerHTML = '';
  var ids = Object.keys(cams);
  if(!ids.length){
    grid.innerHTML = '<div class="empty"><div class="eicon">🎥</div><p>No cameras online.<br/>Run <code>python main.py</code> on a laptop.</p></div>';
    return;
  }
  for(var i=0;i<ids.length;i++){
    var id = ids[i];
    var c  = cams[id];
    var th = thumbs[id];
    var isLive = (id===cur);
    var d = document.createElement('div');
    d.className = 'card online' + (isLive?' live':'');
    d.id = 'c'+id;
    d.innerHTML =
      '<div class="thumb">'+
        '<span>📷</span>'+
        '<img id="t'+id+'"'+(th?' src="data:image/jpeg;base64,'+th+'" class="ok"':'')+' alt=""/>'+
        '<div class="livebadge"><span class="rdot"></span>LIVE</div>'+
      '</div>'+
      '<div class="cinfo">'+
        '<div class="cname">'+escHtml(c.name)+'</div>'+
        '<div class="cstatus"><span class="sdot"></span>'+(isLive?'Streaming':'Online')+'</div>'+
      '</div>';
    d.onclick = (function(cid){ return function(){ openViewer(cid); }; })(id);
    grid.appendChild(d);
  }
}

function escHtml(s){
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── viewer ──────────────────────────────────────────────────────
function openViewer(id){
  if(cur && cur!==id) socket.emit('viewer_leave_cam', cur);
  cur = id;
  socket.emit('viewer_watch', id);
  vname.textContent  = cams[id] ? cams[id].name : id;
  vbadge.className   = '';
  vbadge.textContent = 'Connecting...';
  if(thumbs[id]){
    vfeed.src = 'data:image/jpeg;base64,'+thumbs[id];
    vfeed.classList.add('show'); vph.className='hide';
  } else {
    vfeed.classList.remove('show'); vph.className='';
    vpmsg.textContent='Waiting for stream...';
  }
  viewer.classList.add('open');
  renderGrid(); renderSw();
}

function closeViewer(){
  if(cur) socket.emit('viewer_leave_cam', cur);
  cur = null;
  viewer.classList.remove('open');
  vfeed.classList.remove('show');
  renderGrid();
}

function showPh(msg){ vfeed.classList.remove('show'); vph.className=''; vpmsg.textContent=msg; }

vback.onclick = function(){ closeViewer(); };

// swipe down to close
var ty=0;
viewer.addEventListener('touchstart',function(e){ty=e.touches[0].clientY;},{passive:true});
viewer.addEventListener('touchend',function(e){if(e.changedTouches[0].clientY-ty>80)closeViewer();},{passive:true});

// ── switcher ────────────────────────────────────────────────────
function renderSw(){
  vsw.innerHTML='';
  var ids=Object.keys(cams);
  for(var i=0;i<ids.length;i++){
    var id=ids[i];
    var b=document.createElement('button');
    b.className='swbtn'+(id===cur?' cur':'');
    b.innerHTML='<span class="sd"></span>'+escHtml(cams[id].name);
    b.onclick=(function(cid){return function(){openViewer(cid);};})(id);
    vsw.appendChild(b);
  }
}
</script>
</body>
</html>"""

    # ── Flask routes ──────────────────────────────────────────────
    @app.route("/")
    def index():
        # Inject needs_auth as a CSS class to avoid Jinja2/JS conflicts
        html = VIEWER_HTML.replace(
            'NEEDS_AUTH_CLASS',
            '' if not PASSWORD_HASH else 'hide'
        )
        return html

    @app.route("/health")
    def health():
        return "OK"

    # ── Socket events ──────────────────────────────────────────
    @sio.on("authenticate")
    def on_authenticate(password):
        import hashlib
        h = hashlib.sha256(password.encode()).hexdigest()
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
        print(f"\u2705 Online:  {cam_name}")
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
        if sid in viewers_watching and viewers_watching[sid] != cam_id:
            leave_room(f"viewers_{viewers_watching[sid]}")
        viewers_watching[sid] = cam_id
        join_room(f"viewers_{cam_id}")
        print(f"\u25b6  Watching: {cam_id}")

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
            print(f"\u274c Offline: {info['name']}")
            emit("camera_list", get_camera_list(), broadcast=True)

    port = int(os.environ.get("PORT", 5000))
    print(f"\U0001f680 CamDash server running on port {port}")
    sio.run(app, host="0.0.0.0", port=port)

    # ── Socket events ─────────────────────────────────────────
    @sio.on("authenticate")
    def on_authenticate(password):
        import hashlib
        h = hashlib.sha256(password.encode()).hexdigest()
        if h == PASSWORD_HASH:
            authed_sids.add(flask_request.sid)
            sio.emit("auth_ok",   to=flask_request.sid)
        else:
            sio.emit("auth_fail", to=flask_request.sid)

    @sio.on("register_camera")
    def on_register(data):
        cam_id   = data.get("id",   flask_request.sid[:6])
        cam_name = data.get("name", f"Camera {cam_id}")
        cameras_by_sid[flask_request.sid] = {"id": cam_id, "name": cam_name}
        cam_id_to_sid[cam_id] = flask_request.sid
        print(f"📹 Online:  {cam_name}")
        sio.emit("camera_list", get_camera_list())   # notify all viewers

    @sio.on("frame")
    def on_frame(data):
        cam_id = data.get("id")
        frame  = data.get("frame")
        if cam_id and frame:
            sio.emit("frame", frame, to=f"viewers_{cam_id}")

    @sio.on("viewer_join")
    def on_viewer_join():
        if is_authed(flask_request.sid):
            sio.emit("camera_list", get_camera_list(), to=flask_request.sid)

    @sio.on("viewer_watch")
    def on_viewer_watch(cam_id):
        sid = flask_request.sid
        if not is_authed(sid):
            return
        if sid in viewers_watching:
            old = viewers_watching[sid]
            if old != cam_id:
                leave_room(f"viewers_{old}")
                viewer_stop(old)
        viewers_watching[sid] = cam_id
        join_room(f"viewers_{cam_id}")
        viewer_start(cam_id)

    @sio.on("viewer_leave_cam")
    def on_viewer_leave(cam_id):
        sid = flask_request.sid
        leave_room(f"viewers_{cam_id}")
        if viewers_watching.get(sid) == cam_id:
            viewers_watching.pop(sid, None)
            viewer_stop(cam_id)

    @sio.on("disconnect")
    def on_disconnect():
        sid = flask_request.sid
        authed_sids.discard(sid)
        if sid in viewers_watching:
            cam_id = viewers_watching.pop(sid)
            leave_room(f"viewers_{cam_id}")
            viewer_stop(cam_id)
        if sid in cameras_by_sid:
            info = cameras_by_sid.pop(sid)
            cam_id_to_sid.pop(info["id"], None)
            viewer_counts.pop(info["id"], None)
            print(f"📴 Offline: {info['name']}")
            sio.emit("camera_list", get_camera_list())

    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Multi-camera relay server on port {port}")
    sio.run(app, host="0.0.0.0", port=port)


# ─────────────────────────────────────────────────────────────
#  LAPTOP MODE  (stream this laptop's camera)
# ─────────────────────────────────────────────────────────────

def run_laptop():
    try:
        import cv2, base64, time
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
        print(f"   🎥 Streaming  — open dashboard on phone and tap this camera\n")
        sio.emit("register_camera", {"id": cam_id, "name": cam_name})

    @sio.event
    def disconnect():
        print("🔌 Disconnected — reconnecting...")

    @sio.event
    def connect_error(data):
        print(f"⚠️  Connection error: {data}")

    print(f"🔌 Connecting to {SERVER_URL} as '{cam_name}'...")
    sio.connect(SERVER_URL, transports=["websocket", "polling"])

    # Auto-detect first working camera (internal or external)
    cap = None
    found_index = -1
    print("🔍 Scanning for cameras...")
    for idx in range(4):
        try:
            test = (cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if SYSTEM == "Windows"
                    else cv2.VideoCapture(idx))
            if test.isOpened():
                ret, _ = test.read()
                if ret:
                    cap = test
                    found_index = idx
                    print(f"✅  Found camera at index {idx}")
                    break
                test.release()
        except Exception:
            pass

    if cap is None or not cap.isOpened():
        print("\n❌  No camera found (checked indices 0-3).")
        print("    • Make sure the camera is plugged in")
        print("    • Close Zoom / Teams / any app using the camera")
        print("    • Set CAMERA_INDEX manually at the top of main.py")
        sio.disconnect(); sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"📹 Camera: {w}×{h} @ {TARGET_FPS}fps  |  Ctrl+C to stop\n")

    encode_params  = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    frame_interval = 1.0 / TARGET_FPS

    try:
        while True:
            t0 = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1); continue
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

    if "YOUR-APP-NAME" in SERVER_URL:
        print("❌  SERVER_URL not set"); ok = False
    else:
        print(f"✅  SERVER_URL: {SERVER_URL}")

    for pkg, mod in [("opencv-python","cv2"),
                     ("python-socketio[client]","socketio"),
                     ("websocket-client","websocket")]:
        try:
            __import__(mod); print(f"✅  {pkg}")
        except ImportError:
            print(f"❌  {pkg}  →  pip install \"{pkg}\""); ok = False

    # Camera scan
    try:
        import cv2
        found = []
        for idx in range(4):
            try:
                test = (cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                        if SYSTEM == "Windows"
                        else cv2.VideoCapture(idx))
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

    name = socket.gethostname()
    print(f"✅  Camera name: '{name}'")

    if DASHBOARD_PASSWORD:
        print(f"✅  Password protection: ON")
    else:
        print(f"⚠️  Password protection: OFF (set DASHBOARD_PASSWORD to secure your feed)")

    if SYSTEM == "Windows":
        pw = _pythonw()
        label = "✅" if "pythonw" in pw else "⚠️ "
        print(f"{label}  pythonw.exe: {pw}")

    print(f"\n{'✅  All good! Run: python main.py' if ok else '⚠️  Fix issues above first.'}\n")


# ─────────────────────────────────────────────────────────────
#  INSTALL / UNINSTALL
# ─────────────────────────────────────────────────────────────

def _run_cmd(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"⚠️  {r.stderr.strip()}")
    return r

def _grant_camera_permission_macos():
    """
    Run a quick camera capture to trigger the macOS permission dialog.
    Must be done once in the foreground BEFORE installing the background agent.
    """
    print("📸 Opening camera to trigger macOS permission dialog...")
    print("   → If a popup appears, click OK / Allow.\n")
    try:
        import cv2
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if cap.isOpened():
            cap.read()   # this line triggers the macOS permission request
            cap.release()
            print("✅  Camera permission granted — will work silently from now on.\n")
            return True
        else:
            print("⚠️  Camera did not open.")
            print("   → Go to: System Settings → Privacy & Security → Camera")
            print(f"   → Enable access for Python ({PYTHON_EXE})\n")
            return False
    except ImportError:
        print("❌  opencv-python not installed. Run:  pip install opencv-python")
        return False

def install_startup():
    print(f"\n⚙️  Installing auto-startup on {SYSTEM}...\n")

    # ── macOS: grant camera permission FIRST, then install ──────
    if SYSTEM == "Darwin":
        _grant_camera_permission_macos()

        import getpass
        plist_dir  = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(plist_dir, f"{SERVICE_LABEL}.plist")
        log_path   = os.path.join(SCRIPT_DIR, "camera_stream.log")
        os.makedirs(plist_dir, exist_ok=True)

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
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
</dict>
</plist>"""

        with open(plist_path, "w") as f:
            f.write(plist)

        uid_r = subprocess.run(["id", "-u"], capture_output=True, text=True)
        uid   = uid_r.stdout.strip()

        # Modern bootstrap (macOS 11+) with legacy load fallback
        r = _run_cmd(f"launchctl bootstrap gui/{uid} '{plist_path}'", check=False)
        if r.returncode != 0:
            r = _run_cmd(f"launchctl load -w '{plist_path}'")

        if r.returncode == 0:
            print(f"✅  launchd agent installed — starts automatically on every login.")
            print(f"ℹ️   Logs: tail -f {log_path}")
        else:
            print("❌  Failed to install launchd agent.")

    # ── Windows ─────────────────────────────────────────────────
    elif SYSTEM == "Windows":
        exe = _pythonw()   # no console window on boot

        xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Settings>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <Hidden>true</Hidden>
  </Settings>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Actions>
    <Exec>
      <Command>{exe}</Command>
      <Arguments>"{SCRIPT_PATH}"</Arguments>
      <WorkingDirectory>{SCRIPT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

        xml_path = os.path.join(SCRIPT_DIR, "_task.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)
        _run_cmd(f'schtasks /Delete /TN "{SERVICE_NAME}" /F', check=False)
        r = _run_cmd(f'schtasks /Create /TN "{SERVICE_NAME}" /XML "{xml_path}" /F')
        os.remove(xml_path)

        if r.returncode == 0:
            print(f"✅  Task Scheduler entry created: '{SERVICE_NAME}'")
            print(f"ℹ️   Starts silently on every login — no console window.")
            print(f"ℹ️   Start now without rebooting:")
            print(f'    schtasks /Run /TN "{SERVICE_NAME}"')
        else:
            print("❌  Failed. Try running this script as Administrator.")

        # Windows does not require a separate permission step — camera just works.
        print("\n✅  No extra permission steps needed on Windows.")

    # ── Linux ────────────────────────────────────────────────────
    elif SYSTEM == "Linux":
        svc_dir  = os.path.expanduser("~/.config/systemd/user")
        svc_path = os.path.join(svc_dir, f"{SERVICE_NAME}.service")
        log_path = os.path.join(SCRIPT_DIR, "camera_stream.log")
        os.makedirs(svc_dir, exist_ok=True)

        svc = f"""[Unit]
Description=Camera Stream Service
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
"""
        with open(svc_path, "w") as f:
            f.write(svc)

        _run_cmd("systemctl --user daemon-reload")
        _run_cmd(f"systemctl --user enable {SERVICE_NAME}")
        r = _run_cmd(f"systemctl --user start {SERVICE_NAME}")

        username = os.environ.get("USER", "")
        if username:
            _run_cmd(f"loginctl enable-linger {username}", check=False)

        if r.returncode == 0:
            print(f"✅  systemd service installed — starts on every boot.")
            print(f"ℹ️   Logs: journalctl --user -u {SERVICE_NAME} -f")
        else:
            print(f"❌  Failed. Check: journalctl --user -u {SERVICE_NAME}")
    else:
        print(f"❌  Unsupported OS: {SYSTEM}")
    print()


def uninstall_startup():
    print(f"\n🗑  Removing auto-startup on {SYSTEM}...\n")
    if SYSTEM == "Windows":
        _run_cmd(f'schtasks /Delete /TN "{SERVICE_NAME}" /F')
        print(f"✅  Removed Task Scheduler entry '{SERVICE_NAME}'.")
    elif SYSTEM == "Darwin":
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{SERVICE_LABEL}.plist")
        uid_r = subprocess.run(["id", "-u"], capture_output=True, text=True)
        uid   = uid_r.stdout.strip()
        _run_cmd(f"launchctl bootout gui/{uid} '{plist_path}'", check=False)
        _run_cmd(f"launchctl unload '{plist_path}'",            check=False)
        if os.path.exists(plist_path):
            os.remove(plist_path)
        print(f"✅  Removed launchd agent: {SERVICE_LABEL}")
    elif SYSTEM == "Linux":
        _run_cmd(f"systemctl --user stop {SERVICE_NAME}",    check=False)
        _run_cmd(f"systemctl --user disable {SERVICE_NAME}", check=False)
        svc_path = os.path.expanduser(f"~/.config/systemd/user/{SERVICE_NAME}.service")
        if os.path.exists(svc_path): os.remove(svc_path)
        _run_cmd("systemctl --user daemon-reload", check=False)
        print(f"✅  Removed systemd service: {SERVICE_NAME}")
    print()


# ─────────────────────────────────────────────────────────────
#  AUTO-INSTALL PACKAGES
# ─────────────────────────────────────────────────────────────

def auto_install_packages():
    """Install any missing laptop packages automatically."""
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
            print(f"   📦 Installing {pkg} ...")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                print(f"   ✅ {pkg} installed")
            else:
                print(f"   ❌ Failed to install {pkg}")
                print(f"      Run manually:  pip install \"{pkg}\"")
    if all_ok:
        print("   ✅ All packages already installed")


# ─────────────────────────────────────────────────────────────
#  SAVE SERVER URL BACK INTO THIS FILE
# ─────────────────────────────────────────────────────────────

def save_server_url(new_url):
    """Write the new SERVER_URL into this script so it persists."""
    try:
        import re
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            r'SERVER_URL\s*=\s*"[^"]*"',
            f'SERVER_URL = "{new_url}"',
            content, count=1
        )
        with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        global SERVER_URL
        SERVER_URL = new_url
        print(f"   ✅ URL saved — no need to edit the file manually.")
    except Exception as e:
        print(f"   ⚠️  Could not save URL automatically: {e}")
        print(f"      Edit SERVER_URL at the top of main.py manually.")


# ─────────────────────────────────────────────────────────────
#  FIRST-RUN SETUP  (runs once, skipped forever after)
# ─────────────────────────────────────────────────────────────

MARKER_FILE = os.path.join(SCRIPT_DIR, ".camdash_ready")

def first_run_setup():
    """
    Runs automatically on first launch only — fully silent, no prompts.
    Installs packages and auto-startup without asking any questions.
    After this, future runs go straight to streaming.
    Camera only activates when someone taps it on the phone dashboard.
    """
    if os.path.exists(MARKER_FILE):
        return  # Already configured — skip silently

    print("""
╔══════════════════════════════════════════════════════╗
║         CAMDASH — SETTING UP (first time only)       ║
╚══════════════════════════════════════════════════════╝
""")

    # ── Step 1: Install packages silently ─────────────────────
    print("  [1/2] Installing required packages...")
    auto_install_packages()
    print()

    # ── Step 2: Install auto-startup silently ─────────────────
    print("  [2/2] Installing auto-startup...")
    install_startup()

    # ── Mark setup as done ────────────────────────────────────
    try:
        open(MARKER_FILE, "w").write("ready")
    except Exception:
        pass

    print()
    print("  " + "─" * 50)
    print("  ✅  Setup complete! Starting stream...")
    print("  ✅  Camera activates only when viewed on phone.")
    print("  " + "─" * 50 + "\n")


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

def print_help():
    print("""
╔══════════════════════════════════════════════════════════╗
║            CAMDASH — USAGE                               ║
╠══════════════════════════════════════════════════════════╣
║  python main.py              Auto-setup + stream         ║
║  python main.py --server     Run relay server (Render)   ║
║  python main.py --install    Re-run auto-startup setup   ║
║  python main.py --uninstall  Remove auto-start           ║
║  python main.py --check      Verify everything is ready  ║
║  python main.py --reset      Redo first-time setup       ║
║  python main.py --help       Show this message           ║
╚══════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
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
            print("🔄  Reset done — run  python main.py  to redo setup.")
        else:
            print("ℹ️   Already fresh — no marker found.")
    else:
        first_run_setup()   # runs once on first launch, skipped forever after
        run_laptop()
