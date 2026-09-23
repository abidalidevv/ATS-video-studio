"""
Avatar Storyteller Video Engine — Audio DSP Module
Handles voiceover pitch shifting and speed/tempo adjustment using FFmpeg audio filters.

Pitch Shift Method: asetrate + atempo (sample-rate trick — no external plugins needed).
- asetrate=<new_rate>  : Changes pitch by resampling at different rate (also changes speed)
- atempo=<1/factor>    : Restores original speed while preserving new pitch
- Speed control is layered on top with an additional atempo filter.

The atempo filter supports 0.5x–2.0x per stage. For values outside this range,
we chain multiple atempo filters.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional
from .config import find_ffmpeg, TEMP_DIR


def _build_atempo_chain(rate: float) -> list[str]:
    """
    Builds a chain of atempo filters to handle rates outside 0.5–2.0 range.
    atempo only accepts values in [0.5, 2.0] — for larger changes, chain them.
    """
    filters = []
    remaining = rate
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    if abs(remaining - 1.0) > 0.01:
        filters.append(f"atempo={remaining:.6f}")
    return filters


def process_voiceover_audio(
    input_audio: str,
    output_audio: str,
    pitch_semitones: float = 0.0,
    speed_rate: float = 1.0,
    sample_rate: int = 44100
) -> str:
    """
    Adjusts voiceover pitch and tempo using FFmpeg DSP filters.

    Pitch shift math:
        frequency_ratio = 2^(semitones / 12)
        new_sample_rate = original_sr * frequency_ratio
        compensate_tempo = 1 / frequency_ratio   (restores speed, keeps pitch)

    Then speed_rate is applied on top (independent of pitch).

    Args:
        input_audio:     Path to source audio file (MP3/WAV/M4A/AAC).
        output_audio:    Path for processed output audio.
        pitch_semitones: Pitch shift in semitones (-4.0 = deep, 0 = unchanged, +4.0 = high).
        speed_rate:      Playback speed multiplier (0.8 = slower, 1.0 = normal, 1.25 = faster).
        sample_rate:     Source sample rate for asetrate calculation (default: 44100).

    Returns:
        Path to processed audio file (same as input if no processing needed).
    """
    pitch_semitones = float(pitch_semitones)
    speed_rate      = float(speed_rate)

    needs_pitch = abs(pitch_semitones) > 0.05
    needs_speed = abs(speed_rate - 1.0) > 0.02

    if not needs_pitch and not needs_speed:
        print("[AudioDSP] No pitch/speed adjustment needed — returning original audio.")
        return input_audio

    ffmpeg = find_ffmpeg()
    filters = []

    if needs_pitch:
        freq_ratio      = 2.0 ** (pitch_semitones / 12.0)
        new_rate        = int(sample_rate * freq_ratio)
        restore_tempo   = 1.0 / freq_ratio
        # Set new sample rate (shifts pitch + changes speed)
        filters.append(f"asetrate={new_rate}")
        # Restore original tempo
        filters.extend(_build_atempo_chain(restore_tempo))
        # Resample back to standard rate for compatibility
        filters.append(f"aresample={sample_rate}")
        print(f"[AudioDSP] Pitch: {pitch_semitones:+.1f} semitones → "
              f"asetrate={new_rate}, restore_tempo={restore_tempo:.4f}")

    if needs_speed:
        filters.extend(_build_atempo_chain(speed_rate))
        print(f"[AudioDSP] Speed: {speed_rate}x → atempo chain applied")

    filter_str = ",".join(filters)

    # Determine output format from extension
    out_ext = Path(output_audio).suffix.lower()
    if out_ext in (".mp3",):
        codec_args = ["-c:a", "libmp3lame", "-b:a", "192k"]
    elif out_ext in (".wav",):
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        codec_args = ["-c:a", "aac", "-b:a", "192k"]

    cmd = [
        ffmpeg, "-y",
        "-i", input_audio,
        "-af", filter_str,
        *codec_args,
        output_audio
    ]

    print(f"[AudioDSP] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio DSP failed:\n{result.stderr}")

    print(f"[AudioDSP] ✅ Processed audio saved: {output_audio}")
    return output_audio


def get_audio_duration(audio_path: str) -> float:
    """
    Returns accurate duration of audio file in seconds using ffprobe.
    Falls back to 0.0 on failure.
    """
    from .config import find_ffprobe
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        val = res.stdout.strip()
        if val and val.lower() not in ("n/a", ""):
            return float(val)
    except Exception as e:
        print(f"[AudioDSP] ffprobe duration error: {e}")
    return 0.0


def calculate_output_duration(
    input_duration: float,
    pitch_semitones: float = 0.0,
    speed_rate: float = 1.0
) -> float:
    """
    Calculates the expected output audio duration after DSP processing.
    
    Note: pitch shifting via asetrate + compensate_tempo leaves duration unchanged.
    Only speed_rate changes the output duration.
    
    Args:
        input_duration: Original audio duration in seconds.
        pitch_semitones: Pitch shift (does NOT change duration — compensated by atempo).
        speed_rate:      Speed multiplier (DOES change duration).

    Returns:
        Expected output duration in seconds.
    """
    # Pitch shift is compensated by atempo, so no net duration change
    # Speed rate directly scales duration: faster = shorter, slower = longer
    if abs(speed_rate - 1.0) < 0.01:
        return input_duration
    return input_duration / speed_rate


# ── CLI Test Entrypoint ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Audio DSP — Test Runner")
    parser.add_argument("--input",  "-i", required=True, help="Input audio file")
    parser.add_argument("--output", "-o", default="",    help="Output audio file")
    parser.add_argument("--pitch",  "-p", type=float, default=0.0,
                        help="Pitch in semitones (-4 to +4, default: 0)")
    parser.add_argument("--speed",  "-s", type=float, default=1.0,
                        help="Speed multiplier (0.8–1.25, default: 1.0)")
    args = parser.parse_args()

    if not args.output:
        inp = Path(args.input)
        args.output = str(inp.parent / f"{inp.stem}_processed{inp.suffix}")

    print(f"\n{'='*60}")
    print("  Avatar Storyteller Engine — Audio DSP Test")
    print(f"{'='*60}")
    print(f"  Input:  {args.input}")
    print(f"  Output: {args.output}")
    print(f"  Pitch:  {args.pitch:+.1f} semitones")
    print(f"  Speed:  {args.speed}x")

    orig_dur = get_audio_duration(args.input)
    expected_dur = calculate_output_duration(orig_dur, args.pitch, args.speed)
    print(f"\n  Input Duration:    {orig_dur:.2f}s")
    print(f"  Expected Output:   {expected_dur:.2f}s")

    try:
        out = process_voiceover_audio(
            input_audio=args.input,
            output_audio=args.output,
            pitch_semitones=args.pitch,
            speed_rate=args.speed
        )
        actual_dur = get_audio_duration(out)
        print(f"\n✅ Done! Actual output duration: {actual_dur:.2f}s")
        print(f"   Saved: {out}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
