#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinimalS3 v5 — 自动昼夜 + 文字/图标换深浅 + 冒号透明帧闪烁 + 点击

参考图: ~/Downloads/1/简约表盘，后面做.png (2048x2048)
屏幕圆: 中心(1002,1032) 半径780  →  464 画布换算 K = 464/1560 = 0.29744

相对 v4 的关键修正（来自"字体能否自动换色 / 自动换图能否闪烁"两问的澄清）:
  1. 自动切换统一驱动源用 0811(小时,24值) + imageIndexList 把小时映射到 2 帧(0=白天/1=夜晚),
     翻转边界 6:00-17:59 白天、18:00-5:59 夜晚 —— 用 2 帧而非 24 帧全屏底, 显存可控, 且所有
     自动元素共用同一小时源, 绝对一致(规避 AM/PM 12h 翻转与 24 帧 20MB 的问题)。
  2. 数字(dignum)颜色锁死无法随时段切换 → 时间/电量/温度/心率数字保持中性灰(112)兼顾深浅底。
  3. 图片类文字(问候语/标签)与图标可换色 → 各自做 day/night 两版帧, 绑 0811 随背景切换。
  4. 冒号闪烁改为【透明帧法】: 1811 驱动 60 帧, 偶帧=冒号字形、奇帧=纯透明(露出背景),
     不再用"填背景色的遮挡层" → 自动换背景 与 冒号闪烁 不再冲突。偶帧是字形, 驱动失效也只是
     不闪、冒号不消失(兜底)。

配色:
  白天底 (217,217,215) / 夜晚底 (16,16,18)
  数字中性灰 (112,112,116)
  问候语/标签 白天深 (33,33,37) / 夜晚浅 (228,228,233)
  太阳 白天 (240,165,35) / 夜晚亮 (255,200,95)
  爱心 白天 (232,55,55) / 夜晚亮 (255,95,95)
"""
import os, math, json
from PIL import Image, ImageDraw, ImageFont

import os as _os
ROOT = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isdir(_os.path.join(ROOT, "tools")):
    ROOT = _os.path.dirname(ROOT)
ROOT = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(ROOT, "images")
IMG_AOD = os.path.join(ROOT, "images_aod")
os.makedirs(IMG, exist_ok=True)
os.makedirs(IMG_AOD, exist_ok=True)
W = H = 464

# ---------------- 字体 ----------------
WEIGHT = "Semibold"
def load_font(size, weight=WEIGHT):
    f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f

def ink_size(s, font):
    tmp = Image.new("L", (font.size * (len(s) + 2), font.size * 3), 0)
    ImageDraw.Draw(tmp).text((tmp.width // 2, tmp.height // 2), s, font=font, fill=255, anchor="mm")
    bb = tmp.getbbox()
    return bb[2] - bb[0], bb[3] - bb[1]

def fit_size(target_h, sample, weight=WEIGHT, lo=8, hi=200):
    while lo < hi:
        mid = (lo + hi) // 2
        if ink_size(sample, load_font(mid, weight))[1] < target_h:
            lo = mid + 1
        else:
            hi = mid
    return lo

def load_cn(size):
    for path in ("/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/Hiragino Sans GB.ttc"):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=0)
            except Exception:
                pass
    raise SystemExit("no cn font")

X_SCALE = 0.95

def glyph(s, font, color, cell):
    im = text_image(s, font, color)
    if abs(X_SCALE - 1) > 1e-6:
        im = im.resize((max(1, round(im.width * X_SCALE)), im.height), Image.LANCZOS)
    if im.width > cell[0] or im.height > cell[1]:
        print(f"  ⚠ 字模裁切 '{s}' ink={im.size} cell={cell}")
    base = Image.new("RGBA", cell, (0, 0, 0, 0))
    base.alpha_composite(im, ((cell[0] - im.width) // 2, (cell[1] - im.height) // 2))
    return base

def text_image(s, font, color, cell=None):
    tmp = Image.new("RGBA", (font.size * (len(s) + 2), font.size * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((tmp.width // 2, tmp.height // 2), s, font=font, fill=color, anchor="mm")
    bb = tmp.getbbox()
    im = tmp.crop(bb)
    if cell:
        if im.width > cell[0] or im.height > cell[1]:
            print(f"  ⚠ 字模裁切 '{s}' ink={im.size} cell={cell}")
        base = Image.new("RGBA", cell, (0, 0, 0, 0))
        base.alpha_composite(im, ((cell[0] - im.width) // 2, (cell[1] - im.height) // 2))
        return base
    return im

# ---------------- 布局 (实测, 与 v4 同) ----------------
T_INK_H = 65.7
TIME_SIZE = fit_size(T_INK_H, "0")
TIME_GAP = 2
TIME_CELL = (round(max(ink_size(str(d), load_font(TIME_SIZE))[0] for d in range(10)) * X_SCALE) + TIME_GAP,
             int(T_INK_H) + 4)
COLON_W, COLON_GAP = 14, 13.5
COLON_H, Y_COLON = 47, 100
TIME_BLOCK_W = 4 * TIME_CELL[0] + COLON_GAP
TIME_CENTER_X = 232                                  # 时间块屏幕水平中心
# 威根 dignum 以"整串右边缘"对齐到 x(实测: 原居中模型导致真机偏左), 故 x 取右边缘
HOUR_CX = TIME_CENTER_X - TIME_BLOCK_W / 2 + 2 * TIME_CELL[0]
MIN_CX  = TIME_CENTER_X + TIME_BLOCK_W / 2
Y_TIME = 85

GREETINGS = ["Good Morning", "Good Afternoon", "Good Evening", "Good Night"]
G_INK_H = 25.9
GREET_SIZE = fit_size(G_INK_H, "Good Morning")
_gw = max(ink_size(g, load_font(GREET_SIZE))[0] for g in GREETINGS)
GREET_CELL = (_gw + 4, int(G_INK_H) + 4)
Y_GREET = 164

B_INK_H = 19.6
BAT_SIZE = fit_size(B_INK_H, "8") + 1
BAT_GAP = 2
BAT_CELL = (round(max(ink_size(str(d), load_font(BAT_SIZE))[0] for d in range(10)) * X_SCALE) + BAT_GAP,
            int(B_INK_H) + 4)
BAT_LABEL_C = (393, 218)
BAT_NUM_CX = BAT_LABEL_C[0] + BAT_CELL[0]  # 右边缘: 数字中心 = 标签视觉中心 393
BAT_PCT_X = BAT_NUM_CX + 4
Y_VAL1 = 253

M_INK_H = 42.4
MID_SIZE = fit_size(M_INK_H, "4")
MID_GAP = 2
MID_CELL = (round(max(ink_size(str(d), load_font(MID_SIZE))[0] for d in range(10)) * X_SCALE) + MID_GAP,
            int(M_INK_H) + 4)
SUN_C, HEART_C = (121, 321), (287.6, 320)
W_LABEL_C, HR_LABEL_C = (163.5, 319.5), (325.9, 319.5)
TEMP_CX, HR_CX = W_LABEL_C[0] + MID_CELL[0], HR_LABEL_C[0] + MID_CELL[0]   # 右边缘: 数字中心=标签视觉中心
DEG_X, DEG_Y = TEMP_CX + 4, 363
Y_VAL2 = 359

# ---------------- 自动昼夜分区 (小时→0白天/1夜晚) ----------------
def is_day(h):
    return 6 <= h <= 17
HOUR_MAP = [0 if is_day(h) else 1 for h in range(24)]   # 0=白天帧, 1=夜晚帧

def draw_colon(color, w=COLON_W, h=TIME_CELL[1]):
    """冒号字形: 两圆点, 直径13.3, 圆心 0.335/0.815 字高; 与 image_0001 完全一致"""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top = (h - 65.7) / 2
    for fy in (0.335, 0.815):
        cy = top + fy * 65.7
        r = 13.3 / 2
        d.ellipse([w / 2 - r, cy - r, w / 2 + r, cy + r], fill=color)
    return im

def icon_deg(color, s=15):
    ss = 4
    im = Image.new("RGBA", (s * ss, s * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = int(2.4 * ss)
    d.ellipse([lw, lw, s * ss - lw, s * ss - lw], outline=color, width=lw)
    return im.resize((s, s), Image.LANCZOS)

# ---------------- 图标: 从参考图抠取 ----------------
REF = _os.environ.get("WF_REF_IMAGE", _os.path.join(ROOT, "reference", "design_ref_2048.png"))  # 外部设计参考图, 不入库; 用环境变量 WF_REF_IMAGE 指向本地副本
REF_CX, REF_CY, REF_R, REF_K = 1002, 1032, 780, 464.0 / 1560

def extract_icon(x0, y0, x1, y1, dom, color, size):
    ox0 = int(REF_CX - REF_R + x0 / REF_K)
    oy0 = int(REF_CY - REF_R + y0 / REF_K)
    ox1 = int(REF_CX - REF_R + x1 / REF_K)
    oy1 = int(REF_CY - REF_R + y1 / REF_K)
    src = Image.open(REF).convert("RGB").crop((ox0, oy0, ox1, oy1))
    out = Image.new("RGBA", src.size, color[:3] + (0,))
    sp, op = src.load(), out.load()
    for y in range(src.height):
        for x in range(src.width):
            a = dom(sp[x, y])
            op[x, y] = color[:3] + (int(max(0.0, min(1.0, a)) * 255),)
    return out.resize(size, Image.LANCZOS)

_yellow = lambda c: (c[0] - c[2]) / 115.0 - 0.05
_red = lambda c: (c[0] - c[1]) / 80.0 - 0.05

def sun_extract(color):
    return extract_icon(107.1, 306.7, 135.0, 335.5, _yellow, color, (28, 29))
def heart_extract(color):
    return extract_icon(276.3, 309.9, 298.9, 330.2, _red, color, (23, 21))

# ---------------- 主面素材 (images/) ----------------
INK = (112, 112, 116, 255)
GREET_DAY = (33, 33, 37, 255)
GREET_NIGHT = (228, 228, 233, 255)
LABEL_DAY = (33, 33, 37, 255)
LABEL_NIGHT = (205, 205, 210, 255)
SUN_DAY = (240, 165, 35, 255)
SUN_NIGHT = (255, 200, 95, 255)
HEART_DAY = (232, 55, 55, 255)
HEART_NIGHT = (255, 95, 95, 255)
BG_DAY = (217, 217, 215, 255)
BG_NIGHT = (16, 16, 18, 255)

def gen_main(outdir):
    os.makedirs(outdir, exist_ok=True)
    def save(n, im):
        im.save(os.path.join(outdir, n + ".png"))

    # 背景两帧(0811 映射): 0=白天, 1=夜晚
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bg).ellipse([0, 0, W - 1, H - 1], fill=BG_DAY)
    save("image_0000", bg)
    bgn = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bgn).ellipse([0, 0, W - 1, H - 1], fill=BG_NIGHT)
    save("image_0010", bgn)

    # 数字(中性灰, 昼夜共用)
    f_time = load_font(TIME_SIZE)
    for i in range(10):
        save(f"imagelist_0000_{i:04d}", glyph(str(i), f_time, INK, TIME_CELL))
    # 冒号字形(image_0001, 供闪烁偶帧复用)
    save("image_0001", draw_colon(INK))

    # 问候语 24 帧: 按小时烤深浅色
    f_g = load_font(GREET_SIZE)
    for h in range(24):
        txt = GREETINGS[0 if 5 <= h < 12 else 1 if 12 <= h < 18 else 2 if 18 <= h < 23 else 3]
        col = GREET_DAY if is_day(h) else GREET_NIGHT
        save(f"imagelist_0001_{h:04d}", text_image(txt, f_g, col, GREET_CELL))

    # 电量数字 / % (中性灰)
    f_b = load_font(BAT_SIZE)
    for i in range(10):
        save(f"imagelist_0002_{i:04d}", glyph(str(i), f_b, INK, BAT_CELL))
    _pw = round(ink_size("%", f_b)[0] * X_SCALE) + 2
    save("image_0003", glyph("%", load_font(int(BAT_SIZE * 0.88)), INK, (_pw, BAT_CELL[1])))

    # 温度/心率数字 (中性灰, 含负号帧)
    f_m = load_font(MID_SIZE)
    for i in range(10):
        save(f"imagelist_0003_{i:04d}", glyph(str(i), f_m, INK, MID_CELL))
    save("imagelist_0003_0010", glyph("-", f_m, INK, MID_CELL))

    save("image_0006", icon_deg(INK))

    # 标签两帧(白天深/夜晚浅) — 绑 0811
    f_cn = load_cn(25)
    for idx, text in (("0010", "电量"), ("0011", "天气"), ("0012", "心率")):
        save(f"imagelist_{idx}_0000", text_image(text, f_cn, LABEL_DAY))
        save(f"imagelist_{idx}_0001", text_image(text, f_cn, LABEL_NIGHT))

    # 图标两帧(白天/夜晚) — 绑 0811
    save("imagelist_0013_0000", sun_extract(SUN_DAY))
    save("imagelist_0013_0001", sun_extract(SUN_NIGHT))
    save("imagelist_0014_0000", heart_extract(HEART_DAY))
    save("imagelist_0014_0001", heart_extract(HEART_NIGHT))

    # 冒号闪烁 60 帧(透明帧法): 偶帧=字形, 奇帧=纯透明
    colon = Image.open(os.path.join(outdir, "image_0001.png"))
    for s in range(60):
        im = colon.copy() if s % 2 == 0 else Image.new("RGBA", colon.size, (0, 0, 0, 0))
        im.save(os.path.join(outdir, f"imagelist_0004_{s:04d}.png"))

    # 时间/问候语区透明热区(点击→闹钟)
    Image.new("RGBA", (200, 170), (0, 0, 0, 0)).save(os.path.join(outdir, "image_0009.png"))

# ---------------- AOD 素材 (images_aod/) — 静态深底浅字, 无闪烁无点击 ----------------
CA = dict(ink=(124, 124, 128, 255), greet=(150, 150, 154, 255),
          label=(150, 150, 154, 255), sun=(150, 110, 30, 255), heart=(150, 40, 40, 255))
def gen_aod(outdir):
    os.makedirs(outdir, exist_ok=True)
    def save(n, im):
        im.save(os.path.join(outdir, n + ".png"))

    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bg).ellipse([0, 0, W - 1, H - 1], fill=(0, 0, 0, 255))
    save("image_0000", bg)
    f_time = load_font(TIME_SIZE)
    for i in range(10):
        save(f"imagelist_0000_{i:04d}", glyph(str(i), f_time, CA["ink"], TIME_CELL))
    save("image_0001", draw_colon(CA["ink"]))   # AOD 静态冒号(不闪)
    f_g = load_font(GREET_SIZE)
    for h in range(24):
        txt = GREETINGS[0 if 5 <= h < 12 else 1 if 12 <= h < 18 else 2 if 18 <= h < 23 else 3]
        save(f"imagelist_0001_{h:04d}", text_image(txt, f_g, CA["greet"], GREET_CELL))
    f_b = load_font(BAT_SIZE)
    for i in range(10):
        save(f"imagelist_0002_{i:04d}", glyph(str(i), f_b, CA["ink"], BAT_CELL))
    _pw = round(ink_size("%", f_b)[0] * X_SCALE) + 2
    save("image_0003", glyph("%", load_font(int(BAT_SIZE * 0.88)), CA["ink"], (_pw, BAT_CELL[1])))
    f_m = load_font(MID_SIZE)
    for i in range(10):
        save(f"imagelist_0003_{i:04d}", glyph(str(i), f_m, CA["ink"], MID_CELL))
    save("imagelist_0003_0010", glyph("-", f_m, CA["ink"], MID_CELL))
    save("image_0006", icon_deg(CA["ink"]))
    f_cn = load_cn(25)
    save("image_0002", text_image("电量", f_cn, CA["label"]))
    save("image_0004", sun_extract(CA["sun"]))
    save("image_0005", text_image("天气", f_cn, CA["label"]))
    save("image_0007", heart_extract(CA["heart"]))
    save("image_0008", text_image("心率", f_cn, CA["label"]))

gen_main(IMG)
gen_aod(IMG_AOD)

# ---------------- wfDef ----------------
def p7_dignum(idx, x, y, ds, lst, n, show_zero=True, align=2):
    return {"type": "widge_dignum", "x": int(round(x)), "y": int(round(y)),
            "showCount": 2, "spacing": 0, "align": align, "showZero": show_zero,
            "dataSrc": ds, "imageList": [f"{lst}_{i:04d}" for i in range(n)],
            "prop7Index": idx, "prop7Length": 20,
            "prop7Raw": ds + "16" + "0000" + "E803" + "000000" + "03" + "00" * 8}

def imagelist_raw(ds, values):
    """imagelist prop7Raw 模板(与 v3/v4 问候语同构): ds + 固定头 + 值表"""
    raw = ds + "00" + "20" + "0000" + "0000" + "000000" + "03" + "0002"
    vals = "".join(v.to_bytes(4, "little").hex() for v in values)
    return raw + vals, 16 + len(values) * 4

def p7_bg(idx):
    """背景按小时(0811)切换: image_0000=白天, image_0010=夜晚, 由 HOUR_MAP 映射"""
    raw, plen = imagelist_raw("0811", HOUR_MAP)
    return {"type": "widge_imagelist", "x": 0, "y": 0, "dataSrc": "0811",
            "imageList": ["image_0000", "image_0010"], "imageIndexList": list(HOUR_MAP),
            "prop7Index": idx, "prop7Length": plen, "prop7Raw": raw}

def p7_greeting(idx):
    raw, plen = imagelist_raw("0811", list(range(24)))
    return {"type": "widge_imagelist", "x": int(232 - GREET_CELL[0] // 2), "y": Y_GREET,
            "dataSrc": "0811", "imageList": [f"imagelist_0001_{h:04d}" for h in range(24)],
            "imageIndexList": list(range(24)), "prop7Index": idx, "prop7Length": plen,
            "prop7Raw": raw}

def p7_twostate(idx, x, y, name):
    """标签/图标两帧(0811): _0000=白天, _0001=夜晚, 由 HOUR_MAP 映射
    注: 传入的 (x,y) 视为视觉中心, 内部转成左边缘(威根 imagelist 左边缘对齐)"""
    raw, plen = imagelist_raw("0811", HOUR_MAP)
    w = Image.open(os.path.join(IMG, f"imagelist_{name}_0000.png")).width
    return {"type": "widge_imagelist", "x": int(round(x - w / 2)), "y": int(round(y)),
            "dataSrc": "0811",
            "imageList": [f"imagelist_{name}_0000", f"imagelist_{name}_0001"],
            "imageIndexList": list(HOUR_MAP), "prop7Index": idx, "prop7Length": plen,
            "prop7Raw": raw}

def p7_colon_blink(idx):
    """冒号 1Hz 闪烁(透明帧法): 1811 驱动 60 帧, 偶帧=字形(兜底不闪), 奇帧=透明"""
    raw, plen = imagelist_raw("1811", list(range(60)))
    return {"type": "widge_imagelist",
            "x": int(round(TIME_CENTER_X - COLON_W / 2)), "y": Y_TIME, "dataSrc": "1811",
            "imageList": [f"imagelist_0004_{s:04d}" for s in range(60)],
            "imageIndexList": list(range(60)), "prop7Index": idx, "prop7Length": plen,
            "prop7Raw": raw}

def centered(name, cx, cy, src=IMG):
    im = Image.open(os.path.join(src, name + ".png"))
    return {"type": "element", "x": int(round(cx - im.width / 2)),
            "y": int(round(cy - im.height / 2)), "image": name}

JUMP = {"alarm": "010C8F02", "weather": "030B1F02", "hrm": "03065F00",
        "steps": "03023F01", "music": "010C5F01", "timer": "010C6F02"}
def tap(el, app):
    el = dict(el)
    el["jumpName"] = app
    el["jumpCode"] = JUMP[app]
    return el

def build(aod=False):
    e, p = [], 0
    if aod:
        e.append({"type": "element", "x": 0, "y": 0, "image": "image_0000"})
        e.append(p7_dignum(p, HOUR_CX, Y_TIME, "081102", "imagelist_0000", 10)); p += 1
        e.append(centered("image_0001", TIME_CENTER_X, Y_TIME + TIME_CELL[1] / 2, IMG_AOD))
        e.append(p7_dignum(p, MIN_CX, Y_TIME, "101102", "imagelist_0000", 10)); p += 1
        e.append(p7_greeting(p)); p += 1
        e.append(centered("image_0002", *BAT_LABEL_C, IMG_AOD))
        e.append(p7_dignum(p, BAT_NUM_CX, Y_VAL1, "084103", "imagelist_0002", 10, show_zero=False)); p += 1
        e.append({"type": "element", "x": int(BAT_PCT_X), "y": Y_VAL1, "image": "image_0003"})
        e.append(centered("image_0004", *SUN_C, IMG_AOD))
        e.append(centered("image_0005", *W_LABEL_C, IMG_AOD))
        e.append(p7_dignum(p, TEMP_CX, Y_VAL2, "203103", "imagelist_0003", 11, show_zero=False)); p += 1
        e.append({"type": "element", "x": int(DEG_X), "y": int(DEG_Y), "image": "image_0006"})
        e.append(centered("image_0007", *HEART_C, IMG_AOD))
        e.append(centered("image_0008", *HR_LABEL_C, IMG_AOD))
        e.append(p7_dignum(p, HR_CX, Y_VAL2, "082202", "imagelist_0003", 11)); p += 1
        return e, p

    # 主面
    e.append(p7_bg(p)); p += 1                              # 背景 自动昼夜
    e.append(p7_dignum(p, HOUR_CX, Y_TIME, "081102", "imagelist_0000", 10)); p += 1
    e.append(p7_colon_blink(p)); p += 1                    # 冒号透明帧闪烁
    e.append(p7_dignum(p, MIN_CX, Y_TIME, "101102", "imagelist_0000", 10)); p += 1
    e.append(p7_greeting(p)); p += 1
    e.append(p7_twostate(p, *BAT_LABEL_C, "0010")); p += 1  # 电量标签 换色
    e.append(p7_dignum(p, BAT_NUM_CX, Y_VAL1, "084103", "imagelist_0002", 10, show_zero=False)); p += 1
    e.append({"type": "element", "x": int(BAT_PCT_X), "y": Y_VAL1, "image": "image_0003"})
    e.append(tap(p7_twostate(p, *SUN_C, "0013"), "weather")); p += 1       # 太阳 换色+点击
    e.append(tap(p7_twostate(p, *W_LABEL_C, "0011"), "weather")); p += 1   # 天气标签 换色+点击
    e.append(tap(p7_dignum(p, TEMP_CX, Y_VAL2, "203103", "imagelist_0003", 11, show_zero=False), "weather")); p += 1
    e.append({"type": "element", "x": int(DEG_X), "y": int(DEG_Y), "image": "image_0006"})
    e.append(tap(p7_twostate(p, *HEART_C, "0014"), "hrm")); p += 1        # 爱心 换色+点击
    e.append(tap(p7_twostate(p, *HR_LABEL_C, "0012"), "hrm")); p += 1     # 心率标签 换色+点击
    e.append(tap(p7_dignum(p, HR_CX, Y_VAL2, "082202", "imagelist_0003", 11), "hrm")); p += 1
    e.append(tap(centered("image_0009", 232, 168), "alarm"))              # 时间/问候语区 点击→闹钟
    return e, p

els, np7 = build()
els_aod, _ = build(aod=True)
wf = {"name": "MinimalS3_v5_daynight", "id": "000000000", "previewImg": "preview",
      "faceStyleCount": 4, "elementsNormal": els, "elementsAod": els_aod,
      "extraProp7Normal": [], "extraProp7Aod": [],
      "namedFaceRecords": True, "faceNames": ["样式1", "息屏"]}
json.dump(wf, open(os.path.join(ROOT, "wfDef.json"), "w"), ensure_ascii=False, indent=1)

# ---------------- 预览 ----------------
def render(src, els_list, hour=9, minute=41, bat=82, temp=24, hr=73, sec=41):
    # 背景由元素列表首个元素(主面 imagelist 0811 / AOD 静态 image_0000)在循环中合成
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for el in els_list:
        t = el["type"]
        if t == "element":
            im.alpha_composite(Image.open(os.path.join(src, el["image"] + ".png")).convert("RGBA"), (el["x"], el["y"]))
        elif t == "widge_dignum":
            txt = {"081102": f"{hour:02d}", "101102": f"{minute:02d}",
                   "084103": f"{bat:02d}", "203103": str(temp),
                   "082202": f"{hr:02d}"}[el["dataSrc"]]
            cw = Image.open(os.path.join(src, el["imageList"][0] + ".png")).width
            # 威根 dignum 右对齐到 x(整串右边缘), 与真机一致; 预览才能反映真实位置
            x0 = el["x"] - cw * len(txt)
            for k, ch in enumerate(txt):
                g = Image.open(os.path.join(src, el["imageList"][10 if ch == "-" else int(ch)] + ".png")).convert("RGBA")
                im.alpha_composite(g, (int(x0) + k * cw, el["y"]))
        elif el["dataSrc"] == "0811":
            # imagelist: 24 帧=问候语(按小时); 2 帧=背景/标签/图标(按 HOUR_MAP)
            if len(el["imageList"]) == 24:
                im.alpha_composite(Image.open(os.path.join(src, el["imageList"][hour] + ".png")).convert("RGBA"), (el["x"], el["y"]))
            else:
                im.alpha_composite(Image.open(os.path.join(src, el["imageList"][HOUR_MAP[hour]] + ".png")).convert("RGBA"), (el["x"], el["y"]))
        elif el["dataSrc"] == "1811":   # 冒号闪烁
            im.alpha_composite(Image.open(os.path.join(src, el["imageList"][sec % 60] + ".png")).convert("RGBA"), (el["x"], el["y"]))
    return im

prev_day = render(IMG, els, hour=9, minute=41, sec=40)
prev_night = render(IMG, els, hour=21, minute=7, sec=40)
prev_aod = render(IMG_AOD, els_aod, hour=21, minute=7)
prev_on = render(IMG, els, hour=9, minute=41, sec=40)
prev_off = render(IMG, els, hour=9, minute=41, sec=41)
prev_day.convert("RGB").save(os.path.join(ROOT, "preview_day.png"))
prev_night.convert("RGB").save(os.path.join(ROOT, "preview_night.png"))
prev_aod.convert("RGB").save(os.path.join(ROOT, "preview_aod.png"))
prev_on.convert("RGB").save(os.path.join(ROOT, "preview_blink_on.png"))
prev_off.convert("RGB").save(os.path.join(ROOT, "preview_blink_off.png"))
prev_day.convert("RGB").quantize(256).save(os.path.join(IMG, "preview.png"))
sheet = Image.new("RGB", (W * 3 + 60, H), (18, 18, 20))
for i, im in enumerate((prev_day, prev_night, prev_aod)):
    sheet.paste(im.convert("RGB"), (i * (W + 30), 0))
sheet.resize((sheet.width, sheet.height), Image.LANCZOS).save(os.path.join(ROOT, "preview_v5.png"))
print("OK 主面元素", len(els), "prop7", np7, "AOD元素", len(els_aod),
      "| 时间块宽", round(TIME_BLOCK_W, 1), "| 冒号帧 60(透明法) | 热区:",
      sum(1 for e in els if e.get("jumpCode")))
