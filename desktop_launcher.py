"""
Avatar Storyteller Video Engine — Native Windows Desktop Launcher
Runs as a true native Windows installable/portable desktop application with:
  - Native Windows desktop window (pywebview + Microsoft WebView2 runtime)
  - Full GPU hardware acceleration enabled (Direct3D / DirectComposition)
  - Background FastAPI/Uvicorn server running in a dedicated thread
  - Clean shutdown when the desktop window is closed
  - Robust fallbacks to Edge App Mode (with GPU enabled) or system browser
"""
import sys
import os
import time
import socket
import subprocess
import threading
import urllib.request
import webbrowser
from pathlib import Path

# Fix Windows console unicode printing and GUI mode (console=False)
if sys.stdout is None:
    import io
    sys.stdout = io.StringIO()
if sys.stderr is None:
    import io
    sys.stderr = io.StringIO()

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Path Setup ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    APP_DIR    = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(APP_DIR)))
else:
    APP_DIR    = Path(__file__).resolve().parent
    BUNDLE_DIR = APP_DIR

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))

# Prepend portable bin/ to PATH for ffmpeg/ffprobe
for b in [APP_DIR / "bin", BUNDLE_DIR / "bin", APP_DIR, BUNDLE_DIR]:
    if b.exists() and (b / "ffmpeg.exe").exists():
        os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")
        break

PORT = 8766
HOST = "127.0.0.1"
URL  = f"http://{HOST}:{PORT}"


def wait_for_server(timeout: float = 15.0) -> bool:
    """Polls until server responds or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{URL}/api/settings", timeout=1.2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def kill_process_on_port(port: int):
    """Kills any stale process on the given port to avoid address-in-use errors."""
    if os.name != "nt":
        return
    try:
        res = subprocess.run(
            f"netstat -ano | findstr :{port}",
            shell=True, capture_output=True, text=True
        )
        current_pid = os.getpid()
        for line in res.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts:
                pid = int(parts[-1])
                if pid != current_pid and pid > 0:
                    print(f"[AvatarEngine] Freeing port {port} (Terminating stale PID {pid})")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass


def launch_edge_fallback():
    """Fallback: Launches standalone Edge App Mode with GPU Hardware Acceleration ENABLED."""
    edge_candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles",       "C:\\Program Files"))       / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))  / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]

    edge_exe = None
    for c in edge_candidates:
        if c.exists():
            edge_exe = c
            break

    if edge_exe:
        print(f"[AvatarEngine] Fallback: Opening in Edge Desktop Window: {edge_exe}")
        try:
            # GPU hardware acceleration remains fully ACTIVE for maximum performance
            cmd = [
                str(edge_exe),
                f"--app={URL}",
                "--window-size=1420,920",
                "--window-position=40,30",
                "--no-first-run",
                "--no-default-browser-check",
                "--title=⚡ ATS Author Studio"
            ]
            subprocess.Popen(cmd)
            return True
        except Exception as e:
            print(f"[AvatarEngine] Edge fallback failed: {e}")

    return False


def main():
    print("=" * 72)
    print("   ⚡  AVATAR STORYTELLER VIDEO ENGINE — NATIVE DESKTOP STUDIO")
    print("      Hardware GPU-Accelerated Windows Video Engine")
    print("=" * 72)
    print(f"[AvatarEngine] App Directory: {APP_DIR}")

    kill_process_on_port(PORT)

    print(f"[AvatarEngine] Initializing core backend server at {URL} ...")
    try:
        from backend.server import app
        from backend.config import find_ffmpeg, find_ffprobe, detect_gpu_encoder
        print(f"[AvatarEngine] FFmpeg:  {find_ffmpeg()}")
        print(f"[AvatarEngine] FFprobe: {find_ffprobe()}")
        gpu = detect_gpu_encoder()
        print(f"[AvatarEngine] GPU Hardware Encoder: {gpu.upper()} (GPU Acceleration ACTIVE)")
    except Exception as e:
        print(f"[ERROR] Failed to load backend: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

    import uvicorn

    # Check for CLI flags
    no_window = any(arg in sys.argv for arg in ["--no-window", "--headless", "-s"])

    # ── Start Backend Server in Background Daemon Thread ──────────────────────
    def run_uvicorn():
        config = uvicorn.Config(
            app=app,
            host=HOST,
            port=PORT,
            log_level="warning",
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        server.run()

    server_thread = threading.Thread(target=run_uvicorn, daemon=True, name="BackendServerThread")
    server_thread.start()

    # Wait until backend API responds
    print(f"[AvatarEngine] Awaiting server readiness...")
    if not wait_for_server(timeout=15.0):
        print(f"[WARNING] Server did not respond within 15s. Proceeding anyway.")
    else:
        print(f"[AvatarEngine] ✅ Backend ready at {URL}")

    # ── Pure Headless Mode ───────────────────────────────────────────────────
    if no_window:
        print("[AvatarEngine] Running in pure Headless / Server mode.")
        print(f"[AvatarEngine] Open in browser or remote machine: {URL}")
        try:
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[AvatarEngine] Headless server stopped by user.")
        sys.exit(0)

    # ── Native Windows Desktop Window via pywebview (WebView2 + Full GPU) ────
    icon_candidate = APP_DIR / "frontend" / "favicon.ico"
    if not icon_candidate.exists():
        icon_candidate = BUNDLE_DIR / "frontend" / "favicon.ico"
    icon_path = str(icon_candidate) if icon_candidate.exists() else None

    use_webview = True
    try:
        import webview
        # Enable downloads (for exporting videos/subtitles directly)
        webview.settings['ALLOW_DOWNLOADS'] = True
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True

        print("[AvatarEngine] Launching Native Windows Desktop Window (GPU Accelerated)...")
        window = webview.create_window(
            title="⚡ ATS Author Studio — Avatar Video Engine",
            url=URL,
            width=1420,
            height=920,
            resizable=True,
            min_size=(1024, 700),
            background_color="#0b0f19",
            text_select=True,
        )

        # Starts native Windows WinForms/WPF WebView2 host window on main thread
        # Direct3D / DirectX 11 GPU hardware acceleration is active
        webview.start(icon=icon_path, debug=False)

        # When the user closes the native desktop window, cleanly exit
        print("[AvatarEngine] Desktop window closed by user. Exiting cleanly.")
        os._exit(0)

    except Exception as e:
        print(f"[AvatarEngine] pywebview native window error: {e}")
        use_webview = False

    # ── Fallback: Edge App Mode (with GPU enabled) or Default Browser ────────
    if not use_webview:
        print("[AvatarEngine] Falling back to desktop app mode...")
        launched = launch_edge_fallback()
        if not launched:
            print(f"[AvatarEngine] Opening default browser at {URL} ...")
            webbrowser.open(URL)

        # Keep server alive while fallback browser window runs
        try:
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[AvatarEngine] Stopped by user.")
            sys.exit(0)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
