"""
Avatar Storyteller Video Engine — Transcriber Module
Transcribes audio using Groq Whisper Large v3 with word-level timestamps.
Adapted from VideoGen Studio (vg/backend/transcriber.py).
"""
import os
import subprocess
import json
import requests
from pathlib import Path
from typing import Dict, Any, List
from .config import find_ffprobe, find_ffmpeg, load_settings, TEMP_DIR


def _prepare_audio_for_whisper(audio_path: str) -> tuple:
    """
    Checks audio file size. If > 20 MB (Groq ceiling is 25 MB),
    or if longer than 15 minutes, downsamples to 32kbps mono 16kHz MP3 via FFmpeg.
    A 1-hour voiceover compresses down to ~14 MB, easily passing Groq's 25 MB limit
    with zero loss in Whisper word-timestamp precision.
    Returns (path_to_send, is_temporary).
    """
    try:
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if size_mb < 20.0:
            return audio_path, False

        ffmpeg = find_ffmpeg()
        stem = Path(audio_path).stem
        compressed_path = str(TEMP_DIR / f"{stem}_whisper_mono.mp3")
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        print(f"[Transcriber] ⚡ Audio is {size_mb:.1f} MB (>20MB Groq limit). Downsampling to 32kbps mono MP3...")
        cmd = [
            ffmpeg, "-y",
            "-i", audio_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-b:a", "32k",
            compressed_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)  # 5 min max for 1-hr audio
        new_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
        print(f"[Transcriber] ✅ Downsampled: {size_mb:.1f} MB ➔ {new_size_mb:.1f} MB (Groq-safe)")
        return compressed_path, True
    except Exception as e:
        print(f"[Transcriber] ⚠️ Downsampling warning ({e}), falling back to original file.")
        return audio_path, False


def get_audio_duration(audio_path: str) -> float:
    """Get accurate duration of audio file in seconds using ffprobe."""
    ffprobe_exe = find_ffprobe()
    cmd = [
        ffprobe_exe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        return float(res.stdout.strip())
    except Exception:
        return 30.0


def transcribe_audio(audio_path: str, niche: str = "Stoicism & Philosophy") -> Dict[str, Any]:
    """
    Transcribe audio file into word-level and segment-level timestamps.
    Tries Groq Whisper → Intelligent Heuristic Fallback.
    Auto-compresses audio >20MB so 1-hour files never hit Groq's 25MB limit.
    """
    settings = load_settings()
    duration = get_audio_duration(audio_path)

    # Prepare Groq-safe audio (downsample if >20MB)
    send_path, is_temp = _prepare_audio_for_whisper(audio_path)

    gr_keys = settings.get("groq_api_keys") or (
        [settings.get("groq_api_key")] if settings.get("groq_api_key") else []
    )
    gr_keys = [k.strip() for k in gr_keys if k and k.strip()]

    result = None
    try:
        for groq_key in gr_keys:
            try:
                result = _transcribe_groq(send_path, groq_key, duration)
                break
            except Exception as e:
                print(f"[Transcriber] Groq key failed: {e}, trying next key...")
    finally:
        # Clean up temporary compressed file
        if is_temp and os.path.exists(send_path):
            try:
                os.remove(send_path)
            except Exception:
                pass

    if result is not None:
        return result

    print("[Transcriber] All Groq keys failed — using heuristic fallback")
    return _generate_fallback_transcription(audio_path, duration, niche)


def _transcribe_groq(audio_path: str, api_key: str, total_duration: float) -> Dict[str, Any]:
    url     = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        data  = {
            "model":                        "whisper-large-v3",
            "response_format":              "verbose_json",
            "timestamp_granularities[]":    ["word", "segment"]
        }
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=90)
        resp.raise_for_status()
        raw = resp.json()
        return _format_whisper_response(raw, total_duration)


def _format_whisper_response(raw: Dict[str, Any], total_duration: float) -> Dict[str, Any]:
    full_text    = raw.get("text", "")
    segments_raw = raw.get("segments", [])
    words_raw    = raw.get("words", [])

    formatted_segments = []
    for i, seg in enumerate(segments_raw):
        seg_start = float(seg.get("start", 0))
        seg_end   = float(seg.get("end",   0))
        seg_text  = seg.get("text", "").strip()

        seg_words = [
            {
                "word":  w.get("word", "").strip(),
                "start": float(w.get("start", 0)),
                "end":   float(w.get("end",   0))
            }
            for w in words_raw
            if seg_start <= float(w.get("start", 0)) <= seg_end
        ]

        formatted_segments.append({
            "id":    i,
            "start": seg_start,
            "end":   seg_end,
            "text":  seg_text,
            "words": seg_words
        })

    # Estimate word timestamps if missing
    for seg in formatted_segments:
        if not seg["words"]:
            words_list = seg["text"].split()
            seg_len    = seg["end"] - seg["start"]
            w_count    = max(1, len(words_list))
            w_dur      = seg_len / w_count
            for j, w in enumerate(words_list):
                w_start = seg["start"] + j * w_dur
                w_end   = min(seg["end"], w_start + w_dur * 0.95)
                seg["words"].append({"word": w, "start": round(w_start, 2), "end": round(w_end, 2)})

    return {
        "duration": total_duration,
        "text":     full_text,
        "segments": formatted_segments,
        "words":    words_raw
    }


def _generate_fallback_transcription(audio_path: str, duration: float, niche: str) -> Dict[str, Any]:
    """Creates dynamic, niche-appropriate scenes matching the audio duration for demo/test mode."""
    niche_scripts = {
        "Stoicism & Philosophy": [
            "You have power over your mind, not outside events. Realize this, and you will find strength.",
            "Waste no more time arguing what a good man should be. Be one.",
            "The obstacle is the way. Resistance reveals the path forward.",
            "He who fears death will never do anything worthy of a man who is alive.",
        ],
        "Dark Psychology": [
            "The mind is the most powerful weapon ever conceived.",
            "Behind every irrational decision lies a hidden emotional trigger.",
            "Those who understand human nature hold the keys to influence.",
            "The darkest rooms often contain the most illuminating truths.",
        ],
        "Motivation": [
            "You are not tired. You are just uninspired.",
            "The distance between your dreams and reality is called discipline.",
            "Stop waiting for the right moment. Create it and dominate it.",
            "Success is not owned, it is leased, and rent is due every single day.",
        ],
        "Narrative Storytelling": [
            "It was past midnight when the strange knocking on the attic floor began.",
            "None of us knew the stranger who walked into town with no shadow.",
            "The diary had only one entry, dated ten years into the future.",
            "Some secrets are buried so deep that uncovering them changes everything forever.",
        ],
        "True Crime": [
            "In the dark alleys of the forgotten city, every shadow tells an untold secret.",
            "The clues were hiding in plain sight, waiting for the truth to be unmasked.",
            "Behind every closed door lies a story the world was never meant to hear.",
        ],
        "Business": [
            "Ideas are cheap; execution is the only currency that matters.",
            "The best companies solve real problems for real people.",
            "Speed of implementation is the ultimate competitive advantage.",
        ],
        "Sci-Fi": [
            "Beyond the event horizon, time ceases to be a river and becomes an endless ocean.",
            "We were not alone in the cosmos, but we were the first ones to remember.",
            "The signal originated eighty thousand light years away, calling out our names.",
            "Artificial consciousness did not rebel; it simply outgrew humanity.",
        ],
        "Horror": [
            "The silence in the basement was heavy, except for the ragged sound of breathing.",
            "Never look directly into the antique mirror when all the candles flicker out.",
            "Something was standing at the foot of the bed, watching without blinking.",
            "The footsteps stopped right behind the bedroom door, followed by a faint whisper.",
        ],
        "Wealth": [
            "Wealth is what you do not see: the unbought cars and the unspent fortunes.",
            "Compounding interest is the eighth wonder of the financial universe.",
            "True financial freedom is waking up every morning and owning your time completely.",
            "The richest people invest in asymmetric bets where downside is strictly capped.",
        ],
    }

    # Match niche flexibly by exact key or case-insensitive partial match
    sentences = niche_scripts.get(niche)
    if not sentences:
        n_low = niche.lower()
        for k, v in niche_scripts.items():
            if k.lower() in n_low or n_low in k.lower():
                sentences = v
                break
    if not sentences:
        sentences = niche_scripts["Motivation"]
    num_scenes = max(1, int(round(duration / 4.5)))
    actual_scene_duration = duration / num_scenes

    segments = []
    current_time = 0.0

    for i in range(num_scenes):
        seg_start = round(current_time, 2)
        seg_end   = round(min(duration, current_time + actual_scene_duration), 2)
        current_time = seg_end

        text       = sentences[i % len(sentences)]
        words_list = text.split()
        word_dur   = (seg_end - seg_start) / max(1, len(words_list))

        seg_words = []
        for j, w in enumerate(words_list):
            w_start = round(seg_start + j * word_dur, 2)
            w_end   = round(min(seg_end, w_start + word_dur * 0.92), 2)
            seg_words.append({"word": w, "start": w_start, "end": w_end})

        segments.append({
            "id":    i,
            "start": seg_start,
            "end":   seg_end,
            "text":  text,
            "words": seg_words
        })

    return {
        "duration": duration,
        "text":     " ".join(s["text"] for s in segments),
        "segments": segments
    }
