"""Generate the favicon set and square logo from the ReadyFix logo files in z-photos/.

    uv run --with pillow tools/make_icons.py

The "RF" mark uses the real R and F letterforms from the logo, so it stays on
brand at sizes where the full wordmark would be unreadable.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
WORDMARK = ROOT / "z-photos" / "Ready-Fix-Favicon.png"
LOGO = ROOT / "z-photos" / "ReadyFix Logo Landscape 3.PNG"
OUT_IMG = ROOT / "img"
RED = (225, 35, 43)
INK = (18, 20, 23)
SS = 1024  # working canvas for the mark


def letter_columns(gray, threshold=170):
    """Return (start, end) x-ranges of each connected run of dark columns."""
    w, h = gray.size
    px = gray.load()
    cols = [any(px[x, y] < threshold for y in range(h)) for x in range(w)]
    runs, start = [], None
    for x, on in enumerate(cols + [False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x))
            start = None
    return runs


def glyph_mask(src, box, height):
    """Crop a letter, scale it up smoothly, and return a crisp alpha mask."""
    crop = src.crop(box)
    alpha = Image.eval(crop, lambda v: 255 - v)
    alpha = alpha.crop(alpha.point(lambda v: 255 if v > 90 else 0).getbbox())
    width = round(alpha.width * height / alpha.height)
    big = alpha.resize((width * 2, height * 2), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
    # Steep contrast curve around the edge midpoint re-sharpens the upscaled letter.
    big = big.point(lambda v: max(0, min(255, (v - 118) * 14)))
    return big.resize((width, height), Image.LANCZOS)


def extract_letters():
    src = Image.open(WORDMARK).convert("L")
    # R is the first letter of the wordmark. F starts where black replaces red:
    # find it by the first column whose dark pixels are unsaturated.
    rgb = Image.open(WORDMARK).convert("RGB")
    w, h = rgb.size
    runs = letter_columns(src)
    px = rgb.load()

    def is_black(x0, x1):
        for x in range(x0, x1):
            for y in range(h):
                r, g, b = px[x, y]
                if r < 90 and g < 90 and b < 90:
                    return True
        return False

    first_black = next(r for r in runs if is_black(*r))
    r_box = (runs[0][0], 0, runs[0][1], h)
    f_box = (first_black[0], 0, first_black[1], h)
    return src, r_box, f_box


def render_mark(bg, r_colour, f_colour, cap_ratio=0.52, radius_ratio=0.0, gap_ratio=0.032):
    src, r_box, f_box = extract_letters()
    cap = round(SS * cap_ratio)
    r_mask = glyph_mask(src, r_box, cap)
    f_mask = glyph_mask(src, f_box, cap)
    gap = round(SS * gap_ratio)
    total = r_mask.width + gap + f_mask.width
    x = (SS - total) // 2
    y = (SS - cap) // 2

    canvas = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    plate = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(plate).rounded_rectangle(
        [0, 0, SS - 1, SS - 1], radius=round(SS * radius_ratio), fill=255)
    canvas.paste(Image.new("RGBA", (SS, SS), bg + (255,)), (0, 0), plate)
    canvas.paste(Image.new("RGBA", r_mask.size, r_colour + (255,)), (x, y), r_mask)
    canvas.paste(Image.new("RGBA", f_mask.size, f_colour + (255,)), (x + r_mask.width + gap, y), f_mask)
    return canvas


VARIANTS = {
    "white": dict(bg=(255, 255, 255), r_colour=RED, f_colour=INK),
    "red": dict(bg=RED, r_colour=(255, 255, 255), f_colour=(255, 255, 255)),
    "ink": dict(bg=INK, r_colour=RED, f_colour=(255, 255, 255)),
}


def square_logo(size=800):
    """Full wordmark on white, for Google's logo structured data and profile uploads."""
    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    width = round(size * 0.86)
    logo = logo.resize((width, round(logo.height * width / logo.width)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    canvas.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    return canvas.convert("RGB")


def write_all(variant="red"):
    mark = render_mark(**VARIANTS[variant])
    opaque = mark.convert("RGB")
    for size, path in (
        (32, ROOT / "favicon-32.png"),
        (48, ROOT / "favicon-48.png"),
        (96, ROOT / "favicon-96.png"),
        (180, ROOT / "apple-touch-icon.png"),
        (192, ROOT / "icon-192.png"),
        (512, ROOT / "icon-512.png"),
    ):
        opaque.resize((size, size), Image.LANCZOS).save(path, optimize=True)
    opaque.resize((48, 48), Image.LANCZOS).save(
        ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    square_logo().save(OUT_IMG / "logo-square.png", optimize=True)
    print("icons written")


if __name__ == "__main__":
    write_all()
