"""
The festive scene: falling snow, a snowman, a twinkling tree, snowy ground,
the countdown number, and Santa's sleigh flying past now and then.

Everything here is a pure function of time: draw_scene(t, days, options)
gives the same picture for the same t, so the plugin just calls it every
frame with the current time and the animation takes care of itself.

The characters are "pixel art" written as text. Each letter is one LED and
PALETTE says which colour each letter means. A space is see-through. To
change a character, edit its picture below -- no other code needs to change.

Designed for a 128x32 display (two 64x32 panels side by side).
"""

import math
import os
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Colours (red, green, blue), 0-255. On an LED panel (0, 0, 0) is "off".
# ---------------------------------------------------------------------------
PALETTE = {
    "W": (235, 240, 255),  # snow white
    "S": (110, 130, 190),  # snow in shadow (the ground below the surface)
    "s": (150, 165, 215),  # soft shadow on the snowman's right side
    "k": (0, 0, 0),        # coal: eyes, mouth, buttons (LED off)
    "O": (255, 110, 0),    # carrot nose
    "R": (220, 15, 25),    # red: hats, scarf, sleigh
    "G": (20, 170, 50),    # bright green
    "g": (5, 80, 20),      # dark green
    "B": (130, 70, 25),    # brown: twig arms, reindeer
    "b": (70, 35, 10),     # dark brown: antlers, legs
    "T": (90, 45, 15),     # tree trunk
    "Y": (255, 190, 30),   # gold: star, sleigh trim
    "F": (255, 170, 130),  # Santa's face
    "N": (255, 0, 0),      # Rudolph's nose
}

# Tree lights ("o" in the tree picture) cycle through these colours.
LIGHT_COLOURS = [(255, 30, 30), (255, 190, 30), (40, 120, 255), (255, 60, 200)]

DEFAULT_OPTIONS = {
    "number_color": (220, 15, 25),
    "label_color": (255, 190, 30),
    "show_sleigh": True,
    "sleigh_every_seconds": 30.0,
    "snowflakes": 34,
    "show_snowman": True,
    "show_tree": True,
}

SNOWMAN = [
    "       W       ",
    "      RRR      ",
    "     RRRRR     ",
    "     GGGGG     ",
    "    WWWWWWs    ",
    "    WkWWkWs    ",
    "    WWWWOOO    ",
    "    WkkkWWs    ",
    "     WWWWs     ",
    "    RRRRRRR    ",
    " b   WWWRWs  b ",
    "  b WWWWRWWsb  ",
    "   bWWWkWWWs   ",
    "    WWWWWWWs   ",
    "     WWkWWs    ",
    "    WWWWWWWs   ",
    "   WWWWWWWWWs  ",
    "  WWWWWWkWWWWs ",
    "  WWWWWWWWWWWs ",
    "  WWWWWWkWWWWs ",
    "   WWWWWWWWWs  ",
    "    WWWWWWWs   ",
]

TREE = [
    "       Y       ",
    "      YYY      ",
    "       Y       ",
    "       G       ",
    "      GGG      ",
    "     WGoGW     ",
    "      GGg      ",
    "     GGGGg     ",
    "    GoGGGoG    ",
    "   WGGGGGGgW   ",
    "     GGGGg     ",
    "    GGoGGGg    ",
    "   GGGGGGoGg   ",
    "  WGoGGGGGGgW  ",
    "    GGGGGGg    ",
    "   GGGGoGGGg   ",
    "  GoGGGGGGoGg  ",
    " WGGGGGoGGGGgW ",
    "      TTT      ",
    "      TTT      ",
]

# Santa in his sleigh, facing right (he flies left to right).
SLEIGH = [
    "  W        ",
    "  RRR    Y ",
    "   FF    Y ",
    "Y RWWR  RY ",
    "YRRRRRRRRY ",
    " YYYYYYYYYY",
]

# Two reindeer pictures with the legs in different places; swapping between
# them makes the reindeer gallop.
REINDEER_A = [
    "      bb ",
    "      BBn",
    "BBBBBBB  ",
    " b   b   ",
    "b     b  ",
]
REINDEER_B = [
    "      bb ",
    "      BBn",
    "BBBBBBB  ",
    "  b  b   ",
    "  b  b   ",
]


# ---------------------------------------------------------------------------
# Fonts come from LEDMatrix's assets/fonts folder. On the Pi the plugin sits
# two folders below the LEDMatrix root, so we look upwards for it. For
# previews elsewhere, run from the LEDMatrix folder or set LEDMATRIX_DIR.
# ---------------------------------------------------------------------------
def _find_font_dir():
    candidates = []
    if os.environ.get("LEDMATRIX_DIR"):
        candidates.append(Path(os.environ["LEDMATRIX_DIR"]))
    candidates += list(Path(__file__).resolve().parents)
    candidates.append(Path.cwd())
    for base in candidates:
        if (base / "assets" / "fonts" / "PressStart2P-Regular.ttf").exists():
            return base / "assets" / "fonts"
    return None


FONT_DIR = _find_font_dir()


def _font(name, size):
    if FONT_DIR is not None:
        try:
            return ImageFont.truetype(str(FONT_DIR / name), size)
        except OSError:
            pass
    return ImageFont.load_default()


FONTS = {
    "big": _font("PressStart2P-Regular.ttf", 16),
    "small": _font("PressStart2P-Regular.ttf", 8),
    "label": _font("5by7.regular.ttf", 10),
}


def _dim(colour, amount):
    return tuple(int(c * amount) for c in colour)


def draw_sprite(img, picture, x, y, colour_for=None):
    """Copy a text picture onto the image with its top-left corner at (x, y).

    colour_for(letter, column, row) can return a colour to override the
    palette for that one pixel (used for twinkling lights and Rudolph's nose).
    """
    pixels = img.load()
    width, height = img.size
    for row, line in enumerate(picture):
        for col, letter in enumerate(line):
            if letter == " ":
                continue
            px, py = x + col, y + row
            if not (0 <= px < width and 0 <= py < height):
                continue
            colour = colour_for(letter, col, row) if colour_for else None
            pixels[px, py] = colour or PALETTE.get(letter, (255, 0, 255))


# ---------------------------------------------------------------------------
# Snowflakes. Each flake gets fixed random settings once; its position at any
# moment is worked out from the time, so nothing has to be remembered.
# ---------------------------------------------------------------------------
_rng = random.Random(25)
SNOWFLAKES = [
    {
        "x": _rng.random(),
        "y": _rng.random(),
        "speed": _rng.uniform(3.0, 7.0),      # pixels per second downwards
        "sway": _rng.uniform(0.5, 2.0),       # how far it drifts side to side
        "sway_speed": _rng.uniform(0.5, 1.4),
        "phase": _rng.uniform(0, 2 * math.pi),
        "brightness": _rng.choice([0.35, 0.6, 1.0]),
        "big": i % 7 == 0,                    # some larger "+" flakes
    }
    for i in range(100)
]


def draw_snow(img, t, count):
    pixels = img.load()
    width, height = img.size
    fall_height = height + 4
    for flake in SNOWFLAKES[:count]:
        speed = flake["speed"] * (0.6 if flake["big"] else 1.0)
        y = int((flake["y"] * fall_height + speed * t) % fall_height) - 2
        sway = flake["sway"] * math.sin(t * flake["sway_speed"] + flake["phase"])
        x = int(flake["x"] * width + sway) % width
        if 0 <= y < height:
            pixels[x, y] = _dim(PALETTE["W"], flake["brightness"])
        if flake["big"]:
            arm = _dim(PALETTE["W"], 0.3)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    pixels[x + dx, y + dy] = arm


@lru_cache(maxsize=4)
def _ground_tops(width, height):
    """Height of the snow in every column: a gentle rolling drift."""
    tops = []
    for x in range(width):
        bump = math.sin(x * 0.11) + 0.6 * math.sin(x * 0.29 + 1.3)
        tops.append(height - 3 - (1 if bump > 0.9 else 0))
    return tops


def draw_ground(img, t):
    pixels = img.load()
    width, height = img.size
    for x, top in enumerate(_ground_tops(width, height)):
        for y in range(top, height):
            depth = y - top
            pixels[x, y] = PALETTE["W"] if depth == 0 else _dim(PALETTE["S"], 1.0 - 0.25 * depth)
        # The odd glint of light on the snow surface.
        if (x * 7919 + int(t * 3) * 104729) % 97 == 0:
            pixels[x, top] = (255, 255, 255)


def draw_snowman(img, x):
    _, height = img.size
    draw_sprite(img, SNOWMAN, x, height - len(SNOWMAN) - 2)


def draw_tree(img, x, t):
    _, height = img.size
    step = int(t * 2.5)  # how often the lights change

    def lights(letter, col, row):
        if letter != "o":
            return None
        return LIGHT_COLOURS[(col + row + step) % len(LIGHT_COLOURS)]

    top = height - len(TREE) - 1
    draw_sprite(img, TREE, x, top, lights)
    # Make the star shimmer.
    if int(t * 4) % 3 == 0:
        img.load()[x + 7, top + 1] = (255, 255, 200)


@lru_cache(maxsize=16)
def _text_layer(text, font_key, colour, size, centre_x, top_y, snowcapped):
    """Render a line of text onto a see-through layer.

    Snow-capped text gets a white pixel on every top edge plus a dark drop
    shadow. The result is cached because the text only changes once a day,
    which keeps each frame cheap on the Pi.
    """
    width, height = size
    font = FONTS[font_key]
    mask = Image.new("1", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.fontmode = "1"  # crisp pixels, no blurry edges
    left, top, right, _ = font.getbbox(text)
    mask_draw.text((centre_x - (right - left) // 2 - left, top_y - top), text, font=font, fill=1)

    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    if not snowcapped:
        layer.paste(colour + (255,), mask=mask)
        return layer

    m = mask.load()
    pixels = layer.load()
    shadow = _dim(colour, 0.35) + (255,)
    for y in range(height):
        for x in range(width):
            if m[x, y] and x + 1 < width and y + 1 < height and not m[x + 1, y + 1]:
                pixels[x + 1, y + 1] = shadow
    for y in range(height):
        for x in range(width):
            if m[x, y]:
                snow_on_top = y == 0 or not m[x, y - 1]
                pixels[x, y] = (PALETTE["W"] if snow_on_top else colour) + (255,)
    return layer


def draw_text(img, text, font_key, centre_x, top_y, colour, snowcapped=True):
    layer = _text_layer(text, font_key, tuple(colour), img.size, centre_x, top_y, snowcapped)
    img.paste(layer, (0, 0), layer)


def draw_sleigh(img, t, period=30.0, speed=24.0):
    """Santa and three reindeer cross the sky once every `period` seconds.

    They stay in the top 7 rows (the "sky lane") so they never cover the number.
    """
    width, _ = img.size
    team_width = 42
    phase = t % period
    if phase > (width + team_width + 30) / speed:
        return
    x = int(-team_width + speed * phase)
    y = 1 if math.sin(phase * 3.0) > 0 else 0  # gentle bob up and down

    # Sparkly trail behind the sleigh.
    pixels = img.load()
    for k in range(1, 12):
        tx = x - k * 2
        ty = y + 4 + round(math.sin(phase * 3.0 - k * 0.5))
        if 0 <= tx < width and (k * 31 + int(t * 12)) % 3:
            pixels[tx, ty] = _dim(PALETTE["Y"], max(0.15, 1.0 - k / 11))

    draw_sprite(img, SLEIGH, x, y)

    # Short, dim reins from the sleigh to the first reindeer.
    draw = ImageDraw.Draw(img)
    draw.line([(x + 10, y + 1), (x + 13, y + 2)], fill=_dim(PALETTE["Y"], 0.5))

    gallop = int(t * 8)
    for i, rx in enumerate((x + 13, x + 23, x + 33)):
        picture = REINDEER_A if (gallop + i) % 2 == 0 else REINDEER_B
        is_rudolph = i == 2  # the one at the front
        glow = (gallop // 2) % 2 == 0

        def nose(letter, col, row, rudolph=is_rudolph, on=glow):
            if letter != "n":
                return None
            if rudolph:
                return PALETTE["N"] if on else (120, 0, 0)
            return PALETTE["b"]

        draw_sprite(img, picture, rx, y + 1, nose)


def draw_scene(t, days, width=128, height=32, options=None):
    """Draw one frame of the whole scene and return it as an image.

    t is the time in seconds (any steadily increasing clock), days is the
    number of days until Christmas (0 on Christmas Day).
    """
    opts = dict(DEFAULT_OPTIONS)
    opts.update(options or {})
    img = Image.new("RGB", (width, height), (0, 0, 0))

    # The snowman and tree need room either side of the number; on a narrow
    # display (e.g. a single 64x32 panel) they are left out.
    roomy = width >= 112

    draw_snow(img, t, int(opts["snowflakes"]))
    if roomy and opts["show_snowman"]:
        draw_snowman(img, 0)
    if roomy and opts["show_tree"]:
        draw_tree(img, width - 16, t)
    draw_ground(img, t)

    middle = width // 2
    if days == 0:
        draw_text(img, "MERRY", "small", middle, 9, PALETTE["R"])
        draw_text(img, "XMAS!", "small", middle, 19, PALETTE["G"])
    else:
        draw_text(img, str(days), "big", middle, 7, opts["number_color"])
        label = "DAY TO GO" if days == 1 else "DAYS TO GO"
        draw_text(img, label, "label", middle, 22, opts["label_color"], snowcapped=False)

    if opts["show_sleigh"]:
        draw_sleigh(img, t, period=float(opts["sleigh_every_seconds"]))
    return img
