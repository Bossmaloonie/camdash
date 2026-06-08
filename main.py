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
SERVER_URL = "https://YOUR-APP-NAME.onrender.com"

# Dashboard password — viewers must enter this to see cameras.
# Set to "" (empty string) to disable password protection.
DASHBOARD_PASSWORD = "bossmaloonie"

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
        from flask import Flask, render_template_string, request as flask_request
        from flask_socketio import SocketIO, emit, join_room, leave_room
    except ImportError:
        print("❌  pip install flask flask-socketio gevent gevent-websocket")
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
        async_mode="threading", ping_timeout=60, ping_interval=25,
    )

    cameras_by_sid   = {}   # sid  → {id, name}
    authed_sids      = set() # sids that passed password check
    viewer_counts    = {}   # cam_id → number of active viewers
    viewers_watching = {}   # viewer_sid → cam_id they are watching

    def get_camera_list():
        return [{"id": v["id"], "name": v["name"]} for v in cameras_by_sid.values()]

    def is_authed(sid):
        return (not PASSWORD_HASH) or (sid in authed_sids)

    def viewer_start(cam_id):
        """Increment viewer count. Tell laptop to start if first viewer."""
        viewer_counts[cam_id] = viewer_counts.get(cam_id, 0) + 1
        if viewer_counts[cam_id] == 1:
            emit("start_stream", to=f"cam_{cam_id}")
            print(f"▶  Stream started: {cam_id}")

    def viewer_stop(cam_id):
        """Decrement viewer count. Tell laptop to stop if no viewers left."""
        viewer_counts[cam_id] = max(0, viewer_counts.get(cam_id, 0) - 1)
        if viewer_counts[cam_id] == 0:
            emit("stop_stream", to=f"cam_{cam_id}")
            print(f"⏸  Stream paused:  {cam_id}")

    # ── Phone Dashboard HTML ──────────────────────────────────
    VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>CamDash</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#07070e;
  --bg2:#0d0d1c;
  --glass:rgba(255,255,255,0.035);
  --glass-hover:rgba(255,255,255,0.065);
  --border:rgba(255,255,255,0.07);
  --border-hover:rgba(255,255,255,0.14);
  --accent:#4ade80;
  --accent2:#22d3ee;
  --accent-glow:rgba(74,222,128,0.18);
  --accent-glow2:rgba(74,222,128,0.06);
  --red:#f87171;
  --red-glow:rgba(248,113,113,0.25);
  --text:#eeeef5;
  --text2:#9999b8;
  --text3:#44445a;
  --radius:18px;
  --radius-sm:12px;
}

html,body{height:100%;overflow:hidden}
body{
  font-family:'Inter',system-ui,sans-serif;
  background:var(--bg);
  color:var(--text);
  -webkit-font-smoothing:antialiased;
}

/* subtle radial bg glow */
body::before{
  content:'';
  position:fixed;inset:0;z-index:0;
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%,rgba(74,222,128,0.06) 0%,transparent 60%),
    radial-gradient(ellipse 60% 40% at 100% 100%,rgba(34,211,238,0.04) 0%,transparent 50%);
  pointer-events:none;
}

/* ═══════════════════════ LOGIN ═══════════════════════ */
#login-screen{
  position:fixed;inset:0;z-index:300;
  display:flex;align-items:center;justify-content:center;
  padding:24px;
  background:var(--bg);
}
#login-screen.hidden{display:none}

.login-card{
  width:100%;max-width:360px;
  background:rgba(255,255,255,0.03);
  border:1px solid rgba(255,255,255,0.08);
  border-radius:28px;
  padding:40px 32px 36px;
  box-shadow:0 0 0 1px rgba(74,222,128,0.06),0 32px 80px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.06);
  display:flex;flex-direction:column;align-items:center;gap:0;
  backdrop-filter:blur(40px);
}

.login-logo-ring{
  width:72px;height:72px;border-radius:50%;
  background:radial-gradient(circle at 35% 35%,rgba(74,222,128,0.25),rgba(74,222,128,0.05));
  border:1px solid rgba(74,222,128,0.3);
  display:flex;align-items:center;justify-content:center;
  font-size:1.8rem;margin-bottom:24px;
  box-shadow:0 0 32px rgba(74,222,128,0.15),0 0 80px rgba(74,222,128,0.06);
}

.login-title{
  font-size:1.15rem;font-weight:700;letter-spacing:0.12em;
  text-transform:uppercase;margin-bottom:6px;
  background:linear-gradient(135deg,#fff 0%,rgba(255,255,255,0.6) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.login-sub{font-size:0.78rem;color:var(--text2);margin-bottom:28px;letter-spacing:0.01em}

.input-group{width:100%;position:relative;margin-bottom:12px}
.input-group input{
  width:100%;padding:14px 48px 14px 18px;
  background:rgba(255,255,255,0.05);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:var(--radius-sm);
  color:var(--text);font-size:0.95rem;font-family:'Inter',sans-serif;
  outline:none;transition:border-color 0.2s,box-shadow 0.2s;
  letter-spacing:0.08em;
}
.input-group input::placeholder{color:var(--text3);letter-spacing:0.01em}
.input-group input:focus{
  border-color:rgba(74,222,128,0.5);
  box-shadow:0 0 0 3px rgba(74,222,128,0.1);
}
.input-group input.err{
  border-color:rgba(248,113,113,0.6);
  box-shadow:0 0 0 3px rgba(248,113,113,0.1);
  animation:shake .35s ease;
}
@keyframes shake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-6px)}40%,80%{transform:translateX(6px)}}

.toggle-pw{
  position:absolute;right:14px;top:50%;transform:translateY(-50%);
  background:none;border:none;color:var(--text3);cursor:pointer;
  font-size:1rem;padding:4px;line-height:1;transition:color 0.2s;
}
.toggle-pw:hover{color:var(--text2)}

.login-btn{
  width:100%;padding:14px;border:none;border-radius:var(--radius-sm);
  font-size:0.9rem;font-weight:600;font-family:'Inter',sans-serif;
  cursor:pointer;margin-top:4px;letter-spacing:0.04em;
  background:linear-gradient(135deg,#4ade80 0%,#22c55e 100%);
  color:#052e16;transition:opacity 0.2s,transform 0.15s;
  box-shadow:0 4px 20px rgba(74,222,128,0.3);
}
.login-btn:active{opacity:.85;transform:scale(.98)}
.login-btn:disabled{opacity:.5;cursor:not-allowed}

.login-error{
  font-size:0.75rem;color:var(--red);text-align:center;
  margin-top:10px;min-height:16px;letter-spacing:0.01em;
}

/* ═══════════════════════ TOPBAR ═══════════════════════ */
.topbar{
  position:fixed;top:0;left:0;right:0;z-index:100;
  height:64px;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;
  background:rgba(7,7,14,0.8);
  backdrop-filter:blur(24px);saturate(180%);
  border-bottom:1px solid rgba(255,255,255,0.06);
}
.topbar-left{display:flex;align-items:center;gap:12px}
.logo-ring{
  width:36px;height:36px;border-radius:10px;
  background:linear-gradient(135deg,rgba(74,222,128,0.2),rgba(34,211,238,0.1));
  border:1px solid rgba(74,222,128,0.25);
  display:flex;align-items:center;justify-content:center;font-size:1.05rem;
}
.topbar-title{
  font-size:0.95rem;font-weight:700;letter-spacing:0.08em;
  text-transform:uppercase;
  background:linear-gradient(90deg,#fff,rgba(255,255,255,0.7));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.topbar-sub{font-size:0.67rem;color:var(--text3);margin-top:1px;font-family:'JetBrains Mono',monospace}

.conn-pill{
  display:flex;align-items:center;gap:6px;
  padding:5px 12px 5px 8px;border-radius:999px;
  background:rgba(255,255,255,0.04);
  border:1px solid rgba(255,255,255,0.08);
  font-size:0.7rem;color:var(--text2);letter-spacing:0.02em;
  transition:all 0.3s;
}
.conn-pill.online{background:rgba(74,222,128,0.08);border-color:rgba(74,222,128,0.2);color:var(--accent)}
.conn-pill.offline{background:rgba(248,113,113,0.08);border-color:rgba(248,113,113,0.2);color:var(--red)}

.conn-dot{
  width:7px;height:7px;border-radius:50%;
  background:var(--text3);transition:background 0.3s;
}
.conn-pill.online  .conn-dot{background:var(--accent);box-shadow:0 0 6px var(--accent);animation:pulse-dot 2s infinite}
.conn-pill.offline .conn-dot{background:var(--red)}
@keyframes pulse-dot{0%,100%{opacity:1}50%{opacity:.4}}

/* ═══════════════════════ DASHBOARD ═══════════════════════ */
#main-view{
  position:fixed;inset:0;
  padding-top:64px;
  overflow-y:auto;
  -webkit-overflow-scrolling:touch;
  z-index:10;
}
#main-view::-webkit-scrollbar{display:none}

#dashboard{padding:20px 16px 32px}

.dash-header{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:16px;
}
.section-label{
  font-size:0.65rem;font-weight:600;letter-spacing:0.14em;
  text-transform:uppercase;color:var(--text3);
}
.cam-count-chip{
  font-size:0.65rem;font-family:'JetBrains Mono',monospace;
  padding:3px 9px;border-radius:999px;
  background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
  color:var(--text3);
}

.cam-grid{
  display:grid;
  grid-template-columns:repeat(2,1fr);
  gap:12px;
}
@media(min-width:500px){.cam-grid{grid-template-columns:repeat(3,1fr)}}

/* ── Camera Card ── */
.cam-card{
  border-radius:var(--radius);overflow:hidden;
  background:var(--glass);
  border:1px solid var(--border);
  cursor:pointer;
  transition:transform 0.2s ease,border-color 0.25s,box-shadow 0.25s;
  -webkit-tap-highlight-color:transparent;
  position:relative;
}
.cam-card::after{
  content:'';position:absolute;inset:0;border-radius:var(--radius);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.07);
  pointer-events:none;
}
.cam-card:active{transform:scale(0.96)}
.cam-card:hover,
.cam-card.streaming{
  border-color:rgba(74,222,128,0.25);
  box-shadow:0 0 0 1px rgba(74,222,128,0.1),0 8px 32px rgba(0,0,0,0.4);
}

/* Thumbnail */
.cam-thumb{
  width:100%;aspect-ratio:16/9;
  background:#0a0a16;
  position:relative;overflow:hidden;
  display:flex;align-items:center;justify-content:center;
}
.cam-thumb img{
  position:absolute;inset:0;width:100%;height:100%;
  object-fit:cover;opacity:0;transition:opacity 0.4s ease;
}
.cam-thumb img.loaded{opacity:1}
.thumb-placeholder{
  font-size:1.6rem;opacity:0.15;
  position:absolute;z-index:1;
  transition:opacity 0.3s;
}
.cam-thumb img.loaded ~ .thumb-placeholder{opacity:0}

/* gradient overlay on thumbnail */
.thumb-grad{
  position:absolute;inset:0;z-index:2;
  background:linear-gradient(to top,rgba(7,7,14,0.85) 0%,transparent 55%);
}

/* LIVE badge */
.live-badge{
  position:absolute;top:8px;left:8px;z-index:4;
  display:none;align-items:center;gap:5px;
  padding:3px 8px;border-radius:6px;
  background:rgba(0,0,0,0.65);
  border:1px solid rgba(248,113,113,0.4);
  font-size:0.58rem;font-weight:700;letter-spacing:0.1em;color:#fff;
  backdrop-filter:blur(8px);
}
.cam-card.streaming .live-badge{display:flex}
.live-dot{
  width:6px;height:6px;border-radius:50%;
  background:var(--red);
  box-shadow:0 0 6px var(--red);
  animation:live-pulse 1.2s ease infinite;
}
@keyframes live-pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}

/* Card info row */
.cam-info{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 12px 11px;
}
.cam-name{
  font-size:0.8rem;font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;
  color:var(--text);
}
.cam-sub{
  font-size:0.64rem;color:var(--text3);margin-top:2px;
  font-family:'JetBrains Mono',monospace;letter-spacing:0.02em;
}
.cam-card.online  .cam-sub{color:var(--accent)}
.status-pip{
  width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-left:8px;
  background:var(--text3);
}
.cam-card.online  .status-pip{background:var(--accent);box-shadow:0 0 6px rgba(74,222,128,0.5)}

/* ── Empty state ── */
.empty-state{
  grid-column:1/-1;
  display:flex;flex-direction:column;align-items:center;
  padding:60px 20px;gap:12px;text-align:center;
}
.empty-icon-box{
  width:72px;height:72px;border-radius:20px;
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
  display:flex;align-items:center;justify-content:center;font-size:2rem;
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.06);
}
.empty-state h3{font-size:0.9rem;font-weight:600;color:var(--text2)}
.empty-state p{font-size:0.77rem;color:var(--text3);line-height:1.6}
.empty-state code{
  font-family:'JetBrains Mono',monospace;font-size:0.72rem;
  color:var(--accent);background:rgba(74,222,128,0.08);
  padding:1px 6px;border-radius:4px;
}

/* ═══════════════════════ FULLSCREEN VIEWER ═══════════════════════ */
#viewer{
  position:fixed;inset:0;z-index:200;
  background:#000;
  display:none;flex-direction:column;
  transition:opacity 0.25s;
}
#viewer.open{display:flex}

#viewer-feed-wrap{
  position:absolute;inset:0;
  display:flex;align-items:center;justify-content:center;
}
#fullscreen-feed{
  width:100%;height:100%;object-fit:contain;
  display:none;
}
#fullscreen-feed.visible{display:block}

/* Viewer overlay (fades on tap) */
#viewer-overlay{
  position:absolute;inset:0;z-index:10;
  pointer-events:none;
  transition:opacity 0.35s ease;
}
#viewer-overlay.fade{opacity:0}

/* Top gradient + bar */
.viewer-top-grad{
  position:absolute;top:0;left:0;right:0;
  height:140px;
  background:linear-gradient(to bottom,rgba(0,0,0,0.8) 0%,transparent 100%);
}
.viewer-topbar{
  position:absolute;top:env(safe-area-inset-top,0px);left:0;right:0;
  padding:16px 16px 0;
  display:flex;align-items:center;gap:12px;
}
.back-btn{
  width:38px;height:38px;border-radius:12px;border:none;
  background:rgba(255,255,255,0.1);
  backdrop-filter:blur(12px);
  color:#fff;font-size:1rem;cursor:pointer;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  -webkit-tap-highlight-color:transparent;
  border:1px solid rgba(255,255,255,0.12);
}
.viewer-name{font-size:0.95rem;font-weight:600;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,0.5)}
.viewer-badge{
  margin-left:auto;
  font-size:0.65rem;font-weight:600;padding:4px 10px;border-radius:999px;
  background:rgba(0,0,0,0.5);color:rgba(255,255,255,0.5);
  border:1px solid rgba(255,255,255,0.12);
  backdrop-filter:blur(8px);white-space:nowrap;
  letter-spacing:0.04em;
}
.viewer-badge.live{
  background:rgba(248,113,113,0.2);color:var(--red);
  border-color:rgba(248,113,113,0.35);
}

/* Viewer placeholder */
.viewer-ph{
  position:absolute;inset:0;z-index:5;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:12px;color:rgba(255,255,255,0.2);
}
.viewer-ph .icon{font-size:3rem;opacity:.4}
.viewer-ph p{font-size:0.8rem;opacity:.6}
.viewer-ph.hidden{display:none}

/* Bottom gradient + switcher */
.viewer-bottom-grad{
  position:absolute;bottom:0;left:0;right:0;
  height:160px;
  background:linear-gradient(to top,rgba(0,0,0,0.85) 0%,transparent 100%);
}
.cam-switcher{
  position:absolute;bottom:env(safe-area-inset-bottom,0px);left:0;right:0;
  padding:0 16px 20px;
  display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;
}
.cam-switcher::-webkit-scrollbar{display:none}

.sw-btn{
  flex-shrink:0;display:flex;align-items:center;gap:6px;
  padding:7px 14px;border-radius:999px;
  border:1px solid rgba(255,255,255,0.12);
  background:rgba(255,255,255,0.07);
  color:rgba(255,255,255,0.55);font-size:0.75rem;
  font-family:'Inter',sans-serif;font-weight:500;
  cursor:pointer;white-space:nowrap;
  -webkit-tap-highlight-color:transparent;
  backdrop-filter:blur(12px);
  transition:all 0.2s;
}
.sw-dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}
.sw-btn.active{
  border-color:rgba(74,222,128,0.4);
  background:rgba(74,222,128,0.12);
  color:var(--accent);
}

/* card entrance animation */
@keyframes card-in{
  from{opacity:0;transform:translateY(12px)}
  to  {opacity:1;transform:translateY(0)}
}
.cam-card{animation:card-in 0.3s ease both}
</style>
</head>
<body>

<!-- ═══ LOGIN SCREEN ═══ -->
<div id="login-screen" class="{{ '' if needs_auth else 'hidden' }}">
  <div class="login-card">
    <div class="login-logo-ring">📷</div>
    <div class="login-title">CamDash</div>
    <div class="login-sub">Enter your password to access cameras</div>
    <div class="input-group">
      <input id="pw-input" type="password" placeholder="Password" autocomplete="current-password"/>
      <button class="toggle-pw" id="toggle-pw" tabindex="-1">👁</button>
    </div>
    <button class="login-btn" id="login-btn">Unlock Dashboard</button>
    <div class="login-error" id="login-error"></div>
  </div>
</div>

<!-- ═══ TOPBAR ═══ -->
<div class="topbar">
  <div class="topbar-left">
    <div class="logo-ring">📷</div>
    <div>
      <div class="topbar-title">CamDash</div>
      <div class="topbar-sub" id="cam-count">Connecting...</div>
    </div>
  </div>
  <div class="conn-pill" id="conn-pill">
    <span class="conn-dot" id="conn-dot"></span>
    <span id="conn-text">Connecting</span>
  </div>
</div>

<!-- ═══ MAIN SCROLL VIEW ═══ -->
<div id="main-view">
  <div id="dashboard">
    <div class="dash-header">
      <div class="section-label">Live Cameras</div>
      <div class="cam-count-chip" id="cam-chip">0 online</div>
    </div>
    <div class="cam-grid" id="cam-grid">
      <div class="empty-state">
        <div class="empty-icon-box">🎥</div>
        <h3>No cameras online</h3>
        <p>Run <code>python main.py</code> on a laptop<br>to start streaming.</p>
      </div>
    </div>
  </div>
</div>

<!-- ═══ FULLSCREEN VIEWER ═══ -->
<div id="viewer">
  <div id="viewer-feed-wrap">
    <img id="fullscreen-feed" alt=""/>
  </div>
  <div id="viewer-overlay">
    <div class="viewer-top-grad"></div>
    <div class="viewer-topbar">
      <button class="back-btn" id="back-btn">&#8592;</button>
      <span class="viewer-name" id="viewer-name"></span>
      <span class="viewer-badge" id="viewer-badge">Connecting...</span>
    </div>
    <div class="viewer-ph" id="viewer-ph">
      <div class="icon">🎥</div>
      <p id="viewer-ph-msg">Waiting for stream...</p>
    </div>
    <div class="viewer-bottom-grad"></div>
    <div class="cam-switcher" id="switcher"></div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
<script>
  // ── State ───────────────────────────────────────────────────
  const needsAuth  = {{ 'true' if needs_auth else 'false' }};
  let authenticated = !needsAuth;
  let cameras = {}, currentCam = null, thumbs = {};

  // ── Elements ────────────────────────────────────────────────
  const loginScreen = document.getElementById('login-screen');
  const pwInput     = document.getElementById('pw-input');
  const loginBtn    = document.getElementById('login-btn');
  const loginError  = document.getElementById('login-error');
  const togglePw    = document.getElementById('toggle-pw');
  const connPill    = document.getElementById('conn-pill');
  const connText    = document.getElementById('conn-text');
  const camCount    = document.getElementById('cam-count');
  const camChip     = document.getElementById('cam-chip');
  const camGrid     = document.getElementById('cam-grid');
  const viewer      = document.getElementById('viewer');
  const overlay     = document.getElementById('viewer-overlay');
  const viewerName  = document.getElementById('viewer-name');
  const viewerBadge = document.getElementById('viewer-badge');
  const viewerPh    = document.getElementById('viewer-ph');
  const viewerPhMsg = document.getElementById('viewer-ph-msg');
  const fsFeed      = document.getElementById('fullscreen-feed');
  const switcher    = document.getElementById('switcher');
  const backBtn     = document.getElementById('back-btn');

  // ── Password toggle ─────────────────────────────────────────
  togglePw.onclick = () => {
    pwInput.type = pwInput.type === 'password' ? 'text' : 'password';
    togglePw.textContent = pwInput.type === 'password' ? '👁' : '🙈';
  };

  // ── Socket ──────────────────────────────────────────────────
  const socket = io({ transports:['websocket','polling'] });

  socket.on('connect', () => {
    connPill.className = 'conn-pill online';
    connText.textContent = 'Online';
    if (authenticated) socket.emit('viewer_join');
  });

  socket.on('disconnect', () => {
    connPill.className = 'conn-pill offline';
    connText.textContent = 'Offline';
    camCount.textContent = 'Disconnected';
  });

  socket.on('auth_ok', () => {
    authenticated = true;
    loginScreen.classList.add('hidden');
    socket.emit('viewer_join');
  });

  socket.on('auth_fail', () => {
    pwInput.classList.add('err');
    loginError.textContent = 'Incorrect password. Try again.';
    loginBtn.disabled = false;
    loginBtn.textContent = 'Unlock Dashboard';
    setTimeout(() => pwInput.classList.remove('err'), 400);
    pwInput.focus();
  });

  socket.on('camera_list', list => {
    cameras = {};
    list.forEach(c => cameras[c.id] = c);
    const n = list.length;
    camCount.textContent = n === 0 ? 'No cameras online' : `${n} camera${n>1?'s':''} online`;
    camChip.textContent  = `${n} online`;
    renderDash();
    renderSwitcher();
    if (currentCam && !cameras[currentCam]) {
      currentCam = null;
      viewerBadge.className = 'viewer-badge';
      viewerBadge.textContent = 'Offline';
      showPh('Camera went offline');
    }
  });

  socket.on('frame', b64 => {
    if (!currentCam) return;
    fsFeed.src = 'data:image/jpeg;base64,' + b64;
    if (!fsFeed.classList.contains('visible')) {
      fsFeed.classList.add('visible');
      viewerPh.classList.add('hidden');
    }
    viewerBadge.className = 'viewer-badge live';
    viewerBadge.textContent = '● LIVE';
    thumbs[currentCam] = b64;
    updateThumb(currentCam, b64);
  });

  // ── Login ───────────────────────────────────────────────────
  function tryLogin() {
    const pw = pwInput.value.trim();
    if (!pw) { pwInput.focus(); return; }
    loginBtn.disabled = true;
    loginBtn.textContent = 'Checking...';
    loginError.textContent = '';
    socket.emit('authenticate', pw);
  }
  loginBtn.onclick = tryLogin;
  pwInput.addEventListener('keydown', e => { if (e.key === 'Enter') tryLogin(); });

  // ── Dashboard ────────────────────────────────────────────────
  function renderDash() {
    camGrid.innerHTML = '';
    const ids = Object.keys(cameras);
    if (!ids.length) {
      camGrid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon-box">🎥</div>
          <h3>No cameras online</h3>
          <p>Run <code>python main.py</code> on a laptop<br>to start streaming.</p>
        </div>`;
      return;
    }
    ids.forEach((id, i) => {
      const thumb  = thumbs[id];
      const active = id === currentCam;
      const d = document.createElement('div');
      d.className = 'cam-card online' + (active ? ' streaming' : '');
      d.id  = 'card-' + id;
      d.style.animationDelay = (i * 0.06) + 's';
      d.innerHTML = `
        <div class="cam-thumb">
          <div class="thumb-placeholder">📷</div>
          <img id="thumb-${id}" ${thumb ? `src="data:image/jpeg;base64,${thumb}" class="loaded"` : ''} alt=""/>
          <div class="thumb-grad"></div>
          <div class="live-badge"><span class="live-dot"></span>LIVE</div>
        </div>
        <div class="cam-info">
          <div style="min-width:0">
            <div class="cam-name">${cameras[id].name}</div>
            <div class="cam-sub">${active ? '▶ Streaming' : '● Online'}</div>
          </div>
          <div class="status-pip"></div>
        </div>`;
      d.onclick = () => openViewer(id);
      camGrid.appendChild(d);
    });
  }

  function updateThumb(id, b64) {
    const img  = document.getElementById('thumb-' + id);
    const card = document.getElementById('card-' + id);
    if (img)  { img.src = 'data:image/jpeg;base64,' + b64; img.classList.add('loaded'); }
    if (card) card.classList.add('streaming');
  }

  // ── Viewer ───────────────────────────────────────────────────
  let hideTimer = null;

  function scheduleHide() {
    clearTimeout(hideTimer);
    overlay.classList.remove('fade');
    hideTimer = setTimeout(() => overlay.classList.add('fade'), 3500);
  }

  function openViewer(id) {
    if (currentCam) socket.emit('viewer_leave_cam', currentCam);
    currentCam = id;
    socket.emit('viewer_watch', id);
    viewerName.textContent  = cameras[id]?.name || id;
    viewerBadge.className   = 'viewer-badge';
    viewerBadge.textContent = 'Connecting...';
    if (thumbs[id]) {
      fsFeed.src = 'data:image/jpeg;base64,' + thumbs[id];
      fsFeed.classList.add('visible'); viewerPh.classList.add('hidden');
    } else {
      fsFeed.classList.remove('visible');
      viewerPh.classList.remove('hidden');
      viewerPhMsg.textContent = 'Waiting for stream...';
    }
    viewer.classList.add('open');
    overlay.classList.remove('fade');
    renderDash(); renderSwitcher();
    scheduleHide();
  }

  function closeViewer() {
    clearTimeout(hideTimer);
    if (currentCam) socket.emit('viewer_leave_cam', currentCam);
    currentCam = null;
    viewer.classList.remove('open');
    fsFeed.classList.remove('visible');
    overlay.classList.remove('fade');
    renderDash();
  }

  function showPh(msg) {
    fsFeed.classList.remove('visible');
    viewerPh.classList.remove('hidden');
    viewerPhMsg.textContent = msg;
  }

  // tap feed to toggle overlay
  fsFeed.onclick = () => {
    if (overlay.classList.contains('fade')) { scheduleHide(); }
    else { clearTimeout(hideTimer); overlay.classList.add('fade'); }
  };

  backBtn.onclick = e => { e.stopPropagation(); closeViewer(); };

  let ty = 0;
  viewer.addEventListener('touchstart', e => { ty = e.touches[0].clientY; scheduleHide(); }, {passive:true});
  viewer.addEventListener('touchend',   e => { if (e.changedTouches[0].clientY - ty > 90) closeViewer(); }, {passive:true});

  function renderSwitcher() {
    switcher.innerHTML = '';
    Object.values(cameras).forEach(c => {
      const b = document.createElement('button');
      b.className = 'sw-btn' + (c.id === currentCam ? ' active' : '');
      b.innerHTML = `<span class="sw-dot"></span>${c.name}`;
      b.onclick   = e => { e.stopPropagation(); openViewer(c.id); scheduleHide(); };
      switcher.appendChild(b);
    });
  }
</script>
</body>
</html>"""

    # ── Flask routes ──────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template_string(
            VIEWER_HTML,
            needs_auth=bool(PASSWORD_HASH)
        )

    @app.route("/health")
    def health():
        return "OK"

    # ── Socket events ─────────────────────────────────────────
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
        join_room(f"cam_{cam_id}")
        print(f"📹 Online:  {cam_name}")
        emit("camera_list", get_camera_list(), broadcast=True)

    @sio.on("frame")
    def on_frame(data):
        cam_id = data.get("id"); frame = data.get("frame")
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
        # Leave previous camera if switching
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
        # Clean up if this was a viewer
        if sid in viewers_watching:
            cam_id = viewers_watching.pop(sid)
            leave_room(f"viewers_{cam_id}")
            viewer_stop(cam_id)
        # Clean up if this was a laptop
        if sid in cameras_by_sid:
            info = cameras_by_sid.pop(sid)
            viewer_counts.pop(info["id"], None)
            print(f"📴 Offline: {info['name']}")
            emit("camera_list", get_camera_list(), broadcast=True)

    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Multi-camera relay server on port {port}")
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

    if "YOUR-APP-NAME" in SERVER_URL:
        print("\n❌  Edit SERVER_URL at the top of this file first.\n")
        sys.exit(1)

    cam_name = socket.gethostname()
    cam_id   = cam_name.lower().replace(" ", "_").replace("-", "_")

    # Controls whether frames are sent — only active when someone watches
    streaming = threading.Event()

    sio = sio_lib.Client(
        reconnection=True, reconnection_attempts=0,
        reconnection_delay=2, max_http_buffer_size=10 * 1024 * 1024,
    )

    @sio.event
    def connect():
        print(f"✅ Connected as '{cam_name}'")
        print(f"   📱 Dashboard: {SERVER_URL}")
        print(f"   ⏸  Standby — waiting for a viewer to tap this camera\n")
        sio.emit("register_camera", {"id": cam_id, "name": cam_name})

    @sio.event
    def disconnect():
        streaming.clear()
        print("🔌 Disconnected — reconnecting...")

    @sio.event
    def connect_error(data):
        print(f"⚠️  Connection error: {data}")

    @sio.on("start_stream")
    def on_start_stream():
        print(f"▶  Viewer connected — streaming '{cam_name}'")
        streaming.set()

    @sio.on("stop_stream")
    def on_stop_stream():
        print(f"⏸  No viewers — '{cam_name}' is on standby")
        streaming.clear()

    print(f"🔌 Connecting to {SERVER_URL} as '{cam_name}'...")
    sio.connect(SERVER_URL, transports=["websocket", "polling"])

    # Windows: DirectShow backend is far more reliable
    cap = (cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
           if SYSTEM == "Windows"
           else cv2.VideoCapture(CAMERA_INDEX))

    if not cap.isOpened():
        if SYSTEM == "Windows":
            cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print(f"\n❌  Cannot open camera #{CAMERA_INDEX}.")
            print("    • Close Zoom / Teams / other apps using the camera")
            print("    • Try CAMERA_INDEX = 1 or 2")
            sio.disconnect(); sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS,          TARGET_FPS)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"📹 Camera ready: {w}×{h} @ {TARGET_FPS}fps  |  Ctrl+C to stop\n")

    encode_params  = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    frame_interval = 1.0 / TARGET_FPS

    try:
        while True:
            # Block here (zero CPU) until a viewer taps this camera
            streaming.wait()

            t0  = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1); continue

            _, buf  = cv2.imencode(".jpg", frame, encode_params)
            payload = base64.b64encode(buf).decode("ascii")

            if sio.connected and streaming.is_set():
                sio.emit("frame", {"id": cam_id, "frame": payload})

            wait = frame_interval - (time.monotonic() - t0)
            if wait > 0:
                time.sleep(wait)
    except KeyboardInterrupt:
        print(f"\n⏹  '{cam_name}' stopped.")
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

    try:
        import cv2
        cap = (cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
               if SYSTEM == "Windows" else cv2.VideoCapture(CAMERA_INDEX))
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"✅  Camera #{CAMERA_INDEX} ({w}×{h})")
            cap.release()
        else:
            print(f"❌  Camera #{CAMERA_INDEX} not accessible"); ok = False
    except Exception as e:
        print(f"❌  Camera error: {e}"); ok = False

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
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

def print_help():
    print("""
╔══════════════════════════════════════════════════════════╗
║            MULTI-CAMERA STREAM — USAGE                   ║
╠══════════════════════════════════════════════════════════╣
║  python main.py              Stream this laptop camera   ║
║  python main.py --server     Run relay server (Render)   ║
║  python main.py --install    One-time setup + perms      ║
║  python main.py --uninstall  Remove auto-start           ║
║  python main.py --check      Verify everything is ready  ║
║  python main.py --help       Show this message           ║
╚══════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    args = sys.argv[1:]
    if   "--help"      in args or "-h" in args: print_help()
    elif "--server"    in args:                  run_server()
    elif "--install"   in args:                  install_startup()
    elif "--uninstall" in args:                  uninstall_startup()
    elif "--check"     in args:                  run_check()
    else:                                        run_laptop()
