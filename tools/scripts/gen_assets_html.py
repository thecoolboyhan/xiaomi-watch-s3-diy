#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RouletteS3 HTML 素材生成器
完全模仿 preview_v20.html 的效果，独立于 WorkBuddy 主线。
坐标系: 464x464, 中心 C=(232,232)。
"""
import math, os
from PIL import Image, ImageDraw, ImageFont, ImageChops

OUT = os.path.join(os.path.dirname(__file__), "out_html", "images")
os.makedirs(OUT, exist_ok=True)

CANVAS = 464
C = (CANVAS // 2, CANVAS // 2)   # (232, 232)

# 字体
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

def fnt(sz, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT, sz)
    except Exception:
        return ImageFont.load_default()

def rr(deg):
    return math.radians(deg)

def pt(r, deg):
    a = rr(deg)
    return (C[0] + r*math.sin(a), C[1] - r*math.cos(a))

def new_layer(size=None):
    if size is None:
        size = (CANVAS, CANVAS)
    return Image.new("RGBA", size, (0,0,0,0))

def draw_text_rotated(img, xy, text, font, fill, angle_deg, anchor="mm"):
    bbox = font.getbbox(text)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    pad = 8
    layer = Image.new("RGBA", (tw+pad*2, th+pad*2), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    d.text((pad, pad), text, font=font, fill=fill)
    rot = layer.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
    ix = int(round(xy[0] - rot.width/2))
    iy = int(round(xy[1] - rot.height/2))
    img.alpha_composite(rot, (ix, iy))

# 限色工具
MAX_COLORS = 256
WHITE_MIN_LUMA = 200.0
COLOR_MAX_RATIO = 0.15

def _img_stats(im):
    im = im.convert("RGBA")
    px = list(im.getdata())
    cols = len(set(px))
    op = [q for q in px if q[3] > 200]
    if op:
        luma = sum(r + g + b for r, g, b, a in op) / len(op) / 3
        colored = sum(1 for r, g, b, a in op if max(r, g, b) - min(r, g, b) > 18)
        ratio = colored / len(op)
    else:
        luma, ratio = 0.0, 0.0
    return cols, luma, ratio

def _premultiply_whiten(im):
    im = im.convert("RGBA")
    gray = im.convert("L")
    a = im.getchannel("A")
    new_a = ImageChops.multiply(gray, a)
    white = Image.new("L", im.size, 255)
    return Image.merge("RGBA", (white, white, white, new_a))

def _quantize_256(im):
    im = im.convert("RGBA")
    try:
        q = im.quantize(colors=MAX_COLORS, method=Image.FASTOCTREE)
    except Exception:
        q = im.quantize(colors=MAX_COLORS, method=Image.MEDIANCUT)
    return q.convert("RGBA")

def _to_palette_safe(img):
    im = img.convert("RGBA")
    cols, luma, ratio = _img_stats(im)
    if cols <= MAX_COLORS:
        return im
    if luma > WHITE_MIN_LUMA and ratio < COLOR_MAX_RATIO:
        out = _premultiply_whiten(im)
    else:
        out = _quantize_256(im)
    if len(set(out.getdata())) > MAX_COLORS:
        out = _quantize_256(im)
    return out

def save(img, name):
    p = os.path.join(OUT, name)
    out = _to_palette_safe(img)
    out.save(p)
    final = Image.open(p).convert("RGBA")
    ncol = len(set(final.getdata()))
    if ncol > MAX_COLORS:
        raise RuntimeError(f"[color-limit] {name} 仍有 {ncol} 色(>={MAX_COLORS})")
    print(f"  {name:28s} {out.size} colors={ncol}")
    return p

# ---------------------------------------------------------------------------
# 1. 背景 bg.png : 纯黑 + 外圈淡环 + 双轮盘轨道淡环 + 3点方向红色读数刻度
# ---------------------------------------------------------------------------
def gen_bg():
    img = new_layer()
    d = ImageDraw.Draw(img)
    # 外圈环
    d.ellipse([C[0]-226, C[1]-226, C[0]+226, C[1]+226],
              outline=(70,70,80,255), width=2)
    # 2 条淡轨道环
    d.ellipse([C[0]-164, C[1]-164, C[0]+164, C[1]+164], outline=(42,42,50,255), width=2)
    d.ellipse([C[0]-111, C[1]-111, C[0]+111, C[1]+111], outline=(42,42,50,255), width=2)
    # 分/秒盘交界细线
    d.ellipse([C[0]-140, C[1]-140, C[0]+140, C[1]+140], outline=(52,52,62,255), width=2)
    # 3 点方向红色读数刻度
    tip = pt(183, 90); base1 = pt(170, 86); base2 = pt(170, 94)
    d.polygon([tip, base1, base2], fill=(255,60,60,210))
    save(img, "bg.png")

# ---------------------------------------------------------------------------
# 2. 轮盘环 ring_min / ring_sec : 60 刻度 + 每5格数字 00-55(径向)
# ---------------------------------------------------------------------------
def gen_ring(name, Rnum, RtIn, RtOut, num_font_sz, tick_col, num_col, num_bold,
             plate_r_in=None, plate_r_out=None):
    img = new_layer()
    d = ImageDraw.Draw(img)
    # 不透明环形带
    if plate_r_out:
        d.ellipse([C[0]-plate_r_out, C[1]-plate_r_out, C[0]+plate_r_out, C[1]+plate_r_out],
                  fill=(0, 0, 0, 255))
        if plate_r_in:
            d.ellipse([C[0]-plate_r_in, C[1]-plate_r_in, C[0]+plate_r_in, C[1]+plate_r_in],
                      fill=(0, 0, 0, 0))
    font = fnt(num_font_sz, num_bold)
    for n in range(60):
        a_img = (90 - 6*n)
        if n % 5 != 0:
            continue
        d.line([pt(RtIn - 4, a_img), pt(RtOut, a_img)],
               fill=(230,230,236,255), width=4)
        px, py = pt(Rnum, a_img)
        draw_text_rotated(img, (px, py), f"{n:02d}", font, num_col, -a_img)
    save(img, name)

# ---------------------------------------------------------------------------
# 3. 数字图集 digits : 大(时) / 中(胶囊) / 小(弧/电量/温/日)
# ---------------------------------------------------------------------------
def gen_digits(prefix, sz, bold, with_blank=False):
    font = fnt(sz, bold)
    max_w = 0
    for i in range(10):
        bbox = font.getbbox(str(i))
        w = bbox[2] - bbox[0]
        if w > max_w:
            max_w = w
    cell_w = max_w + 2
    cell_h = int(sz * 0.95)
    for i in range(10):
        tmp = new_layer((cell_w, cell_h))
        d = ImageDraw.Draw(tmp)
        d.text((cell_w//2, cell_h//2), str(i), font=font,
               fill=(255,255,255,255), anchor="mm")
        save(tmp, f"{prefix}_{i}.png")
    if with_blank:
        img = new_layer((cell_w, cell_h))
        save(img, f"{prefix}_10.png")
    return cell_w, cell_h

# ---------------------------------------------------------------------------
# 4. 星期 / 月份 图集
# ---------------------------------------------------------------------------
def gen_text_frames(prefix, labels, sz):
    font = fnt(sz, False)
    max_w = 0
    for lab in labels:
        bbox = font.getbbox(lab)
        w = bbox[2] - bbox[0]
        if w > max_w:
            max_w = w
    cell_w = max_w + 4
    cell_h = int(sz * 1.05)
    for i, lab in enumerate(labels):
        tmp = new_layer((cell_w, cell_h))
        d = ImageDraw.Draw(tmp)
        col = (170,170,178,255)
        d.text((cell_w//2, cell_h//2), lab, font=font, fill=col, anchor="mm")
        save(tmp, f"{prefix}_{i}.png")
    return cell_w, cell_h

# ---------------------------------------------------------------------------
# 5. 冒号 + 斜杠 + 百分号
# ---------------------------------------------------------------------------
def gen_punct():
    img = new_layer((12, 12))
    d = ImageDraw.Draw(img)
    d.ellipse([4,1,8,5], fill=(255,255,255,255))
    d.ellipse([4,7,8,11], fill=(255,255,255,255))
    save(img, "colon.png")

    img = new_layer((12, 14))
    d = ImageDraw.Draw(img)
    d.line([(3,11), (9,3)], fill=(160,160,168,255), width=2)
    save(img, "slash.png")

    img = new_layer((12, 13))
    d = ImageDraw.Draw(img)
    d.text((6, 6), "%", font=fnt(13, True), fill=(235,235,240,255), anchor="mm")
    save(img, "percent.png")

    img = new_layer((14, 14))
    d = ImageDraw.Draw(img)
    d.ellipse([3,2,11,10], outline=(235,235,240,255), width=2)
    save(img, "deg.png")

# ---------------------------------------------------------------------------
# 6. 红色胶囊底图
# ---------------------------------------------------------------------------
def gen_capsule():
    w, h = 128, 57
    img = new_layer((w+8, h+8))
    d = ImageDraw.Draw(img)
    ox, oy = 4, 4
    d.rounded_rectangle([ox, oy, ox+w, oy+h], radius=h//2,
                        fill=(16,4,6,255), outline=(255,60,60,255), width=4)
    save(img, "capsule_bg.png")

# ---------------------------------------------------------------------------
# 7. 四弧 arcs.png (静态) : 轨道 + 图标
# ---------------------------------------------------------------------------
ARC_SPEC = [
    ("temp",    20,  70,  79, "sun",   "2031", 0,  50, 11),
    ("battery", 110, 160, 169,"bolt",  "0841", 0, 100, 21),
    ("calories",200, 250, 191,"flame", "0822", 0, 500, 21),
    ("steps",   290, 340, 281,"shoe",  "1021", 0, 100, 21),
]
ARC_R = 206
ARC_W = 11

def draw_icon(d, kind, x, y, r):
    def P(pts):
        return [(x+dx, y+dy) for dx,dy in pts]
    w = 3
    if kind == "sun":
        d.ellipse([x-r*0.38,y-r*0.38,x+r*0.38,y+r*0.38], outline=(235,235,240,255), width=w)
        for ang in range(0,360,45):
            a=math.radians(ang)
            d.line([(x+(r*0.58)*math.sin(a), y-(r*0.58)*math.cos(a)),
                    (x+(r*0.95)*math.sin(a), y-(r*0.95)*math.cos(a))],
                   fill=(235,235,240,255), width=w)
    elif kind == "bolt":
        d.polygon(P([(-1,-9*r/13),(-8*r/13,r/13),(-2*r/13,r/13),(-4*r/13,9*r/13),
                     (6*r/13,-2*r/13),(0,-2*r/13),(4*r/13,-9*r/13)]),
                  outline=(235,235,240,255), width=w)
    elif kind == "flame":
        d.polygon(P([(0,-9*r/13),(7*r/13,-r/13),(5*r/13,6*r/13),(-r/13,9*r/13),
                     (-7*r/13,4*r/13),(-4*r/13,-2*r/13)]),
                  outline=(235,235,240,255), width=w)
    elif kind == "shoe":
        d.line(P([(-8*r/13,4*r/13),(-2*r/13,-2*r/13),(6*r/13,0),(10*r/13,-5*r/13),
                  (13*r/13,r/13),(12*r/13,5*r/13),(-2*r/13,6*r/13)]),
               fill=(235,235,240,255), width=w, joint="curve")
    else:
        d.ellipse([x-r,y-r,x+r,y+r], outline=(235,235,240,255), width=w)

def gen_arcs():
    img = new_layer()
    d = ImageDraw.Draw(img)
    for name, s, e, ia, icon, ds, dmin, dmax, nlv in ARC_SPEC:
        d.arc([C[0]-ARC_R,C[1]-ARC_R,C[0]+ARC_R,C[1]+ARC_R], -e, -s, fill=(60,60,70,255), width=ARC_W)
        ic_pos = pt(ARC_R, ia)
        draw_icon(d, icon, ic_pos[0], ic_pos[1], 18)
    save(img, "arcs.png")

# ---------------------------------------------------------------------------
# 8. 点击热区
# ---------------------------------------------------------------------------
def gen_hotzone(w=80, h=40):
    save(new_layer((w, h)), "hotzone.png")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("== gen_bg ==");        gen_bg()
    print("== gen_ring (min/sec) ==")
    # 完全模仿 HTML 预览: minuteRing Rnum=99, RtIn=119, RtOut=128
    #                   secondRing Rnum=148, RtIn=168, RtOut=177
    gen_ring("ring_min.png", 99, 119, 128, 22, None, (220,220,226,255), False, plate_r_in=85, plate_r_out=140)
    gen_ring("ring_sec.png", 148, 168, 177, 22, None, (235,235,240,255), False, plate_r_in=140, plate_r_out=231)
    print("== gen_digits ==")
    digH_w, digH_h = gen_digits("digH", 56, True)
    digM_w, digM_h = gen_digits("digM", 24, True)
    digS_w, digS_h = gen_digits("digS", 16, False, with_blank=True)
    print(f"  -> cell sizes: digH={digH_w}x{digH_h}  digM={digM_w}x{digM_h}  digS={digS_w}x{digS_h}")
    print("== gen_text_frames ==")
    wd_w, wd_h = gen_text_frames("wd", ["SUN","MON","TUE","WED","THU","FRI","SAT"], 20)
    mo_w, mo_h = gen_text_frames("mo", ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"], 18)
    print(f"  -> frame sizes: wd={wd_w}x{wd_h}  mo={mo_w}x{mo_h}")
    print("== gen_punct ==");       gen_punct()
    print("== gen_capsule ==");     gen_capsule()
    print("== gen_arcs ==");        gen_arcs()
    print("== gen_hotzone ==");     gen_hotzone()
    print("== gen_arc_fills ==")
    # 生成动态填充进度帧 (仅步数 1021)
    for name, s, e, ia, icon, ds, dmin, dmax, nlv in ARC_SPEC:
        if ds != "1021":
            continue
        for i in range(nlv):
            val = dmin + (dmax - dmin) * i / (nlv - 1)
            ratio = (val - dmin) / (dmax - dmin)
            ratio = max(0.0, min(1.0, ratio))
            fe = s + (e - s) * ratio
            img = new_layer()
            d = ImageDraw.Draw(img)
            d.arc([C[0]-ARC_R,C[1]-ARC_R,C[0]+ARC_R,C[1]+ARC_R],
                  (s-0.6)-90, fe-90, fill=(235,235,240,255), width=ARC_W)
            save(img, f"arcfill_{name}_{i}.png")
        print(f"  arcfill_{name}: {nlv} 帧 (ds={ds} {dmin}..{dmax})")
    print("DONE ->", OUT)
