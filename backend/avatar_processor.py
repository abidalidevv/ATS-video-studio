"""
Avatar Storyteller Video Engine — Avatar Processor
Generates a crisp outer stroke / glow border around a portrait PNG so the
avatar stands out distinctly against any video background.

Method: PIL alpha mask dilation (ImageFilter.MaxFilter) — no anti-aliasing artifacts.
Supported stroke colors: White, Gold, Cyan, Black, or any custom RGBA tuple.
"""
import os
import shutil
from pathlib import Path
from typing import Tuple, Optional

try:
    from PIL import Image, ImageFilter, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[AvatarProcessor] ⚠️  Pillow not installed. Install with: pip install Pillow")


# ── Preset Stroke Colors ──────────────────────────────────────────────────────
STROKE_COLOR_PRESETS = {
    "white":  (255, 255, 255, 255),
    "gold":   (255, 215,  60, 255),   # Warm gold
    "cyan":   ( 20, 220, 255, 255),   # Electric cyan
    "black":  (  0,   0,   0, 255),
    "silver": (200, 210, 220, 255),
    "red":    (255,  50,  50, 255),
    "purple": (160,  60, 255, 255),
    "none":   None,                    # No stroke
}

# Standard avatar dimensions (height on 1080p canvas)
# Default height is 920px (anchored to bottom edge), with generous max_width so wide/pointing avatars stay large
AVATAR_HEIGHT_PX = 920    # ~85% of 1080p canvas height, anchored to bottom
AVATAR_WIDTH_PX  = 1100   # Wide enough so pointing/horizontal gestures don't artificially shrink avatar height


def _load_image_as_rgba(image_path: str) -> "Image.Image":
    """Loads any image format and converts to RGBA for processing."""
    img = Image.open(image_path)
    if img.mode != "RGBA":
        # For JPG (no alpha), create full-opacity alpha channel
        img = img.convert("RGBA")
    return img


def _make_avatar_transparent_bg(img: "Image.Image") -> "Image.Image":
    """
    If image has no meaningful transparency (e.g., JPG), attempts to remove
    a white or near-white background. For proper cutouts (PNG with alpha), 
    the existing alpha is preserved.
    """
    data = img.getdata()
    # Check if alpha channel has any transparent pixels
    has_transparency = any(pixel[3] < 250 for pixel in data)
    if has_transparency:
        return img  # Already has alpha cutout, preserve it

    # JPG portrait — convert using luma-based threshold (simple approach)
    # For best results, users should provide proper PNG cutouts
    return img


def add_avatar_stroke(
    input_image_path: str,
    stroke_color: str | Tuple[int, int, int, int] = "white",
    stroke_width: int = 10,
    output_path: Optional[str] = None,
    flip_horizontal: bool = False
) -> str:
    """
    Adds a crisp outer stroke / glow border to a portrait PNG using alpha mask dilation.
    Optionally mirrors the avatar horizontally (for pointing gestures / facing direction).
    
    The stroke is applied OUTSIDE the avatar silhouette so the original portrait
    pixels are never modified. Resulting image is saved as PNG (RGBA).

    Args:
        input_image_path: Path to the portrait image (PNG/JPG).
        stroke_color:     Color name ('white','gold','cyan','black','none') or RGBA tuple.
        stroke_width:     Stroke border width in pixels (recommended: 8–16px).
        output_path:      Where to save the result. Defaults to {name}_stroked.png
                          in the same directory.

    Returns:
        Path to the saved stroked PNG image.
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow library is required. Install: pip install Pillow")

    # Resolve stroke color
    if isinstance(stroke_color, str):
        color_val = STROKE_COLOR_PRESETS.get(stroke_color.lower().strip())
        if color_val is None and stroke_color.lower().strip() != "none":
            color_val = (255, 255, 255, 255)  # Default to white
    else:
        color_val = tuple(stroke_color)

    # Determine output path
    if not output_path:
        inp = Path(input_image_path)
        output_path = str(inp.parent / f"{inp.stem}_stroked.png")

    # Load & normalize to RGBA
    img = _load_image_as_rgba(input_image_path)
    img = _make_avatar_transparent_bg(img)

    # Apply horizontal flip / mirror if requested
    if flip_horizontal:
        img = ImageOps.mirror(img)
        print("[AvatarProcessor] 🔄 Avatar horizontally mirrored (flip_horizontal=True)")

    if color_val is None:
        # No stroke requested — just convert to RGBA PNG
        img.save(output_path, format="PNG")
        return output_path

    # Extract alpha channel
    alpha = img.split()[-1]  # Alpha channel (L mode)

    # Dilate the alpha mask to create a larger silhouette for the stroke
    # MaxFilter with size (2*radius+1) expands bright (white) areas
    kernel_size = stroke_width * 2 + 1
    stroke_mask = alpha.filter(ImageFilter.MaxFilter(kernel_size))

    # Apply a very slight blur to soften jagged stroke edges (anti-alias effect)
    # stroke_mask = stroke_mask.filter(ImageFilter.GaussianBlur(radius=0.8))

    # Create solid-color stroke image using dilated mask
    stroke_layer = Image.new("RGBA", img.size, color_val[:3] + (0,))
    stroke_pixels = list(stroke_layer.getdata())
    mask_pixels   = list(stroke_mask.getdata())
    img_pixels    = list(alpha.getdata())

    # Stroke pixel is visible where dilated mask > 0 but original alpha may be 0
    for i in range(len(stroke_pixels)):
        dilated_alpha = mask_pixels[i]
        if dilated_alpha > 0:
            stroke_pixels[i] = (*color_val[:3], dilated_alpha)
    stroke_layer.putdata(stroke_pixels)

    # Composite: draw stroke layer first, then overlay original portrait on top
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.alpha_composite(stroke_layer)
    result.alpha_composite(img)

    result.save(output_path, format="PNG")
    print(f"[AvatarProcessor] ✅ Stroke applied → {output_path}")
    return output_path


def resize_avatar_for_canvas(
    image_path: str,
    target_height: int = AVATAR_HEIGHT_PX,
    max_width: int = AVATAR_WIDTH_PX,
    output_path: Optional[str] = None
) -> str:
    """
    Resizes the avatar portrait to fit the 1080p canvas proportionally.
    Maintains aspect ratio. Output is always PNG RGBA.

    Args:
        image_path:    Path to the stroked or source portrait image.
        target_height: Desired output height in pixels (default: 860px for 1080p).
        max_width:     Maximum allowed width (default: 480px for left/right placement).
        output_path:   Where to save result. Defaults to {name}_resized.png

    Returns:
        Path to the resized PNG.
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow library is required.")

    if not output_path:
        inp = Path(image_path)
        output_path = str(inp.parent / f"{inp.stem}_resized.png")

    img = _load_image_as_rgba(image_path)
    ow, oh = img.size

    # Scale to target height first, maintain aspect ratio
    scale = target_height / oh
    new_w = int(ow * scale)
    new_h = target_height

    # If width exceeds max_width after height-scale, re-scale from width constraint instead
    if new_w > max_width:
        scale = max_width / ow  # Scale from ORIGINAL width (not already-scaled)
        new_w = max_width
        new_h = int(oh * scale)  # Apply to ORIGINAL height to avoid double-scaling

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)
    img_resized.save(output_path, format="PNG")
    print(f"[AvatarProcessor] ✅ Resized {ow}×{oh} → {new_w}×{new_h} → {output_path}")
    return output_path


def process_avatar(
    input_image_path: str,
    stroke_color: str = "white",
    stroke_width: int = 10,
    target_height: int = AVATAR_HEIGHT_PX,
    max_width: int = AVATAR_WIDTH_PX,
    output_dir: Optional[str] = None,
    flip_horizontal: bool = False
) -> dict:
    """
    Full avatar processing pipeline:
    1. Optionally mirror horizontally (flip_horizontal).
    2. Add outer stroke border.
    3. Resize to fit 1080p canvas (25% width max, height up to 900px anchored to bottom).
    4. Return metadata (dimensions, path).
    """
    inp = Path(input_image_path)
    out_dir = Path(output_dir) if output_dir else inp.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    flip_tag = "_flipped" if flip_horizontal else ""
    stroked_path = str(out_dir / f"{inp.stem}{flip_tag}_stroked.png")
    final_path   = str(out_dir / f"{inp.stem}{flip_tag}_final.png")

    add_avatar_stroke(
        input_image_path=input_image_path,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        output_path=stroked_path,
        flip_horizontal=flip_horizontal
    )

    resize_avatar_for_canvas(
        image_path=stroked_path,
        target_height=target_height,
        max_width=max_width,
        output_path=final_path
    )

    if PIL_AVAILABLE:
        with Image.open(final_path) as final_img:
            w, h = final_img.size
    else:
        w, h = max_width, target_height

    return {
        "path":            final_path,
        "width":           w,
        "height":          h,
        "stroke_color":    stroke_color,
        "stroke_width":    stroke_width,
        "flip_horizontal": flip_horizontal,
    }


# ── CLI Test Entrypoint ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Avatar Processor — Test Runner")
    parser.add_argument("--image", "-i", required=True, help="Input portrait image path")
    parser.add_argument("--stroke-color", "-c", default="white",
                        choices=list(STROKE_COLOR_PRESETS.keys()),
                        help="Stroke border color preset")
    parser.add_argument("--stroke-width", "-w", type=int, default=10,
                        help="Stroke width in pixels (default: 10)")
    parser.add_argument("--height", type=int, default=AVATAR_HEIGHT_PX,
                        help=f"Target avatar height (default: {AVATAR_HEIGHT_PX})")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Avatar Storyteller Engine — Avatar Processor Test")
    print(f"{'='*60}")
    print(f"  Input:        {args.image}")
    print(f"  Stroke Color: {args.stroke_color}")
    print(f"  Stroke Width: {args.stroke_width}px")

    try:
        result = process_avatar(
            input_image_path=args.image,
            stroke_color=args.stroke_color,
            stroke_width=args.stroke_width,
            target_height=args.height
        )
        print(f"\n✅ Avatar processed successfully!")
        print(f"   Output:  {result['path']}")
        print(f"   Size:    {result['width']}×{result['height']}px")
        print(f"   Stroke:  {result['stroke_color']} ({result['stroke_width']}px)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
