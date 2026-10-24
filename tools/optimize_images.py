"""Resize and compress photos for the website.

Writes <name>-<width>.webp and <name>-<width>.jpg into img/ for each width.

    uv run --with pillow tools/optimize_images.py <source image> <name> [--widths 800,1600] [--crop 16:9]

Example (a new job photo):
    uv run --with pillow tools/optimize_images.py "~/Downloads/IMG_1234.jpg" drywall-ceiling-patch --widths 600,1200
"""
import argparse
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "img"


def crop_to_ratio(im, ratio):
    w, h = (int(x) for x in ratio.split(":"))
    target = w / h
    cur = im.width / im.height
    if cur > target:  # too wide: trim sides
        new_w = int(im.height * target)
        left = (im.width - new_w) // 2
        return im.crop((left, 0, left + new_w, im.height))
    new_h = int(im.width / target)
    top = (im.height - new_h) // 2
    return im.crop((0, top, im.width, top + new_h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("name")
    ap.add_argument("--widths", default="800,1600")
    ap.add_argument("--crop", help="aspect ratio such as 16:9")
    args = ap.parse_args()

    im = ImageOps.exif_transpose(Image.open(Path(args.source).expanduser())).convert("RGB")
    if args.crop:
        im = crop_to_ratio(im, args.crop)
    OUT.mkdir(exist_ok=True)
    for width in (int(w) for w in args.widths.split(",")):
        resized = im if im.width <= width else im.resize(
            (width, round(im.height * width / im.width)), Image.LANCZOS)
        base = OUT / f"{args.name}-{width}"
        resized.save(base.with_suffix(".webp"), "WEBP", quality=78, method=6)
        resized.save(base.with_suffix(".jpg"), "JPEG", quality=80, optimize=True, progressive=True)
        print(f"{base.name}: {resized.width}x{resized.height}")


if __name__ == "__main__":
    main()
