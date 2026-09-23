"""
Avatar Storyteller Video Engine — Adaptive Subtitle Engine
Wraps the 12-preset CapCut subtitle generator with smart margin adaptation
based on avatar position. Captions always occupy the FREE half of the screen.

Position Logic:
  Avatar LEFT   → Captions RIGHT  (MarginL=960, MarginR=60,  Alignment=6)
  Avatar RIGHT  → Captions LEFT   (MarginL=60,  MarginR=960, Alignment=4)
  Avatar CENTER → Bottom Center   (MarginL=60,  MarginR=60,  MarginV=50, Alignment=2)
"""
from typing import List, Dict, Any, Optional
from .subtitle_generator import generate_ass_subtitles, PRESET_STYLES


# Avatar position → subtitle margin config
ADAPTIVE_MARGIN_MAP = {
    "left": {
        "margin_l":  960,   # Push captions to right half
        "margin_r":  60,
        "margin_v":  100,
        "alignment": 6,     # Middle-Right
        "description": "Captions in RIGHT half (Avatar occupies LEFT 40%)"
    },
    "right": {
        "margin_l":  60,    # Push captions to left half
        "margin_r":  960,
        "margin_v":  100,
        "alignment": 4,     # Middle-Left
        "description": "Captions in LEFT half (Avatar occupies RIGHT 40%)"
    },
    "center": {
        "margin_l":  80,
        "margin_r":  80,
        "margin_v":  50,
        "alignment": 2,     # Bottom-Center
        "description": "Captions at BOTTOM CENTER (Avatar occupies center)"
    }
}


def generate_adaptive_subtitles(
    scenes: List[Dict[str, Any]],
    output_path: str,
    avatar_position: str = "right",
    preset_key: str = "capcut_yellow",
    custom_options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates an adaptive .ass subtitle file where caption margins are automatically
    set based on the avatar placement position.

    Args:
        scenes:          List of scene dicts with 'words', 'start', 'end', 'text'.
        output_path:     Where to write the .ass subtitle file.
        avatar_position: 'left', 'right', or 'center'.
        preset_key:      Caption style preset (e.g., 'capcut_yellow', 'dark_stoic').
        custom_options:  Additional subtitle customization dict.

    Returns:
        Path to generated .ass subtitle file.
    """
    pos = str(avatar_position).lower().strip()
    if pos not in ADAPTIVE_MARGIN_MAP:
        print(f"[AdaptiveSubs] Unknown position '{pos}', defaulting to 'right'")
        pos = "right"

    margin_config = ADAPTIVE_MARGIN_MAP[pos]
    print(f"[AdaptiveSubs] Avatar={pos} → {margin_config['description']}")

    # Build merged custom_options with adaptive margins
    opts = dict(custom_options or {})
    opts["margin_l"] = margin_config["margin_l"]
    opts["margin_r"] = margin_config["margin_r"]
    opts["margin_v"] = margin_config["margin_v"]
    # Override alignment based on position
    opts["_adaptive_alignment"] = margin_config["alignment"]

    # Generate using the CapCut subtitle engine
    return _generate_with_adaptive_margins(
        scenes=scenes,
        output_path=output_path,
        preset_key=preset_key,
        custom_options=opts,
        alignment_override=margin_config["alignment"]
    )


def _generate_with_adaptive_margins(
    scenes: List[Dict[str, Any]],
    output_path: str,
    preset_key: str,
    custom_options: dict,
    alignment_override: int
) -> str:
    """
    Internal generator that patches the ASS Style line with adaptive margins
    after calling the base subtitle generator.
    """
    import re

    # Generate base subtitles first
    generate_ass_subtitles(
        scenes=scenes,
        output_path=output_path,
        preset_key=preset_key,
        custom_options=custom_options
    )

    # Patch the Style line to inject adaptive margins and alignment
    margin_l = custom_options.get("margin_l", 60)
    margin_r = custom_options.get("margin_r", 60)
    margin_v = custom_options.get("margin_v", 70)
    alignment = alignment_override

    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse and replace the Default style line
    # ASS Style format: Name, Fontname, Fontsize, ..., Alignment, MarginL, MarginR, MarginV, Encoding
    # Fields: Name(0) Fontname(1) Fontsize(2) PrimaryCol(3) SecondaryCol(4) OutlineCol(5) BackCol(6)
    #         Bold(7) Italic(8) Underline(9) StrikeOut(10) ScaleX(11) ScaleY(12) Spacing(13) Angle(14)
    #         BorderStyle(15) Outline(16) Shadow(17) Alignment(18) MarginL(19) MarginR(20) MarginV(21) Encoding(22)

    def patch_style_line(match):
        line = match.group(0)
        fields = line.split(",")
        if len(fields) >= 23:
            fields[18] = str(alignment)
            fields[19] = str(margin_l * 2)   # ASS uses 2x for PlayResY=1080
            fields[20] = str(margin_r * 2)
            fields[21] = str(margin_v * 2)
        return ",".join(fields)

    # Only patch the Default style line
    content = re.sub(r"^Style: Default,.*$", patch_style_line, content, flags=re.MULTILINE)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[AdaptiveSubs] ✅ Adaptive subtitles written: {output_path}")
    return output_path


def get_available_presets() -> Dict[str, str]:
    """Returns dict of {preset_key: display_name} for all available caption presets."""
    return {k: v.get("name", k) for k, v in PRESET_STYLES.items()}
