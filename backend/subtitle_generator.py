import os
from pathlib import Path
from typing import List, Dict, Any

PRESET_STYLES = {
    "capcut_yellow": {
        "name": "CapCut Viral Yellow",
        "font_name": "Montserrat",
        "fallback_font": "Arial Black",
        "font_size": 24,
        "primary_color": "&H00FFFFFF",     # BGR: White
        "highlight_color": "&H0010E0FF",   # BGR: Warm Yellow / Gold (#FFE010)
        "outline_color": "&H00000000",     # BGR: Solid Black outline
        "outline_width": 4,
        "shadow_color": "&H80000000",
        "shadow_dist": 2,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,                     # Bottom Center
        "margin_v": 70
    },
    "hormozi_green": {
        "name": "Hormozi Punch Green",
        "font_name": "Impact",
        "fallback_font": "Arial Black",
        "font_size": 26,
        "primary_color": "&H00FFFFFF",     # White
        "highlight_color": "&H0014FF39",   # Neon Green (#39FF14)
        "outline_color": "&H00000000",     # Black
        "outline_width": 4.5,
        "shadow_color": "&HA0000000",
        "shadow_dist": 3,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 80
    },
    "neon_cyber": {
        "name": "Neon Cyber Glow",
        "font_name": "Montserrat",
        "fallback_font": "Arial",
        "font_size": 24,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H00FFFF00",   # Electric Cyan (#00FFFF)
        "outline_color": "&H00401000",     # Deep Dark Blue outline
        "outline_width": 3.5,
        "shadow_color": "&H60FFFF00",     # Cyan Glow
        "shadow_dist": 4,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 70
    },
    "red_fire": {
        "name": "Red Fire Accent",
        "font_name": "Trebuchet MS",
        "fallback_font": "Impact",
        "font_size": 24,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H003333FF",   # Punchy Red (#FF3333)
        "outline_color": "&H00000000",
        "outline_width": 4,
        "shadow_color": "&H80000000",
        "shadow_dist": 2,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 70
    },
    "clean_minimal": {
        "name": "Clean Minimalist",
        "font_name": "Inter",
        "fallback_font": "Segoe UI",
        "font_size": 22,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H00E0E0E0",   # Soft Gray highlight
        "outline_color": "&H00151515",
        "outline_width": 2,
        "shadow_color": "&H80000000",
        "shadow_dist": 1,
        "bold": 1,
        "uppercase": False,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 60
    },
    "mrbeast_punch": {
        "name": "MrBeast Punchy Gold",
        "font_name": "Bangers",
        "fallback_font": "Impact",
        "font_size": 28,
        "primary_color": "&H0010E0FF",     # Warm Gold/Yellow
        "highlight_color": "&H003333FF",   # Punchy Red
        "outline_color": "&H00000000",
        "outline_width": 5.5,
        "shadow_color": "&H90000000",
        "shadow_dist": 3,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 75
    },
    "ali_abdaal": {
        "name": "Ali Abdaal Aesthetic",
        "font_name": "Poppins",
        "fallback_font": "Inter",
        "font_size": 22,
        "primary_color": "&H00FFFFFF",     # Clean Crisp White
        "highlight_color": "&H004DA9FF",   # Warm Amber / Orange (#FFA94D)
        "outline_color": "&H001A1A1A",
        "outline_width": 2.5,
        "shadow_color": "&H60000000",
        "shadow_dist": 1.5,
        "bold": 1,
        "uppercase": False,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 65
    },
    "iman_gadzhi": {
        "name": "Iman Gadzhi Luxury",
        "font_name": "Cinzel",
        "fallback_font": "Georgia",
        "font_size": 23,
        "primary_color": "&H00EAFEF4",     # Ivory Warm White
        "highlight_color": "&H0037AFD4",   # Champagne Gold (#D4AF37)
        "outline_color": "&H00000000",
        "outline_width": 3.5,
        "shadow_color": "&HA0000000",
        "shadow_dist": 2.5,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 70
    },
    "tiktok_violet": {
        "name": "TikTok Viral Violet",
        "font_name": "Archivo Black",
        "fallback_font": "Arial Black",
        "font_size": 25,
        "primary_color": "&H00852AFF",     # Hot Pink / Magenta (#FF2A85)
        "highlight_color": "&H00FF00BD",   # Electric Violet (#BD00FF)
        "outline_color": "&H00000000",
        "outline_width": 4.5,
        "shadow_color": "&H80FF00BD",
        "shadow_dist": 3,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 75
    },
    "podcast_pill": {
        "name": "Vox / Podcast Box",
        "font_name": "Outfit",
        "fallback_font": "Montserrat",
        "font_size": 22,
        "primary_color": "&H00FFFFFF",     # White
        "highlight_color": "&H0000E6FF",   # Sharp Amber Yellow (#FFE600)
        "outline_color": "&H00111111",
        "outline_width": 3,
        "shadow_color": "&HC0000000",
        "shadow_dist": 2,
        "bold": 1,
        "uppercase": False,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 65
    },
    "streamer_lime": {
        "name": "Streamer High-Voltage",
        "font_name": "Luckiest Guy",
        "fallback_font": "Impact",
        "font_size": 26,
        "primary_color": "&H0000FFA6",     # Lime Green (#A6FF00)
        "highlight_color": "&H00FFF000",   # Electric Cyan (#00F0FF)
        "outline_color": "&H00000000",
        "outline_width": 5,
        "shadow_color": "&H90000000",
        "shadow_dist": 3,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 75
    },
    "dark_stoic": {
        "name": "Stoic Slate Wisdom",
        "font_name": "Oswald",
        "fallback_font": "Bebas Neue",
        "font_size": 26,
        "primary_color": "&H00FFFFFF",     # White
        "highlight_color": "&H00F88C81",   # Slate Indigo (#818CF8)
        "outline_color": "&H000F0F14",
        "outline_width": 4,
        "shadow_color": "&HA0000000",
        "shadow_dist": 2,
        "bold": 1,
        "uppercase": True,
        "animation": "active_word_highlight",
        "alignment": 2,
        "margin_v": 70
    }
}

CALLOUT_STYLES = {
    "badge_yellow": {
        "name": "Badge Viral Yellow",
        "font_name": "Montserrat",
        "font_size": 28,
        "primary_color": "&H0010E0FF",     # Warm Gold/Yellow (#FFE010)
        "secondary_color": "&H000000FF",
        "outline_color": "&H00050508",     # Deep black edge
        "back_color": "&HA00E0E14",        # Translucent dark charcoal box
        "bold": 1,
        "border_style": 3,                 # Opaque background box
        "outline_width": 6.0,
        "shadow_dist": 0.0,
        "alignment": 8,                    # Top Center
        "margin_v": 75
    },
    "badge_cyan": {
        "name": "Badge Electric Cyan",
        "font_name": "Montserrat",
        "font_size": 28,
        "primary_color": "&H00FFFF00",     # Electric Cyan (#00FFFF)
        "secondary_color": "&H000000FF",
        "outline_color": "&H000F0500",
        "back_color": "&HA0150A05",        # Deep navy box
        "bold": 1,
        "border_style": 3,
        "outline_width": 6.0,
        "shadow_dist": 0.0,
        "alignment": 8,
        "margin_v": 75
    },
    "badge_dark": {
        "name": "Badge Minimal Dark",
        "font_name": "Inter",
        "font_size": 26,
        "primary_color": "&H00FFFFFF",     # Crisp White
        "secondary_color": "&H000000FF",
        "outline_color": "&H002A2A2A",
        "back_color": "&HB008080C",        # Midnight glass box
        "bold": 1,
        "border_style": 3,
        "outline_width": 5.5,
        "shadow_dist": 0.0,
        "alignment": 8,
        "margin_v": 75
    }
}


def hex_to_ass_color(hex_str: str, alpha: int = 0) -> str:
    """Converts #RRGGBB hex string to ASS &HAABBGGRR format."""
    clean = hex_str.strip().lstrip('#')
    if len(clean) == 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
        return f"&H{alpha:02X}{b}{g}{r}"
    return "&H00FFFFFF"


def format_ass_time(seconds: float) -> str:
    """Formats float seconds to ASS timestamp H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_ass_subtitles(
    scenes: List[Dict[str, Any]],
    output_path: str,
    preset_key: str = "capcut_yellow",
    custom_options: Dict[str, Any] = None
) -> str:
    """
    Generates a stylized .ass subtitle file with CapCut kinetic active-word highlighting
    and optional top-third callout badge cards.
    """
    norm_key = str(preset_key or "capcut_yellow").lower().replace("-", "_")
    preset = PRESET_STYLES.get(norm_key, PRESET_STYLES.get(preset_key, PRESET_STYLES["capcut_yellow"])).copy()
    if custom_options:
        if "font_size" in custom_options:
            preset["font_size"] = int(custom_options["font_size"])
        if "font_name" in custom_options and custom_options["font_name"]:
            preset["font_name"] = custom_options["font_name"]
        if "primary_color" in custom_options:
            preset["primary_color"] = hex_to_ass_color(custom_options["primary_color"])
        if "highlight_color" in custom_options:
            preset["highlight_color"] = hex_to_ass_color(custom_options["highlight_color"])
        if "outline_color" in custom_options:
            preset["outline_color"] = hex_to_ass_color(custom_options["outline_color"])
        if "outline_width" in custom_options:
            preset["outline_width"] = float(custom_options["outline_width"])
        if "uppercase" in custom_options:
            preset["uppercase"] = bool(custom_options["uppercase"])
        if "margin_v" in custom_options:
            preset["margin_v"] = int(custom_options["margin_v"])

    font_family = preset.get("font_name", "Arial Black")
    font_size = preset.get("font_size", 24)
    primary_c = preset.get("primary_color", "&H00FFFFFF")
    highlight_c = preset.get("highlight_color", "&H0010E0FF")
    outline_c = preset.get("outline_color", "&H00000000")
    outline_w = preset.get("outline_width", 4)
    shadow_c = preset.get("shadow_color", "&H80000000")
    shadow_d = preset.get("shadow_dist", 2)
    bold = 1 if preset.get("bold", 1) else 0
    align = preset.get("alignment", 2)
    margin_v = preset.get("margin_v", 70)
    uppercase = preset.get("uppercase", True)
    letter_spacing = float(custom_options.get("letter_spacing", 1.0) if custom_options else 1.0)
    word_spacing = float(custom_options.get("word_spacing", 6.0) if custom_options else 6.0)

    # Callout badge settings
    callouts_enabled = bool(custom_options.get("callouts_enabled", False) if custom_options else False)
    callout_style_key = str(custom_options.get("callout_style", "badge_yellow") if custom_options else "badge_yellow").lower().replace("-", "_")
    callout_preset = CALLOUT_STYLES.get(callout_style_key, CALLOUT_STYLES["badge_yellow"])

    c_font = callout_preset["font_name"]
    c_size = callout_preset["font_size"] * 2.0
    c_primary = callout_preset["primary_color"]
    c_outline = callout_preset["outline_color"]
    c_back = callout_preset["back_color"]
    c_border_style = callout_preset["border_style"]
    c_outline_w = callout_preset["outline_width"]
    c_margin_v = callout_preset["margin_v"]

    # Word separator based on word_spacing parameter
    if word_spacing >= 16:
        word_separator = " \\h\\h "
    elif word_spacing >= 10:
        word_separator = "  "
    else:
        word_separator = " "

    header = f"""[Script Info]
Title: VideoGen CapCut Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{font_size * 2.2:.0f},{primary_c},&H000000FF,{outline_c},{shadow_c},{bold},0,0,0,100,100,{letter_spacing * 2:.1f},0,1,{outline_w * 2:.1f},{shadow_d * 2:.1f},{align},50,50,{margin_v * 2},1
Style: Callout,{c_font},{c_size:.0f},{c_primary},&H000000FF,{c_outline},{c_back},1,0,0,0,100,100,1.2,0,{c_border_style},{c_outline_w:.1f},0,8,60,60,{c_margin_v * 2},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []

    # Inject Callout Dialogue lines if callouts enabled
    if callouts_enabled:
        for scene in scenes:
            callout = scene.get("callout_text")
            if callout and str(callout).strip():
                c_start = format_ass_time(float(scene.get("start", 0)))
                c_end = format_ass_time(float(scene.get("end", 0)))
                c_clean = str(callout).strip().replace('{', '(').replace('}', ')').upper()
                anim = r"{\fad(180,180)\t(0,120,\fscx106\fscy106)\t(120,240,\fscx100\fscy100)}"
                dialogue_lines.append(f"Dialogue: 1,{c_start},{c_end},Callout,,0,0,0,,{anim}{c_clean}")

    for scene in scenes:
        words = scene.get("words", [])
        if not words:
            # Fallback if no word level timestamps: display whole sentence for scene duration
            t_start = format_ass_time(float(scene.get("start", 0)))
            t_end = format_ass_time(float(scene.get("end", 0)))
            stext = scene.get("text", "").replace('{', '(').replace('}', ')')
            if uppercase:
                stext = stext.upper()
            dialogue_lines.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{stext}")
            continue

        # Group words into chunks of 3-5 words for optimal TikTok/CapCut/YouTube Shorts readability
        word_chunks = _chunk_words(words, max_chunk_words=5)

        for chunk in word_chunks:
            chunk_start = chunk[0]["start"]
            chunk_end = chunk[-1]["end"]

            # For each word in the chunk, create a continuous sub-interval where that word is actively highlighted
            for active_idx, active_word in enumerate(chunk):
                # Start: if first word, start at chunk_start; otherwise at word start
                t_start_val = chunk_start if active_idx == 0 else active_word["start"]
                # End: extend to the start of the next word to eliminate inter-word flicker gaps!
                if active_idx < len(chunk) - 1:
                    t_end_val = chunk[active_idx + 1]["start"]
                else:
                    t_end_val = max(active_word["end"], chunk_end + 0.15)

                w_start = format_ass_time(t_start_val)
                w_end = format_ass_time(t_end_val)

                # Build styled line
                line_parts = []
                for idx, w in enumerate(chunk):
                    raw_word = w["word"].strip().replace('{', '(').replace('}', ')')
                    if uppercase:
                        raw_word = raw_word.upper()

                    if idx == active_idx:
                        # Active word highlighted with accent color (and subtle scale pop if kinetic animation is enabled)
                        anim_style = str((custom_options or {}).get("animation", "word_bounce")).lower().strip()
                        if anim_style == "none":
                            line_parts.append(f"{{\\c{highlight_c}}}{raw_word}{{\\c{primary_c}}}")
                        else:
                            line_parts.append(f"{{\\c{highlight_c}\\fscx108\\fscy108\\b1}}{raw_word}{{\\c{primary_c}\\fscx100\\fscy100\\b{bold}}}")
                    else:
                        line_parts.append(raw_word)

                dialogue_text = word_separator.join(line_parts)
                dialogue_lines.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{dialogue_text}")

    content = header + "\n".join(dialogue_lines) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def _chunk_words(words: List[Dict[str, Any]], max_chunk_words: int = 5) -> List[List[Dict[str, Any]]]:
    """Splits a list of words into readable sentence chunks (3-5 words each)."""
    chunks = []
    current = []
    for w in words:
        current.append(w)
        # Break on punctuation or max chunk size
        text = w.get("word", "")
        if len(current) >= max_chunk_words or text.endswith(('.', '!', '?', ',', ';')):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks
