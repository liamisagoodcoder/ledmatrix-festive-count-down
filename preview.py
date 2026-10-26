"""
Preview the festive scene on your computer, no LED panel needed.

Run it from your LEDMatrix folder (that's where the fonts live), or set
LEDMATRIX_DIR to that folder:

    python3 ~/ledmatrix-festive-countdown/preview.py             # 24 days to go
    python3 ~/ledmatrix-festive-countdown/preview.py --days 0    # Christmas Day

Writes preview/still.png and preview/animation.gif next to this file. Each
LED is drawn as a round dot so it looks close to the real panel.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

import festive_scene
from festive_scene import draw_scene

HERE = Path(__file__).resolve().parent


def led_look(frame, scale=6):
    """Blow the frame up and turn each pixel into a round LED dot."""
    big = frame.resize((frame.width * scale, frame.height * scale), Image.NEAREST)
    dot = Image.new("L", (scale, scale), 0)
    ImageDraw.Draw(dot).ellipse((0, 0, scale - 2, scale - 2), fill=255)
    mask = Image.new("L", big.size, 0)
    for x in range(0, big.width, scale):
        for y in range(0, big.height, scale):
            mask.paste(dot, (x, y))
    out = Image.new("RGB", big.size, (12, 12, 14))
    out.paste(big, (0, 0), mask)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=24)
    parser.add_argument("--seconds", type=float, default=14.0)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--out", type=Path, default=HERE / "preview")
    args = parser.parse_args()

    if festive_scene.FONT_DIR is None:
        print("Warning: LEDMatrix fonts not found -- run this from your LEDMatrix "
              "folder or set LEDMATRIX_DIR. Using a fallback font.")

    args.out.mkdir(exist_ok=True)
    # The sleigh repeats every clip length here so it shows up in a short clip.
    options = {"sleigh_every_seconds": args.seconds}
    frames = [
        led_look(draw_scene(i / args.fps, args.days, options=options))
        for i in range(int(args.seconds * args.fps))
    ]
    led_look(draw_scene(4.2, args.days, options=options)).save(args.out / "still.png")
    frames[0].save(
        args.out / "animation.gif",
        save_all=True,
        append_images=frames[1:],
        duration=1000 // args.fps,
        loop=0,
    )
    print(f"Wrote {args.out / 'still.png'} and {args.out / 'animation.gif'}")


if __name__ == "__main__":
    main()
