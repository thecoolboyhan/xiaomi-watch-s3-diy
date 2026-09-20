#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenerate image_0002.png (static track layer) with ROUNDED-CAP arcs.
Fixes the "底层进度条不够圆润" part of bug #4.

Visual content of v60 image_0002.png is exactly 4 dim track arcs + 4 icons.
We redraw the 4 arcs with rounded caps (same ARC_R=206, ARC_W=11, dim gray
(60,60,70)) and reuse gen_assets_v3.draw_icon for the icons.
"""
import sys, math
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
from PIL import Image, ImageDraw

OUT = "/Users/admin/ai/watch/project/ws3/images/image_0002.png"
CANVAS = 464
C = (232, 232)
ARC_R = 206
ARC_W = 11
SCALE = 4
TRACK = (60, 60, 70, 255)

# (name, s, e, icon_angle, icon)
ARCS = [("temp", 20, 70, 79, "sun"),
        ("battery", 110, 160, 169, "bolt"),
        ("calories", 200, 250, 191, "flame"),
        ("steps", 290, 340, 281, "shoe")]

def web_to_pil(theta):
    return theta - 90.0

def endpoint(theta, sc):
    # cap must sit on the band centreline (PIL strokes inward) -> ARC_R - W/2
    pil = math.radians(web_to_pil(theta))
    r = (ARC_R - ARC_W / 2) * sc
    x = C[0] * sc + r * math.cos(pil)
    y = C[1] * sc + r * math.sin(pil)
    return x, y

def pt(r, deg):
    a = math.radians(deg)
    return (C[0] + r * math.sin(a), C[1] - r * math.cos(a))

# Draw rounded-cap full track arc on a supersampled canvas
big = Image.new("RGBA", (CANVAS * SCALE, CANVAS * SCALE), (0, 0, 0, 0))
d = ImageDraw.Draw(big)
for name, s, e, ia, icon in ARCS:
    start_pil = web_to_pil(s - 0.6)
    end_pil = web_to_pil(e)
    bbox = [C[0] * SCALE - ARC_R * SCALE, C[1] * SCALE - ARC_R * SCALE,
            C[0] * SCALE + ARC_R * SCALE, C[1] * SCALE + ARC_R * SCALE]
    d.arc(bbox, start_pil, end_pil, fill=TRACK, width=ARC_W * SCALE)
    # rounded caps at both ends
    rw = ARC_W / 2 * SCALE
    for th in (s - 0.6, e):
        x, y = endpoint(th, SCALE)
        d.ellipse([x - rw, y - rw, x + rw, y + rw], fill=TRACK)

# Downscale to final canvas
canvas = big.resize((CANVAS, CANVAS), Image.LANCZOS)
dc = ImageDraw.Draw(canvas)

# Draw icons at final scale (same as gen_assets)
for name, s, e, ia, icon in ARCS:
    ic = pt(ARC_R, ia)
    G.draw_icon(dc, icon, ic[0], ic[1], 18)

# Palette-safe save
canvas = G._to_palette_safe(canvas)
ncol = len(set(canvas.getdata()))
if ncol > 256:
    raise RuntimeError(f"image_0002: {ncol} colors > 256!")
canvas.save(OUT)
print(f"image_0002.png regenerated with rounded-cap tracks: {ncol} colors")
