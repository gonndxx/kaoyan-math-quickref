"""Generate the application ICO asset."""

from pathlib import Path

from PIL import Image, ImageDraw


def make_icon(size: int) -> Image.Image:
    scale = size / 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = round(16 * scale)
    radius = round(58 * scale)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=(39, 103, 232, 255),
    )
    # A geometric sigma stays legible down to the 16 px tray size.
    points = [
        (round(177 * scale), round(61 * scale)),
        (round(80 * scale), round(61 * scale)),
        (round(139 * scale), round(128 * scale)),
        (round(79 * scale), round(195 * scale)),
        (round(179 * scale), round(195 * scale)),
    ]
    draw.line(points, fill=(255, 255, 255, 255), width=max(2, round(24 * scale)), joint="curve")
    return image


def main() -> None:
    output = Path(__file__).resolve().parent / "assets" / "app.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    base = make_icon(256)
    base.save(output, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(output)


if __name__ == "__main__":
    main()
