"""Generate the VoiceWriter app icon and save it to frontend/images/icon.png."""

from pathlib import Path

from PIL import Image, ImageDraw


def generate_icon(output_path: Path, size: int = 256) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark circle background
    margin = size // 16
    draw.ellipse([margin, margin, size - margin, size - margin], fill="#1a1a2e")

    # Microphone body (teal rectangle with rounded top)
    teal = "#028268"
    cx = size // 2
    mic_w = size // 6
    mic_h = size // 3
    mic_top = size // 5
    mic_left = cx - mic_w // 2
    mic_right = cx + mic_w // 2
    mic_bottom = mic_top + mic_h
    radius = mic_w // 2

    draw.rounded_rectangle([mic_left, mic_top, mic_right, mic_bottom], radius=radius, fill=teal)

    # Microphone stand arc
    arc_margin = size // 5
    arc_top = mic_top + mic_h // 3
    arc_bottom = mic_bottom + size // 8
    draw.arc([arc_margin, arc_top, size - arc_margin, arc_bottom], start=0, end=180, fill=teal, width=size // 20)

    # Stand vertical line
    stand_x = cx
    stand_top = mic_bottom + size // 8
    stand_bottom = mic_bottom + size // 5
    draw.line([stand_x, stand_top, stand_x, stand_bottom], fill=teal, width=size // 20)

    # Stand base horizontal line
    base_w = size // 5
    draw.line([stand_x - base_w // 2, stand_bottom, stand_x + base_w // 2, stand_bottom], fill=teal, width=size // 20)

    img.save(output_path, "PNG")
    print(f"Icon saved to {output_path}")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    output = repo_root / "frontend" / "images" / "icon.png"
    generate_icon(output)
