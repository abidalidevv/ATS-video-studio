"""
Avatar Storyteller Video Engine — Adaptive Subtitle Engine
Wraps the 12-preset CapCut subtitle generator with smart margin adaptation
based on avatar position. Captions always occupy the FREE half of the screen.

Position Logic:
  Avatar LEFT   → Captions RIGHT  (MarginL=960, MarginR=60,  Alignment=6)
  Avatar RIGHT  → Captions LEFT   (MarginL=60,  MarginR=960, Alignment=4)
  Avatar CENTER → Bottom Center   (MarginL=60,  MarginR=60,  MarginV=50, Alignment=2)
"""
from typing import List, Dict, Any, Optional, Tuple
from .subtitle_generator import generate_ass_subtitles, PRESET_STYLES


# Avatar position → subtitle margin config (75% free area layout)
# Canvas is 1920x1080. Avatar occupies 25% (480px).
# Subtitles occupy remaining 75% (1440px) with bottom alignment.
ADAPTIVE_MARGIN_MAP = {
    "left": {
        "margin_l":  500,   # Leaves 0-480px for avatar, captions centered in right 75%
        "margin_r":  60,
        "margin_v":  75,
        "alignment": 2,     # Bottom Center of the 75% area
        "description": "Captions in RIGHT 75% area (Avatar occupies LEFT 25% bottom)"
    },
    "right": {
        "margin_l":  60,    # Captions centered in left 75% area
        "margin_r":  500,   # Leaves 1440-1920px for avatar
        "margin_v":  75,
        "alignment": 2,     # Bottom Center of the 75% area
        "description": "Captions in LEFT 75% area (Avatar occupies RIGHT 25% bottom)"
    },
    "center": {
        "margin_l":  80,
        "margin_r":  80,
        "margin_v":  50,
        "alignment": 2,     # Bottom-Center
        "description": "Captions at BOTTOM CENTER (Avatar occupies center bottom)"
    }
}


def generate_adaptive_subtitles(
    scenes: List[Dict[str, Any]],
    output_path: str,
    avatar_position: str = "right",
    preset_key: str = "capcut_yellow",
    caption_position: str = "center",
    caption_size: str = "large",
    custom_options: Optional[Dict[str, Any]] = None,
    caption_box: Optional[Dict[str, int]] = None,
) -> str:
    """
    Generates an adaptive .ass subtitle file with customizable alignment, box boundaries, and font size.

    Args:
        scenes:           List of scene dicts with 'words', 'start', 'end', 'text'.
        output_path:      Where to write the .ass subtitle file.
        avatar_position:  'left', 'right', or 'center'.
        preset_key:       Caption style preset (e.g., 'capcut_yellow', 'dark_stoic').
        caption_position: 'center' (Dead Center horizontally & vertically), 'bottom', or 'custom'.
        caption_size:     'large' (68pt, default), 'medium' (52pt), or 'huge' (82pt).
        custom_options:   Additional subtitle customization dict.
        caption_box:      Optional dict {'x': int, 'y': int, 'w': int, 'h': int} on 1920x1080 canvas.

    Returns:
        Path to generated .ass subtitle file.
    """
    pos = str(avatar_position).lower().strip()
    cap_pos = str(caption_position).lower().strip()
    cap_size = str(caption_size).lower().strip()

    # Font size mapping for 1080p canvas (prominent, bold viral captions)
    size_map = {
        "medium": (58, 5.0),
        "large":  (74, 6.0),
        "huge":   (92, 7.5),
    }
    font_size, outline_w = size_map.get(cap_size, (74, 6.0))
    custom_pos_xy = None

    if caption_box and isinstance(caption_box, dict) and "x" in caption_box and "y" in caption_box:
        # User freely dragged & resized the caption box on the interactive Studio Canvas!
        bx = int(round(float(caption_box.get("x", 420))))
        by = int(round(float(caption_box.get("y", 460))))
        bw = max(200, int(round(float(caption_box.get("w", 1080)))))
        bh = max(80, int(round(float(caption_box.get("h", 200)))))

        alignment = 5  # Middle-Center anchor
        margin_l = max(20, bx)
        margin_r = max(20, 1920 - (bx + bw))
        margin_v = 0
        cx = int(bx + bw / 2)
        cy = int(by + bh / 2)
        custom_pos_xy = (cx, cy)
        desc = f"Captions CUSTOM BOX: x={bx}, y={by}, w={bw}, h={bh} -> Anchor=({cx},{cy})"
    elif cap_pos == "center":
        # Dead Center vertically and horizontally (Alignment 5: Middle-Center)
        alignment = 5
        margin_l = 80
        margin_r = 80
        margin_v = 0
        desc = "Captions DEAD CENTER (vertically & horizontally, large text)"
    else:
        # Bottom placement adapted to avatar position
        if pos not in ADAPTIVE_MARGIN_MAP:
            pos = "right"
        m_cfg = ADAPTIVE_MARGIN_MAP[pos]
        alignment = m_cfg["alignment"]
        margin_l = m_cfg["margin_l"]
        margin_r = m_cfg["margin_r"]
        margin_v = m_cfg["margin_v"]
        desc = m_cfg["description"]

    print(f"[AdaptiveSubs] Mode={cap_pos}, Size={cap_size} ({font_size}pt) → {desc}")

    opts = dict(custom_options or {})
    opts["margin_l"] = margin_l
    opts["margin_r"] = margin_r
    opts["margin_v"] = margin_v
    opts["font_size"] = font_size

    return _generate_with_adaptive_margins(
        scenes=scenes,
        output_path=output_path,
        preset_key=preset_key,
        custom_options=opts,
        alignment_override=alignment,
        font_size_override=font_size,
        outline_override=outline_w,
        custom_pos_xy=custom_pos_xy
    )


def _generate_with_adaptive_margins(
    scenes: List[Dict[str, Any]],
    output_path: str,
    preset_key: str,
    custom_options: dict,
    alignment_override: int,
    font_size_override: int = 68,
    outline_override: float = 6.0,
    custom_pos_xy: Optional[Tuple[int, int]] = None
) -> str:
    """
    Internal generator that patches the ASS Style line with adaptive margins,
    alignment, and font size.
    """
    import re

    # Generate base subtitles first
    generate_ass_subtitles(
        scenes=scenes,
        output_path=output_path,
        preset_key=preset_key,
        custom_options=custom_options
    )

    margin_l = custom_options.get("margin_l", 80)
    margin_r = custom_options.get("margin_r", 80)
    margin_v = custom_options.get("margin_v", 0)
    alignment = alignment_override

    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Format: Name(0) Fontname(1) Fontsize(2) ... Spacing(13) Angle(14) BorderStyle(15) Outline(16) Shadow(17) Alignment(18) MarginL(19) MarginR(20) MarginV(21) Encoding(22)
    # IMPORTANT: subtitle_generator.py writes font_size*2.2 and outline*2 in the Style line.
    # We must match those same scaled values so font appears large and bold in output.
    # Margins are pixel values (1:1 with the 1920x1080 canvas, no extra scaling needed).
    ass_font_size = int(round(font_size_override * 2.2))
    ass_outline_w = round(outline_override * 2, 1)

    def patch_style_line(match):
        line = match.group(0)
        fields = line.split(",")
        if len(fields) >= 23:
            fields[2]  = str(ass_font_size)
            fields[16] = f"{ass_outline_w:.1f}"
            fields[18] = str(alignment)
            fields[19] = str(int(margin_l))
            fields[20] = str(int(margin_r))
            fields[21] = str(int(margin_v))
        return ",".join(fields)

    content = re.sub(r"^Style: Default,.*$", patch_style_line, content, flags=re.MULTILINE)

    # Patch Dialogue lines with custom anchor coordinates if user positioned the box
    if custom_pos_xy:
        cx, cy = custom_pos_xy
        pos_tag = "{\\pos(" + str(cx) + "," + str(cy) + ")}"
        def add_pos_to_dialogue(m):
            return m.group(1) + pos_tag + m.group(2)
        content = re.sub(r"^(Dialogue: (?:[^,]*,){9})(.*)$", add_pos_to_dialogue, content, flags=re.MULTILINE)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[AdaptiveSubs] ✅ Adaptive subtitles written: {output_path}")
    return output_path


def get_available_presets() -> Dict[str, str]:
    """Returns dict of {preset_key: display_name} for all available caption presets."""
    return {k: v.get("name", k) for k, v in PRESET_STYLES.items()}
