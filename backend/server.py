"""
Avatar Storyteller Video Engine — FastAPI Backend Server
All API endpoints for the desktop app UI.
"""
import os
import uuid
import asyncio
import json
import shutil
import traceback
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    load_settings, save_settings, TEMP_DIR, OUTPUT_DIR,
    AVATARS_DIR, FRONTEND_DIR, detect_gpu_encoder, get_encoder_params
)

app = FastAPI(title="Avatar Storyteller Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Job Progress Store ─────────────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}


def _update_job(job_id: str, data: dict):
    if job_id in _jobs:
        _jobs[job_id].update(data)


# ── Static Frontend ────────────────────────────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


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


# ── B-Roll Folder Scan ─────────────────────────────────────────────────────────
@app.post("/api/scan-folder")
async def scan_folder(body: dict):
    folder = body.get("folder_path", "").strip()
    if not folder:
        raise HTTPException(400, "folder_path is required")
    try:
        from .local_pool import get_folder_stats
        stats = get_folder_stats(folder)
        return stats
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Avatar Upload ──────────────────────────────────────────────────────────────
@app.post("/api/upload-avatar")
async def upload_avatar(file: UploadFile = File(...)):
    try:
        ext     = Path(file.filename).suffix.lower() or ".png"
        dest    = AVATARS_DIR / f"avatar_{uuid.uuid4().hex[:8]}{ext}"
        with open(str(dest), "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {
            "success":   True,
            "path":      str(dest),
            "filename":  dest.name,
            "size_bytes": dest.stat().st_size
        }
    except Exception as e:
        raise HTTPException(500, f"Avatar upload failed: {e}")


# ── Voiceover Upload ───────────────────────────────────────────────────────────
@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    try:
        ext  = Path(file.filename).suffix.lower() or ".mp3"
        dest = TEMP_DIR / f"voiceover_{uuid.uuid4().hex[:8]}{ext}"
        with open(str(dest), "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Get duration
        from .transcriber import get_audio_duration
        duration = get_audio_duration(str(dest))

        return {
            "success":  True,
            "path":     str(dest),
            "filename": dest.name,
            "duration": round(duration, 2),
            "duration_min": round(duration / 60, 2),
        }
    except Exception as e:
        raise HTTPException(500, f"Audio upload failed: {e}")


# ── Preview Clip Selection ─────────────────────────────────────────────────────
@app.post("/api/preview-clips")
async def preview_clips(body: dict):
    """
    Returns clip selection plan without actually running ffprobe on all clips.
    Uses folder stats + estimates for fast UI feedback.
    """
    folder         = body.get("folder_path", "").strip()
    audio_duration = float(body.get("audio_duration", 120))
    speed          = float(body.get("stock_speed", 0.75))

    if not folder:
        raise HTTPException(400, "folder_path required")

    try:
        from .local_pool import get_folder_stats, scan_folder
        stats = get_folder_stats(folder)
        if not stats.get("success"):
            return stats

        avg_raw_dur     = stats.get("estimated_avg_duration_sec", 45.0)
        avg_eff_dur     = avg_raw_dur / max(0.1, speed)
        clips_needed    = max(1, int(audio_duration / avg_eff_dur) + 1)

        return {
            "success":            True,
            "folder_clip_count":  stats["clip_count"],
            "clips_needed":       clips_needed,
            "audio_duration":     audio_duration,
            "stock_speed":        speed,
            "estimated_avg_clip": round(avg_eff_dur, 1),
            "will_wrap_pool":     clips_needed > stats["clip_count"],
        }
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

        avatar_position = params.get("avatar_position", "right")
        stroke_color    = params.get("stroke_color",   "white")
        stroke_width    = int(params.get("stroke_width",    10))
        blur_radius     = int(params.get("blur_radius",     12))
        dark_tint       = float(params.get("dark_tint",     0.25))
        stock_speed     = float(params.get("stock_speed",   0.75))
        pitch_semitones = float(params.get("pitch_semitones", 0.0))
        voice_speed     = float(params.get("voice_speed",    1.0))
        caption_preset  = params.get("caption_preset", "capcut_yellow")
        niche           = params.get("niche", "Stoicism & Philosophy")

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
        pool_result = select_local_clips(
            folder_path=broll_folder,
            target_duration_sec=audio_duration,
            speed_multiplier=stock_speed
        )
        clips = pool_result["clips"]
        _update_job(job_id, {
            "percent": 35,
            "message": f"Selected {len(clips)} clips ({pool_result['total_effective']:.0f}s effective duration)"
        })

        # ─ Step 3: Process Avatar ─────────────────────────────────────────────
        _update_job(job_id, {"percent": 40, "message": "Processing avatar image (stroke + resize)..."})
        from .avatar_processor import process_avatar
        avatar_result = process_avatar(
            input_image_path=avatar_path,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            output_dir=str(TEMP_DIR / job_id)
        )
        processed_avatar_path = avatar_result["path"]
        _update_job(job_id, {"percent": 48, "message": f"Avatar ready: {avatar_result['width']}×{avatar_result['height']}px"})

        # ─ Step 4: Transcribe Audio → Subtitles ──────────────────────────────
        _update_job(job_id, {"percent": 52, "message": "Transcribing voiceover (Groq Whisper)..."})
        from .transcriber import transcribe_audio
        transcript = transcribe_audio(processed_audio, niche=niche)
        scenes     = transcript.get("segments", [])
        _update_job(job_id, {"percent": 65, "message": f"Transcribed {len(scenes)} segments. Generating adaptive subtitles..."})

        # ─ Step 5: Generate Adaptive Subtitles ───────────────────────────────
        ass_path = str(TEMP_DIR / f"{job_id}_subs.ass")
        from .adaptive_subtitles import generate_adaptive_subtitles
        generate_adaptive_subtitles(
            scenes=scenes,
            output_path=ass_path,
            avatar_position=avatar_position,
            preset_key=caption_preset
        )
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
            voiceover_path=processed_audio,
            clips=clips,
            avatar_path=processed_avatar_path,
            ass_subtitle_path=ass_path,
            output_path=output_path,
            blur_radius=blur_radius,
            dark_tint=dark_tint,
            speed_multiplier=stock_speed,
            avatar_position=avatar_position,
            progress_callback=on_progress
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
