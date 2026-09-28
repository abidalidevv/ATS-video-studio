"""
Avatar Storyteller Video Engine — Desktop Launcher
Launches the FastAPI backend and opens the UI in Microsoft Edge App Mode (no browser chrome).
Adapted from VideoGen Studio (vg/desktop_launcher.py).
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

# Fix Windows console unicode printing
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

PORT = 8766    # Different from vg's 8765 to avoid port conflicts
HOST = "127.0.0.1"
URL  = f"http://{HOST}:{PORT}"


def wait_for_server(timeout: float = 15.0) -> bool:
    """Polls until server responds or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{URL}/api/settings", timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def launch_native_window():
    """Opens the app in Edge App Mode (no address bar, no browser chrome)."""
    ready = wait_for_server()
    if not ready:
        time.sleep(1.5)

    print(f"\n[AvatarEngine] ✅ Server ready at {URL}")

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
        print(f"[AvatarEngine] Opening in Edge App Mode: {edge_exe}")
        try:
            subprocess.Popen([
                str(edge_exe),
                f"--app={URL}",
                "--window-size=1400,920",
                "--window-position=40,30",
                "--title=⚡ Avatar Storyteller Engine"
            ])
            return
        except Exception as e:
            print(f"[AvatarEngine] Edge App Mode failed: {e}")

    print("[AvatarEngine] Opening in default browser...")
    webbrowser.open(URL)


def kill_process_on_port(port: int):
    """Kills any stale process on the given port."""
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
                    print(f"[AvatarEngine] Killing stale process PID {pid} on port {port}")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass


def main():
    print("=" * 70)
    print("   ⚡  AVATAR STORYTELLER VIDEO ENGINE")
    print("      Ultra-Fast Single-Pass GPU Faceless Video Generator")
    print("=" * 70)
    print(f"[AvatarEngine] App Directory: {APP_DIR}")

    kill_process_on_port(PORT)

    print(f"[AvatarEngine] Starting backend server at {URL} ...")

    try:
        from backend.server import app
        from backend.config import find_ffmpeg, find_ffprobe
        print(f"[AvatarEngine] FFmpeg: {find_ffmpeg()}")
        print(f"[AvatarEngine] FFprobe: {find_ffprobe()}")
    except Exception as e:
        print(f"[ERROR] Failed to load backend: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

    launcher_thread = threading.Thread(target=launch_native_window, daemon=True)
    launcher_thread.start()

    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
