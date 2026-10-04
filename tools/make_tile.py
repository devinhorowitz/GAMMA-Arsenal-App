"""Arsenal's tile for MAC's launcher: the shape of GAMMA's own AK-74 inventory icon as flat art
in the theme's colors, like the tiles beside it: light gray (enabled), amber (highlighted),
white (touched), dim gray (disabled). Same 512x512 four-state atlas as the other app tiles:
e top-left, h top-right, t bottom-left, d bottom-right.

    make_tile.py OUT.dds [PREVIEW.png] [--style fill|outline] [--angle DEG]
"""
import argparse
import os
import struct

from PIL import Image, ImageChops, ImageFilter

ATLAS = r"D:\GAMMA\mods\G.A.M.M.A. Icons\gamedata\textures\ui\ui_icon_equipment.dds"
AK74 = (1000, 0, 1250, 100)          # wpn_ak74: inv_grid 20,0 size 5x2, 50 px a cell
STATES = {                            # quadrant origin -> color
    "e": ((0, 0), (200, 200, 200)),
    "h": ((256, 0), (238, 196, 112)),
    "t": ((0, 256), (255, 255, 255)),
    "d": ((256, 256), (110, 110, 110)),
}
SETTLEMENTS = r"D:\GAMMA\mods\Homestead PDA reskin (dynz, WIP)\gamedata\textures\ui\app_settlement.dds"


def shape(style, angle, fit=212):
    icon = Image.open(ATLAS).crop(AK74).convert("RGBA")
    mask = icon.getchannel("A").point(lambda a: 255 if a > 60 else 0)
    if angle:
        mask = mask.rotate(angle, resample=Image.BICUBIC, expand=True)
    mask = mask.crop(mask.getbbox())
    k = fit / max(mask.size)
    mask = mask.resize((max(1, round(mask.width * k)), max(1, round(mask.height * k))), Image.LANCZOS)
    if style == "outline":
        inner = mask.filter(ImageFilter.MinFilter(9))
        mask = ImageChops.subtract(mask, inner)
    tile = Image.new("L", (256, 256), 0)
    tile.paste(mask, ((256 - mask.width) // 2, (256 - mask.height) // 2))
    return tile


def atlas(mask):
    out = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    for (x, y), color in STATES.values():
        t = Image.new("RGBA", (256, 256), color + (0,))
        t.putalpha(mask)
        out.paste(t, (x, y))
    return out


def write_dds(img, path):
    """Uncompressed A8R8G8B8 DDS, no mipmaps."""
    w, h = img.size
    head = struct.pack("<4s7I44x9I12x4x", b"DDS ", 124, 0x100F, h, w, w * 4, 0, 1,
                       32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, 0x1000)
    assert len(head) == 128
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(head + img.convert("RGBA").tobytes("raw", "BGRA"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("preview", nargs="?")
    ap.add_argument("--style", default="fill", choices=("fill", "outline"))
    ap.add_argument("--angle", type=float, default=0)
    a = ap.parse_args()
    img = atlas(shape(a.style, a.angle))
    write_dds(img, a.out)
    if a.preview:
        # next to the Settlements tile, enabled and highlighted, on the PDA's dark ground
        bg = Image.new("RGBA", (1024, 512), (24, 26, 28, 255))
        bg.alpha_composite(img, (0, 0))
        try:
            s = Image.open(SETTLEMENTS).convert("RGBA").crop((0, 0, 512, 256))
            bg.alpha_composite(s, (512, 0))
        except OSError:
            pass
        bg.save(a.preview)
    print("tile ->", a.out)


if __name__ == "__main__":
    main()
