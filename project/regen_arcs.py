#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenerate the 4 arc-fill imagelists (imagelist_0000..0003) for v61 with
ROUNDED caps (fixes bug #4: "进度条不够圆润").

Strategy:
  - Replicate gen_assets_v3 geometry EXACTLY (ARC_R=206, ARC_W=11, C=(232,232),
    web angles 0=12点顺时针, start=(s-0.6)-90 PIL). This guarantees the new
    fills align with image_0002's static track (verified: track clusters at
    web ~45/134/225/315 match fill positions).
  - Square ends (d.arc) replaced by: thick arc stroke + filled circles
    (radius ARC_W/2) at BOTH endpoints, with 4x supersampling + LANCZOS for
    smooth edges.
  - Palette-safe via gen_assets_v3._to_palette_safe (byte-compatible with v60;
    only the cap shape differs).
  - Frame 0 (ratio 0) = fully transparent (matches v60 empty frame).
  - Output 464x464 (full canvas, transparent bg) so the element can be placed
    at x=0,y=0 (no opaque-black square, track shows through).
"""
import sys, math
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
from PIL import Image, ImageDraw

OUT = "/Users/admin/ai/watch/project/ws3/images"
CANVAS = 464
C = (232, 232)
ARC_R = 206
ARC_W = 11
SCALE = 4
FILL = (235, 235, 240, 255)
N = 11

# (imagelist index, start web angle, end web angle)
#  0 = battery  (0841)  lower-right 110-160
#  1 = steps    (0821)  upper-left  290-340
#  2 = calories (0822)  lower-left  200-250
#  3 = temp     (2031)  upper-right 20-70
ARCS = [(0, 110, 160), (1, 290, 340), (2, 200, 250), (3, 20, 70)]

def web_to_pil(theta):
    return theta - 90.0

def endpoint(theta, sc):
    # PIL arc(width=W) strokes INWARD from the bbox (outer edge = ARC_R), so the
    # band centreline is ARC_R - W/2. Caps must sit on that centreline, otherwise
    # they bulge W/2 outward and read as a blob at each arc end.
    pil = math.radians(web_to_pil(theta))
    r = (ARC_R - ARC_W / 2) * sc
    x = C[0] * sc + r * math.cos(pil)
    y = C[1] * sc + r * math.sin(pil)
    return x, y

def draw_arc_frame(s, e, ratio):
    if ratio <= 0:
        return Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sc = SCALE
    big = Image.new("RGBA", (CANVAS * sc, CANVAS * sc), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    fe = s + (e - s) * ratio
    start_pil = web_to_pil(s - 0.6)
    end_pil = web_to_pil(fe)
    bbox = [C[0] * sc - ARC_R * sc, C[1] * sc - ARC_R * sc,
            C[0] * sc + ARC_R * sc, C[1] * sc + ARC_R * sc]
    # thick arc stroke (the bar)
    d.arc(bbox, start_pil, end_pil, fill=FILL, width=ARC_W * sc)
    # rounded caps at both ends
    rw = ARC_W / 2 * sc
    for th in (s - 0.6, fe):
        x, y = endpoint(th, sc)
        d.ellipse([x - rw, y - rw, x + rw, y + rw], fill=FILL)
    return big.resize((CANVAS, CANVAS), Image.LANCZOS)

for li, s, e in ARCS:
    for i in range(N):
        ratio = i / (N - 1)
        img = draw_arc_frame(s, e, ratio)
        img = G._to_palette_safe(img)
        ncol = len(set(img.getdata()))
        if ncol > 256:
            raise RuntimeError(f"arc list {li} frame {i}: {ncol} colors > 256!")
        img.save(f"{OUT}/imagelist_000{li}_{i:04d}.png")
    print(f"arc list {li} (web {s}-{e}): {N} frames OK")
print("ALL ARC FILLS REGENERATED (rounded caps)")
