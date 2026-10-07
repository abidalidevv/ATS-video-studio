"""
Avatar Storyteller Video Engine — Single-Pass GPU Turbo Renderer

Architecture:
  - Input 0: FFmpeg concat demuxer (local B-Roll clips with setpts slow-mo)
  - Input 1: Avatar portrait PNG (loop=1)
  - Input 2: Processed voiceover MP3

  Filter Graph (single pass):
    [0:v] scale → setpts(slow-mo) → boxblur → colorchannelmixer(tint) → [bg]
    [bg][1:v] overlay(avatar position) → [comp]
    [comp] subtitles(ass file) → [vout]

  Output: 1080p MP4 with GPU-accelerated codec (NVENC/QSV/AMF/libx264)

Performance: ~400-500 FPS on 4GB GPU → 1-hour video in 4-5 minutes.
"""
import os
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from .config import (
    find_ffmpeg, TEMP_DIR, OUTPUT_DIR, FONTS_DIR,
    detect_gpu_encoder, get_encoder_params, load_settings
)
from .local_pool import write_concat_list


def _build_avatar_overlay_coords(
    position: str,
    avatar_width: int,
    avatar_height: int,
    canvas_w: int = 1920,
    canvas_h: int = 1080,
    custom_x: Optional[int] = None,
    custom_y: Optional[int] = None
) -> str:
    """
    Returns FFmpeg overlay x:y coordinates string for the avatar position.
    Supports free XY coordinates from interactive Studio Canvas.
    """
    if custom_x is not None and custom_y is not None:
        return f"x={int(round(float(custom_x)))}:y={int(round(float(custom_y)))}"

    y_bottom = "H-h"

    if position == "left":
        x = "0"
        y = y_bottom
    elif position == "right":
        x = "W-w"
        y = y_bottom
    elif position == "center":
        x = "(W-w)/2"
        y = y_bottom
    else:
        x = "W-w"
        y = y_bottom

    return f"x={x}:y={y}"


def _prepare_isolated_fonts_dir(ass_path: str, temp_dir: Path) -> Optional[str]:
    """
    Scans the ASS subtitle file to find which fonts are actually used.
    Copies only the needed fonts into an isolated temp directory to prevent
    libass from pre-loading and indexing all 12 heavy fonts into RAM.
    """
    try:
        ass_p = Path(ass_path)
        if not ass_p.exists():
            return None

        fonts_source_dir = FONTS_DIR if (FONTS_DIR and FONTS_DIR.exists()) else (Path(__file__).parent / "assets" / "fonts")
        if not fonts_source_dir.exists():
            return None

        # Find font names from Style lines in the ASS file
        used_fonts = set()
        with open(ass_p, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("Style:"):
                    parts = line.split(",")
                    if len(parts) >= 2:
                        font_name = parts[1].strip().lower()
                        if font_name:
                            used_fonts.add(font_name)

        if not used_fonts:
            return str(fonts_source_dir)

        isolated_dir = temp_dir / "isolated_fonts"
        isolated_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        import shutil
        for f_file in fonts_source_dir.iterdir():
            if f_file.suffix.lower() in (".ttf", ".otf"):
                stem_lower = f_file.stem.lower()
                if any(uf in stem_lower or stem_lower in uf for uf in used_fonts):
                    target = isolated_dir / f_file.name
                    if not target.exists():
                        shutil.copy2(str(f_file), str(target))
                    copied += 1

        if copied > 0:
            return str(isolated_dir)
        return str(fonts_source_dir)
    except Exception as e:
        print(f"[Renderer] Isolated fonts warning: {e}")
        return None


def _build_filter_complex(
    blur_radius: int,
    dark_tint: float,
    speed_multiplier: float,
    avatar_position: str,
    avatar_width: int,
    avatar_height: int,
    ass_subtitle_path: str,
    canvas_w: int = 1920,
    canvas_h: int = 1080,
    visualizer_enabled: bool = False,
    visualizer_style: str = "glass_pill_cyan",
    visualizer_position: str = "top_center",
    visualizer_card_path: Optional[str] = None,
    audio_duration: float = 0.0,
    card_input_idx: int = 3,
    avatar_opacity: float = 1.0,
    avatar_custom_x: Optional[int] = None,
    avatar_custom_y: Optional[int] = None,
    visualizer_custom_x: Optional[int] = None,
    visualizer_custom_y: Optional[int] = None,
    visualizer_scale: float = 1.0,
    visualizer_mode: str = "template",
    custom_vis_video_path: Optional[str] = None,
    chroma_key_color: str = "#00FF00",
    chroma_similarity: float = 0.25,
    chroma_blend: float = 0.08,
    target_vis_w: int = 400,
    target_vis_h: int = 200,
    fonts_dir_override: Optional[str] = None
) -> str:
    """
    Builds the single-pass FFmpeg filter_complex string.

    Stream assignments:
        [0:v] = concat B-Roll video
        [1:v] = avatar PNG (no loop, repeated via overlay eof_action=repeat)
        [2:a] = processed voiceover audio
        [3:v] = (optional) audio player card PNG OR looped custom green-screen video
    """
    # Slow-motion factor: if speed=0.75, setpts = 1/0.75 ≈ 1.333
    setpts_factor = 1.0 / max(0.1, speed_multiplier)

    # Avatar overlay coordinates (handles free canvas drag & drop)
    overlay_coords = _build_avatar_overlay_coords(
        position=avatar_position,
        avatar_width=avatar_width,
        avatar_height=avatar_height,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        custom_x=avatar_custom_x,
        custom_y=avatar_custom_y
    )

    # Escape paths for FFmpeg filter_complex on Windows:
    # Drive letter colon must be escaped as \: and backslashes → forward slashes
    def _ffmpeg_path(p: str) -> str:
        p = str(Path(p).resolve()).replace("\\", "/")
        # Escape the colon in drive letter (e.g. C:/ → C\:/)
        if len(p) >= 2 and p[1] == ":":
            p = p[0] + "\\:" + p[2:]
        # Escape any remaining unescaped colons
        return p

    ass_path_escaped = _ffmpeg_path(ass_subtitle_path)

    # Build filter graph
    filters = []

    # Step 1: Standardize stock footage to 1920x1080 (16:9 square pixels), apply slow-mo, single 30fps quantization
    bg_subfilters = [
        f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=fast_bilinear",
        f"crop={canvas_w}:{canvas_h}",
        "setsar=1",
        f"setpts=PTS/{max(0.1, float(speed_multiplier)):.4f}",
        "fps=30"
    ]
    if blur_radius > 0:
        r = max(1, min(30, int(blur_radius)))
        bg_subfilters.append(f"avgblur=sizeX={r}:sizeY={r}")
    if dark_tint > 0.02:
        tint_alpha = max(0.20, 1.0 - float(dark_tint))
        bg_subfilters.append(f"colorchannelmixer=aa={tint_alpha:.3f}")

    filters.append(f"[0:v]{','.join(bg_subfilters)}[bg]")

    # Step 2: Overlay avatar on background (avatar is crisp, not blurred)
    if avatar_opacity < 0.99:
        op = max(0.1, min(1.0, float(avatar_opacity)))
        filters.append(
            f"[1:v]format=rgba,colorchannelmixer=aa={op:.3f}[avatar_trans]"
        )
        avatar_stream = "avatar_trans"
    else:
        avatar_stream = "1:v"

    filters.append(
        f"[bg][{avatar_stream}]overlay={overlay_coords}:eof_action=repeat[comp]"
    )

    # Step 3: Audio Visualizer Overlay (Template or Custom Green-Screen Video)
    comp_stream = "comp"
    if visualizer_enabled and visualizer_position != "none":
        if visualizer_mode == "video" and custom_vis_video_path:
            # Custom Green-Screen Video Visualizer with Chroma Keying
            from .visualizer_generator import get_visualizer_overlay_coords
            vis_coords = get_visualizer_overlay_coords(
                position=visualizer_position,
                widget_w=target_vis_w,
                widget_h=target_vis_h,
                custom_x=visualizer_custom_x,
                custom_y=visualizer_custom_y
            )
            # Choose colorkey (RGB Euclidean distance - exactly matches browser canvas sampler)
            # This ensures white waveforms, glowing lines, and text are 100% preserved
            # whereas YUV chromakey discards luminance (Y) and erases white bars.
            hex_clean = chroma_key_color.lstrip("#").upper()
            key_color_code = f"0x{hex_clean}" if len(hex_clean) == 6 else "0x00FF00"
            key_filter = f"colorkey=color={key_color_code}:similarity={chroma_similarity:.3f}:blend={chroma_blend:.3f}"

            filters.append(
                f"[{card_input_idx}:v]setsar=1,fps=30,{key_filter},"
                f"scale={target_vis_w}:{target_vis_h}:flags=fast_bilinear,"
                f"format=rgba[custom_vis_keyed]"
            )
            filters.append(
                f"[{comp_stream}][custom_vis_keyed]overlay={vis_coords}:eof_action=repeat[comp_vis]"
            )
            comp_stream = "comp_vis"
        elif visualizer_card_path:
            # Procedural Template Card with Dynamic Audio Visualizer
            from .visualizer_generator import build_visualizer_filter_snippet
            vis_snippet, comp_stream = build_visualizer_filter_snippet(
                style_key=visualizer_style,
                card_png_path=visualizer_card_path,
                audio_stream_label="2:a",
                input_card_index=card_input_idx,
                total_duration_sec=audio_duration,
                position=visualizer_position,
                in_video_label="comp",
                out_video_label="comp_vis",
                custom_x=visualizer_custom_x,
                custom_y=visualizer_custom_y,
                scale=visualizer_scale
            )
            filters.append(vis_snippet)

    # Step 4: Burn ASS subtitles on top with isolated font directory (avoids 12-font RAM bloat)
    fonts_dir_target = fonts_dir_override or (str(FONTS_DIR) if (FONTS_DIR and FONTS_DIR.exists()) else str(Path(__file__).parent / "assets" / "fonts"))
    if fonts_dir_target and Path(fonts_dir_target).exists():
        fonts_dir_escaped = _ffmpeg_path(str(fonts_dir_target))
        filters.append(
            f"[{comp_stream}]ass=filename='{ass_path_escaped}':fontsdir='{fonts_dir_escaped}'[vout]"
        )
    else:
        filters.append(
            f"[{comp_stream}]ass=filename='{ass_path_escaped}'[vout]"
        )

    return ";\n    ".join(filters)


def render_avatar_video(
    voiceover_path: str,
    clips: List[Dict[str, Any]],
    avatar_path: str,
    ass_subtitle_path: str,
    output_path: Optional[str] = None,
    blur_radius: int = 0,
    dark_tint: float = 0.25,
    speed_multiplier: float = 0.75,
    avatar_position: str = "right",
    progress_callback=None,
    visualizer_enabled: bool = False,
    visualizer_style: str = "glass_pill_cyan",
    visualizer_position: str = "top_center",
    visualizer_title: str = "Stoic Wisdom",
    visualizer_subtitle: str = "Audio Story Series",
    avatar_opacity: float = 1.0,
    avatar_custom_x: Optional[int] = None,
    avatar_custom_y: Optional[int] = None,
    visualizer_custom_x: Optional[int] = None,
    visualizer_custom_y: Optional[int] = None,
    visualizer_scale: float = 1.0,
    visualizer_mode: str = "template",
    custom_vis_video_path: Optional[str] = None,
    chroma_key_color: str = "#00FF00",
    chroma_similarity: float = 0.25,
    chroma_blend: float = 0.08,
    visualizer_width: Optional[int] = None,
    visualizer_height: Optional[int] = None
) -> str:
    """
    Single-pass GPU-accelerated render of the complete avatar storyteller video.

    Args:
        voiceover_path:      Path to processed voiceover MP3/WAV.
        clips:               List of clip dicts from select_local_clips() with 'path'.
        avatar_path:         Path to processed avatar PNG (with stroke, pre-resized).
        ass_subtitle_path:   Path to .ass subtitle file.
        output_path:         Output video path. Auto-generated if None.
        blur_radius:         Background blur strength (0 = no blur, 30 = heavy).
        dark_tint:           Background darkness (0.0 = original, 0.8 = 80% dimmed).
        speed_multiplier:    Stock footage speed (0.5 = half speed, 1.0 = normal).
        avatar_position:     'left', 'right', or 'center'.
        progress_callback:   Optional function(dict) for progress updates.
        visualizer_enabled:  Whether to overlay audio player / visualizer motion graphics.
        visualizer_style:    Preset key (1 of 10 styles).
        visualizer_position: 'top_center', 'top_left', 'top_right', 'bottom_center', or 'none'.
        visualizer_title:    Display title on podcast/minimal cards.
        visualizer_subtitle: Display subtitle on podcast/minimal cards.
        avatar_opacity:      Avatar layer opacity (0.1 to 1.0, default 1.0 = solid).
        avatar_custom_x:     Optional custom X px coordinate on 1920x1080 canvas.
        avatar_custom_y:     Optional custom Y px coordinate on 1920x1080 canvas.
        visualizer_custom_x: Optional custom X px coordinate for audio player card.
        visualizer_custom_y: Optional custom Y px coordinate for audio player card.
        visualizer_scale:    Scaling factor for audio player card (default 1.0).
        visualizer_mode:     'template' or 'video' (custom green-screen video).
        custom_vis_video_path: Path to user's uploaded green-screen visualizer video.
        chroma_key_color:    Hex color to key out (e.g. '#00FF00' or '#000000').
        chroma_similarity:   Tolerance slider (0.05 to 0.50, default 0.25).
        chroma_blend:        Smoothness/blend slider (0.0 to 0.25, default 0.08).
        visualizer_width:    Optional custom width on 1920x1080 canvas.
        visualizer_height:   Optional custom height on 1920x1080 canvas.

    Returns:
        Path to the rendered output video.
    """
    ffmpeg = find_ffmpeg()
    settings = load_settings()

    # Detect GPU encoder
    encoder = detect_gpu_encoder()
    enc_params = get_encoder_params(encoder)
    print(f"[Renderer] Using GPU encoder: {encoder}")

    # Auto-generate output path
    if not output_path:
        ts = int(time.time())
        output_path = str(OUTPUT_DIR / f"avatar_story_{ts}.mp4")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Write concat list for clean, normalized B-Roll clips (guarantees no freezing across mixed files)
    from .local_pool import prepare_clean_concat_clips, write_concat_list
    def _on_clip_prep(msg: str):
        if progress_callback:
            progress_callback({"status": "running", "message": msg, "percent": 28})

    clean_clip_paths = prepare_clean_concat_clips(clips, str(TEMP_DIR), progress_callback=_on_clip_prep)
    concat_list_path = str(TEMP_DIR / "concat_list.txt")
    write_concat_list(clean_clip_paths, concat_list_path)
    print(f"[Renderer] Clean concat list written: {concat_list_path} ({len(clean_clip_paths)} clips)")

    # Get avatar dimensions from the PNG file
    avatar_w, avatar_h = _get_image_dimensions(avatar_path)
    print(f"[Renderer] Avatar dimensions: {avatar_w}×{avatar_h}px, position={avatar_position}, opacity={avatar_opacity}")

    voiceover_duration = _get_file_duration(voiceover_path)

    # Prepare visualizer overlay (Template or Custom Green-Screen Video)
    visualizer_card_path = None
    target_vis_w = 400
    target_vis_h = 200
    use_visualizer = bool(visualizer_enabled and visualizer_position != "none")

    if use_visualizer:
        if visualizer_mode == "video" and custom_vis_video_path and Path(custom_vis_video_path).exists():
            from .local_pool import probe_clip_info
            vis_info = probe_clip_info(custom_vis_video_path)
            orig_w = vis_info.get("width", 640)
            orig_h = vis_info.get("height", 360)
            if visualizer_width and visualizer_height:
                target_vis_w = max(64, min(1920, int(round(float(visualizer_width)))))
                target_vis_h = max(36, min(1080, int(round(float(visualizer_height)))))
            else:
                base_w = 640 if orig_w >= 960 else orig_w
                base_h = int(round(base_w * (orig_h / max(1, orig_w))))
                target_vis_w = max(64, min(1920, int(round(float(base_w) * float(visualizer_scale)))))
                target_vis_h = max(36, min(1080, int(round(float(base_h) * float(visualizer_scale)))))
            # FFmpeg encoders require even dimensions
            target_vis_w = target_vis_w if target_vis_w % 2 == 0 else target_vis_w + 1
            target_vis_h = target_vis_h if target_vis_h % 2 == 0 else target_vis_h + 1
            print(f"[Renderer] 🟢 Custom Video Visualizer ready: {custom_vis_video_path} ({target_vis_w}×{target_vis_h}px, scale={visualizer_scale})")
        else:
            try:
                from .visualizer_generator import generate_player_card_image
                visualizer_card_path = generate_player_card_image(
                    style_key=visualizer_style,
                    title=visualizer_title or "Stoic Wisdom",
                    subtitle=visualizer_subtitle or "Audio Story Series",
                    avatar_image_path=avatar_path,
                    output_dir=str(TEMP_DIR),
                    total_duration_sec=voiceover_duration
                )
                print(f"[Renderer] 🎵 Visualizer card ready: {visualizer_card_path} (Style: {visualizer_style})")
            except Exception as e:
                print(f"[Renderer] ⚠️ Visualizer card generation failed: {e}")
                use_visualizer = False

    # Prepare isolated fonts directory for libass (loads only active font into RAM)
    isolated_fonts_dir = _prepare_isolated_fonts_dir(ass_subtitle_path, TEMP_DIR)

    # Build the filter complex
    filter_complex = _build_filter_complex(
        blur_radius=blur_radius,
        dark_tint=dark_tint,
        speed_multiplier=speed_multiplier,
        avatar_position=avatar_position,
        avatar_width=avatar_w,
        avatar_height=avatar_h,
        ass_subtitle_path=ass_subtitle_path,
        visualizer_enabled=use_visualizer,
        visualizer_style=visualizer_style,
        visualizer_position=visualizer_position,
        visualizer_card_path=visualizer_card_path,
        audio_duration=voiceover_duration,
        card_input_idx=3,
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
        target_vis_w=target_vis_w,
        target_vis_h=target_vis_h,
        fonts_dir_override=isolated_fonts_dir
    )
    print(f"[Renderer] Filter complex:\n    {filter_complex}")

    # Build FFmpeg command inputs
    cmd_inputs = [
        # Input 0: B-Roll via concat demuxer with auto-looping to guarantee video never ends before audio
        "-stream_loop", "-1",
        "-fflags", "+genpts",
        "-f", "concat", "-safe", "0", "-i", concat_list_path,
        # Input 1: Avatar PNG (static image; repeated by overlay eof_action=repeat without RAM leak)
        "-i", avatar_path,
        # Input 2: Voiceover audio
        "-i", voiceover_path,
    ]
    # Input 3: Visualizer card PNG OR Looped Custom Green-Screen Video
    if use_visualizer:
        if visualizer_mode == "video" and custom_vis_video_path and Path(custom_vis_video_path).exists():
            cmd_inputs.extend(["-stream_loop", "-1", "-i", custom_vis_video_path])
        elif visualizer_card_path:
            cmd_inputs.extend(["-i", visualizer_card_path])

    # Safe multithreading: on <= 12GB RAM systems, 2 threads prevents unbounded parallel filter buffering
    try:
        import psutil
        total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        total_ram_gb = 8.0
    safe_threads = 2 if total_ram_gb <= 12.0 else 4

    # Build complete FFmpeg command
    cmd = [
        ffmpeg, "-y",
        "-threads", str(safe_threads),
        *cmd_inputs,
        # Filter graph
        "-filter_complex", filter_complex,
        # Map outputs
        "-map", "[vout]",
        "-map", "2:a:0",
        # Video codec
        "-c:v", enc_params["codec"],
        "-preset", enc_params["preset"],
        *enc_params["extras"],
        "-pix_fmt", enc_params["pix_fmt"],
        # Audio with monotonic A/V sync resampler (guarantees zero drift over 2hr+ timeline)
        "-af", "aresample=async=1000",
        "-c:a", "aac", "-b:a", "192k",
        "-max_muxing_queue_size", "1024",
        # Duration: stop when voiceover ends
        "-shortest",
        # Aspect Ratio & FPS
        "-aspect", "16:9",
        "-r", str(settings.get("fps", 30)),
        output_path
    ]

    print(f"\n[Renderer] ⚡ Starting single-pass GPU render...")
    print(f"[Renderer] Output: {output_path}")
    print(f"[Renderer] Command: {' '.join(cmd[:10])} ... [truncated]")

    if progress_callback:
        progress_callback({"status": "rendering", "message": "Single-pass GPU render started...", "percent": 73})

    start_time = time.time()

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    # Stream stderr for progress parsing
    stderr_lines = []
    voiceover_duration = _get_file_duration(voiceover_path)

    while True:
        line = process.stderr.readline()
        if not line and process.poll() is not None:
            break
        if line:
            stderr_lines.append(line)
            # Parse FFmpeg progress from time= field
            if "time=" in line and progress_callback:
                try:
                    import re
                    match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                    if match and voiceover_duration > 0:
                        h, m, s = match.groups()
                        encoded_secs = int(h) * 3600 + int(m) * 60 + float(s)
                        pct = min(95, int(encoded_secs / voiceover_duration * 90) + 5)
                        elapsed = time.time() - start_time
                        fps_match = re.search(r"fps=\s*(\d+\.?\d*)", line)
                        fps_val = float(fps_match.group(1)) if fps_match else 0
                        progress_callback({
                            "status":   "rendering",
                            "message":  f"Encoding: {int(encoded_secs//60)}:{int(encoded_secs%60):02d} / "
                                        f"{int(voiceover_duration//60)}:{int(voiceover_duration%60):02d} "
                                        f"@ {fps_val:.0f} FPS",
                            "percent":  pct,
                            "elapsed":  round(elapsed, 1),
                        })
                except Exception:
                    pass

    process.wait()
    elapsed = time.time() - start_time

    if process.returncode != 0:
        stderr_output = "".join(stderr_lines[-40:])  # Last 40 lines for debugging
        raise RuntimeError(
            f"FFmpeg render failed (code {process.returncode}):\n{stderr_output}"
        )

    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n[Renderer] ✅ Render complete!")
    print(f"[Renderer]    Output:   {output_path}")
    print(f"[Renderer]    Size:     {output_size_mb:.1f} MB")
    print(f"[Renderer]    Time:     {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"[Renderer]    Encoder:  {encoder}")

    if progress_callback:
        progress_callback({
            "status":  "complete",
            "message": f"✅ Render complete in {elapsed:.0f}s! File: {output_path}",
            "percent": 100,
            "output":  output_path,
            "size_mb": round(output_size_mb, 1),
            "elapsed": round(elapsed, 1),
        })

    return output_path


def _get_image_dimensions(image_path: str) -> tuple[int, int]:
    """Returns (width, height) of an image file."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        pass
    # Fallback via ffprobe
    try:
        from .config import find_ffprobe
        ffprobe = find_ffprobe()
        cmd = [ffprobe, "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", image_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        parts = res.stdout.strip().split("x")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 480, 860  # Default avatar dimensions


def _get_file_duration(file_path: str) -> float:
    """Returns duration of audio/video file in seconds."""
    try:
        from .config import find_ffprobe
        ffprobe = find_ffprobe()
        cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def get_render_estimate(voiceover_duration_sec: float, encoder: str = None) -> dict:
    """
    Estimates render time based on voiceover duration and encoder type.
    Based on benchmarks: NVENC ~120x realtime, QSV ~60x, libx264 ~15x.
    """
    if not encoder:
        encoder = detect_gpu_encoder()

    speedup = {"h264_nvenc": 120, "h264_qsv": 60, "h264_amf": 80, "libx264": 15}.get(encoder, 20)
    estimated_sec = voiceover_duration_sec / speedup

    return {
        "encoder":            encoder,
        "voiceover_duration": round(voiceover_duration_sec, 1),
        "estimated_render_sec": round(estimated_sec, 1),
        "estimated_render_min": round(estimated_sec / 60, 1),
        "speedup_factor":     speedup,
    }
