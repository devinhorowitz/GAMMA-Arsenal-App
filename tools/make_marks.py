"""Arsenal's marks, textures/ui/arsenal/ui_marks.dds: a 128x64 atlas in white, which the script
tints (textures_descr/ui_arsenal.xml names the parts):

- arsenal_glow (0,0, 128x20): a new list row's glow. Even over the left half, where the name
  is, fading toward the right end; soft at the top and bottom. The page pulses its alpha.
- arsenal_badge_1, _2, _3 (y 32, 20 high; 20, 28 and 36 wide at x 0, 24 and 56): the badge on
  the launcher tile for a count of 1, 2 or 3 digits, a circle or a pill with a slightly darker
  rim, so the tint reads as a raised button.

    make_marks.py OUT.dds [PREVIEW.png]
"""
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_tile import write_dds  # noqa: E402

SS = 8                      # supersampling for the badges' edges
BADGES = ((0, 20), (24, 28), (56, 36))
BADGE_Y, BADGE_H = 32, 20


def glow(w=128, h=20):
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    px = img.load()
    for y in range(h):
        v = math.sin(math.pi * (y + 0.5) / h)
        for x in range(w):
            t = x / (w - 1)
            across = 1.0 if t < 0.5 else 1.0 - 0.8 * ((t - 0.5) / 0.5) ** 1.2
            px[x, y] = (255, 255, 255, int(round(255 * v * across)))
    return img


def pill(w, h=BADGE_H, rim_shade=170):
    big = Image.new("RGBA", (w * SS, h * SS), (rim_shade, rim_shade, rim_shade, 0))
    d = ImageDraw.Draw(big)
    r = h * SS // 2
    d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r, fill=(rim_shade, rim_shade, rim_shade, 255))
    rim = int(1.2 * SS)
    d.rounded_rectangle((rim, rim, w * SS - 1 - rim, h * SS - 1 - rim), radius=r - rim, fill=(255, 255, 255, 255))
    return big.resize((w, h), Image.LANCZOS)


def atlas():
    img = Image.new("RGBA", (128, 64), (255, 255, 255, 0))
    img.alpha_composite(glow(), (0, 0))
    for x, w in BADGES:
        img.alpha_composite(pill(w), (x, BADGE_Y))
    return img


def tinted(part, rgb, alpha=255):
    r, g, b, a = part.split()
    k = alpha / 255
    return Image.merge("RGBA", (r.point(lambda v: v * rgb[0] // 255), g.point(lambda v: v * rgb[1] // 255),
                                b.point(lambda v: v * rgb[2] // 255), a.point(lambda v: int(v * k))))


def main():
    out = sys.argv[1]
    img = atlas()
    write_dds(img, out)
    if len(sys.argv) > 2:
        # as the page and the launcher tint them, at 3x on the PDA's dark ground
        bg = Image.new("RGBA", (300, 110), (24, 26, 28, 255))
        for i, a in enumerate((40, 110)):
            bg.alpha_composite(tinted(img.crop((0, 0, 128, 20)), (238, 196, 112), a).resize((250, 20)), (10, 10 + 26 * i))
        for x, w in BADGES:
            bg.alpha_composite(tinted(img.crop((x, BADGE_Y, x + w, BADGE_Y + BADGE_H)), (200, 36, 30)), (10 + x * 2, 70))
        bg.resize((900, 330), Image.NEAREST).save(sys.argv[2])
    print("marks ->", out)


if __name__ == "__main__":
    main()
