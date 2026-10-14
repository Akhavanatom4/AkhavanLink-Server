# AkhavanLink — Created by Alireza Akhavan (علیرضا اخوان)
"""Render the AkhavanLink logo to assets/icon.ico and the UI favicon (needs Pillow + numpy)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # supersampled canvas


def render(size):
    k = S / 64.0
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(15 * k), fill=(7, 10, 20, 255))
    mask = Image.new("L", (S, S), 0)
    m = ImageDraw.Draw(mask)
    w = int(4.6 * k)

    def stroke(a, b):
        m.line([(a[0] * k, a[1] * k), (b[0] * k, b[1] * k)], fill=255, width=w)
        for p in (a, b):
            m.ellipse((p[0] * k - w / 2, p[1] * k - w / 2, p[0] * k + w / 2, p[1] * k + w / 2), fill=255)
    stroke((32, 12), (14, 52)); stroke((32, 12), (50, 52)); stroke((22, 38), (42, 38))
    yy, xx = np.mgrid[0:S, 0:S]
    t = ((xx + yy) / (2.0 * S)).astype(np.float32)
    stops = [(0.0, (55, 220, 255)), (0.55, (141, 107, 255)), (1.0, (255, 79, 210))]
    rgb = np.zeros((S, S, 3), np.float32)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        sel = (t >= t0) & (t <= t1)
        f = ((t - t0) / (t1 - t0))[sel][:, None]
        rgb[sel] = np.array(c0) * (1 - f) + np.array(c1) * f
    grad = Image.fromarray(rgb.astype(np.uint8), "RGB")
    img.paste(grad, (0, 0), mask)
    for p in ((32, 12), (14, 52), (50, 52)):
        r = 4.8 * k
        d.ellipse((p[0] * k - r, p[1] * k - r, p[0] * k + r, p[1] * k + r), fill=(255, 255, 255, 255))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    (ROOT / "assets").mkdir(exist_ok=True)
    big = render(256)
    big.save(ROOT / "assets" / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    big.save(ROOT / "akhavanlink" / "client" / "web" / "icon.png")
    big.save(ROOT / "assets" / "icon.png")
    print("icons written")
