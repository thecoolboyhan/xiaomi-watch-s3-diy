#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v67 builder（在 v66 基础上）:
  1. 日期换公历源（Mi-Create sources.json xiaomi_watch_s3 官方表实锤）:
     月 3012(dateLunarMounth) -> 1012(Month)
     日 3812(dateLunarDay)    -> 1812(Day)
     帧/映射表不动（月[1..12]、日[1..31] 正好匹配公历，日 31 帧比农历盘的 30 帧更对）。
  2. 四个数据图标完全重绘（白色剪影风格，4x 超采样），重建 image_0002（圆角轨道保留）。
  3. AOD: 启用命名 face 记录布局（namedFaceRecords，谷歌/寻路者同款结构）。
"""
import sys, math, json
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
from PIL import Image, ImageDraw

WS3 = "/Users/admin/ai/watch/project/ws3"
CANVAS, C = 464, (232, 232)
ARC_R, ARC_W, SCALE = 206, 11, 4
TRACK = (60, 60, 70, 255)

ARCS = [("temp", 20, 70, 79, "sun"),
        ("battery", 110, 160, 169, "bolt"),
        ("calories", 200, 250, 191, "flame"),
        ("steps", 290, 340, 281, "shoe")]

# ---------------------------------------------------------------- 图标绘制
# 风格 = v60 原版线稿风（gen_assets_html.draw_icon 同款形状, w=3, r=18），
# 但全部在 4x 超采样画布上绘制再降采样 —— 消除原版 1x 直绘的锯齿（"不精致"根因）。
LINE = (235, 235, 240, 255)

def rcap(d, x, y, w):
    """圆头端点"""
    r = w / 2
    d.ellipse([x - r, y - r, x + r, y + r], fill=LINE)

def icon_sun(d, cx, cy, R, w):
    r = 0.38 * R
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=LINE, width=w)
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        x1 = cx + (R * 0.58) * math.sin(a); y1 = cy - (R * 0.58) * math.cos(a)
        x2 = cx + (R * 0.95) * math.sin(a); y2 = cy - (R * 0.95) * math.cos(a)
        d.line([x1, y1, x2, y2], fill=LINE, width=w)
        rcap(d, x2, y2, w)          # 外端圆头（内端与线自然相接）

def icon_bolt(d, cx, cy, R, w):
    k = R / 13.0
    pts = [(0, -9 * k), (-8 * k, 1 * k), (-2 * k, 1 * k), (-4 * k, 9 * k),
           (6 * k, -2 * k), (0, -2 * k), (4 * k, -9 * k), (0, -9 * k)]
    d.line([(cx + px, cy + py) for px, py in pts], fill=LINE, width=w, joint="curve")
    rcap(d, cx + 0 * k, cy - 9 * k, w)   # 顶点圆头

def _bezier(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n; mt = 1 - t
        pts.append((mt**3*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t**3*p3[0],
                    mt**3*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t**3*p3[1]))
    return pts

def icon_flame(d, cx, cy, R, w):
    """经典火焰: 外焰泪滴(尖端右倾) + 内焰小泪滴"""
    s = 0.92 * R
    r1 = _bezier((0.10,-1.0), (0.42,-0.66), (0.64,-0.34), (0.54,0.10))
    r2 = _bezier((0.54,0.10), (0.47,0.52), (0.27,0.80), (0,0.86))
    path = r1 + r2 + [(-x, y) for x, y in (r1 + r2[1:])[::-1]]
    pts = [(cx + x*s, cy + y*s) for x, y in path]
    d.line(pts, fill=LINE, width=w, joint="curve")
    rcap(d, pts[0][0], pts[0][1], w); rcap(d, pts[-1][0], pts[-1][1], w)
    # 内焰
    i1 = _bezier((0,-0.10), (0.16,-0.02), (0.24,0.16), (0.20,0.34))
    i2 = _bezier((0.20,0.34), (0.15,0.52), (0.08,0.58), (0,0.58))
    ip = i1 + i2 + [(-x, y) for x, y in (i1 + i2[1:])[::-1]]
    ipts = [(cx + x*s, cy + y*s) for x, y in ip]
    d.line(ipts, fill=LINE, width=w, joint="curve")
    rcap(d, ipts[0][0], ipts[0][1], w)

def icon_shoe(d, cx, cy, R, w):
    """步数 = 鞋印(footprint): 脚掌纵椭圆 + 脚跟圆, 两形分离不粘连, 4x 直绘最锐利"""
    s = 0.92 * R
    # 脚掌: 纵椭圆 (中心 cy-0.32s, rx 0.40s, ry 0.50s)
    d.ellipse([cx-0.40*s, cy-0.82*s, cx+0.40*s, cy+0.18*s], outline=LINE, width=w)
    # 脚跟: 圆 (中心 cy+0.58s, r 0.30s) —— 与脚掌留 0.10s 间隙
    hr = 0.30 * s
    hx, hy = cx + 0.08*s, cy + 0.58*s
    d.ellipse([hx-hr, hy-hr, hx+hr, hy+hr], outline=LINE, width=w)

_BIG = None  # 4x 主画布, 绘制循环前注入
ICONS = {"sun": icon_sun, "bolt": icon_bolt, "flame": icon_flame, "shoe": icon_shoe}

# ---------------------------------------------------------------- 重建 image_0002
def web2pil(t): return t - 90.0
def endpoint(theta, sc):
    pil = math.radians(web2pil(theta))
    r = (ARC_R - ARC_W/2) * sc
    return C[0]*sc + r*math.cos(pil), C[1]*sc + r*math.sin(pil)

big = Image.new("RGBA", (CANVAS*SCALE, CANVAS*SCALE), (0,0,0,0))
d = ImageDraw.Draw(big)
for name, s, e, ia, icon in ARCS:
    bbox = [C[0]*SCALE-ARC_R*SCALE, C[1]*SCALE-ARC_R*SCALE,
            C[0]*SCALE+ARC_R*SCALE, C[1]*SCALE+ARC_R*SCALE]
    d.arc(bbox, web2pil(s-0.6), web2pil(e), fill=TRACK, width=ARC_W*SCALE)
    rw = ARC_W/2*SCALE
    for th in (s-0.6, e):
        x, y = endpoint(th, SCALE)
        d.ellipse([x-rw, y-rw, x+rw, y+rw], fill=TRACK)
# 图标：与轨道同一 4x 画布，1x 半径 18 / 线宽 3（=v60 原版参数），降采样后自然锐利
_BIG = big
for name, s, e, ia, icon in ARCS:
    ic = (C[0]*SCALE + ARC_R*SCALE*math.sin(math.radians(ia)),
          C[1]*SCALE - ARC_R*SCALE*math.cos(math.radians(ia)))
    ICONS[icon](d, ic[0], ic[1], 18*SCALE, 3*SCALE)
canvas = big.resize((CANVAS, CANVAS), Image.LANCZOS)
canvas = G._to_palette_safe(canvas)
canvas.save(f"{WS3}/images/image_0002.png")
print("image_0002 重建: 圆角轨道 + v60 线稿风图标(4x 超采样, r=18, w=3)")

# ---------------------------------------------------------------- wfDef
wf = json.load(open(f"{WS3}/wfDef.json"))
for e in wf["elementsNormal"]:
    if e.get("dataSrc") == "3012" and e.get("type") == "widge_imagelist":
        e["dataSrc"] = "1012"; print("月: 3012(农历) -> 1012(公历)")
    if e.get("dataSrc") == "3812" and e.get("type") == "widge_imagelist":
        e["dataSrc"] = "1812"; print("日: 3812(农历) -> 1812(公历)")
wf["namedFaceRecords"] = True
wf["faceNames"] = ["样式1", "息屏"]
wf["name"] = "RouletteS3_v67"
json.dump(wf, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
print("wfDef -> v67 (named face layout)")
