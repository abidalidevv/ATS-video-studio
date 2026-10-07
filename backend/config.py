"""
Avatar Storyteller Video Engine — Configuration Module
Provides path resolution, settings management, ffmpeg/ffprobe detection,
and GPU encoder auto-detection. Adapted from VideoGen Studio (vg/backend/config.py).
"""
import sys
import os
import re
import json
import shutil
import subprocess
from pathlib import Path

# ── Path Resolution ──────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR   = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(BASE_DIR)))
else:
    BASE_DIR   = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR

DATA_DIR         = BASE_DIR / "data"
SETTINGS_FILE    = DATA_DIR / "settings.json"
OUTPUT_DIR       = DATA_DIR / "output"
TEMP_DIR         = DATA_DIR / "temp"
AVATARS_DIR      = DATA_DIR / "avatars"
BIN_DIR          = BASE_DIR / "bin"
FONTS_DIR        = BUNDLE_DIR / "backend" / "assets" / "fonts"
if not FONTS_DIR.exists():
    FONTS_DIR = BASE_DIR / "backend" / "assets" / "fonts"
if not FONTS_DIR.exists():
    FONTS_DIR = BASE_DIR / "assets" / "fonts"

FRONTEND_DIR = BUNDLE_DIR / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = BASE_DIR / "frontend"

LOGS_DIR     = DATA_DIR / "logs"
LOG_FILE     = LOGS_DIR / "ats_studio.log"

# Ensure directories exist
for d in [DATA_DIR, OUTPUT_DIR, TEMP_DIR, AVATARS_DIR, BIN_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class LogTee:
    """Tees stdout/stderr to both original console and persistent ats_studio.log."""
    def __init__(self, original_stream, log_file: Path):
        self.original_stream = original_stream
        self.log_file = log_file

    def write(self, data):
        if self.original_stream:
            try:
                self.original_stream.write(data)
                self.original_stream.flush()
            except Exception:
                pass
        if data:
            try:
                with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                    f.write(data)
            except Exception:
                pass

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass

    def isatty(self):
        if self.original_stream and hasattr(self.original_stream, "isatty"):
            try:
                return self.original_stream.isatty()
            except Exception:
                return False
        return False

    def fileno(self):
        if self.original_stream and hasattr(self.original_stream, "fileno"):
            try:
                return self.original_stream.fileno()
            except Exception:
                pass
        raise OSError("LogTee stream has no fileno")

    def __getattr__(self, name):
        if self.original_stream and hasattr(self.original_stream, name):
            return getattr(self.original_stream, name)
        raise AttributeError(f"'LogTee' object has no attribute '{name}'")


_logging_initialized = False

def setup_file_logging():
    global _logging_initialized
    if _logging_initialized:
        return
    _logging_initialized = True
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("=== ATS Video Studio Engine Log Initialized ===\n")
        except Exception:
            pass
    # Avoid double wrapping if already a LogTee
    if not isinstance(sys.stdout, LogTee):
        sys.stdout = LogTee(sys.stdout, LOG_FILE)
    if not isinstance(sys.stderr, LogTee):
        sys.stderr = LogTee(sys.stderr, LOG_FILE)

# Automatically enable file logging on import
setup_file_logging()


# ── Default Settings ──────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    # API Keys
    "groq_api_key":          "",
    "groq_api_keys":         [],
    # Local Pool
    "broll_folder":          "",
    "stock_speed":           0.75,          # 0.5x – 1.0x
    # Avatar
    "avatar_path":           "",
    "avatar_position":       "right",       # left | center | right
    "avatar_stroke_color":   "white",       # white | gold | cyan | none
    "avatar_stroke_width":   10,
    # Background
    "blur_radius":           0,             # 0 – 30 (0 = clear/off)
    "dark_tint":             0.25,          # 0.0 – 0.8
    "visualizer_enabled":    False,         # Off by default for maximum render speed
    # Audio DSP
    "pitch_semitones":       0.0,           # -4.0 – +4.0
    "voice_speed":           1.0,           # 0.8 – 1.25
    # Subtitles
    "caption_preset":        "capcut_yellow",
    # Output
    "output_dir":            str(OUTPUT_DIR),
    # Performance
    "hardware_encoder":      "auto",        # auto | nvenc | qsv | amf | cpu
    "resolution":            "1920x1080",
    "fps":                   30,
}


# ── Settings I/O ──────────────────────────────────────────────────────────────
def _clean_key_list(val) -> list:
    """Normalizes string or list into a clean unique list of keys."""
    if isinstance(val, str):
        parts = [k.strip() for k in re.split(r'[\r\n,;]+', val) if k.strip()]
        return list(dict.fromkeys(parts))
    if isinstance(val, (list, tuple)):
        cleaned = []
        for item in val:
            if isinstance(item, str):
                for k in re.split(r'[\r\n,;]+', item):
                    k_s = k.strip()
                    if k_s and k_s not in cleaned:
                        cleaned.append(k_s)
        return cleaned
    return []


def load_settings() -> dict:
    data = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    merged = {**DEFAULT_SETTINGS, **data}

    # Normalize Groq pool
    gr_keys = _clean_key_list(merged.get("groq_api_keys", []))
    single_gr = str(merged.get("groq_api_key", "")).strip()
    if single_gr and single_gr not in gr_keys:
        gr_keys.insert(0, single_gr)
    merged["groq_api_keys"] = gr_keys
    merged["groq_api_key"]  = gr_keys[0] if gr_keys else ""

    out_dir_val = str(merged.get("output_dir", "")).strip()
    try:
        p = Path(out_dir_val)
        # Portability check: If invalid, doesn't exist, not a directory, or belongs to another user's profile
        user_home_str = str(Path.home()).lower()
        is_foreign_user = ("\\users\\" in out_dir_val.lower()) and not out_dir_val.lower().startswith(user_home_str)
        if not out_dir_val or is_foreign_user or not p.exists() or not p.is_dir():
            merged["output_dir"] = str(OUTPUT_DIR)
    except Exception:
        merged["output_dir"] = str(OUTPUT_DIR)
    return merged


def save_settings(new_settings: dict) -> dict:
    current = load_settings()
    if "groq_api_keys" in new_settings or "groq_api_key" in new_settings:
        raw = new_settings.get("groq_api_keys", current.get("groq_api_keys", []))
        single = new_settings.get("groq_api_key", current.get("groq_api_key", ""))
        all_k = _clean_key_list(raw)
        if single and single.strip() not in all_k:
            all_k.insert(0, single.strip())
        new_settings["groq_api_keys"] = all_k
        new_settings["groq_api_key"]  = all_k[0] if all_k else ""
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current


# ── FFmpeg / FFprobe Resolution ───────────────────────────────────────────────
def find_ffmpeg() -> str:
    candidates = [
        BIN_DIR / "ffmpeg.exe",
        BUNDLE_DIR / "bin" / "ffmpeg.exe",
        BUNDLE_DIR / "ffmpeg.exe",
        BASE_DIR / "ffmpeg.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    found = shutil.which("ffmpeg")
    if found:
        return found
    common = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for p in common:
        if p.exists():
            return str(p)
    return "ffmpeg"


def find_ffprobe() -> str:
    candidates = [
        BIN_DIR / "ffprobe.exe",
        BUNDLE_DIR / "bin" / "ffprobe.exe",
        BUNDLE_DIR / "ffprobe.exe",
        BASE_DIR / "ffprobe.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    found = shutil.which("ffprobe")
    if found:
        return found
    common = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffprobe.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffprobe.exe",
    ]
    for p in common:
        if p.exists():
            return str(p)
    return "ffprobe"


# ── GPU Encoder Auto-Detection ────────────────────────────────────────────────
_ENCODER_CACHE: str | None = None

def detect_gpu_encoder(force_probe: bool = False) -> str:
    """
    Probes FFmpeg for available hardware encoders and returns the best available:
    h264_nvenc (NVIDIA) → h264_qsv (Intel) → h264_amf (AMD) → libx264 (CPU).
    Result is cached for session lifetime.
    """
    global _ENCODER_CACHE
    if _ENCODER_CACHE and not force_probe:
        return _ENCODER_CACHE

    settings = load_settings()
    pref = str(settings.get("hardware_encoder", "auto")).lower().strip()

    if pref in ("nvenc", "h264_nvenc"):
        _ENCODER_CACHE = "h264_nvenc"; return _ENCODER_CACHE
    if pref in ("qsv", "h264_qsv"):
        _ENCODER_CACHE = "h264_qsv";  return _ENCODER_CACHE
    if pref in ("amf", "h264_amf"):
        _ENCODER_CACHE = "h264_amf";  return _ENCODER_CACHE
    if pref in ("cpu", "libx264"):
        _ENCODER_CACHE = "libx264";   return _ENCODER_CACHE

    # Auto-detect
    ffmpeg = find_ffmpeg()
    probe_order = ["h264_nvenc", "h264_qsv", "h264_amf"]
    for enc in probe_order:
        try:
            res = subprocess.run(
                [ffmpeg, "-f", "lavfi", "-i", "color=black:s=64x64:d=1",
                 "-c:v", enc, "-frames:v", "1", "-f", "null", "-"],
                capture_output=True, timeout=8
            )
            if res.returncode == 0:
                _ENCODER_CACHE = enc
                print(f"[Config] GPU encoder detected: {enc}")
                return enc
        except Exception:
            pass

    _ENCODER_CACHE = "libx264"
    print("[Config] No GPU encoder detected — using CPU libx264")
    return _ENCODER_CACHE


def get_encoder_params(encoder: str) -> dict:
    """Returns optimal FFmpeg encoding parameters for maximum hardware throughput."""
    params = {
        "h264_nvenc": {
            "codec":   "h264_nvenc",
            "preset":  "p1",
            "extras":  ["-tune", "ull", "-rc", "vbr", "-cq", "22", "-b:v", "0"],
            "pix_fmt": "yuv420p",
        },
        "h264_qsv": {
            "codec":   "h264_qsv",
            "preset":  "veryfast",
            "extras":  ["-async_depth", "4", "-b:v", "5M", "-maxrate", "7M", "-bufsize", "10M"],
            "pix_fmt": "nv12",
        },
        "h264_amf": {
            "codec":   "h264_amf",
            "preset":  "speed",
            "extras":  ["-b:v", "8M"],
            "pix_fmt": "yuv420p",
        },
        "libx264": {
            "codec":   "libx264",
            "preset":  "veryfast",
            "extras":  ["-crf", "20"],
            "pix_fmt": "yuv420p",
        },
    }
    return params.get(encoder, params["libx264"])
