#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flip the roulette discs' number arrangement from COUNTER-clockwise to CLOCKWISE.

Why:
  v60/v61 draw number n at image-angle A(n) = 90 - 6n  (numbers increase CCW
  around the disc). The firmware rotates the disc CLOCKWISE by 6 deg/unit
  (allAngle=+3600), so number n reaches the 3 o'clock red marker at value=n.

  The user wants the discs to rotate COUNTER-CLOCKWISE. With CCW rotation the
  number arriving at the marker would be (60-n) -> counting DOWN. To keep the
  red box showing the CURRENT time while spinning CCW, the numbers must be
  arranged CLOCKWISE: A'(n) = 90 + 6n.
     check: screen = A'(n) - 6*value ; at marker 90deg -> 90+6n-6v = 90 -> v = n  OK

  A'(n) - A(n) = 12n, so each spoke (number + its tick) is rigidly rotated
  CLOCKWISE by 12n degrees about the watch centre.
  Equivalently the whole layout maps angle A -> 180 - A (a vertical flip), but
  done per-spoke so the glyphs stay upright (a true flip would mirror them).

  Rigid rotation => glyph orientation (top pointing outward) is preserved
  exactly, and the original font/antialiasing is reused (no font guesswork).

PIL convention verified empirically: rotate(-x) = clockwise by x.
"""
import sys, math
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
from PIL import Image

CANVAS = 464
C = (232, 232)
OUT = "/Users/admin/ai/watch/project/ws3/images"


def build_wedge_mask(r0, r1, center_deg, half_width):
    """L-mode mask: annulus [r0,r1] limited to +/-half_width around center_deg (web angle)."""
    m = Image.new("L", (CANVAS, CANVAS), 0)
    px = m.load()
    for y in range(CANVAS):
        for x in range(CANVAS):
            dx = x - C[0]; dy = y - C[1]
            r = math.hypot(dx, dy)
            if r < r0 or r > r1:
                continue
            a = (math.degrees(math.atan2(dy, dx)) + 90) % 360
            d = abs(a - center_deg)
            d = d if d < 180 else 360 - d
            if d <= half_width:
                px[x, y] = 255
    return m


def flip_ring(name, r0, r1, hw=15.0):
    path = f"{OUT}/{name}.png"
    orig = Image.open(path).convert("RGBA")
    new = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    blank = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    M0 = build_wedge_mask(r0, r1, 90.0, hw)  # canonical wedge at 3 o'clock
    for n in range(0, 60, 5):
        delta = 12 * n                       # clockwise rotation for this spoke
        rot = orig.rotate(-delta, center=C, resample=Image.BICUBIC)
        mask = M0.rotate(-6 * n, center=C, resample=Image.NEAREST)  # wedge -> 90+6n
        layer = Image.composite(rot, blank, mask)
        new = Image.alpha_composite(new, layer)
    new = G._to_palette_safe(new)
    ncol = len(set(new.getdata()))
    if ncol > 256:
        raise RuntimeError(f"{name}: {ncol} colors > 256!")
    new.save(path)
    print(f"{name}: numbers re-arranged CLOCKWISE (12 spokes), {ncol} colors")


# radius band covering number glyphs + tick marks (measured from the actual images)
flip_ring("image_0000", 125, 190)   # second disc: glyphs 136-160, ticks 166-178
flip_ring("image_0001", 76, 140)    # minute disc: glyphs  87-111, ticks 118-128
print("DISC ARRANGEMENT FLIPPED")
