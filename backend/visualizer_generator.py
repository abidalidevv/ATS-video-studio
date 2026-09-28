"""
Avatar Storyteller Video Engine — Dynamic Audio Player & Visualizer Generator

Generates dynamic, audio-reactive motion graphics overlays in 10 customizable styles:
  1. glass_pill_cyan     — Glassmorphic dark pill with cyan glow wave & progress bar
  2. cosmic_orbit        — Glowing cosmic orb pod with white audio wave & controls
  3. sunset_vibes        — Sunset gradient pill with pink-orange-yellow soundwave
  4. podcast_doc         — Space documentary card with cover art & live equalizer bars
  5. cyber_avatar        — Circular avatar halo pod with crisp white wave & controls
  6. neon_cyber          — Magenta-cyan gradient border with neon violet waveform
  7. apple_minimal       — Modern frosted light card with emerald green visualizer
  8. retro_vinyl         — Vintage vinyl disc player with crimson red audio wave
  9. particle_aura       — Floating transparent minimalist blue wave with center play button
  10. studio_monochrome  — Modern frosted white pill with matte charcoal soundwave

Supports placements:
  - top_center (Default)
  - top_left
  - top_right
  - bottom_center
  - none (Disabled)
"""
import math
import os
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ── Presets Configuration ───────────────────────────────────────────────────────
VISUALIZER_PRESETS: Dict[str, Dict[str, Any]] = {
    "glass_pill_cyan": {
        "id": "glass_pill_cyan",
        "name": "Glassmorphism Cyan",
        "emoji": "🌊",
        "desc": "Dark frosted glass pill with electric cyan soundwave & progress bar",
        "width": 720,
        "height": 116,
        "type": "waves",            # showwaves cline
        "color": "0x00d2ff",
        "vis_x": 112, "vis_y": 20, "vis_w": 496, "vis_h": 46,
        "prog_x": 112, "prog_y": 78, "prog_w": 496, "prog_color": "0x00d2ff@0.95",
        "time_y": 85, "time_color": "0x88ccff",
    },
    "cosmic_orbit": {
        "id": "cosmic_orbit",
        "name": "Cosmic Orbit Pod",
        "emoji": "🪐",
        "desc": "Neon blue planetary ring with crisp white audio waveform & playback icons",
        "width": 740,
        "height": 116,
        "type": "waves",
        "color": "0xffffff",
        "vis_x": 116, "vis_y": 20, "vis_w": 470, "vis_h": 46,
        "prog_x": 116, "prog_y": 78, "prog_w": 470, "prog_color": "0x00d2ff@0.9",
        "time_y": 85, "time_color": "0xaaddff",
    },
    "sunset_vibes": {
        "id": "sunset_vibes",
        "name": "Sunset Waveform",
        "emoji": "🌅",
        "desc": "Warm dark glass capsule with glowing pink-orange-yellow soundwave",
        "width": 720,
        "height": 116,
        "type": "waves",
        "color": "0xff5533",
        "vis_x": 112, "vis_y": 20, "vis_w": 496, "vis_h": 46,
        "prog_x": 112, "prog_y": 78, "prog_w": 496, "prog_color": "0xff6622@0.95",
        "time_y": 85, "time_color": "0xffaa88",
    },
    "podcast_doc": {
        "id": "podcast_doc",
        "name": "Documentary Card",
        "emoji": "🎙️",
        "desc": "Rich podcast card with story cover art, title & dynamic equalizer bars",
        "width": 720,
        "height": 124,
        "type": "freqs",           # showfreqs vertical bars
        "color": "0x00d2ff|0xffffff",
        "vis_x": 510, "vis_y": 24, "vis_w": 185, "vis_h": 48,
        "prog_x": 118, "prog_y": 88, "prog_w": 490, "prog_color": "0x00d2ff@0.95",
        "time_y": 95, "time_color": "0x99ccff",
    },
    "cyber_avatar": {
        "id": "cyber_avatar",
        "name": "Avatar Halo Pod",
        "emoji": "🧑‍🚀",
        "desc": "User avatar in glowing neon pod with clean white audio wave & controls",
        "width": 740,
        "height": 116,
        "type": "waves",
        "color": "0xffffff",
        "vis_x": 118, "vis_y": 20, "vis_w": 465, "vis_h": 46,
        "prog_x": 118, "prog_y": 78, "prog_w": 465, "prog_color": "0x38bdf8@0.95",
        "time_y": 85, "time_color": "0xbae6fd",
    },
    "neon_cyber": {
        "id": "neon_cyber",
        "name": "Neon Cyber Pill",
        "emoji": "⚡",
        "desc": "Glowing magenta-to-cyan gradient border with violet pulse soundwave",
        "width": 720,
        "height": 116,
        "type": "waves",
        "color": "0xbf55ec",
        "vis_x": 112, "vis_y": 20, "vis_w": 496, "vis_h": 46,
        "prog_x": 112, "prog_y": 78, "prog_w": 496, "prog_color": "0x00e5ff@0.95",
        "time_y": 85, "time_color": "0xd8b4fe",
    },
    "apple_minimal": {
        "id": "apple_minimal",
        "name": "Modern Minimal Light",
        "emoji": "🍏",
        "desc": "Frosted clean light card with story thumbnail & emerald green visualizer",
        "width": 720,
        "height": 124,
        "type": "freqs",
        "color": "0x10b981|0x34d399",
        "vis_x": 510, "vis_y": 24, "vis_w": 150, "vis_h": 48,
        "prog_x": 118, "prog_y": 88, "prog_w": 490, "prog_color": "0x10b981@0.95",
        "time_y": 95, "time_color": "0x64748b",
    },
    "retro_vinyl": {
        "id": "retro_vinyl",
        "name": "Retro Vinyl Player",
        "emoji": "💿",
        "desc": "Grooved vinyl record disc on left, crimson red soundwave & heart icon",
        "width": 750,
        "height": 116,
        "type": "waves",
        "color": "0xff3355",
        "vis_x": 175, "vis_y": 20, "vis_w": 450, "vis_h": 46,
        "prog_x": 175, "prog_y": 78, "prog_w": 450, "prog_color": "0xff3355@0.95",
        "time_y": 85, "time_color": "0xff99aa",
    },
    "particle_aura": {
        "id": "particle_aura",
        "name": "Particle Aura Wave",
        "emoji": "✨",
        "desc": "Floating frameless luminous blue audio wave with glowing center play orb",
        "width": 780,
        "height": 116,
        "type": "waves",
        "color": "0x00d2ff",
        "vis_x": 30, "vis_y": 20, "vis_w": 720, "vis_h": 48,
        "prog_x": 60, "prog_y": 84, "prog_w": 660, "prog_color": "0x00d2ff@0.95",
        "time_y": 91, "time_color": "0x88ccff",
    },
    "studio_monochrome": {
        "id": "studio_monochrome",
        "name": "Studio Monochrome",
        "emoji": "🎚️",
        "desc": "Frosted smoke-white pill with matte black play circle & dark charcoal wave",
        "width": 720,
        "height": 116,
        "type": "waves",
        "color": "0x1e293b",
        "vis_x": 112, "vis_y": 20, "vis_w": 490, "vis_h": 46,
        "prog_x": 112, "prog_y": 78, "prog_w": 490, "prog_color": "0x1e293b@0.90",
        "time_y": 85, "time_color": "0x64748b",
    },
}


def _get_system_fonts() -> Tuple[Any, Any, Any]:
    """Finds crisp TrueType fonts on Windows."""
    for fpath in ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if Path(fpath).exists():
            try:
                font_bold  = ImageFont.truetype(fpath, 16)
                font_small = ImageFont.truetype(fpath, 12)
                font_tiny  = ImageFont.truetype(fpath, 11)
                return font_bold, font_small, font_tiny
            except Exception:
                pass
    def_font = ImageFont.load_default()
    return def_font, def_font, def_font


def generate_player_card_image(
    style_key: str = "glass_pill_cyan",
    title: str = "Stoic Wisdom",
    subtitle: str = "Audio Story Series",
    avatar_image_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    total_duration_sec: float = 0.0
) -> str:
    """
    Renders high-resolution transparent PNG base card for the chosen audio player style.
    """
    preset = VISUALIZER_PRESETS.get(style_key, VISUALIZER_PRESETS["glass_pill_cyan"])
    W, H   = preset["width"], preset["height"]

    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_bold, font_small, font_tiny = _get_system_fonts()

    # ── Style 1: Glassmorphism Cyan ───────────────────────────────────────────
    if style_key == "glass_pill_cyan":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(10, 16, 28, 220), outline=(0, 210, 255, 110), width=2)
        # Play button circle on left
        cx, cy, r = 55, 54, 28
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(16, 26, 44, 255), outline=(0, 220, 255, 190), width=2)
        draw.polygon([(cx-8, cy-12), (cx-8, cy+12), (cx+11, cy)], fill=(255, 255, 255, 250))
        # Empty progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 30))

    # ── Style 2: Cosmic Orbit Pod ─────────────────────────────────────────────
    elif style_key == "cosmic_orbit":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(8, 12, 22, 230), outline=(0, 160, 255, 80), width=2)
        # Glowing orb / planet circle on left
        cx, cy, r = 58, 55, 34
        draw.ellipse([(cx-r-3, cy-r-3), (cx+r+3, cy+r+3)], outline=(0, 210, 255, 140), width=3)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(14, 24, 45, 255), outline=(0, 120, 255, 200), width=2)
        draw.ellipse([(cx-12, cy-12), (cx+16, cy+16)], fill=(0, 180, 255, 120))
        # Right controls: ⏮ ⏸ ⏭
        ctrl_y = 52
        _draw_prev_icon(draw, W - 145, ctrl_y, color=(200, 220, 255, 220))
        _draw_pause_circle(draw, W - 110, ctrl_y, r=16, color=(0, 210, 255, 220))
        _draw_next_icon(draw, W - 75, ctrl_y, color=(200, 220, 255, 220))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 35))

    # ── Style 3: Sunset Waveform ──────────────────────────────────────────────
    elif style_key == "sunset_vibes":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(18, 10, 16, 225), outline=(255, 90, 50, 120), width=2)
        # Glowing orange/pink play button
        cx, cy, r = 55, 54, 28
        draw.ellipse([(cx-r-2, cy-r-2), (cx+r+2, cy+r+2)], outline=(255, 60, 100, 100), width=2)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(32, 14, 24, 255), outline=(255, 90, 40, 220), width=2)
        draw.polygon([(cx-8, cy-12), (cx-8, cy+12), (cx+11, cy)], fill=(255, 255, 255, 250))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 35))

    # ── Style 4: Documentary Podcast Card ─────────────────────────────────────
    elif style_key == "podcast_doc":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=22, fill=(12, 16, 26, 230), outline=(255, 255, 255, 35), width=2)
        # Left story cover box
        art_box = [(16, 16), (102, 102)]
        draw.rounded_rectangle(art_box, radius=14, fill=(20, 32, 52, 255), outline=(0, 210, 255, 90), width=1)
        _embed_thumbnail(img, avatar_image_path, art_box)
        # Typography
        draw.text((118, 22), title[:26], font=font_bold, fill=(255, 255, 255, 240))
        draw.text((118, 46), subtitle[:32], font=font_small, fill=(150, 175, 205, 210))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 40))

    # ── Style 5: Cyber Avatar Halo Pod ────────────────────────────────────────
    elif style_key == "cyber_avatar":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(10, 16, 26, 225), outline=(56, 189, 248, 100), width=2)
        # Glowing circular avatar pod on left
        cx, cy, r = 58, 55, 36
        draw.ellipse([(cx-r-3, cy-r-3), (cx+r+3, cy+r+3)], outline=(56, 189, 248, 160), width=3)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(18, 28, 48, 255), outline=(255, 255, 255, 120), width=1)
        _embed_circle_avatar(img, avatar_image_path, cx, cy, r)
        # Right controls: ⏮ ⏸ ⏭
        ctrl_y = 52
        _draw_prev_icon(draw, W - 135, ctrl_y, color=(220, 235, 255, 220))
        _draw_pause_circle(draw, W - 100, ctrl_y, r=16, color=(56, 189, 248, 220))
        _draw_next_icon(draw, W - 65, ctrl_y, color=(220, 235, 255, 220))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 35))

    # ── Style 6: Neon Cyber Pill ──────────────────────────────────────────────
    elif style_key == "neon_cyber":
        # Dual-tone neon border
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(14, 10, 24, 230), outline=(191, 85, 236, 150), width=2)
        # Glowing multi-ring neon pause button
        cx, cy, r = 55, 54, 30
        draw.ellipse([(cx-r-3, cy-r-3), (cx+r+3, cy+r+3)], outline=(0, 229, 255, 140), width=2)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(26, 16, 44, 255), outline=(191, 85, 236, 220), width=3)
        _draw_pause_bars(draw, cx, cy, color=(255, 255, 255, 240))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 35))

    # ── Style 7: Modern Minimal Light (Apple/Spotify) ─────────────────────────
    elif style_key == "apple_minimal":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=22, fill=(248, 250, 252, 240), outline=(226, 232, 240, 255), width=2)
        art_box = [(16, 16), (102, 102)]
        draw.rounded_rectangle(art_box, radius=14, fill=(226, 232, 240, 255), outline=(203, 213, 225, 255), width=1)
        _embed_thumbnail(img, avatar_image_path, art_box)
        draw.text((118, 22), title[:26], font=font_bold, fill=(15, 23, 42, 240))
        draw.text((118, 46), subtitle[:32], font=font_small, fill=(100, 116, 139, 210))
        # Options dots
        for dx in [0, 8, 16]:
            draw.ellipse([(W-45+dx, 48), (W-41+dx, 52)], fill=(148, 163, 184, 200))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(0, 0, 0, 25))

    # ── Style 8: Retro Vinyl Player ───────────────────────────────────────────
    elif style_key == "retro_vinyl":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(16, 14, 20, 230), outline=(255, 51, 85, 110), width=2)
        # Vinyl record disc with grooves
        cx, cy, r = 58, 55, 42
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(18, 18, 22, 255), outline=(45, 45, 55, 255), width=1)
        for dr in [35, 28, 21, 14]:
            draw.ellipse([(cx-dr, cy-dr), (cx+dr, cy+dr)], outline=(32, 32, 40, 180), width=1)
        # Vinyl center red label
        draw.ellipse([(cx-12, cy-12), (cx+12, cy+12)], fill=(225, 29, 72, 255))
        draw.ellipse([(cx-3, cy-3), (cx+3, cy+3)], fill=(255, 255, 255, 255))
        # Play button circle next to vinyl
        px, py, pr = 126, 54, 22
        draw.ellipse([(px-pr, py-pr), (px+pr, py+pr)], fill=(28, 24, 32, 255), outline=(255, 51, 85, 200), width=2)
        draw.polygon([(px-6, py-9), (px-6, py+9), (px+8, py)], fill=(255, 255, 255, 250))
        # Heart icon on right
        _draw_heart_icon(draw, W - 45, 52, color=(255, 51, 85, 220))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(255, 255, 255, 35))

    # ── Style 9: Particle Aura Wave ───────────────────────────────────────────
    elif style_key == "particle_aura":
        # Minimalist transparent background (no heavy card box)
        cx, cy, r = W // 2, 44, 28
        # Central glowing play button
        draw.ellipse([(cx-r-5, cy-r-5), (cx+r+5, cy+r+5)], outline=(0, 210, 255, 90), width=2)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(12, 22, 42, 240), outline=(0, 220, 255, 220), width=2)
        draw.polygon([(cx-8, cy-11), (cx-8, cy+11), (cx+10, cy)], fill=(255, 255, 255, 255))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 2)], radius=2, fill=(255, 255, 255, 35))

    # ── Style 10: Studio Monochrome ───────────────────────────────────────────
    elif style_key == "studio_monochrome":
        draw.rounded_rectangle([(2, 2), (W-2, H-2)], radius=32, fill=(240, 244, 248, 235), outline=(203, 213, 225, 255), width=2)
        # Matte black play button
        cx, cy, r = 55, 54, 28
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(20, 24, 33, 255), outline=(15, 23, 42, 255), width=1)
        draw.polygon([(cx-7, cy-11), (cx-7, cy+11), (cx+10, cy)], fill=(255, 255, 255, 255))
        # EQ sliders icon on far right
        _draw_eq_icon(draw, W - 60, 52, color=(100, 116, 139, 220))
        # Progress track
        draw.rounded_rectangle([(preset["prog_x"], preset["prog_y"]), (preset["prog_x"] + preset["prog_w"], preset["prog_y"] + 3)], radius=2, fill=(0, 0, 0, 30))

    # Pre-render clean timecodes in TrueType font
    if "prog_w" in preset and "time_y" in preset:
        is_light = style_key in ["apple_minimal", "studio_monochrome"]
        t_col = (100, 116, 139, 210) if is_light else (150, 190, 230, 200)
        tot_m = int(max(0.0, total_duration_sec) // 60)
        tot_s = int(max(0.0, total_duration_sec) % 60)
        dur_str = f"{tot_m:02d}:{tot_s:02d}" if total_duration_sec > 0 else "08:35"
        draw.text((preset["prog_x"], preset["time_y"]), "00:00", font=font_tiny, fill=t_col)
        draw.text((preset["prog_x"] + preset["prog_w"] - 32, preset["time_y"]), dur_str, font=font_tiny, fill=t_col)

    # Output path
    if not output_dir:
        output_dir = Path("./data/temp")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = str(out_dir / f"player_card_{style_key}.png")
    img.save(out_file)
    return out_file


# ── Helper Drawing Functions ────────────────────────────────────────────────────
def _draw_prev_icon(draw: ImageDraw.ImageDraw, x: int, y: int, color=(255, 255, 255, 200)):
    draw.rectangle([(x-8, y-7), (x-6, y+7)], fill=color)
    draw.polygon([(x+6, y-7), (x+6, y+7), (x-4, y)], fill=color)

def _draw_next_icon(draw: ImageDraw.ImageDraw, x: int, y: int, color=(255, 255, 255, 200)):
    draw.rectangle([(x+6, y-7), (x+8, y+7)], fill=color)
    draw.polygon([(x-6, y-7), (x-6, y+7), (x+4, y)], fill=color)

def _draw_pause_circle(draw: ImageDraw.ImageDraw, x: int, y: int, r: int = 15, color=(0, 210, 255, 220)):
    draw.ellipse([(x-r, y-r), (x+r, y+r)], outline=color, width=2)
    draw.rectangle([(x-5, y-6), (x-2, y+6)], fill=color)
    draw.rectangle([(x+2, y-6), (x+5, y+6)], fill=color)

def _draw_pause_bars(draw: ImageDraw.ImageDraw, cx: int, cy: int, color=(255, 255, 255, 240)):
    draw.rounded_rectangle([(cx-7, cy-10), (cx-3, cy+10)], radius=2, fill=color)
    draw.rounded_rectangle([(cx+3, cy-10), (cx+7, cy+10)], radius=2, fill=color)

def _draw_heart_icon(draw: ImageDraw.ImageDraw, x: int, y: int, color=(255, 51, 85, 220)):
    # Simple aesthetic heart representation
    draw.ellipse([(x-8, y-7), (x, y+1)], fill=color)
    draw.ellipse([(x, y-7), (x+8, y+1)], fill=color)
    draw.polygon([(x-8, y-2), (x+8, y-2), (x, y+8)], fill=color)

def _draw_eq_icon(draw: ImageDraw.ImageDraw, x: int, y: int, color=(100, 116, 139, 220)):
    # Three equalizer sliders
    for dx, knob_y in [(-8, -2), (0, 3), (8, -4)]:
        draw.line([(x+dx, y-8), (x+dx, y+8)], fill=color, width=2)
        draw.rectangle([(x+dx-3, y+knob_y-2), (x+dx+3, y+knob_y+2)], fill=color)

def _embed_thumbnail(canvas: Image.Image, img_path: Optional[str], box: list):
    if not img_path or not Path(img_path).exists():
        return
    try:
        w = box[1][0] - box[0][0]
        h = box[1][1] - box[0][1]
        thumb = Image.open(img_path).convert("RGBA")
        thumb = thumb.resize((w, h), Image.Resampling.LANCZOS)
        # Rounded mask
        mask = Image.new("L", (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (w, h)], radius=12, fill=255)
        canvas.paste(thumb, (box[0][0], box[0][1]), mask)
    except Exception as e:
        print(f"[Visualizer] Thumbnail embed error: {e}")

def _embed_circle_avatar(canvas: Image.Image, img_path: Optional[str], cx: int, cy: int, r: int):
    if not img_path or not Path(img_path).exists():
        return
    try:
        size = r * 2
        thumb = Image.open(img_path).convert("RGBA")
        thumb = thumb.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([(0, 0), (size, size)], fill=255)
        canvas.paste(thumb, (cx - r, cy - r), mask)
    except Exception as e:
        print(f"[Visualizer] Circle avatar embed error: {e}")


# ── Filter Complex Builder ──────────────────────────────────────────────────────
def get_visualizer_overlay_coords(
    position: str,
    widget_w: int,
    widget_h: int,
    custom_x: Optional[int] = None,
    custom_y: Optional[int] = None
) -> str:
    """Calculates overlay coordinates for the chosen placement on 1920x1080 canvas."""
    if custom_x is not None and custom_y is not None:
        return f"x={int(round(float(custom_x)))}:y={int(round(float(custom_y)))}"
    if position == "top_center":
        return f"x=(W-{widget_w})/2:y=35"
    elif position == "top_left":
        return f"x=60:y=35"
    elif position == "top_right":
        return f"x=W-{widget_w}-60:y=35"
    elif position == "bottom_center":
        return f"x=(W-{widget_w})/2:y=H-{widget_h}-35"
    else:
        return f"x=(W-{widget_w})/2:y=35"


def build_visualizer_filter_snippet(
    style_key: str,
    card_png_path: str,
    audio_stream_label: str,
    input_card_index: int,
    total_duration_sec: float,
    position: str = "top_center",
    in_video_label: str = "comp",
    out_video_label: str = "vout_vis",
    custom_x: Optional[int] = None,
    custom_y: Optional[int] = None,
    scale: float = 1.0
) -> Tuple[str, str]:
    """
    Constructs the single-pass FFmpeg filtergraph snippet for the audio player widget.

    Returns:
        (filter_snippet, out_label)
    """
    preset = VISUALIZER_PRESETS.get(style_key, VISUALIZER_PRESETS["glass_pill_cyan"])
    font_path = "C\\:/Windows/Fonts/segoeui.ttf"
    if not Path("C:/Windows/Fonts/segoeui.ttf").exists():
        font_path = "C\\:/Windows/Fonts/arial.ttf"

    total_dur = max(1.0, float(total_duration_sec))
    tot_m = int(total_dur // 60)
    tot_s = int(total_dur % 60)
    total_str = f"{tot_m:02d}\\:{tot_s:02d}"

    vis_type = preset.get("type", "waves")
    color    = preset.get("color", "0x00d2ff")
    vx, vy   = preset["vis_x"], preset["vis_y"]
    vw, vh   = preset["vis_w"], preset["vis_h"]
    px, py   = preset["prog_x"], preset["prog_y"]
    pw       = preset["prog_w"]
    prog_col = preset.get("prog_color", "0x00d2ff@0.95")
    time_y   = preset.get("time_y", 85)
    time_col = preset.get("time_color", "0xaaddff")

    # Timecode X positions
    time1_x = px
    time2_x = px + pw - 38

    lines = []

    # 1. Generate audio-reactive visualizer stream from input audio
    if vis_type == "freqs":
        # Equalizer vertical bars
        lines.append(
            f"[{audio_stream_label}]showfreqs=s={vw}x{vh}:mode=bar:ascale=cbrt:fscale=log:"
            f"colors={color}:win_size=1024,format=rgba,colorkey=black:0.25:0.1[raw_vis]"
        )
    else:
        # Symmetrical centered audio waveform
        lines.append(
            f"[{audio_stream_label}]showwaves=s={vw}x{vh}:mode=cline:scale=cbrt:draw=full:"
            f"colors={color}:rate=30,format=rgba,colorkey=black:0.25:0.1[raw_vis]"
        )

    # 2. Overlay visualizer onto the card base PNG
    lines.append(
        f"[{input_card_index}:v][raw_vis]overlay=x={vx}:y={vy}[w_c1]"
    )

    # 3. Dynamic animated progress bar fill (drawbox with t/duration expression)
    lines.append(
        f"[w_c1]drawbox=x={px}:y={py}:w='min({pw}, {pw}*(t/{total_dur:.2f}))':h=3:"
        f"color={prog_col}:t=fill[player_widget]"
    )

    final_widget_stream = "player_widget"
    actual_w = preset["width"]
    actual_h = preset["height"]

    # 4. Optional scaling if user resized widget on Studio Canvas
    if abs(scale - 1.0) > 0.02:
        actual_w = int(round(actual_w * float(scale)))
        actual_h = int(round(actual_h * float(scale)))
        actual_w = actual_w if actual_w % 2 == 0 else actual_w + 1
        actual_h = actual_h if actual_h % 2 == 0 else actual_h + 1
        lines.append(
            f"[player_widget]scale={actual_w}:{actual_h}:flags=fast_bilinear[player_widget_scaled]"
        )
        final_widget_stream = "player_widget_scaled"

    # 5. Overlay complete player widget onto the video composition
    coords = get_visualizer_overlay_coords(
        position=position,
        widget_w=actual_w,
        widget_h=actual_h,
        custom_x=custom_x,
        custom_y=custom_y
    )
    lines.append(
        f"[{in_video_label}][{final_widget_stream}]overlay={coords}:eof_action=repeat[{out_video_label}]"
    )

    snippet = ";\n    ".join(lines)
    return snippet, out_video_label
