#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinimalS3 v4 — 自动昼夜版（背景按 AM/PM 自动切换，文字用中性灰兼顾深浅底）

参考图: ~/Downloads/1/简约表盘，后面做.png (2048x2048)
屏幕圆: 中心(1002,1032) 半径780  →  464 画布换算 K = 464/1560 = 0.29744

实测基准 (464 空间):
  背景 (217,217,215) / 时间数值墨 (3,4,3) / 问候语 (59,58,56) / 标签 (51,51,49)
  时间: 块 x 127.9..333.4 (宽205.5) 字高65.7 冒号13.7 两点直径13.3
  问候语: y 165.7..190.1, x 151.1..314.1, 中心(232.6,177.9)
  电量标签: 中心(392.9,218.2)  电量数值: x 366.4..419.7 中心(393,251.6)
  太阳: 中心(121,321) 28.0x28.9 (250,170,37)
  心:   中心(287.6,320) 22.6x20.2 (235,49,49)
  天气标签: 中心(163.5,319.5)   心率标签: 中心(325.9,319.5)
  24°: x 119.3..202.3 (数值中心152, °在187.7)  73: x 281.4..345.0 (中心313.2)
  数值行 y 345.3..389.0 (中心367.2)
"""
import os, math, json
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(ROOT, "images")
IMG_AOD = os.path.join(ROOT, "images_aod")
os.makedirs(IMG, exist_ok=True)
os.makedirs(IMG_AOD, exist_ok=True)
W = H = 464

# ---------------- 配色 (实测) ----------------
C = dict(bg=(217, 217, 215, 255), bg_night=(16, 16, 18, 255),
         ink=(112, 112, 116, 255), greet=(104, 104, 108, 255),
         label=(104, 104, 108, 255), sun=(250, 170, 37, 255), heart=(235, 49, 49, 255))
CA = dict(bg=(0, 0, 0, 255), ink=(124, 124, 128, 255), greet=(104, 104, 108, 255),
          label=(106, 106, 110, 255), sun=(150, 110, 30, 255), heart=(140, 32, 32, 255))

# ---------------- 字体 ----------------
WEIGHT = "Semibold"        # 实测字干/字高=0.172 → Semibold(0.164) 最近; 字宽比介于 Regular/Medium 之间
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
    """按目标墨迹高度反解字号"""
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

X_SCALE = 0.95            # 横向压缩: 参考为 SF Pro Display 比例, 比 SFNS(Text) 窄约 5%


def glyph(s, font, color, cell):
    """数字/符号字模: 渲染 → 横向压缩(逼近 Display 比例) → 居中放入固定画布"""
    im = text_image(s, font, color)
    if abs(X_SCALE - 1) > 1e-6:
        im = im.resize((max(1, round(im.width * X_SCALE)), im.height), Image.LANCZOS)
    if im.width > cell[0] or im.height > cell[1]:
        print(f"  ⚠ 字模裁切 '{s}' ink={im.size} cell={cell}")
    base = Image.new("RGBA", cell, (0, 0, 0, 0))
    base.alpha_composite(im, ((cell[0] - im.width) // 2, (cell[1] - im.height) // 2))
    return base


def text_image(s, font, color, cell=None):
    """渲染文本; cell=(w,h) 时在固定画布内居中 (画布务必 >= 墨迹尺寸, 否则裁切)"""
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

# ---------------- 布局 (实测) ----------------
# --- 字模尺寸: 按参考实测墨迹高度自动拟合 ---
T_INK_H = 65.7              # 时间字高(实测)
TIME_SIZE = fit_size(T_INK_H, "0")
TIME_GAP = 2                # 字间距(固定字模下尽量紧凑, 参考为比例字距视觉间隙约2-6)
TIME_CELL = (round(max(ink_size(str(d), load_font(TIME_SIZE))[0] for d in range(10)) * X_SCALE) + TIME_GAP,
             int(T_INK_H) + 4)
COLON_W, COLON_GAP = 14, 13.5
COLON_H, Y_COLON = 47, 100        # 闪烁冒号: 画布 14x47, 两点墨迹 y 101.4..146.3
COLON_Y1, COLON_Y2 = 8.05, 39.6   # 画布内两点圆心 (参考 108.0 / 139.6)
TIME_BLOCK_W = 4 * TIME_CELL[0] + COLON_GAP
TIME_SHIFT = 4                # 补偿 '1' 在固定字模中居中导致的墨迹重心左偏
TIME_LEFT = 232 - TIME_BLOCK_W / 2 + TIME_SHIFT
HOUR_CX = TIME_LEFT + TIME_CELL[0]
MIN_CX = TIME_LEFT + 3 * TIME_CELL[0] + COLON_GAP
Y_TIME = 85                 # 画布顶 → 墨迹顶 ≈ 86

GREETINGS = ["Good Morning", "Good Afternoon", "Good Evening", "Good Night"]
G_INK_H = 25.9              # 问候语墨迹高(含 g 下沉; 拟合补偿后实测=24.4)
GREET_SIZE = fit_size(G_INK_H, "Good Morning")
_gw = max(ink_size(g, load_font(GREET_SIZE))[0] for g in GREETINGS)
GREET_CELL = (_gw + 4, int(G_INK_H) + 4)
Y_GREET = 164               # 画布顶 → 墨迹中心 177.9

B_INK_H = 19.6              # 电量数字高(实测 20.8 含 %, 数字本身略小)
BAT_SIZE = fit_size(B_INK_H, "8") + 1
BAT_GAP = 2
BAT_CELL = (round(max(ink_size(str(d), load_font(BAT_SIZE))[0] for d in range(10)) * X_SCALE) + BAT_GAP,
            int(B_INK_H) + 4)
BAT_LABEL_C = (393, 218)
BAT_NUM_CX = 381            # "82" 中心 (366.4+396.2)/2
BAT_PCT_X = 399             # % 墨迹左
Y_VAL1 = 239                # 画布顶 → 墨迹中心 251.6

M_INK_H = 42.4              # 温度/心率字高(实测 43.7 含描边扩散)
MID_SIZE = fit_size(M_INK_H, "4")
MID_GAP = 2
MID_CELL = (round(max(ink_size(str(d), load_font(MID_SIZE))[0] for d in range(10)) * X_SCALE) + MID_GAP,
            int(M_INK_H) + 4)
SUN_C, HEART_C = (121, 321), (287.6, 320)
W_LABEL_C, HR_LABEL_C = (163.5, 319.5), (325.9, 319.5)
TEMP_CX, HR_CX = 152, 313.2
DEG_X, DEG_Y = 187.7, 349
Y_VAL2 = 345                # 画布顶 → 墨迹中心 367.2

def icon_sun(color, w=28, h=29):
    ss = 4
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = (w * ss / 2, h * ss / 2)
    r = 5.4 * ss                      # 实测外接 28 → 圆+光芒
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=color)
    for k in range(8):
        a = math.pi * k / 4
        d.line([c[0] + math.cos(a) * r * 1.85, c[1] + math.sin(a) * r * 1.85,
                c[0] + math.cos(a) * r * 2.85, c[1] + math.sin(a) * r * 2.85],
               fill=color, width=int(2.0 * ss))
    return im.resize((w, h), Image.LANCZOS)

def icon_heart(color, w=23, h=21):
    ss = 4
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = w * ss * 0.26
    d.ellipse([0, 0, 2 * r, 2 * r], fill=color)
    d.ellipse([w * ss - 2 * r, 0, w * ss, 2 * r], fill=color)
    d.polygon([(0, r * 1.1), (w * ss, r * 1.1), (w * ss / 2, h * ss * 0.86)], fill=color)
    d.ellipse([w * ss * 0.5 - r * 1.0, h * ss * 0.52, w * ss * 0.5 + r * 1.0, h * ss * 1.05], fill=color)
    return im.resize((w, h), Image.LANCZOS)

def icon_deg(color, s=15):
    ss = 4
    im = Image.new("RGBA", (s * ss, s * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = int(2.4 * ss)
    d.ellipse([lw, lw, s * ss - lw, s * ss - lw], outline=color, width=lw)
    return im.resize((s, s), Image.LANCZOS)

def gen(outdir, pal):
    os.makedirs(outdir, exist_ok=True)
    def save(n, im):
        im.save(os.path.join(outdir, n + ".png"))

    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bg).ellipse([0, 0, W - 1, H - 1], fill=pal["bg"])
    save("image_0000", bg)
    if pal.get("bg_night"):          # 夜间背景(AM/PM 帧列表第 2 帧)
        bgn = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(bgn).ellipse([0, 0, W - 1, H - 1], fill=pal["bg_night"])
        save("image_0010", bgn)

    f_time = load_font(TIME_SIZE)
    for i in range(10):
        save(f"imagelist_0000_{i:04d}", glyph(str(i), f_time, pal["ink"], TIME_CELL))
    # 冒号: 两圆点, 直径13.3, 圆心 0.335/0.815 字高
    col = Image.new("RGBA", (COLON_W, TIME_CELL[1]), (0, 0, 0, 0))
    d = ImageDraw.Draw(col)
    top = (TIME_CELL[1] - 65.7) / 2
    for fy in (0.335, 0.815):
        cy = top + fy * 65.7
        r = 13.3 / 2
        d.ellipse([COLON_W / 2 - r, cy - r, COLON_W / 2 + r, cy + r], fill=pal["ink"])
    save("image_0001", col)

    f_g = load_font(GREET_SIZE)
    greets = [text_image(g, f_g, pal["greet"], GREET_CELL) for g in GREETINGS]
    for hr in range(24):
        gi = 0 if 5 <= hr < 12 else 1 if 12 <= hr < 18 else 2 if 18 <= hr < 23 else 3
        save(f"imagelist_0001_{hr:04d}", greets[gi])

    f_cn = load_cn(25)
    save("image_0002", text_image("电量", f_cn, pal["label"]))
    save("image_0005", text_image("天气", f_cn, pal["label"]))
    save("image_0008", text_image("心率", f_cn, pal["label"]))

    f_b = load_font(BAT_SIZE)
    for i in range(10):
        save(f"imagelist_0002_{i:04d}", glyph(str(i), f_b, pal["ink"], BAT_CELL))
    _pw = round(ink_size("%", f_b)[0] * X_SCALE) + 2
    save("image_0003", glyph("%", load_font(int(BAT_SIZE * 0.88)), pal["ink"], (_pw, BAT_CELL[1])))

    f_m = load_font(MID_SIZE)
    for i in range(10):
        save(f"imagelist_0003_{i:04d}", glyph(str(i), f_m, pal["ink"], MID_CELL))
    save("imagelist_0003_0010", glyph("-", f_m, pal["ink"], MID_CELL))

    save("image_0006", icon_deg(pal["ink"]))

gen(IMG, C)
gen(IMG_AOD, CA)

# ---------------- 图标: 直接从参考图抠取 (形状 100% 一致) ----------------
REF = "/Users/admin/Downloads/1/简约表盘，后面做.png"
REF_CX, REF_CY, REF_R, REF_K = 1002, 1032, 780, 464.0 / 1560


def extract_icon(x0, y0, x1, y1, dom, color, size):
    """x0..y1 为 464 空间墨迹框; dom(c)->0..1 色彩显著度; 抠取后缩放到 size"""
    # 直接用实测墨迹框(不裁 bbox, 保证图标占满与参考相同的footprint)
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


_yellow = lambda c: (c[0] - c[2]) / 115.0 - 0.05      # 太阳
_red = lambda c: (c[0] - c[1]) / 80.0 - 0.05         # 爱心
for _dir, _pal in ((IMG, C), (IMG_AOD, CA)):
    extract_icon(107.1, 306.7, 135.0, 335.5, _yellow, _pal["sun"], (28, 29)).save(
        os.path.join(_dir, "image_0004.png"))
    extract_icon(276.3, 309.9, 298.9, 330.2, _red, _pal["heart"], (23, 21)).save(
        os.path.join(_dir, "image_0007.png"))

# 时间/问候语区域透明热区(点击 → 闹钟), 需在 build() 前落盘
Image.new("RGBA", (200, 170), (0, 0, 0, 0)).save(os.path.join(IMG, "image_0009.png"))

# ---------------- wfDef ----------------
def p7_dignum(idx, x, y, ds, lst, n, show_zero=True, align=2):
    return {"type": "widge_dignum", "x": int(round(x)), "y": int(round(y)),
            "showCount": 2, "spacing": 0, "align": align, "showZero": show_zero,
            "dataSrc": ds, "imageList": [f"{lst}_{i:04d}" for i in range(n)],
            "prop7Index": idx, "prop7Length": 20,
            "prop7Raw": ds + "16" + "0000" + "E803" + "000000" + "03" + "00" * 8}

def p7_greeting(idx):
    raw = "0811" + "00" + "20" + "0000" + "0000" + "000000" + "03" + "0002" + "0000"
    vals = "".join(h.to_bytes(4, "little").hex() for h in range(24))
    return {"type": "widge_imagelist", "x": int(232 - GREET_CELL[0] // 2), "y": Y_GREET,
            "dataSrc": "0811", "imageList": [f"imagelist_0001_{h:04d}" for h in range(24)],
            "imageIndexList": list(range(24)), "prop7Index": idx,
            "prop7Length": 16 + 24 * 4, "prop7Raw": raw + vals}

def p7_bg_am_pm(idx):
    """背景按 AM/PM(0813) 自动切换: 帧0=白天浅底, 帧1=夜间深底"""
    raw = "0813" + "00" + "20" + "0000" + "0000" + "000000" + "03" + "0002" + "0000"
    vals = "".join(v.to_bytes(4, "little").hex() for v in (0, 1))
    return {"type": "widge_imagelist", "x": 0, "y": 0, "dataSrc": "0813",
            "imageList": ["image_0000", "image_0010"], "imageIndexList": [0, 1],
            "prop7Index": idx, "prop7Length": 16 + 2 * 4, "prop7Raw": raw + vals}

def p7_colon_blink(idx):
    """冒号 1Hz 闪烁(遮挡层方案): 偶数秒透明(露冒号) / 奇数秒背景色遮住"""
    raw = "1811" + "00" + "20" + "0000" + "0000" + "000000" + "03" + "0002" + "0000"
    vals = "".join(s.to_bytes(4, "little").hex() for s in range(60))
    return {"type": "widge_imagelist",
            "x": int(round(TIME_LEFT + 2 * TIME_CELL[0] + (COLON_GAP - COLON_W) / 2)),
            "y": Y_COLON, "dataSrc": "1811",
            "imageList": [f"imagelist_0004_{s:04d}" for s in range(60)],
            "imageIndexList": list(range(60)), "prop7Index": idx,
            "prop7Length": 16 + 60 * 4, "prop7Raw": raw + vals}

def centered(name, cx, cy, src=IMG):
    im = Image.open(os.path.join(src, name + ".png"))
    return {"type": "element", "x": int(round(cx - im.width / 2)),
            "y": int(round(cy - im.height / 2)), "image": name}

# 点击跳转码 (来自 Mi-Create 官方导出器 src/utils/exporter.py jump_codes)
JUMP = {"alarm": "010C8F02", "weather": "030B1F02", "hrm": "03065F00",
        "steps": "03023F01", "music": "010C5F01", "timer": "010C6F02"}

def tap(el, app):
    el = dict(el)
    el["jumpName"] = app
    el["jumpCode"] = JUMP[app]
    return el


def tap_if(el, app, enabled):
    return tap(el, app) if enabled else el

def build(aod=False):
    e, p = [], 0
    if aod:
        e.append({"type": "element", "x": 0, "y": 0, "image": "image_0000"})
    else:
        e.append(p7_bg_am_pm(p)); p += 1
    e.append(tap_if(p7_dignum(p, HOUR_CX, Y_TIME, "081102", "imagelist_0000", 10), "alarm", not aod)); p += 1
    # 静态冒号常驻(兜底: 即便闪烁驱动失效, 冒号仍在)
    e.append({"type": "element", "x": int(round(TIME_LEFT + 2 * TIME_CELL[0])),
              "y": Y_TIME, "image": "image_0001"})
    # 自动昼夜版不做冒号闪烁: 遮挡层需跟随背景色, 而一个 imagelist 只能绑一个数据源
    e.append(tap_if(p7_dignum(p, MIN_CX, Y_TIME, "101102", "imagelist_0000", 10), "alarm", not aod)); p += 1
    e.append(p7_greeting(p)); p += 1
    e.append(centered("image_0002", *BAT_LABEL_C))
    e.append(p7_dignum(p, BAT_NUM_CX, Y_VAL1, "084103", "imagelist_0002", 10, show_zero=False)); p += 1
    e.append({"type": "element", "x": int(BAT_PCT_X), "y": Y_VAL1, "image": "image_0003"})
    e.append(tap_if(centered("image_0004", *SUN_C), "weather", not aod))
    e.append(tap_if(centered("image_0005", *W_LABEL_C), "weather", not aod))
    e.append(tap_if(p7_dignum(p, TEMP_CX, Y_VAL2, "203103", "imagelist_0003", 11, show_zero=False),
                 "weather", not aod)); p += 1
    e.append({"type": "element", "x": int(DEG_X), "y": int(DEG_Y), "image": "image_0006"})
    e.append(tap_if(centered("image_0007", *HEART_C), "hrm", not aod))
    e.append(tap_if(centered("image_0008", *HR_LABEL_C), "hrm", not aod))
    e.append(tap_if(p7_dignum(p, HR_CX, Y_VAL2, "082202", "imagelist_0003", 11), "hrm", not aod)); p += 1
    if not aod:   # 时间/问候语区域整块热区(透明图) → 闹钟
        e.append(tap(centered("image_0009", 232, 168), "alarm"))
    return e, p

els, np7 = build()
els_aod, _ = build(aod=True)
wf = {"name": "MinimalS3_v4_daynight", "id": "000000000", "previewImg": "preview",
      "faceStyleCount": 4, "elementsNormal": els, "elementsAod": els_aod,
      "extraProp7Normal": [], "extraProp7Aod": [],
      "namedFaceRecords": True, "faceNames": ["样式1", "息屏"]}
json.dump(wf, open(os.path.join(ROOT, "wfDef.json"), "w"), ensure_ascii=False, indent=1)

# ---------------- 预览 ----------------
def render(pal, src, els_list, hour=9, minute=41, bat=82, temp=24, hr=73, sec=41, bg_name=None):
    im = Image.new("RGBA", (W, H), (12, 12, 13, 255))
    im.alpha_composite(Image.open(os.path.join(src, (bg_name or "image_0000") + ".png")))
    for el in els_list:
        t = el["type"]
        if t == "element":
            im.alpha_composite(Image.open(os.path.join(src, el["image"] + ".png")).convert("RGBA"),
                               (el["x"], el["y"]))
        elif t == "widge_dignum":
            txt = {"081102": f"{hour:02d}", "101102": f"{minute:02d}",
                   "084103": f"{bat:02d}", "203103": str(temp),
                   "082202": f"{hr:02d}"}[el["dataSrc"]]
            cw = Image.open(os.path.join(src, el["imageList"][0] + ".png")).width
            x0 = el["x"] - cw * len(txt) // 2 if el.get("align") == 2 else el["x"]
            for k, ch in enumerate(txt):
                g = Image.open(os.path.join(src, el["imageList"][10 if ch == "-" else int(ch)] + ".png")).convert("RGBA")
                im.alpha_composite(g, (int(x0) + k * cw, el["y"]))
        elif el["dataSrc"] == "0813":      # 背景(AM/PM)
            im.alpha_composite(Image.open(os.path.join(src, bg_name or "image_0000") + ".png").convert("RGBA"),
                               (el["x"], el["y"]))
        elif el["dataSrc"] == "0811":      # 问候语
            im.alpha_composite(Image.open(os.path.join(src, f"imagelist_0001_{hour:04d}.png")).convert("RGBA"),
                               (el["x"], el["y"]))
        else:                              # 冒号遮挡层(自动昼夜版不启用)
            im.alpha_composite(Image.open(os.path.join(src, f"imagelist_0004_{sec % 60:04d}.png")).convert("RGBA"),
                               (el["x"], el["y"]))
    return im

# 冒号闪烁帧 + 时间区透明热区
def gen_blink(pal):
    """60 帧: 偶数秒全透明(露出静态冒号) / 奇数秒用背景色遮挡"""
    for s in range(60):
        im = Image.new("RGBA", (COLON_W, COLON_H), (0, 0, 0, 0))
        if s % 2 == 1:
            ImageDraw.Draw(im).rectangle([0, 0, COLON_W - 1, COLON_H - 1], fill=pal["bg"])
        im.save(os.path.join(IMG, f"imagelist_0004_{s:04d}.png"))


gen_blink(C)
prev_day = render(C, IMG, els, hour=9, minute=41, bg_name="image_0000")
prev_night = render(C, IMG, els, hour=21, minute=7, bg_name="image_0010")
prev = prev_day
prev_aod = render(CA, IMG_AOD, els_aod, hour=21, minute=7)
prev.convert("RGB").save(os.path.join(ROOT, "preview_render.png"))
prev_aod.convert("RGB").save(os.path.join(ROOT, "preview_render_aod.png"))
# 闪烁两态对比帧
prev_on = render(C, IMG, els, hour=9, minute=41, sec=40)
prev_off = render(C, IMG, els, hour=9, minute=41, sec=41)
prev_on.convert("RGB").save(os.path.join(ROOT, "preview_blink_on.png"))
prev_off.convert("RGB").save(os.path.join(ROOT, "preview_blink_off.png"))
prev.convert("RGB").quantize(256).save(os.path.join(IMG, "preview.png"))
prev_day.convert("RGB").save(os.path.join(ROOT, "preview_day.png"))
prev_night.convert("RGB").save(os.path.join(ROOT, "preview_night.png"))
sheet = Image.new("RGB", (W * 3 + 60, H), (18, 18, 20))
for i, im in enumerate((prev_day, prev_night, prev_aod)):
    sheet.paste(im.convert("RGB"), (i * (W + 30), 0))
sheet.resize((sheet.width, sheet.height), Image.LANCZOS).save(os.path.join(ROOT, "preview_daynight.png"))
print("OK 元素", len(els), "prop7", np7, "| 时间块宽", round(TIME_BLOCK_W, 1),
      "| 冒号帧 60 | 热区:", sum(1 for e in els if e.get("jumpCode")))
