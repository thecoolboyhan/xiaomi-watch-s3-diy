#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v69 构建器（在 v68 基础上）: 整体布局向外扩
  官方屏: 466×466 AMOLED (可用半径 233, 画布 464 中心 232)
  1. 弧半径 ARC_R 206 -> 218 (弧外缘 223.5, 边距 8.5px; 图标 79/169/191/281° 不裁边)
  2. 双轮盘原生重绘 ×1.06 (gen_assets_html.gen_ring, 比位图放大锐利):
     分盘 Rnum 99->105, Rt 119/128->126/136; 秒盘 148->157, 168/177->178/188
  3. 红框读数窗 + 冒号 + 分/秒数字 ×1.06 (同步随圈外扩)
  4. 44 弧帧重生成 @218 (圆角帽, 裁剪小图块)
  5. AOD 背景重建 = 主表盘静态层调暗(~38%) + 暗红读数窗 (对齐寻路者"主盘调暗版"风格)
     AOD 元素位置不变 (时 232,182 / 分 363,212 恰在新红框中心 / 星期 203,166)
"""
import sys, math, json
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
import gen_assets_html as G2
from PIL import Image, ImageDraw

WS3 = "/Users/admin/ai/watch/project/ws3"
CANVAS, C = 464, (232, 232)
ARC_R, ARC_W, SCALE, N = 218, 11, 4, 11
K = 1.06                      # 圈环/读数窗缩放系数
TRACK = (60, 60, 70, 255)
FILL  = (235, 235, 240, 255)
LINE  = (235, 235, 240, 255)

ARCS = [("temp", 20, 70, 79, "sun"),
        ("battery", 110, 160, 169, "bolt"),
        ("calories", 200, 250, 191, "flame"),
        ("steps", 290, 340, 281, "shoe")]
FILL_ARCS = [(0, 110, 160), (1, 290, 340), (2, 200, 250), (3, 20, 70)]

def web2pil(t): return t - 90.0
def pt(r, deg):
    a = math.radians(deg)
    return (C[0] + r*math.sin(a), C[1] - r*math.cos(a))

# ---------------------------------------------------------- A. 图标 (沿用 v68 线稿风)
def rcap(d, x, y, w):
    r = w / 2
    d.ellipse([x-r, y-r, x+r, y+r], fill=LINE)

def icon_sun(d, cx, cy, R, w):
    r = 0.38 * R
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=LINE, width=w)
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        x1 = cx + (R*0.58)*math.sin(a); y1 = cy - (R*0.58)*math.cos(a)
        x2 = cx + (R*0.95)*math.sin(a); y2 = cy - (R*0.95)*math.cos(a)
        d.line([x1, y1, x2, y2], fill=LINE, width=w)
        rcap(d, x2, y2, w)

def icon_bolt(d, cx, cy, R, w):
    k = R / 13.0
    pts = [(0,-9*k), (-8*k,1*k), (-2*k,1*k), (-4*k,9*k), (6*k,-2*k), (0,-2*k), (4*k,-9*k), (0,-9*k)]
    d.line([(cx+px, cy+py) for px, py in pts], fill=LINE, width=w, joint="curve")
    rcap(d, cx, cy-9*k, w)

def _bezier(p0, p1, p2, p3, n=16):
    out = []
    for i in range(n+1):
        t = i/n; mt = 1-t
        out.append((mt**3*p0[0]+3*mt*mt*t*p1[0]+3*mt*t*t*p2[0]+t**3*p3[0],
                    mt**3*p0[1]+3*mt*mt*t*p1[1]+3*mt*t*t*p2[1]+t**3*p3[1]))
    return out

def icon_flame(d, cx, cy, R, w):
    s = 0.92 * R
    r1 = _bezier((0.10,-1.0), (0.42,-0.66), (0.64,-0.34), (0.54,0.10))
    r2 = _bezier((0.54,0.10), (0.47,0.52), (0.27,0.80), (0,0.86))
    path = r1 + r2 + [(-x, y) for x, y in (r1 + r2[1:])[::-1]]
    pts = [(cx+x*s, cy+y*s) for x, y in path]
    d.line(pts, fill=LINE, width=w, joint="curve")
    rcap(d, *pts[0], w); rcap(d, *pts[-1], w)
    i1 = _bezier((0,-0.10), (0.16,-0.02), (0.24,0.16), (0.20,0.34))
    i2 = _bezier((0.20,0.34), (0.15,0.52), (0.08,0.58), (0,0.58))
    ip = i1 + i2 + [(-x, y) for x, y in (i1 + i2[1:])[::-1]]
    ipts = [(cx+x*s, cy+y*s) for x, y in ip]
    d.line(ipts, fill=LINE, width=w, joint="curve")
    rcap(d, *ipts[0], w)

def icon_shoe(d, cx, cy, R, w):
    """鞋印: 脚掌纵椭圆 + 脚跟圆, 分离"""
    s = 0.92 * R
    d.ellipse([cx-0.40*s, cy-0.82*s, cx+0.40*s, cy+0.18*s], outline=LINE, width=w)
    hr = 0.30 * s
    hx, hy = cx + 0.08*s, cy + 0.58*s
    d.ellipse([hx-hr, hy-hr, hx+hr, hy+hr], outline=LINE, width=w)
ICONS = {"sun": icon_sun, "bolt": icon_bolt, "flame": icon_flame, "shoe": icon_shoe}

# ---------------------------------------------------------- B. 静态层 image_0002 @218
big = Image.new("RGBA", (CANVAS*SCALE, CANVAS*SCALE), (0,0,0,0))
d = ImageDraw.Draw(big)
for name, s, e, ia, icon in ARCS:
    bbox = [C[0]*SCALE-ARC_R*SCALE, C[1]*SCALE-ARC_R*SCALE,
            C[0]*SCALE+ARC_R*SCALE, C[1]*SCALE+ARC_R*SCALE]
    d.arc(bbox, web2pil(s-0.6), web2pil(e), fill=TRACK, width=ARC_W*SCALE)
    rw = ARC_W/2*SCALE
    for th in (s-0.6, e):
        a = math.radians(th-90)
        x = C[0]*SCALE + (ARC_R-ARC_W/2)*SCALE*math.cos(a)
        y = C[1]*SCALE + (ARC_R-ARC_W/2)*SCALE*math.sin(a)
        d.ellipse([x-rw, y-rw, x+rw, y+rw], fill=TRACK)
for name, s, e, ia, icon in ARCS:
    ic = (C[0]*SCALE + (ARC_R-2)*SCALE*math.sin(math.radians(ia)),
          C[1]*SCALE - (ARC_R-2)*SCALE*math.cos(math.radians(ia)))
    ICONS[icon](d, ic[0], ic[1], 18*SCALE, 3*SCALE)
canvas = big.resize((CANVAS, CANVAS), Image.LANCZOS)
G._to_palette_safe(canvas).save(f"{WS3}/images/image_0002.png")
print("image_0002: 轨道+图标 @ARC_R=218")

# ---------------------------------------------------------- C. 双轮盘原生重绘 ×1.06
def _save_to(proj_name):
    def _s(img, name):
        out = f"{WS3}/images/{proj_name}.png"
        G._to_palette_safe(img).save(out)
        return out
    return _s
# 分盘 (Rnum 99->105)
G2.save = _save_to("image_0001")
G2.gen_ring("ring_min", 105, 126, 136, 23, None, (220,220,226,255), False)
# 秒盘 (Rnum 148->157)
G2.save = _save_to("image_0000")
G2.gen_ring("ring_sec", 157, 178, 188, 23, None, (235,235,240,255), False)
print("双轮盘原生重绘: 分盘 105/126/136, 秒盘 157/178/188")

# ---------------------------------------------------------- D. 红框/冒号/读数数字 ×1.06
def scale_img(name, k):
    im = Image.open(f"{WS3}/images/{name}.png").convert("RGBA")
    w, h = max(1, round(im.size[0]*k)), max(1, round(im.size[1]*k))
    out = im.resize((w, h), Image.LANCZOS)
    G._to_palette_safe(out).save(f"{WS3}/images/{name}.png")
    return w, h

cw, ch = scale_img("image_0004", K)      # 红框
scale_img("image_0005", K)               # 冒号
for i in range(10):
    scale_img(f"imagelist_0008_{i:04d}", K)   # 分数字
    scale_img(f"imagelist_0009_{i:04d}", K)   # 秒数字
print(f"红框/冒号/读数数字 ×{K}")

# ---------------------------------------------------------- E. 44 弧帧 @218
def endpoint(theta, sc):
    a = math.radians(web2pil(theta))
    r = (ARC_R - ARC_W/2) * sc
    return C[0]*sc + r*math.cos(a), C[1]*sc + r*math.sin(a)

def render(s, e, ratio):
    big = Image.new("RGBA", (CANVAS*SCALE, CANVAS*SCALE), (0,0,0,0))
    d = ImageDraw.Draw(big)
    fe = s + (e - s) * ratio
    d.arc([C[0]*SCALE-ARC_R*SCALE, C[1]*SCALE-ARC_R*SCALE,
           C[0]*SCALE+ARC_R*SCALE, C[1]*SCALE+ARC_R*SCALE],
          web2pil(s-0.6), web2pil(fe), fill=FILL, width=ARC_W*SCALE)
    rw = ARC_W/2*SCALE
    for th in (s-0.6, fe):
        x, y = endpoint(th, SCALE)
        d.ellipse([x-rw, y-rw, x+rw, y+rw], fill=FILL)
    return big.resize((CANVAS, CANVAS), Image.LANCZOS)

boxes = {}
for li, s, e in FILL_ARCS:
    frames = [G._to_palette_safe(render(s, e, i/(N-1))) for i in range(N)]
    bb = frames[N-1].getbbox()
    pad = 2
    x0, y0 = max(0, bb[0]-pad), max(0, bb[1]-pad)
    x1, y1 = min(CANVAS, bb[2]+pad), min(CANVAS, bb[3]+pad)
    boxes[li] = (x0, y0)
    for i in range(N):
        frames[i].crop((x0, y0, x1, y1)).save(f"{WS3}/images/imagelist_000{li}_{i:04d}.png")
print("44 弧帧重生成 @218")

# ---------------------------------------------------------- F. wfDef
wf = json.load(open(f"{WS3}/wfDef.json"))
XY = {"0841": boxes[0], "0821": boxes[1], "1023": boxes[2], "2031": boxes[3]}
for e in wf["elementsNormal"]:
    ds = e.get("dataSrc")
    if ds in XY and e.get("type") == "widge_imagelist":
        e["x"], e["y"] = XY[ds]
# 骑圈元素 ×1.06
def repos(x, y):
    return round(232 + (x-232)*K), round(232 + (y-232)*K)
MOVES = {"image_0004": (299, 204), "image_0005": (358, 222)}
for e in wf["elementsNormal"]:
    if e.get("image") in MOVES:
        e["x"], e["y"] = repos(*MOVES[e["image"]])
    if e.get("dataSrc") == "101102" and e.get("type") == "widge_dignum":
        e["x"], e["y"] = repos(330, 212)
    if e.get("dataSrc") == "181102" and e.get("type") == "widge_dignum":
        e["x"], e["y"] = repos(394, 209)
wf["name"] = "RouletteS3_v69"
json.dump(wf, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
print("wfDef -> v69 (红框/冒号/数字外扩, 弧 x/y 回写)")

# ---------------------------------------------------------- G. AOD 背景 = 主盘调暗版
track = Image.open(f"{WS3}/images/image_0002.png").convert("RGBA")
px = track.load()
for y in range(CANVAS):
    for x in range(CANVAS):
        r, g, b, a = px[x, y]
        if a > 0:
            px[x, y] = (int(r*0.16), int(g*0.16), int(b*0.16), a)   # 轨道/图标 ~16%
# 暗红读数窗 (同新红框位置/尺寸)
cap = Image.open(f"{WS3}/images/image_0004.png").convert("RGBA")
cpx = cap.load()
for y in range(cap.size[1]):
    for x in range(cap.size[0]):
        r, g, b, a = cpx[x, y]
        if a > 0:
            cpx[x, y] = (int(r*0.42), int(g*0.10), int(b*0.10), a)  # 暗红 ~42%
track.alpha_composite(cap, tuple(repos(299, 204)))
G._to_palette_safe(track).save(f"{WS3}/images_aod/image_0000.png")
print("AOD 背景重建: 主盘静态层调暗 + 暗红读数窗 @", repos(299, 204))
