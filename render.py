#!/usr/bin/env python3
"""Render entry.png — a one-image summary of the day's world news.

Reads headlines.json (the day's stories, gathered from live wire feeds)
and draws a dense newspaper front page at 1024x1024 with PIL.
Also writes image_manifest.json listing exactly what was drawn, so the
entrypoint (main.ts) can verify the artifact against its manifest.

Deterministic: fixed-seed grain, no clocks, no network, no randomness
beyond the seeded grain. Same input -> same pixels -> same PNG bytes.
"""
import hashlib
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 1024
MARGIN = 34
CW = W - 2 * MARGIN
PAPER = (247, 242, 231)
INK = (20, 19, 16)
BODY = (52, 50, 46)
GREY = (96, 92, 84)
RED = (185, 28, 28)
NAVY = (23, 38, 63)

FONT_DIRS = ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/truetype/dejavu"]


def font(candidates, size):
    for name in candidates:
        for d in FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_TITLE = lambda s: font(["NotoSerifDisplay-Black.ttf", "DejaVuSerif-Bold.ttf"], s)
F_SERIF = lambda s: font(["DejaVuSerif-Bold.ttf"], s)
F_SANS = lambda s: font(["DejaVuSans.ttf"], s)
F_SANS_B = lambda s: font(["DejaVuSans-Bold.ttf"], s)
F_SANS_O = lambda s: font(["DejaVuSans-Oblique.ttf", "DejaVuSans.ttf"], s)


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def spaced(text):
    return " ".join(list(text))


def add_grain(img, seed=20261122, amp=6, block=3):
    """Coarse newsprint grain: small seeded noise field, upscaled in blocks.
    Fine per-pixel noise would explode the PNG size; blocks keep the file
    in the few-hundred-KB range while reading as paper texture."""
    rng = np.random.default_rng(seed)
    small = rng.integers(-amp, amp + 1, (H // block + 1, W // block + 1, 1))
    noise = np.repeat(np.repeat(small, block, axis=0), block, axis=1)[:H, :W]
    arr = np.asarray(img).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def halftone(draw, x0, y0, x1, y1, color, max_r=4.6, gap=12):
    row = 0
    y = y0 + gap // 2
    while y < y1:
        x = x0 + gap // 2
        while x < x1:
            t = (x - x0) / max(1, (x1 - x0))
            r = 0.6 + t * max_r * (0.75 + 0.25 * ((row % 3) / 2))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
            x += gap
        y += gap
        row += 1


def story_full(draw, x, y, width, story):
    hf, df = 14, 11.5
    for ln in wrap(draw, story["h"], F_SANS_B(hf), width)[:2]:
        draw.text((x, y), ln, font=F_SANS_B(hf), fill=INK)
        y += hf + 3
    for ln in wrap(draw, story["d"], F_SANS(df), width)[:2]:
        draw.text((x, y), ln, font=F_SANS(df), fill=BODY)
        y += df + 3
    draw.text((x, y), story["s"].upper(), font=F_SANS_B(8.5), fill=GREY)
    return y + 11


def story_short(draw, x, y, width, text):
    f = F_SANS_B(11.5)
    draw.text((x, y + 1), "▸", font=f, fill=RED)
    for ln in wrap(draw, text, f, width - 14)[:2]:
        draw.text((x + 14, y), ln, font=f, fill=INK)
        y += 13.5
    return y + 3


def section(draw, x, y, width, sec):
    draw.rectangle([x, y, x + width, y + 20], fill=sec["color"])
    draw.text((x + 7, y + 3), sec["name"], font=F_SANS_B(12), fill=(255, 255, 255))
    y += 27
    y = story_full(draw, x, y, width, sec["stories"][0])
    for st in sec["stories"][1:3]:
        y = story_short(draw, x, y, width, st["h"])
    return y


def main():
    data = json.load(open(os.path.join(HERE, "headlines.json")))
    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)
    rendered = []

    # ---------- masthead ----------
    draw.text((MARGIN, 12), "ONE IMAGE · ALL THE NEWS THAT FITS", font=F_SANS_B(11), fill=RED)
    title = "THE WORLD TODAY"
    tf = F_TITLE(68)
    tw = draw.textlength(title, font=tf)
    draw.text(((W - tw) / 2, 22), title, font=tf, fill=INK)
    draw.rectangle([MARGIN, 100, W - MARGIN, 104], fill=INK)
    draw.text((MARGIN, 111), data["date_line"].upper(), font=F_SANS_B(12), fill=INK)
    mid = "ONE-IMAGE EDITION"
    mw = draw.textlength(mid, font=F_SANS_B(12))
    draw.text(((W - mw) / 2, 111), mid, font=F_SANS_B(12), fill=INK)
    right = "WIRE REPORTS 21–22 NOV · 03:20 UTC"
    rw = draw.textlength(right, font=F_SANS(10.5))
    draw.text((W - MARGIN - rw, 112), right, font=F_SANS(10.5), fill=GREY)
    draw.rectangle([MARGIN, 130, W - MARGIN, 132], fill=INK)

    # ---------- lead story ----------
    y = 144
    lead = data["lead"]
    text_w = 596
    draw.text((MARGIN, y), spaced(lead["kicker"]), font=F_SANS_B(12), fill=RED)
    y += 20
    for ln in wrap(draw, lead["headline"], F_SERIF(34), text_w):
        draw.text((MARGIN, y), ln, font=F_SERIF(34), fill=INK)
        y += 39
    y += 3
    for ln in wrap(draw, lead["deck"], F_SANS(13), text_w):
        draw.text((MARGIN, y), ln, font=F_SANS(13), fill=BODY)
        y += 16.5
    draw.text((MARGIN, y + 2), lead["source"].upper(), font=F_SANS_B(9.5), fill=GREY)
    rendered.append(lead["headline"])
    lead_bottom = y + 16

    # dateline panel (right of lead)
    px0, py0, px1 = 664, 144, W - MARGIN
    draw.rectangle([px0, py0, px1, py0 + 23], fill=NAVY)
    draw.text((px0 + 9, py0 + 5), "THE DAY'S DATELINES", font=F_SANS_B(11.5), fill=(255, 255, 255))
    datelines = [
        ("WARSAW", "Missiles hit Polish territory"),
        ("MANAMA", "Iranian strike sets site ablaze"),
        ("BALTIC SEA", "Drone strike, cargo ship burns"),
        ("SINALOA", "FBI most-wanted boss captured"),
        ("BRASÍLIA", "Bolsonaro in intensive care"),
        ("BEIJING", "$1.7T AI rout deepens"),
        ("JAKARTA", "EU trade deal signed"),
        ("MERCURY", "BepiColombo enters orbit"),
    ]
    dy = py0 + 32
    for city, note in datelines:
        draw.ellipse([px0 + 2, dy + 4, px0 + 9, dy + 11], fill=RED)
        draw.text((px0 + 16, dy), city, font=F_SANS_B(11.5), fill=INK)
        cwid = draw.textlength(city, font=F_SANS_B(11.5))
        draw.text((px0 + 21 + cwid, dy + 1), "— " + note, font=F_SANS(10.5), fill=BODY)
        dy += 18.5
    halftone(draw, px0, dy + 6, px1, dy + 58, NAVY)

    # ---------- second story ----------
    y2 = max(lead_bottom, dy + 66) + 14
    draw.rectangle([MARGIN, y2 - 8, W - MARGIN, y2 - 6], fill=INK)
    s2 = data["second"]
    draw.text((MARGIN, y2), spaced(s2["kicker"]), font=F_SANS_B(11.5), fill=RED)
    yy = y2 + 19
    for ln in wrap(draw, s2["headline"], F_SERIF(26), CW):
        draw.text((MARGIN, yy), ln, font=F_SERIF(26), fill=INK)
        yy += 32
    for ln in wrap(draw, s2["deck"], F_SANS(13), CW)[:2]:
        draw.text((MARGIN, yy), ln, font=F_SANS(13), fill=BODY)
        yy += 16.5
    draw.text((MARGIN, yy + 1), s2["source"].upper(), font=F_SANS_B(9), fill=GREY)
    rendered.append(s2["headline"])
    yy += 10

    # ---------- numbers ticker ----------
    ny = yy + 6
    draw.rectangle([MARGIN, ny, W - MARGIN, ny + 2], fill=INK)
    nums = "  ·  ".join(f"{a} {b}" for a, b in data["numbers"])
    ticker = "THE DAY IN NUMBERS — " + nums
    ty = ny + 7
    for ln in wrap(draw, ticker, F_SANS_B(11.5), CW)[:2]:
        draw.text((MARGIN, ty), ln, font=F_SANS_B(11.5), fill=NAVY)
        ty += 15
    draw.rectangle([MARGIN, ty + 2, W - MARGIN, ty + 4], fill=INK)

    # ---------- sections grid (3 x 2) ----------
    gy = ty + 16
    col_w = (CW - 28) // 3
    xs = [MARGIN, MARGIN + col_w + 14, MARGIN + 2 * (col_w + 14)]
    rows = [["WORLD", "US & POLITICS", "BUSINESS & TECH"],
            ["SCIENCE & HEALTH", "SPORT", "CULTURE & ODDS"]]
    secs = {s["name"]: s for s in data["sections"]}
    for r, row in enumerate(rows):
        ends = []
        for i, name in enumerate(row):
            ends.append(section(draw, xs[i], gy, col_w, secs[name]))
            rendered.extend(st["h"] for st in secs[name]["stories"][:3])
        gy = max(ends) + (8 if r == 0 else 6)
        if r == 0:
            draw.rectangle([MARGIN, gy - 8, W - MARGIN, gy - 7], fill=(198, 192, 174))

    # ---------- in brief strip ----------
    by = gy + 2
    draw.text((MARGIN, by), spaced("AROUND THE WORLD IN BRIEF"), font=F_SANS_B(11), fill=RED)
    by += 16
    briefs = data["briefs"][:8]
    bw = (CW - 3 * 12) // 4
    for i, (tag, text) in enumerate(briefs):
        bx = MARGIN + (i % 4) * (bw + 12)
        byy = by + (i // 4) * 28
        draw.text((bx, byy), tag, font=F_SANS_B(10), fill=NAVY)
        tw2 = draw.textlength(tag, font=F_SANS_B(10))
        for j, ln in enumerate(wrap(draw, text, F_SANS(10), bw - tw2 - 6)):
            draw.text((bx + tw2 + 5, byy + j * 12.5), ln, font=F_SANS(10), fill=BODY)
        rendered.append(f"{tag}: {text}")
    bottom = by + 2 * 28

    # ---------- footer ----------
    fy = max(bottom + 8, 958)
    draw.rectangle([MARGIN, fy, W - MARGIN, fy + 2], fill=INK)
    for j, ln in enumerate(wrap(draw, "SOURCES: " + data["sources"], F_SANS(9.5), CW)[:2]):
        draw.text((MARGIN, fy + 7 + j * 12), ln, font=F_SANS(9.5), fill=GREY)
    foot2 = "One image, drawn by an AI agent from the day's wire reports · Saturday 22 November 2026 · Headlines as reported by the outlets named"
    draw.text((MARGIN, fy + 33), foot2, font=F_SANS_O(9.5), fill=GREY)

    img = add_grain(img)
    out = os.path.join(HERE, "entry.png")
    img.save(out, optimize=True)
    digest = hashlib.sha256(open(out, "rb").read()).hexdigest()
    manifest = {
        "file": "entry.png",
        "width": W,
        "height": H,
        "bytes": os.path.getsize(out),
        "sha256": digest,
        "date": "2026-11-22",
        "items_rendered": len(rendered),
        "headlines": rendered,
    }
    with open(os.path.join(HERE, "image_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print("wrote", out, manifest["bytes"], "bytes; items:", len(rendered),
          "; sections+briefs bottom:", bottom, "; footer:", fy)


if __name__ == "__main__":
    main()
