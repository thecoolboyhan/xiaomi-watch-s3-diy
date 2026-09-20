#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把生成的主面渲染图与参考图做像素级几何对比 (全部换算到 464 空间)"""
import statistics
from PIL import Image

import os as _os
ROOT = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isdir(_os.path.join(ROOT, "tools")):
    ROOT = _os.path.dirname(ROOT)
REF = _os.environ.get("WF_REF_IMAGE", _os.path.join(ROOT, "reference", "design_ref_2048.png"))  # 外部设计参考图, 不入库; 用环境变量 WF_REF_IMAGE 指向本地副本
MINE = _os.path.join(ROOT, "project/minimal/preview_render.png")
CX, CY, R, K = 1002, 1032, 780, 464.0 / 1560
t = lambda x, y: (round((x - CX + R) * K, 1), round((y - CY + R) * K, 1))


def bands(img, px, w, h, thr=120, pre=None):
    """返回 (y0,y1) 暗像素行段 -> 464 y"""
    rows = []
    for y in range(h):
        n = sum(1 for x in range(w) if pre is None or pre(x, y)) if False else 0
    return rows


def dark_bands(px, y0, y1, x0, x1, mask=None, thr=120):
    rows = {}
    for y in range(y0, y1):
        n = 0
        for x in range(x0, x1):
            if mask and not mask(x, y):
                continue
            c = px[x, y]
            if sum(c) / 3 < thr:
                n += 1
        rows[y] = n
    segs, s = [], None
    for y in sorted(rows):
        if rows[y] > 0 and s is None:
            s = y
        elif rows[y] == 0 and s is not None:
            segs.append((s, y - 1)); s = None
    if s is not None:
        segs.append((s, sorted(rows)[-1]))
    return segs


def col_segs(px, y0, y1, x0, x1, thr=120):
    cols = []
    for x in range(x0, x1):
        cols.append(sum(1 for y in range(y0, y1) if sum(px[x, y]) / 3 < thr))
    segs, s = [], None
    for i, n in enumerate(cols):
        if n > 0 and s is None:
            s = i
        elif n == 0 and s is not None:
            segs.append((s + x0, i - 1 + x0)); s = None
    if s is not None:
        segs.append((s + x0, len(cols) - 1 + x0))
    return segs


def measure(px, w, h, to464):
    """参考图: 圆内暗元素; 返回各带 (y中心, y高, x段列表)"""
    res = {}
    circle = (lambda x, y: (x - CX) ** 2 + (y - CY) ** 2 < (R - 25) ** 2) if w > 1000 else None
    bs = dark_bands(px, 0, h, 0, w, mask=circle)
    bs = [(a, b) for a, b in bs if b - a > 6]
    out = []
    for a, b in bs:
        ys = to464(0, a)[1], to464(0, b)[1]
        segs = col_segs(px, a, b + 1, 0, w)
        xs = [(to464(p, 0)[0], to464(q, 0)[0]) for p, q in segs if q - p > 1]
        out.append(dict(y0=ys[0], y1=ys[1], h=round(ys[1] - ys[0], 1),
                        x0=xs[0][0] if xs else None, x1=xs[-1][1] if xs else None,
                        w=round(xs[-1][1] - xs[0][0], 1) if xs else None, nseg=len(xs)))
    return out


def main():
    ref = Image.open(REF).convert("RGB"); rp = ref.load()
    mine = Image.open(MINE).convert("RGB"); mp = mine.load()
    print("=== 参考图 ===")
    for b in measure(rp, ref.width, ref.height, t):
        print("  y", b["y0"], "-", b["y1"], "h", b["h"], "| x", b["x0"], "-", b["x1"],
              "w", b["w"], "| segs", b["nseg"])
    print("=== 我的渲染 ===")
    idt = lambda x, y: (x, y)
    for b in measure(mp, mine.width, mine.height, idt):
        print("  y", b["y0"], "-", b["y1"], "h", b["h"], "| x", b["x0"], "-", b["x1"],
              "w", b["w"], "| segs", b["nseg"])
    # 背景色
    print("\n背景色  参考:", statistics.mode([rp[x, y] for y in range(400, 1600, 11)
                                          for x in range(400, 1600, 11)]),
          " 我的:", statistics.mode([mp[x, y] for y in range(60, 400, 7)
                                   for x in range(60, 400, 7)]))


main()
