"""
Avatar Storyteller Video Engine — Local B-Roll Pool Engine
Scans a local folder for video clips, shuffles randomly without repeating any clip,
accounts for slow-motion speed multiplier, and accumulates clips matching target duration.

Key Design:
- Strictly ZERO clip repeats within one video session
- speed_multiplier < 1.0  ➜  clips appear longer on screen (effective_dur = raw_dur / speed)
- If folder exhausted before duration is met, pool wraps with re-shuffle (with warning)
- Uses ffprobe for accurate duration reading (no mutagen dependency)
"""
import os
import time
import random
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from .config import find_ffprobe


VALID_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def get_clip_duration(clip_path: str) -> float:
    """
    Returns accurate duration of a video clip in seconds using ffprobe.
    Falls back to 30.0 seconds on any error (conservative estimate).
    """
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(clip_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        val = res.stdout.strip()
        if val and val.lower() not in ("n/a", ""):
            return max(0.5, float(val))
    except Exception as e:
        print(f"[LocalPool] ffprobe error for {clip_path}: {e}")
    return 30.0


def probe_clip_info(clip_path: str) -> Dict[str, Any]:
    """
    Returns media information: width, height, duration, has_audio.
    """
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "stream=width,height,codec_type",
        "-show_entries", "format=duration",
        "-of", "json",
        str(clip_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(res.stdout) if res.stdout else {}
        dur = float(data.get("format", {}).get("duration", 30.0))
        streams = data.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video" and s.get("width")]
        w = int(video_streams[0]["width"]) if video_streams else 1920
        h = int(video_streams[0]["height"]) if video_streams else 1080
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        is_pure_video = len(streams) == 1 and bool(video_streams)
        return {
            "duration": max(0.5, dur),
            "width": w,
            "height": h,
            "is_landscape": w >= h,
            "has_audio": has_audio,
            "is_pure_video": is_pure_video
        }
    except Exception as e:
        print(f"[LocalPool] probe error for {clip_path}: {e}")
        return {"duration": 30.0, "width": 1920, "height": 1080, "is_landscape": True, "has_audio": False, "is_pure_video": True}


# In-memory scan cache: folder_path -> (timestamp, list_of_clip_paths)
_FOLDER_CACHE: Dict[str, Tuple[float, List[str]]] = {}


def scan_folder(folder_path: str, landscape_only: bool = True, force_refresh: bool = False) -> List[str]:
    """
    Ultra-fast recursive scan of a folder for valid video clip files.
    Skips hidden/system directories ($RECYCLE.BIN, .git, temp) and caches results
    for 5 minutes to prevent UI freezes when browsing or selecting clips.
    """
    folder_str = str(folder_path).strip().strip('"').strip("'")
    if not folder_str:
        raise FileNotFoundError("Folder path cannot be empty")

    folder = Path(folder_str).resolve()
    folder_key = str(folder)
    now = time.time()

    # Return cached results if fresh (< 300s)
    if not force_refresh and folder_key in _FOLDER_CACHE:
        cached_time, cached_clips = _FOLDER_CACHE[folder_key]
        if now - cached_time < 300:
            return cached_clips

    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"B-Roll folder not found: {folder_path}")

    clips = []
    # Directories to strictly skip for instant traversal
    SKIP_DIRS = {"$recycle.bin", "system volume information", ".git", "node_modules", "temp", "tmp", "__pycache__"}

    for root, dirs, files in os.walk(str(folder)):
        # Prune search in junk/hidden folders
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VALID_EXTENSIONS:
                clips.append(os.path.join(root, f))

    if not clips:
        raise FileNotFoundError(f"No video clips found in '{folder_path}'. "
                                f"Supported formats: {', '.join(sorted(VALID_EXTENSIONS))}")

    _FOLDER_CACHE[folder_key] = (now, clips)
    return clips


def select_local_clips(
    folder_path: str,
    target_duration_sec: float,
    speed_multiplier: float = 1.0,
    shuffle_seed: int | None = None,
    pacing_mode: str = "full",
    min_clip_sec: float = 5.0,
    max_clip_sec: float = 9.0
) -> Dict[str, Any]:
    """
    Selects a non-repeating sequence of local clips that fills the voiceover duration.

    Args:
        folder_path:         Path to local B-Roll folder (scanned recursively).
        target_duration_sec: Total voiceover duration in seconds to fill.
        speed_multiplier:    Slow-motion factor (0.5 = half speed, 1.0 = normal).
                             Clips appear longer: effective_dur = raw_dur / speed_multiplier.
        shuffle_seed:        Optional random seed for reproducibility.
        pacing_mode:         'full' (use whole clip as-is) or 'fast_cuts' (dynamic YouTube fair use trimming).
        min_clip_sec:        Minimum slice duration in seconds for dynamic cuts (default: 5.0s).
        max_clip_sec:        Maximum slice duration in seconds for dynamic cuts (default: 9.0s).

    Returns:
        Dict with:
            - clips:            List of {path, raw_duration, effective_duration, setpts_factor, start_offset, slice_dur, is_sliced}
            - total_effective:  Total effective duration of selected clips (>= target)
            - total_raw:        Total raw duration of source files
            - clip_count:       Number of clips selected
            - folder_clip_count: Total available clips in folder
            - wrapped:          True if folder was exhausted and re-shuffled
            - speed_multiplier: The speed_multiplier used
            - pacing_mode:      Pacing mode used ('full' or 'fast_cuts')
    """
    speed_multiplier = max(0.1, min(2.0, float(speed_multiplier)))
    # setpts factor: if speed=0.75, setpts = 1/0.75 ≈ 1.333 (stretches time)
    setpts_factor = 1.0 / speed_multiplier

    all_clips = scan_folder(folder_path)
    folder_clip_count = len(all_clips)

    # Shuffle the pool (without replacement)
    rng = random.Random(shuffle_seed)
    pool = all_clips.copy()
    rng.shuffle(pool)

    selected: List[Dict[str, Any]] = []
    accumulated_dur = 0.0
    wrapped = False
    used_paths: set = set()
    pool_index = 0

    # Dynamic cuts parameters
    is_fast_cuts = (str(pacing_mode).lower() in ("fast_cuts", "dynamic", "fair_use"))
    min_sec = max(2.0, float(min_clip_sec))
    max_sec = max(min_sec + 0.5, float(max_clip_sec))

    # Add 10s safety buffer so video never ends before audio (prevents -shortest cutting off voiceover tail)
    while accumulated_dur < (target_duration_sec + 10.0):
        if pool_index >= len(pool):
            # Pool exhausted — re-shuffle unused clips for wrap-around
            remaining = [c for c in all_clips if c not in used_paths]
            if not remaining:
                # All clips used at least once — allow reuse with new shuffle
                remaining = all_clips.copy()
                used_paths.clear()
                wrapped = True
                print(f"[LocalPool] ⚠️  All {folder_clip_count} clips exhausted "
                      f"(accumulated {accumulated_dur:.1f}s / {target_duration_sec:.1f}s). "
                      f"Re-shuffling pool for continuation...")
            rng.shuffle(remaining)
            pool = remaining
            pool_index = 0

        clip_path = pool[pool_index]
        pool_index += 1

        raw_dur = get_clip_duration(clip_path)

        # Dynamic cuts: if enabled and clip is longer than min_sec, slice randomly
        if is_fast_cuts and raw_dur > min_sec:
            target_slice = rng.uniform(min_sec, min(raw_dur, max_sec))
            max_start = max(0.0, raw_dur - target_slice)
            start_offset = rng.uniform(0.0, max_start)
            slice_dur = target_slice
            is_sliced = True
            effective_dur = slice_dur / speed_multiplier
        else:
            slice_dur = raw_dur
            start_offset = 0.0
            is_sliced = False
            effective_dur = raw_dur / speed_multiplier

        used_paths.add(clip_path)
        selected.append({
            "path":               clip_path,
            "raw_duration":       round(raw_dur, 3),
            "effective_duration": round(effective_dur, 3),
            "setpts_factor":      round(setpts_factor, 4),
            "start_offset":       round(start_offset, 3),
            "slice_dur":          round(slice_dur, 3),
            "is_sliced":          is_sliced,
        })
        accumulated_dur += effective_dur

    total_raw = sum(c["raw_duration"] for c in selected)

    return {
        "clips":              selected,
        "total_effective":    round(accumulated_dur, 3),
        "total_raw":          round(total_raw, 3),
        "clip_count":         len(selected),
        "folder_clip_count":  folder_clip_count,
        "wrapped":            wrapped,
        "speed_multiplier":   speed_multiplier,
        "setpts_factor":      round(setpts_factor, 4),
        "pacing_mode":        "fast_cuts" if is_fast_cuts else "full",
    }


def prepare_clean_concat_clips(
    clips: List[Any],
    work_dir: str,
    progress_callback=None
) -> List[Any]:
    """
    Sanitizes B-Roll clips for the concat demuxer:
    - Pure video only (strips audio/data/timecode tracks via stream-copy in <0.05s).
    - Clips already pure video are passed through instantly (0 latency).
    - Preserves inpoint/outpoint slicing metadata without re-encoding.
    - Prevents FFmpeg concat demuxer stream-count mismatches, non-monotonic DTS, and RAM leaks.
    """
    import hashlib
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from .config import find_ffmpeg
    ffmpeg = find_ffmpeg()
    out_dir = Path(work_dir) / "clean_broll"
    out_dir.mkdir(parents=True, exist_ok=True)

    cleaned_clips = [None] * len(clips)
    max_workers = min(4, max(1, os.cpu_count() or 4))

    def _clean_worker(idx: int, c: Any):
        if isinstance(c, dict):
            raw_p = c.get("path", "")
            is_dict = True
        else:
            raw_p = str(c)
            is_dict = False

        if not raw_p or not os.path.exists(raw_p):
            return idx, c

        info = probe_clip_info(raw_p)
        if info.get("is_pure_video", False):
            # Already pure video with no extra audio or data tracks
            return idx, c

        # Strip audio and data streams via ultra-fast stream copy (-c:v copy -an -dn)
        p_hash = hashlib.md5(str(Path(raw_p).resolve()).encode('utf-8')).hexdigest()[:12]
        clean_file = out_dir / f"pure_v_{p_hash}.mp4"
        clean_path = str(clean_file)

        if not (clean_file.exists() and clean_file.stat().st_size > 1000):
            cmd = [
                ffmpeg, "-y", "-v", "error",
                "-i", raw_p,
                "-c:v", "copy",
                "-an", "-dn",
                clean_path
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=15)
            except Exception as e:
                print(f"[LocalPool] Stream copy warning for {raw_p}: {e}, using original")
                return idx, c

        if is_dict:
            c_copy = dict(c)
            c_copy["path"] = clean_path
            return idx, c_copy
        else:
            return idx, clean_path

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_clean_worker, i, c) for i, c in enumerate(clips)]
        done_cnt = 0
        for f in as_completed(futures):
            i, cl = f.result()
            cleaned_clips[i] = cl
            done_cnt += 1
            if progress_callback and (done_cnt % 5 == 0 or done_cnt == len(clips)):
                progress_callback(f"Sanitized B-Roll clips {done_cnt}/{len(clips)} (pure video mode)...")

    print(f"[LocalPool] ⚡ Sanitized {len(cleaned_clips)} B-Roll clips in parallel (pure video concat mode).")
    return cleaned_clips


def write_concat_list(clips: List[Any], output_path: str) -> str:
    """
    Writes an FFmpeg concat demuxer list file for the provided clips.
    Supports native 'inpoint' and 'outpoint' directives for dynamic sliced cuts
    without requiring any intermediate video files or CPU re-encoding overhead.
    """
    lines = ["# FFmpeg concat demuxer list — Avatar Storyteller Engine"]
    for c in clips:
        if isinstance(c, dict):
            raw_p = c.get("path", "")
            is_sliced = c.get("is_sliced", False)
            start_offset = float(c.get("start_offset", 0.0))
            slice_dur = float(c.get("slice_dur", 0.0))
        else:
            raw_p = str(c)
            is_sliced = False
            start_offset = 0.0
            slice_dur = 0.0

        abs_p = Path(raw_p).resolve()
        path_escaped = str(abs_p).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{path_escaped}'")
        if is_sliced and slice_dur > 0:
            lines.append(f"inpoint {start_offset:.3f}")
            lines.append(f"outpoint {(start_offset + slice_dur):.3f}")

    content = "\n".join(lines) + "\n"
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def get_folder_stats(folder_path: str) -> Dict[str, Any]:
    """
    Returns quick statistics about a B-Roll folder without probing all durations.
    Uses file count + size as estimates (for fast UI feedback before full scan).
    """
    try:
        clips = scan_folder(folder_path)
        count = len(clips)
        if count > 150:
            sample = clips[:40]
            avg_size = sum(os.path.getsize(p) for p in sample) / len(sample)
            total_size_mb = (avg_size * count) / (1024 * 1024)
        else:
            total_size_mb = sum(os.path.getsize(p) for p in clips) / (1024 * 1024)
        extensions = {}
        for c in clips[:100]:
            ext = Path(c).suffix.lower()
            extensions[ext] = extensions.get(ext, 0) + 1
        return {
            "success":       True,
            "folder":        str(folder_path),
            "clip_count":    count,
            "total_size_mb": round(total_size_mb, 1),
            "extensions":    extensions,
            "estimated_avg_duration_sec": 45.0,  # Conservative estimate
        }
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}


# ── CLI Test Entrypoint ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Local B-Roll Pool — Test Runner")
    parser.add_argument("--folder", "-f", type=str, default="",
                        help="Path to local B-Roll folder")
    parser.add_argument("--duration", "-d", type=float, default=120.0,
                        help="Target duration in seconds (default: 120s = 2 minutes)")
    parser.add_argument("--speed", "-s", type=float, default=0.75,
                        help="Slow-motion speed multiplier (default: 0.75x)")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only show folder stats without selecting clips")
    args = parser.parse_args()

    if not args.folder:
        print("Usage: python -m backend.local_pool --folder D:/StockFootage --duration 120 --speed 0.75")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("  Avatar Storyteller Engine — Local B-Roll Pool Test")
    print(f"{'='*60}")
    print(f"  Folder:   {args.folder}")
    print(f"  Duration: {args.duration}s ({args.duration/60:.1f} minutes)")
    print(f"  Speed:    {args.speed}x (setpts={1/args.speed:.3f})")
    print()

    if args.stats_only:
        stats = get_folder_stats(args.folder)
        print(json.dumps(stats, indent=2))
        sys.exit(0)

    try:
        result = select_local_clips(
            folder_path=args.folder,
            target_duration_sec=args.duration,
            speed_multiplier=args.speed
        )
        print(f"✅ Selected {result['clip_count']} clips from {result['folder_clip_count']} available")
        print(f"   Target Duration:    {args.duration:.1f}s  ({args.duration/60:.1f} min)")
        print(f"   Effective Duration: {result['total_effective']:.1f}s ({result['total_effective']/60:.1f} min)")
        print(f"   Raw File Duration:  {result['total_raw']:.1f}s")
        print(f"   Speed Multiplier:   {result['speed_multiplier']}x")
        print(f"   setpts Factor:      {result['setpts_factor']} (FFmpeg filter)")
        if result['wrapped']:
            print(f"   ⚠️  Pool wrapped (folder had fewer clips than needed)")
        print()
        print("  Clip List:")
        for i, clip in enumerate(result["clips"], 1):
            name = Path(clip["path"]).name
            print(f"  {i:3d}. [{clip['raw_duration']:6.1f}s → {clip['effective_duration']:6.1f}s] {name}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
