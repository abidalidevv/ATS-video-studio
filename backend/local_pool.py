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
import random
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any
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


def scan_folder(folder_path: str) -> List[str]:
    """
    Recursively scans a folder for valid video clip files.
    Returns a list of absolute path strings.
    """
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"B-Roll folder not found: {folder_path}")

    clips = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS:
            clips.append(str(p.resolve()))

    if not clips:
        raise FileNotFoundError(f"No video clips found in '{folder_path}'. "
                                f"Supported formats: {', '.join(sorted(VALID_EXTENSIONS))}")
    return clips


def select_local_clips(
    folder_path: str,
    target_duration_sec: float,
    speed_multiplier: float = 1.0,
    shuffle_seed: int | None = None
) -> Dict[str, Any]:
    """
    Selects a non-repeating sequence of local clips that fills the voiceover duration.

    Args:
        folder_path:       Path to local B-Roll folder (scanned recursively).
        target_duration_sec: Total voiceover duration in seconds to fill.
        speed_multiplier:  Slow-motion factor (0.5 = half speed, 1.0 = normal).
                           Clips appear longer: effective_dur = raw_dur / speed_multiplier.
        shuffle_seed:      Optional random seed for reproducibility.

    Returns:
        Dict with:
            - clips:            List of {path, raw_duration, effective_duration, setpts_factor}
            - total_effective:  Total effective duration of selected clips (>= target)
            - total_raw:        Total raw duration of source files
            - clip_count:       Number of clips selected
            - folder_clip_count: Total available clips in folder
            - wrapped:          True if folder was exhausted and re-shuffled
            - speed_multiplier: The speed_multiplier used
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

    while accumulated_dur < target_duration_sec:
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
        effective_dur = raw_dur / speed_multiplier  # screen-time after slow-mo

        used_paths.add(clip_path)
        selected.append({
            "path":              clip_path,
            "raw_duration":      round(raw_dur, 3),
            "effective_duration": round(effective_dur, 3),
            "setpts_factor":     round(setpts_factor, 4),
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
    }


def write_concat_list(clips: List[Dict[str, Any]], output_path: str) -> str:
    """
    Writes an FFmpeg concat demuxer list file for the selected clips.
    Each clip path is written as an absolute path with proper escaping.

    Args:
        clips:       List of clip dicts from select_local_clips()
        output_path: Where to write the concat_list.txt file

    Returns:
        Absolute path to the written concat_list.txt
    """
    lines = ["# FFmpeg concat demuxer list — Avatar Storyteller Engine"]
    for clip in clips:
        # Ensure absolute path, escape backslashes and single quotes for FFmpeg concat format
        abs_p = Path(clip["path"]).resolve()
        path_escaped = str(abs_p).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{path_escaped}'")
        # Note: setpts is applied in filtergraph, not concat list
    content = "\n".join(lines) + "\n"
    output_path = str(output_path)
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
        total_size_mb = sum(os.path.getsize(p) for p in clips) / (1024 * 1024)
        extensions = {}
        for c in clips:
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
