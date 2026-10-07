"""
Avatar Storyteller Video Engine — FastAPI Backend Server
All API endpoints for the desktop app UI.
"""
import os
import uuid
import asyncio
import json
import shutil
import subprocess
import traceback
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    load_settings, save_settings, TEMP_DIR, OUTPUT_DIR,
    AVATARS_DIR, FRONTEND_DIR, detect_gpu_encoder, get_encoder_params, find_ffmpeg
)

app = FastAPI(title="Avatar Storyteller Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Job Progress & Background Transcription Store ──────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}

_TRANSCRIPTION_CACHE: Dict[str, Dict[str, Any]] = {}
_TRANSCRIPTION_TASKS: Dict[str, Dict[str, Any]] = {}
_TRANSCRIPTION_LOCK = threading.Lock()


def _update_job(job_id: str, data: dict):
    if job_id in _jobs:
        if "message" in data and data["message"]:
            msg = str(data["message"])
            if "logs" not in _jobs[job_id]:
                _jobs[job_id]["logs"] = []
            if not _jobs[job_id]["logs"] or _jobs[job_id]["logs"][-1] != msg:
                _jobs[job_id]["logs"].append(msg)
                print(f"[{job_id[:6]}] {msg}")
        _jobs[job_id].update(data)


# ── Static Frontend & Media Mounts ────────────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
if AVATARS_DIR.exists():
    app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")
if TEMP_DIR.exists():
    app.mount("/temp", StaticFiles(directory=str(TEMP_DIR)), name="temp")


@app.get("/")
async def serve_index():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return JSONResponse({"status": "Avatar Storyteller Engine running"})


# ── Settings ───────────────────────────────────────────────────────────────────
@app.get("/api/settings")
async def get_settings():
    return load_settings()


@app.post("/api/settings")
async def update_settings(body: dict):
    saved = save_settings(body)
    return {"success": True, "settings": saved}


# ── System Health & Storage Guard ─────────────────────────────────────────────
@app.get("/api/system/health")
async def system_health():
    settings = load_settings()
    keys_list = settings.get("groq_api_keys", [])
    primary_key = settings.get("groq_api_key", "").strip()
    if primary_key and primary_key not in keys_list:
        keys_list.insert(0, primary_key)

    masked_primary = f"{primary_key[:6]}...{primary_key[-4:]}" if len(primary_key) > 10 else ("***" if primary_key else "")
    
    linked_keys = []
    for idx, k in enumerate(keys_list):
        k_str = str(k).strip()
        if not k_str:
            continue
        m = f"{k_str[:6]}...{k_str[-4:]}" if len(k_str) > 10 else "***"
        linked_keys.append({
            "key_masked": m,
            "is_primary": (k_str == primary_key or idx == 0),
        })

    groq_status = {
        "configured": bool(primary_key or keys_list),
        "valid": False,
        "masked_key": masked_primary,
        "linked_keys": linked_keys,
        "linked_keys_count": len(linked_keys),
        "latency_ms": 0,
        "message": "No Groq API Key linked" if not (primary_key or keys_list) else "Verifying connection..."
    }

    test_key = primary_key or (keys_list[0] if keys_list else "")
    if test_key:
        try:
            import httpx
            t0 = time.time()
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {test_key}"}
                )
                lat = int((time.time() - t0) * 1000)
                groq_status["latency_ms"] = lat
                if res.status_code == 200:
                    groq_status["valid"] = True
                    groq_status["message"] = f"Groq Whisper API Connected ({lat}ms)"
                elif res.status_code == 401:
                    groq_status["valid"] = False
                    groq_status["message"] = "Authentication Failed: Invalid/Expired Key (401)"
                else:
                    groq_status["valid"] = False
                    groq_status["message"] = f"Groq API returned HTTP {res.status_code}"
        except Exception as e:
            groq_status["valid"] = False
            groq_status["message"] = f"Connection warning: {str(e)[:50]}"

    temp_size_bytes = 0
    temp_files = []
    if TEMP_DIR.exists():
        for p in TEMP_DIR.glob("**/*"):
            if p.is_file() and p.name != ".gitkeep":
                sz = p.stat().st_size
                temp_size_bytes += sz
                temp_files.append({"name": p.name, "size": sz})

    def format_size(bytes_num):
        if bytes_num < 1024:
            return f"{bytes_num} B"
        if bytes_num < 1024 * 1024:
            return f"{round(bytes_num / 1024, 1)} KB"
        return f"{round(bytes_num / (1024 * 1024), 1)} MB"

    cache_status = {
        "size_bytes": temp_size_bytes,
        "size_formatted": format_size(temp_size_bytes),
        "file_count": len(temp_files),
        "has_heavy_cache": temp_size_bytes > (5 * 1024 * 1024)
    }

    encoder = detect_gpu_encoder()
    return {
        "status": "ok",
        "groq": groq_status,
        "cache": cache_status,
        "gpu": encoder,
        "ffmpeg": bool(find_ffmpeg())
    }


@app.post("/api/system/ping-groq")
async def ping_groq(body: dict = None):
    """
    Tests one or all linked Groq API keys against Groq API.
    Measures roundtrip latency in ms and returns individual key health.
    """
    body = body or {}
    key_override = str(body.get("groq_api_key", "")).strip()

    settings = load_settings()
    keys_list = settings.get("groq_api_keys", [])
    primary = settings.get("groq_api_key", "").strip()
    if primary and primary not in keys_list:
        keys_list.insert(0, primary)

    if key_override:
        keys_to_test = [key_override]
    else:
        keys_to_test = list(keys_list) if keys_list else ([primary] if primary else [])

    if not keys_to_test:
        return {
            "success": False,
            "has_valid": False,
            "message": "No Groq API keys configured to ping",
            "results": []
        }

    results = []
    import httpx
    async with httpx.AsyncClient(timeout=7.0) as client:
        for idx, k in enumerate(keys_to_test):
            k_str = str(k).strip()
            if not k_str:
                continue
            masked = f"{k_str[:6]}...{k_str[-4:]}" if len(k_str) > 10 else "***"
            t0 = time.time()
            try:
                res = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {k_str}"}
                )
                lat = int((time.time() - t0) * 1000)
                if res.status_code == 200:
                    results.append({
                        "key_masked": masked,
                        "valid": True,
                        "status_code": 200,
                        "latency_ms": lat,
                        "message": f"Active & Operational ({lat}ms)",
                        "is_primary": (idx == 0)
                    })
                elif res.status_code == 401:
                    results.append({
                        "key_masked": masked,
                        "valid": False,
                        "status_code": 401,
                        "latency_ms": lat,
                        "message": "Invalid or Expired API Key (401 Unauthorized)",
                        "is_primary": (idx == 0)
                    })
                else:
                    results.append({
                        "key_masked": masked,
                        "valid": False,
                        "status_code": res.status_code,
                        "latency_ms": lat,
                        "message": f"HTTP {res.status_code}",
                        "is_primary": (idx == 0)
                    })
            except Exception as e:
                lat = int((time.time() - t0) * 1000)
                results.append({
                    "key_masked": masked,
                    "valid": False,
                    "status_code": 0,
                    "latency_ms": lat,
                    "message": f"Connection error: {str(e)[:50]}",
                    "is_primary": (idx == 0)
                })

    has_valid = any(r["valid"] for r in results)
    best_lat = min([r["latency_ms"] for r in results if r["valid"]], default=0)

    # If key_override tested valid, save it as primary
    if key_override and has_valid:
        settings["groq_api_key"] = key_override
        save_settings(settings)

    return {
        "success": True,
        "has_valid": has_valid,
        "results": results,
        "best_latency_ms": best_lat,
        "active_key_masked": results[0]["key_masked"] if results else "",
        "message": f"Ping passed: {best_lat}ms latency" if has_valid else "Ping test failed: No working API key"
    }


@app.post("/api/system/clean-cache")
async def clean_system_cache():
    freed_bytes = 0
    removed_count = 0
    if TEMP_DIR.exists():
        for p in list(TEMP_DIR.glob("**/*")):
            if p.is_file() and p.name != ".gitkeep":
                try:
                    freed_bytes += p.stat().st_size
                    p.unlink(missing_ok=True)
                    removed_count += 1
                except Exception:
                    pass

    def format_size(bytes_num):
        if bytes_num < 1024:
            return f"{bytes_num} B"
        if bytes_num < 1024 * 1024:
            return f"{round(bytes_num / 1024, 1)} KB"
        return f"{round(bytes_num / (1024 * 1024), 1)} MB"

    return {
        "success": True,
        "freed_bytes": freed_bytes,
        "freed_formatted": format_size(freed_bytes),
        "removed_files": removed_count,
        "remaining_bytes": 0,
        "message": f"Successfully cleaned {removed_count} temporary files ({format_size(freed_bytes)} freed)"
    }


@app.post("/api/system/update-groq-key")
async def update_groq_key(body: dict):
    key = str(body.get("groq_api_key", "")).strip()
    if not key:
        return {"success": False, "valid": False, "message": "API key cannot be empty"}

    is_valid = False
    err_msg = ""
    lat = 0
    try:
        import httpx
        t0 = time.time()
        async with httpx.AsyncClient(timeout=6.0) as client:
            res = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"}
            )
            lat = int((time.time() - t0) * 1000)
            if res.status_code == 200:
                is_valid = True
            elif res.status_code == 401:
                return {"success": False, "valid": False, "message": "Authentication failed: Invalid Groq API key (401)"}
            else:
                err_msg = f"Groq API returned HTTP {res.status_code}"
    except Exception as e:
        err_msg = f"Network connection warning: {e}"

    # Save to settings
    settings = load_settings()
    settings["groq_api_key"] = key
    save_settings(settings)

    masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
    if is_valid:
        return {
            "success": True,
            "valid": True,
            "masked_key": masked,
            "latency_ms": lat,
            "message": f"✅ Groq API Key verified and saved successfully ({lat}ms)!"
        }
    else:
        return {
            "success": True,
            "valid": False,
            "masked_key": masked,
            "latency_ms": lat,
            "message": f"Saved, but validation note: {err_msg or 'Verification unconfirmed'}"
        }


# ── Background Pre-Transcription Engine ───────────────────────────────────────
@app.post("/api/pre-transcribe")
async def pre_transcribe(body: dict):
    """
    Kicks off background transcription of voiceover as soon as it is selected,
    eliminating transcription waiting during final render.
    """
    audio_path = str(body.get("audio_path", "")).strip()
    niche = str(body.get("niche", "Stoicism & Philosophy")).strip()

    if not audio_path or not Path(audio_path).exists():
        return {"success": False, "error": "Voiceover audio file not found"}

    with _TRANSCRIPTION_LOCK:
        if audio_path in _TRANSCRIPTION_CACHE:
            return {
                "success": True,
                "status": "ready",
                "cached": True,
                "segments_count": len(_TRANSCRIPTION_CACHE[audio_path].get("segments", []))
            }

        if audio_path in _TRANSCRIPTION_TASKS and _TRANSCRIPTION_TASKS[audio_path].get("status") == "running":
            return {"success": True, "status": "running"}

        def _worker():
            try:
                from .transcriber import transcribe_audio
                print(f"[PreTranscribe] 🚀 Starting background pre-transcription for {Path(audio_path).name}...")
                res = transcribe_audio(audio_path, niche=niche)
                with _TRANSCRIPTION_LOCK:
                    _TRANSCRIPTION_CACHE[audio_path] = res
                    if audio_path in _TRANSCRIPTION_TASKS:
                        _TRANSCRIPTION_TASKS[audio_path]["status"] = "ready"
                        _TRANSCRIPTION_TASKS[audio_path]["segments_count"] = len(res.get("segments", []))
                print(f"[PreTranscribe] ✅ Pre-transcription cached for {Path(audio_path).name} ({len(res.get('segments', []))} segments)")
            except Exception as err:
                print(f"[PreTranscribe] ⚠️ Background pre-transcription failed: {err}")
                with _TRANSCRIPTION_LOCK:
                    if audio_path in _TRANSCRIPTION_TASKS:
                        _TRANSCRIPTION_TASKS[audio_path]["status"] = "failed"
                        _TRANSCRIPTION_TASKS[audio_path]["error"] = str(err)

        th = threading.Thread(target=_worker, daemon=True)
        _TRANSCRIPTION_TASKS[audio_path] = {
            "status": "running",
            "thread": th,
            "started_at": time.time()
        }
        th.start()

    return {"success": True, "status": "started"}


@app.get("/api/pre-transcribe-status")
async def pre_transcribe_status(audio_path: str = ""):
    """Returns background pre-transcription progress/status for an audio file."""
    audio_path = audio_path.strip()
    if not audio_path:
        return {"status": "idle"}

    with _TRANSCRIPTION_LOCK:
        if audio_path in _TRANSCRIPTION_CACHE:
            return {
                "status": "ready",
                "cached": True,
                "segments_count": len(_TRANSCRIPTION_CACHE[audio_path].get("segments", []))
            }
        if audio_path in _TRANSCRIPTION_TASKS:
            task = _TRANSCRIPTION_TASKS[audio_path]
            return {
                "status": task.get("status", "running"),
                "error": task.get("error", ""),
                "elapsed": round(time.time() - task.get("started_at", time.time()), 1)
            }
    return {"status": "idle"}


# ── GPU Info ───────────────────────────────────────────────────────────────────
@app.get("/api/gpu-info")
async def gpu_info():
    try:
        encoder = detect_gpu_encoder(force_probe=True)
        params  = get_encoder_params(encoder)
        return {
            "encoder":      encoder,
            "codec":        params["codec"],
            "preset":       params["preset"],
            "gpu_detected": encoder != "libx264"
        }
    except Exception as e:
        return {"encoder": "libx264", "error": str(e)}


# ── Visualizer Presets ────────────────────────────────────────────────────────
@app.get("/api/visualizer-presets")
async def get_visualizer_presets():
    try:
        from .visualizer_generator import VISUALIZER_PRESETS
        return {"success": True, "presets": list(VISUALIZER_PRESETS.values())}
    except Exception as e:
        return {"success": False, "error": str(e), "presets": []}


# ── B-Roll Folder Scan & Browse ────────────────────────────────────────────────
def _show_native_folder_dialog(initial_dir: str = "") -> str:
    """Opens a native Windows folder browser dialog."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(
            title="Select B-Roll Video Folder",
            initialdir=initial_dir or str(Path.home())
        )
        root.destroy()
        if folder:
            return folder
    except Exception:
        pass

    try:
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$f.Description = 'Select B-Roll Video Folder'; "
            "$f.ShowNewFolderButton = $false; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
            "  Write-Output $f.SelectedPath "
            "}"
        )
        res = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps_script], capture_output=True, text=True, timeout=30)
        return res.stdout.strip()
    except Exception as e:
        print(f"[Server] Folder dialog error: {e}")
        return ""


@app.post("/api/browse-folder")
async def browse_folder():
    """Triggers native Windows folder picker dialog and returns stats asynchronously."""
    folder = await asyncio.to_thread(_show_native_folder_dialog)
    if not folder:
        return {"success": False, "cancelled": True}
    try:
        from .local_pool import get_folder_stats
        stats = await asyncio.to_thread(get_folder_stats, folder)
        return {"success": True, "folder_path": folder, "stats": stats}
    except Exception as e:
        return {"success": True, "folder_path": folder, "error": str(e)}


@app.post("/api/scan-folder")
async def scan_folder(body: dict):
    folder = body.get("folder_path", "").strip()
    if not folder:
        raise HTTPException(400, "folder_path is required")
    try:
        from .local_pool import get_folder_stats
        stats = await asyncio.to_thread(get_folder_stats, folder)
        return stats
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Avatar Upload ──────────────────────────────────────────────────────────────
@app.post("/api/upload-avatar")
async def upload_avatar(file: UploadFile = File(...)):
    try:
        ext  = Path(file.filename).suffix.lower() or ".png"
        dest = AVATARS_DIR / f"avatar_{uuid.uuid4().hex[:8]}{ext}"

        def _save():
            with open(str(dest), "wb") as f:
                shutil.copyfileobj(file.file, f)
            return dest.stat().st_size

        size = await asyncio.to_thread(_save)
        return {
            "success":    True,
            "path":       str(dest),
            "url":        f"/avatars/{dest.name}",
            "filename":   dest.name,
            "size_bytes": size
        }
    except Exception as e:
        raise HTTPException(500, f"Avatar upload failed: {e}")


# ── Voiceover Upload ───────────────────────────────────────────────────────────
@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    try:
        ext  = Path(file.filename).suffix.lower() or ".mp3"
        dest = TEMP_DIR / f"voiceover_{uuid.uuid4().hex[:8]}{ext}"

        def _save_and_probe():
            with open(str(dest), "wb") as f:
                shutil.copyfileobj(file.file, f)
            from .transcriber import get_audio_duration
            return get_audio_duration(str(dest))

        duration = await asyncio.to_thread(_save_and_probe)

        return {
            "success":      True,
            "path":         str(dest),
            "url":          f"/temp/{dest.name}",
            "filename":     dest.name,
            "duration":     round(duration, 2),
            "duration_min": round(duration / 60, 2),
        }
    except Exception as e:
        raise HTTPException(500, f"Audio upload failed: {e}")


# ── Background Music / Ambience Upload ─────────────────────────────────────────
@app.post("/api/upload-bgm")
async def upload_bgm(file: UploadFile = File(...)):
    """Uploads an optional background music/ambience audio file asynchronously."""
    try:
        ext  = Path(file.filename).suffix.lower() or ".mp3"
        dest = TEMP_DIR / f"bgm_{uuid.uuid4().hex[:8]}{ext}"

        def _save_and_probe():
            with open(str(dest), "wb") as f:
                shutil.copyfileobj(file.file, f)
            from .transcriber import get_audio_duration
            return get_audio_duration(str(dest))

        duration = await asyncio.to_thread(_save_and_probe)

        return {
            "success":      True,
            "path":         str(dest),
            "url":          f"/temp/{dest.name}",
            "filename":     dest.name,
            "duration":     round(duration, 2),
            "duration_min": round(duration / 60, 2),
        }
    except Exception as e:
        raise HTTPException(500, f"Background music upload failed: {e}")


# ── Custom Visualizer Green-Screen Video Upload ───────────────────────────────
@app.post("/api/upload-vis-video")
async def upload_vis_video(file: UploadFile = File(...)):
    """Uploads a user-supplied green-screen visualizer / soundwave animation video."""
    try:
        ext  = Path(file.filename).suffix.lower() or ".mp4"
        dest = TEMP_DIR / f"vis_video_{uuid.uuid4().hex[:8]}{ext}"

        def _save_and_probe():
            with open(str(dest), "wb") as f:
                shutil.copyfileobj(file.file, f)
            from .local_pool import probe_clip_info
            return probe_clip_info(str(dest))

        info = await asyncio.to_thread(_save_and_probe)

        return {
            "success":    True,
            "path":       str(dest),
            "url":        f"/temp/{dest.name}",
            "filename":   dest.name,
            "duration":   round(info.get("duration", 0), 2),
            "width":      info.get("width", 640),
            "height":     info.get("height", 360),
            "size_bytes": dest.stat().st_size
        }
    except Exception as e:
        raise HTTPException(500, f"Visualizer video upload failed: {e}")


# ── Extract Sample B-Roll Frame for Live Studio Canvas ─────────────────────────
@app.post("/api/sample-broll-frame")
async def sample_broll_frame(body: dict):
    """
    Extracts a 1080p preview frame from the first clip in the given B-Roll folder.
    Executed in a background worker thread to prevent event loop stutter.
    """
    import time
    folder = body.get("folder_path", "").strip()
    if not folder or not Path(folder).exists():
        return {"success": False, "error": "Folder not found"}

    def _extract():
        from .local_pool import scan_folder
        from .config import find_ffmpeg
        clips = scan_folder(folder)
        if not clips:
            return {"success": False, "error": "No clips found in folder"}
        first_clip = clips[0]
        out_frame = TEMP_DIR / "broll_preview_frame.jpg"
        ffmpeg = find_ffmpeg()
        cmd = [
            ffmpeg, "-y",
            "-ss", "00:00:01",
            "-i", first_clip,
            "-vframes", "1",
            "-q:v", "2",
            str(out_frame)
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
        if out_frame.exists():
            return {"success": True, "url": f"/temp/broll_preview_frame.jpg?t={int(time.time())}"}
        return {"success": False, "error": "Could not extract frame"}

    try:
        res = await asyncio.to_thread(_extract)
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Preview Clip Selection ─────────────────────────────────────────────────────
@app.post("/api/preview-clips")
async def preview_clips(body: dict):
    """
    Returns clip selection plan without probing all durations.
    Runs asynchronously in thread pool.
    """
    folder         = body.get("folder_path", "").strip()
    audio_duration = float(body.get("audio_duration", 120))
    speed          = float(body.get("stock_speed", 0.75))
    pacing_mode    = body.get("pacing_mode", "full")
    min_clip_sec   = float(body.get("min_clip_sec", 5.0))
    max_clip_sec   = float(body.get("max_clip_sec", 9.0))

    if not folder:
        raise HTTPException(400, "folder_path required")

    def _calc():
        from .local_pool import get_folder_stats
        stats = get_folder_stats(folder)
        if not stats.get("success"):
            return stats

        is_fast_cuts = (str(pacing_mode).lower() in ("fast_cuts", "dynamic", "fair_use"))
        if is_fast_cuts:
            avg_raw_dur = max(2.0, (min_clip_sec + max_clip_sec) / 2.0)
        else:
            avg_raw_dur = stats.get("estimated_avg_duration_sec", 45.0)

        avg_eff_dur     = avg_raw_dur / max(0.1, speed)
        clips_needed    = max(1, int(audio_duration / avg_eff_dur) + 1)

        return {
            "success":            True,
            "folder_clip_count":  stats["clip_count"],
            "clips_needed":       clips_needed,
            "audio_duration":     audio_duration,
            "stock_speed":        speed,
            "pacing_mode":        "fast_cuts" if is_fast_cuts else "full",
            "estimated_avg_clip": round(avg_eff_dur, 1),
            "will_wrap_pool":     clips_needed > stats["clip_count"],
        }

    try:
        res = await asyncio.to_thread(_calc)
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Render Job ─────────────────────────────────────────────────────────────────
@app.post("/api/render")
async def start_render(body: dict, background_tasks: BackgroundTasks):
    """
    Starts a full avatar video render job.
    
    Required body fields:
        voiceover_path:    Path to uploaded voiceover audio
        broll_folder:      Path to local B-Roll folder
        avatar_path:       Path to uploaded avatar image
    
    Optional body fields:
        avatar_position:   'left' | 'center' | 'right'  (default: right)
        stroke_color:      'white' | 'gold' | 'cyan' | 'none'
        stroke_width:      int (default: 10)
        blur_radius:       int 0-30  (default: 12)
        dark_tint:         float 0-0.8 (default: 0.25)
        stock_speed:       float 0.5-1.0 (default: 0.75)
        pitch_semitones:   float -4 to +4 (default: 0)
        voice_speed:       float 0.8-1.25 (default: 1.0)
        caption_preset:    string (default: capcut_yellow)
        output_filename:   string (optional)
    """
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "job_id":  job_id,
        "status":  "queued",
        "message": "Job queued — starting render pipeline...",
        "percent": 0,
    }
    background_tasks.add_task(_run_render_pipeline, job_id, body)
    return {"job_id": job_id, "status": "queued"}


async def _run_render_pipeline(job_id: str, params: dict):
    """Full pipeline: DSP → Scan Clips → Process Avatar → Transcribe → Subtitles → Render"""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_render_pipeline_sync, job_id, params)


def _run_render_pipeline_sync(job_id: str, params: dict):
    try:
        _update_job(job_id, {"status": "running", "percent": 2, "message": "Initializing render pipeline..."})

        voiceover_path  = params.get("voiceover_path", "")
        broll_folder    = params.get("broll_folder", "")
        avatar_path     = params.get("avatar_path", "")

        if not voiceover_path or not Path(voiceover_path).exists():
            raise ValueError("Voiceover audio file not found.")
        if not broll_folder or not Path(broll_folder).exists():
            raise ValueError("B-Roll folder not found.")
        if not avatar_path or not Path(avatar_path).exists():
            raise ValueError("Avatar image not found.")

        avatar_position  = params.get("avatar_position", "right")
        avatar_size      = int(params.get("avatar_size", 920))
        flip_horizontal  = bool(params.get("flip_horizontal", False))
        stroke_color     = params.get("stroke_color",   "white")
        stroke_width     = int(params.get("stroke_width",    10))
        blur_radius      = int(params.get("blur_radius",     0))   # Default 0 (Crystal clear / Off)
        dark_tint        = float(params.get("dark_tint",     0.25))
        stock_speed      = float(params.get("stock_speed",   0.75))
        pitch_semitones  = float(params.get("pitch_semitones", 0.0))
        voice_speed      = float(params.get("voice_speed",    1.0))
        caption_preset   = params.get("caption_preset", "capcut_yellow")
        caption_position = params.get("caption_position", "center")  # Default: Dead Center
        caption_size     = params.get("caption_size", "large")       # Default: Large 68pt
        niche            = params.get("niche", "Stoicism & Philosophy")
        visualizer_enabled  = bool(params.get("visualizer_enabled", False))
        visualizer_style    = str(params.get("visualizer_style", "glass_pill_cyan"))
        visualizer_position = str(params.get("visualizer_position", "top_center"))
        visualizer_title    = str(params.get("visualizer_title", "")).strip() or niche
        visualizer_subtitle = str(params.get("visualizer_subtitle", "Audio Story Series")).strip()

        # Custom coordinates & scaling from Studio Canvas Stage
        avatar_opacity      = float(params.get("avatar_opacity", 1.0))
        avatar_custom_x     = params.get("avatar_custom_x")
        avatar_custom_y     = params.get("avatar_custom_y")
        caption_box         = params.get("caption_box")
        visualizer_custom_x = params.get("visualizer_custom_x")
        visualizer_custom_y = params.get("visualizer_custom_y")
        visualizer_scale    = float(params.get("visualizer_scale", 1.0))

        # Custom Green-Screen Video Visualizer Settings
        custom_vis_video_path = params.get("custom_vis_video_path")
        visualizer_mode       = str(params.get("visualizer_mode", "template"))
        if custom_vis_video_path and Path(custom_vis_video_path).exists():
            visualizer_mode = "video"
        chroma_key_color      = str(params.get("chroma_key_color", "#00FF00"))
        chroma_similarity     = float(params.get("chroma_similarity", 0.25))
        chroma_blend          = float(params.get("chroma_blend", 0.08))
        visualizer_width      = params.get("visualizer_width")
        visualizer_height     = params.get("visualizer_height")

        # ─ Step 1: Audio DSP ─────────────────────────────────────────────────
        _update_job(job_id, {"percent": 8, "message": "Processing voiceover audio (pitch/speed DSP)..."})
        from .audio_dsp import process_voiceover_audio, get_audio_duration

        needs_dsp = abs(pitch_semitones) > 0.05 or abs(voice_speed - 1.0) > 0.02
        if needs_dsp:
            processed_audio = str(TEMP_DIR / f"{job_id}_processed.mp3")
            process_voiceover_audio(
                input_audio=voiceover_path,
                output_audio=processed_audio,
                pitch_semitones=pitch_semitones,
                speed_rate=voice_speed
            )
        else:
            processed_audio = voiceover_path
            print("[Server] No DSP needed — using original audio")

        audio_duration = get_audio_duration(processed_audio)
        _update_job(job_id, {"percent": 15, "message": f"Audio ready. Duration: {audio_duration:.1f}s"})

        # ─ Step 2: Select B-Roll Clips ────────────────────────────────────────
        _update_job(job_id, {"percent": 20, "message": "Scanning B-Roll folder and selecting clips..."})
        from .local_pool import select_local_clips
        broll_pacing_mode = params.get("broll_pacing_mode", "full")
        broll_min_sec     = float(params.get("broll_min_sec", 5.0))
        broll_max_sec     = float(params.get("broll_max_sec", 9.0))
        pool_result = select_local_clips(
            folder_path=broll_folder,
            target_duration_sec=audio_duration,
            speed_multiplier=stock_speed,
            pacing_mode=broll_pacing_mode,
            min_clip_sec=broll_min_sec,
            max_clip_sec=broll_max_sec
        )
        clips = pool_result["clips"]
        _update_job(job_id, {
            "percent": 35,
            "message": f"Selected {len(clips)} clips ({pool_result['total_effective']:.0f}s effective duration, pacing: {pool_result.get('pacing_mode', 'full')})"
        })

        # ─ Step 3: Process Avatar ─────────────────────────────────────────────
        _update_job(job_id, {"percent": 40, "message": "Processing avatar image (stroke + flip + resize)..."})
        from .avatar_processor import process_avatar
        avatar_result = process_avatar(
            input_image_path=avatar_path,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            target_height=avatar_size,
            output_dir=str(TEMP_DIR / job_id),
            flip_horizontal=flip_horizontal
        )
        processed_avatar_path = avatar_result["path"]
        _update_job(job_id, {"percent": 48, "message": f"Avatar ready: {avatar_result['width']}×{avatar_result['height']}px"})

        # ─ Step 4: Transcribe Audio → Subtitles ──────────────────────────────
        _update_job(job_id, {"percent": 52, "message": "Transcribing voiceover (Groq Whisper)..."})
        from .transcriber import transcribe_audio

        def on_transcribe_progress(msg: str, pct_delta: int = 0):
            _update_job(job_id, {"percent": min(65, 52 + pct_delta), "message": msg})

        transcript = None
        with _TRANSCRIPTION_LOCK:
            if processed_audio in _TRANSCRIPTION_CACHE:
                print(f"[Server] ⚡ Instant Cache Hit: Voiceover already pre-transcribed for {Path(processed_audio).name} (0s wait)!")
                _update_job(job_id, {"percent": 63, "message": "Instant Cache Hit: Voiceover already pre-transcribed!"})
                transcript = _TRANSCRIPTION_CACHE[processed_audio]

        if not transcript and processed_audio in _TRANSCRIPTION_TASKS:
            task_info = _TRANSCRIPTION_TASKS[processed_audio]
            if task_info.get("status") == "running":
                _update_job(job_id, {"percent": 55, "message": "Awaiting background pre-transcription completion..."})
                th = task_info.get("thread")
                if th and th.is_alive():
                    th.join(timeout=300)
                with _TRANSCRIPTION_LOCK:
                    transcript = _TRANSCRIPTION_CACHE.get(processed_audio)

        if not transcript:
            transcript = transcribe_audio(processed_audio, niche=niche, progress_callback=on_transcribe_progress)
            with _TRANSCRIPTION_LOCK:
                _TRANSCRIPTION_CACHE[processed_audio] = transcript

        scenes = transcript.get("segments", [])
        _update_job(job_id, {"percent": 65, "message": f"Transcribed {len(scenes)} segments. Generating adaptive subtitles..."})

        # ─ Step 5: Generate Adaptive Subtitles ───────────────────────────────
        ass_path = str(TEMP_DIR / f"{job_id}_subs.ass")
        try:
            from .adaptive_subtitles import generate_adaptive_subtitles
            generate_adaptive_subtitles(
                scenes=scenes,
                output_path=ass_path,
                avatar_position=avatar_position,
                preset_key=caption_preset,
                caption_position=caption_position,
                caption_size=caption_size,
                caption_box=caption_box
            )
        except Exception as sub_err:
            print(f"[Server] ⚠️ Subtitle generation failed: {sub_err} — continuing without subtitles")
            # Write an empty ASS file so FFmpeg doesn't error on the subtitle filter
            with open(ass_path, "w", encoding="utf-8") as _f:
                _f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        # Mix background music if provided
        bg_audio_path   = params.get("bg_audio_path")
        bg_music_volume = float(params.get("bg_music_volume", 0.07))
        final_render_audio = processed_audio
        if bg_audio_path and str(bg_audio_path).strip() and Path(bg_audio_path).exists():
            _update_job(job_id, {"percent": 70, "message": f"Blending background ambience ({bg_music_volume*100:.0f}% volume)..."})
            try:
                from .audio_dsp import mix_voiceover_and_bgm
                mixed_audio = str(TEMP_DIR / f"{job_id}_voice_bgm.mp3")
                final_render_audio = mix_voiceover_and_bgm(
                    voiceover_path=processed_audio,
                    bgm_path=bg_audio_path,
                    output_path=mixed_audio,
                    bgm_volume=bg_music_volume
                )
            except Exception as bgm_err:
                print(f"[Server] ⚠️ BGM mix failed: {bgm_err} — proceeding with pure voiceover")
                final_render_audio = processed_audio

        _update_job(job_id, {"percent": 72, "message": "Subtitles generated. Starting GPU render..."})

        # ─ Step 6: Single-Pass GPU Render ────────────────────────────────────
        output_filename = params.get("output_filename") or f"avatar_story_{job_id[:8]}.mp4"
        output_path = str(OUTPUT_DIR / output_filename)

        from .fast_renderer import render_avatar_video

        def on_progress(data: dict):
            _update_job(job_id, {
                "percent": data.get("percent", 72),
                "message": data.get("message", "Rendering..."),
                "status":  data.get("status", "running"),
            })

        render_avatar_video(
            voiceover_path=final_render_audio,
            clips=clips,
            avatar_path=processed_avatar_path,
            ass_subtitle_path=ass_path,
            output_path=output_path,
            blur_radius=blur_radius,
            dark_tint=dark_tint,
            speed_multiplier=stock_speed,
            avatar_position=avatar_position,
            progress_callback=on_progress,
            visualizer_enabled=visualizer_enabled,
            visualizer_style=visualizer_style,
            visualizer_position=visualizer_position,
            visualizer_title=visualizer_title,
            visualizer_subtitle=visualizer_subtitle,
            avatar_opacity=avatar_opacity,
            avatar_custom_x=avatar_custom_x,
            avatar_custom_y=avatar_custom_y,
            visualizer_custom_x=visualizer_custom_x,
            visualizer_custom_y=visualizer_custom_y,
            visualizer_scale=visualizer_scale,
            visualizer_mode=visualizer_mode,
            custom_vis_video_path=custom_vis_video_path,
            chroma_key_color=chroma_key_color,
            chroma_similarity=chroma_similarity,
            chroma_blend=chroma_blend,
            visualizer_width=visualizer_width,
            visualizer_height=visualizer_height
        )

        # ─ Done ───────────────────────────────────────────────────────────────
        output_size_mb = Path(output_path).stat().st_size / (1024 * 1024) if Path(output_path).exists() else 0
        _update_job(job_id, {
            "status":    "complete",
            "percent":   100,
            "message":   f"✅ Video rendered successfully! ({output_size_mb:.1f} MB)",
            "output":    output_path,
            "size_mb":   round(output_size_mb, 1),
            "clips_used": len(clips),
            "duration":   round(audio_duration, 1),
        })

        # Auto-open output folder and highlight output video in Windows Explorer
        try:
            if os.name == "nt" and Path(output_path).exists():
                subprocess.Popen(f'explorer /select,"{output_path}"')
                print(f"[Server] 📂 Auto-opened explorer with output file highlighted")
        except Exception as ex:
            print(f"[Server] Auto-open folder warning: {ex}")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Server] Render job {job_id} FAILED:\n{tb}")
        _update_job(job_id, {
            "status":  "error",
            "percent": 0,
            "message": f"❌ Error: {e}",
            "error":   str(e),
            "traceback": tb
        })


# ── Job Status ─────────────────────────────────────────────────────────────────
@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    return _jobs[job_id]


@app.get("/api/jobs")
async def list_jobs():
    return list(_jobs.values())


# ── Output Files ───────────────────────────────────────────────────────────────
@app.get("/api/outputs")
async def list_outputs():
    files = []
    for f in OUTPUT_DIR.glob("*.mp4"):
        stat = f.stat()
        files.append({
            "name":      f.name,
            "path":      str(f),
            "size_mb":   round(stat.st_size / (1024 * 1024), 1),
            "created":   stat.st_ctime,
        })
    files.sort(key=lambda x: x["created"], reverse=True)
    return files


@app.get("/api/download/{filename}")
async def download_output(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path), media_type="video/mp4", filename=filename)


@app.post("/api/open-output-folder")
async def open_output_folder():
    """Opens the output folder in Windows Explorer."""
    try:
        os.startfile(str(OUTPUT_DIR))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Caption Presets ────────────────────────────────────────────────────────────
@app.get("/api/caption-presets")
async def get_caption_presets():
    from .adaptive_subtitles import get_available_presets
    return get_available_presets()
