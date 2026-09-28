#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ElderS3 v1 — 老人数字表盘素材生成 + wfDef + 预览（464x464，深色单配色，Normal+AOD 双面）

布局（圆心 232,232）：
  日期行 y=58 : 「N月」(1012,12帧) + 「N日」(1812,31帧) + 「周X」(2012,7帧)  预渲染帧
  大时间 y=140: dignum 081102 时 + 静态冒号 + dignum 101102 分 (118px Bold)
  心率  cy=268: ❤图标 + dignum 082202 (92px 红) + 「心率」标签（同行）
  底部三列 cx=138/232/326:
      电量: 电池图标 + dignum 084103 (40px) + 「电量」
      天气: 3031 天气码 imagelist (25码→9种图标) + dignum 203103 (40px) + 「天气」
      步数: 脚印图标 + dignum 082105 (40px, spacing 254) + 「步数」
prop7Raw 模板逐字复用 RouletteS3 v58 金标准（打包器覆写 b0-2/b3/b8-10/b13）。
无指针盘 → 无需 ep7 伴侣；无 AOD 闪烁；无点击热区（防老人误触）。
"""
import os, json, math, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(ROOT, "images")
IMG_AOD = os.path.join(ROOT, "images_aod")
os.makedirs(IMG, exist_ok=True)
os.makedirs(IMG_AOD, exist_ok=True)
W = H = 464

# ---------------- 配色 ----------------
C = dict(bg=(0, 0, 0, 255), ink=(255, 255, 255, 255), date=(235, 235, 240, 255),
         label=(185, 185, 190, 255), heart=(255, 69, 58, 255),
         batt=(48, 209, 88, 255), sun=(255, 204, 0, 255), step=(100, 160, 255, 255),
         cloud=(235, 235, 240, 255), rain=(100, 160, 255, 255), fog=(170, 170, 178, 255),
         haze=(200, 160, 90, 255))
CA = dict(bg=(0, 0, 0, 255), ink=(168, 168, 173, 255), date=(150, 150, 155, 255),
          label=(110, 110, 115, 255), heart=(140, 32, 32, 255),
          batt=(60, 120, 70, 255), sun=(150, 120, 20, 255), step=(70, 105, 160, 255),
          cloud=(150, 150, 155, 255), rain=(70, 105, 160, 255), fog=(120, 120, 125, 255),
          haze=(140, 112, 62, 255))

# ---------------- 字体 ----------------
def load_font(size, weight="Semibold"):
    f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f

def load_cn(size):
    return ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", size, index=0)

def ink_size(s, font):
    tmp = Image.new("L", (font.size * (len(s) + 2), font.size * 3), 0)
    ImageDraw.Draw(tmp).text((tmp.width // 2, tmp.height // 2), s, font=font, fill=255, anchor="mm")
    bb = tmp.getbbox()
    return bb[2] - bb[0], bb[3] - bb[1]

def text_image(s, font, color):
    tmp = Image.new("RGBA", (font.size * (len(s) + 2), font.size * 3), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((tmp.width // 2, tmp.height // 2), s, font=font, fill=color, anchor="mm")
    return tmp.crop(tmp.getbbox())

def glyph(s, font, color, cell):
    im = text_image(s, font, color)
    if im.width > cell[0] or im.height > cell[1]:
        print(f"  ⚠ 字模裁切 '{s}' ink={im.size} cell={cell}")
    base = Image.new("RGBA", cell, (0, 0, 0, 0))
    base.alpha_composite(im, ((cell[0] - im.width) // 2, (cell[1] - im.height) // 2))
    return base

# ---------------- 布局 ----------------
DATE_SIZE = 38
F_DATE = load_cn(DATE_SIZE)
MONTHS = [f"{m}月" for m in range(1, 13)]
DAYS = [f"{dd}日" for dd in range(1, 32)]
WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]   # 源12: 0=周日
M_CELL = (max(ink_size(t, F_DATE)[0] for t in MONTHS) + 10, DATE_SIZE + 12)
D_CELL = (max(ink_size(t, F_DATE)[0] for t in DAYS) + 10, DATE_SIZE + 12)
W_CELL = (max(ink_size(t, F_DATE)[0] for t in WEEKDAYS) + 8, DATE_SIZE + 12)
Y_DATE = 58
DATE_GAP_M, DATE_GAP_W = 6, 10
DATE_TOTAL = M_CELL[0] + DATE_GAP_M + D_CELL[0] + DATE_GAP_W + W_CELL[0]
DATE_LEFT = round(232 - DATE_TOTAL / 2)
MONTH_X = DATE_LEFT
DAY_X = DATE_LEFT + M_CELL[0] + DATE_GAP_M
WK_X = DAY_X + D_CELL[0] + DATE_GAP_W

TIME_INK = ink_size("0", load_font(118, "Bold"))[1]        # ≈83
T_CELL = (max(ink_size(str(d), load_font(118, "Bold"))[0] for d in range(10)) + 4, TIME_INK + 6)
COLON_W, COLON_GAP = 16, 14
TIME_BLOCK = 4 * T_CELL[0] + COLON_GAP
TIME_LEFT = round(232 - TIME_BLOCK / 2)
Y_TIME = 140
HOUR_CX = TIME_LEFT + T_CELL[0]                 # dignum align=2 中心锚点
MIN_CX = TIME_LEFT + 3 * T_CELL[0] + COLON_GAP

HR_SIZE = 92
F_HR = load_font(HR_SIZE, "Bold")
HR_CELL = (max(ink_size(str(d), F_HR)[0] for d in range(10)) + 4, HR_SIZE + 8)
Y_HR_CY = 268
HR_ICON_S = 50
HR_GAP1, HR_GAP2 = 12, 16
HR_LW = ink_size("心率", load_cn(34))[0]
HR_TOTAL = HR_ICON_S + HR_GAP1 + 2 * HR_CELL[0] + HR_GAP2 + HR_LW
HR_X0 = round(232 - HR_TOTAL / 2)
HR_ICON_CX = HR_X0 + HR_ICON_S / 2
HR_NUM_CX = HR_X0 + HR_ICON_S + HR_GAP1 + HR_CELL[0]       # 2位 dignum align=2 中心
HR_LAB_X = HR_X0 + HR_ICON_S + HR_GAP1 + 2 * HR_CELL[0] + HR_GAP2

B_SIZE = 40
F_B = load_font(B_SIZE, "Semibold")
B_CELL = (max(ink_size(str(d), F_B)[0] for d in range(10)) + 3, B_SIZE + 6)
COL_BAT, COL_WEA, COL_STP = 138, 232, 326
Y_ICON_CY = 342
Y_NUM = 360
Y_LAB_CY = 416

# ---------------- 图标 ----------------
def ss_draw(w, h, fn):
    ss = 4
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), w * ss, h * ss)
    return im.resize((w, h), Image.LANCZOS)

def icon_heart(color, w=HR_ICON_S, h=HR_ICON_S - 4):
    def fn(d, W, H):
        r = W * 0.27
        cy = H * 0.42
        d.ellipse([W * 0.04, cy - r, W * 0.04 + 2 * r, cy + r], fill=color)
        d.ellipse([W * 0.96 - 2 * r, cy - r, W * 0.96, cy + r], fill=color)
        d.polygon([(W * 0.06, cy + r * 0.6), (W * 0.94, cy + r * 0.6), (W * 0.5, H * 0.92)], fill=color)
    return ss_draw(w, h, fn)

def icon_battery(fill_color, body, pct=0.75, w=38, h=22):
    def fn(d, W, H):
        lw = int(W * 0.07)
        d.rounded_rectangle([1, 1, W - W * 0.10, H - 1], radius=lw, outline=body, width=lw)
        d.rounded_rectangle([W - W * 0.08, H * 0.30, W - 1, H * 0.70], radius=2, fill=body)
        fw = (W - W * 0.10 - 4) * pct
        d.rounded_rectangle([1 + lw, 1 + lw, 1 + lw + fw, H - 1 - lw], radius=lw // 2, fill=fill_color)
    return ss_draw(w, h, fn)

def icon_sun(color, w=40, h=40):
    def fn(d, W, H):
        c = (W / 2, H / 2)
        r = W * 0.24
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=color)
        for k in range(8):
            a = math.pi * k / 4
            d.line([c[0] + math.cos(a) * r * 1.5, c[1] + math.sin(a) * r * 1.5,
                    c[0] + math.cos(a) * r * 2.2, c[1] + math.sin(a) * r * 2.2],
                   fill=color, width=int(W * 0.06) + 1)
    return ss_draw(w, h, fn)

def icon_cloud(color, w=44, h=32, dy=0.0):
    def fn(d, W, H):
        y = H * 0.5 + H * dy
        r1 = H * 0.30
        d.ellipse([W * 0.10, y - r1, W * 0.10 + 2 * r1, y + r1], fill=color)
        d.ellipse([W * 0.52, y - r1 * 1.15, W * 0.52 + 2 * r1 * 1.15, y + r1 * 1.15], fill=color)
        d.rounded_rectangle([W * 0.10 + r1 * 0.4, y - r1 * 0.2, W * 0.90, y + r1], fill=color)
    return ss_draw(w, h, fn)

def icon_rain(color, cloud, heavy=False, w=44, h=44):
    def fn(d, W, H):
        pass
    im = icon_cloud(cloud, 44, 30, dy=-0.28)
    out = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    out.alpha_composite(im.resize((im.width * 2, im.height * 2)), (0, 0))
    d = ImageDraw.Draw(out)
    lw = int(w * 0.05) * 4
    xs = [0.30, 0.52] if not heavy else [0.24, 0.42, 0.60]
    for fx in xs:
        x = W_ = w * 4 * fx
        y0 = h * 4 * 0.62
        d.line([x, y0, x - w * 0.04 * 4, y0 + h * 0.16 * 4], fill=color, width=lw)
        if heavy:
            d.line([x + w * 0.10 * 4, y0 + h * 0.05 * 4, x + w * 0.06 * 4, y0 + h * 0.21 * 4],
                   fill=color, width=lw)
    return out.resize((w, h), Image.LANCZOS)

def icon_thunder(color, cloud, w=44, h=44):
    im = icon_cloud(cloud, 44, 30, dy=-0.28)
    out = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    out.alpha_composite(im.resize((im.width * 2, im.height * 2)), (0, 0))
    d = ImageDraw.Draw(out)
    cx = w * 4 * 0.5
    y0 = h * 4 * 0.58
    d.polygon([(cx, y0), (cx - w * 0.10 * 4, y0 + h * 0.16 * 4), (cx - w * 0.01 * 4, y0 + h * 0.16 * 4),
               (cx - w * 0.09 * 4, y0 + h * 0.32 * 4), (cx + w * 0.08 * 4, y0 + h * 0.12 * 4),
               (cx - w * 0.01 * 4, y0 + h * 0.12 * 4)], fill=color)
    return out.resize((w, h), Image.LANCZOS)

def icon_snow(color, cloud, w=44, h=44):
    im = icon_cloud(cloud, 44, 30, dy=-0.28)
    out = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    out.alpha_composite(im.resize((im.width * 2, im.height * 2)), (0, 0))
    d = ImageDraw.Draw(out)
    r = w * 0.05 * 4
    for fx, fy in ((0.30, 0.68), (0.50, 0.78), (0.64, 0.64)):
        d.ellipse([w * 4 * fx - r, h * 4 * fy - r, w * 4 * fx + r, h * 4 * fy + r], fill=color)
    return out.resize((w, h), Image.LANCZOS)

def icon_fog(color, w=44, h=36):
    def fn(d, W, H):
        lw = int(H * 0.09)
        for i, (x0, x1) in enumerate(((0.06, 0.94), (0.0, 0.80), (0.16, 0.94))):
            y = H * (0.22 + i * 0.28)
            d.rounded_rectangle([W * x0, y, W * x1, y + lw], radius=lw // 2, fill=color)
    return ss_draw(w, h, fn)

# 天气码 → 图标帧（源3031 官方25码, RouletteS3 同序）
WCODES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17, 18, 19, 20, 29, 30, 33, 53, 99, 301]
ICON_IDX = dict(sunny=0, partly=1, overcast=2, rain=3, heavy=4, thunder=5, snow=6, fog=7, haze=8)
def weather_frames(pal):
    return {
        0: ("sunny", icon_sun(pal["sun"])),
        1: ("partly", icon_sun(pal["sun"], 30, 30)),
        2: ("overcast", icon_cloud(pal["cloud"])),
        3: ("rain", icon_rain(pal["rain"], pal["cloud"])),
        4: ("thunder", icon_thunder(pal["sun"], pal["cloud"])),
        5: ("thunder", icon_thunder(pal["sun"], pal["cloud"])),
        6: ("rain", icon_rain(pal["rain"], pal["cloud"])),
        7: ("rain", icon_rain(pal["rain"], pal["cloud"])),
        8: ("heavy", icon_rain(pal["rain"], pal["cloud"], heavy=True)),
        9: ("heavy", icon_rain(pal["rain"], pal["cloud"], heavy=True)),
        10: ("heavy", icon_rain(pal["rain"], pal["cloud"], heavy=True)),
        13: ("snow", icon_snow(pal["cloud"], pal["cloud"])),
        14: ("snow", icon_snow(pal["cloud"], pal["cloud"])),
        15: ("snow", icon_snow(pal["cloud"], pal["cloud"])),
        16: ("snow", icon_snow(pal["cloud"], pal["cloud"])),
        17: ("snow", icon_snow(pal["cloud"], pal["cloud"])),
        18: ("fog", icon_fog(pal["fog"])),
        19: ("rain", icon_rain(pal["rain"], pal["cloud"])),
        20: ("haze", icon_fog(pal["haze"])),
        29: ("haze", icon_fog(pal["haze"])),
        30: ("haze", icon_fog(pal["haze"])),
        33: ("overcast", icon_cloud(pal["cloud"])),
        53: ("haze", icon_fog(pal["haze"])),
        99: ("overcast", icon_cloud(pal["cloud"])),
        301: ("overcast", icon_cloud(pal["cloud"])),
    }

def icon_steps(color, w=32, h=30):
    def fn(d, W, H):
        d.rounded_rectangle([W * 0.12, H * 0.06, W * 0.44, H * 0.62], radius=W * 0.16, fill=color)
        d.rounded_rectangle([W * 0.56, H * 0.38, W * 0.88, H * 0.94], radius=W * 0.16, fill=color)
    return ss_draw(w, h, fn)

# ---------------- 素材生成 ----------------
def gen_set(outdir, pal):
    os.makedirs(outdir, exist_ok=True)
    def save(name, im):
        im.save(os.path.join(outdir, name + ".png"))

    # 背景
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bg).ellipse([0, 0, W - 1, H - 1], fill=pal["bg"])
    save("image_0000", bg)
    # 冒号（静态）
    col = Image.new("RGBA", (COLON_W, T_CELL[1]), (0, 0, 0, 0))
    d = ImageDraw.Draw(col)
    top = (T_CELL[1] - TIME_INK) / 2
    for fy in (0.335, 0.815):
        cy = top + fy * TIME_INK
        r = TIME_INK * 0.075
        d.ellipse([COLON_W / 2 - r, cy - r, COLON_W / 2 + r, cy + r], fill=pal["ink"])
    save("image_0001", col)

    # 时间字模（时/分共用）
    f_t = load_font(118, "Bold")
    for i in range(10):
        save(f"imagelist_0000_{i:04d}", glyph(str(i), f_t, pal["ink"], T_CELL))

    # 日期行帧（预渲染 N月 / N日 / 周X）
    for i, t in enumerate(MONTHS):
        save(f"imagelist_0001_{i:04d}", glyph(t, F_DATE, pal["date"], M_CELL))
    for i, t in enumerate(DAYS):
        save(f"imagelist_0002_{i:04d}", glyph(t, F_DATE, pal["date"], D_CELL))
    for i, t in enumerate(WEEKDAYS):
        save(f"imagelist_0003_{i:04d}", glyph(t, F_DATE, pal["date"], W_CELL))

    # 心率字模（红）
    for i in range(10):
        save(f"imagelist_0004_{i:04d}", glyph(str(i), F_HR, pal["heart"], HR_CELL))

    # 底部共用字模（白，0-9 + 负号，温度用）
    for i in range(10):
        save(f"imagelist_0005_{i:04d}", glyph(str(i), F_B, pal["ink"], B_CELL))
    save("imagelist_0005_0010", glyph("-", F_B, pal["ink"], B_CELL))

    # 天气 25 帧（9 种图标映射官方 25 码）
    wf = weather_frames(pal)
    for k, code in enumerate(WCODES):
        im = wf[code][1]
        cell = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
        cell.alpha_composite(im, ((44 - im.width) // 2, (44 - im.height) // 2))
        save(f"imagelist_0006_{k:04d}", cell)

    # 图标与标签
    save("image_0002", icon_heart(pal["heart"]))
    save("image_0003", text_image("心率", load_cn(34), pal["label"]))
    save("image_0004", icon_battery(pal["batt"], pal["label"]))
    save("image_0005", text_image("电量", load_cn(24), pal["label"]))
    save("image_0006", icon_steps(pal["step"]))
    save("image_0007", text_image("步数", load_cn(24), pal["label"]))
    save("image_0008", text_image("天气", load_cn(24), pal["label"]))

BLINK_RAW = ("1811" + "00" + "20" + "0000" + "0000" + "000000" + "03" + "0002"
             + "".join(v.to_bytes(4, "little").hex() for v in range(60)))

def gen_blink(outdir):
    os.makedirs(outdir, exist_ok=True)
    for sec in range(60):
        im = Image.new("RGBA", (COLON_W, T_CELL[1]), (0, 0, 0, 0))
        if sec % 2 == 1:
            ImageDraw.Draw(im).rectangle([0, 0, COLON_W - 1, T_CELL[1] - 1], fill=(0, 0, 0, 255))
        im.save(os.path.join(outdir, f"imagelist_0007_{sec:04d}.png"))

gen_set(IMG, C)
gen_set(IMG_AOD, CA)
gen_blink(IMG)          # 遮挡层只入正常面（AOD 不闪烁省电）

# ---------------- wfDef ----------------
RAW_DIGNUM = {
    "081102": "081102120000E803000000030000000000000000",
    "101102": "101102120000E803000000030000000000000000",
    "082202": "082202120000E803000000030000000000000000",
    "084103": "084103120000E803000000030000000000000000",
    "203103": "203103120000E803000000030000000000000000",
    "082105": "082105120000E8030000000300FE000000000000",
}
RAW_MONTH = ("301200200000000003000003000200000100000002000000030000000400000005000000"
             "060000000700000008000000090000000A0000000B0000000C000000")
RAW_DAY = ("381200200000000004000003000200000100000002000000030000000400000005000000"
           "060000000700000008000000090000000A0000000B0000000C0000000D0000000E000000"
           "0F0000001000000011000000120000001300000014000000150000001600000017000000"
           "18000000190000001A0000001B0000001C0000001D0000001E0000001F000000")
RAW_WEEK = "20120020000000000000000300020000" + "".join(
    v.to_bytes(4, "little").hex() for v in range(7))
RAW_WEATHER = ("3031002000000000000000030002" + "00" * 2 +
               "".join(c.to_bytes(4, "little").hex() for c in WCODES))

def dignum(idx, x, y, ds, lst, n, show_zero=True, align=2, spacing=0):
    return {"type": "widge_dignum", "x": int(x), "y": int(y), "showCount": 2,
            "spacing": spacing, "align": align, "showZero": show_zero, "dataSrc": ds,
            "imageList": [f"{lst}_{i:04d}" for i in range(n)],
            "prop7Index": idx, "prop7Length": 20, "prop7Raw": RAW_DIGNUM[ds]}

def imagelist_el(idx, x, y, ds, lst, n, raw, index_list=None, length=None):
    e = {"type": "widge_imagelist", "x": int(x), "y": int(y), "dataSrc": ds,
         "imageList": [f"{lst}_{i:04d}" for i in range(n)],
         "prop7Index": idx, "prop7Length": length or (16 + n * 4), "prop7Raw": raw}
    if index_list is not None:
        e["imageIndexList"] = index_list
    return e

def centered(name, cx, cy, src=IMG):
    im = Image.open(os.path.join(src, name + ".png"))
    return {"type": "element", "x": int(round(cx - im.width / 2)),
            "y": int(round(cy - im.height / 2)), "image": name}

def build(aod=False):
    e, p = [], 0
    e.append({"type": "element", "x": 0, "y": 0, "image": "image_0000"})
    # 日期行
    e.append(imagelist_el(p, MONTH_X, Y_DATE, "1012", "imagelist_0001", 12, RAW_MONTH,
                          list(range(1, 13)))); p += 1
    e.append(imagelist_el(p, DAY_X, Y_DATE, "1812", "imagelist_0002", 31, RAW_DAY,
                          list(range(1, 32)))); p += 1
    e.append(imagelist_el(p, WK_X, Y_DATE, "2012", "imagelist_0003", 7, RAW_WEEK,
                          list(range(7)))); p += 1
    # 大时间
    e.append(dignum(p, HOUR_CX, Y_TIME, "081102", "imagelist_0000", 10)); p += 1
    e.append({"type": "element", "x": TIME_LEFT + 2 * T_CELL[0],
              "y": Y_TIME, "image": "image_0001"})
    if not aod:   # 冒号 1Hz 闪烁（遮挡层法，仅正常面）
        e.append(imagelist_el(p, TIME_LEFT + 2 * T_CELL[0], Y_TIME, "1811",
                              "imagelist_0007", 60, BLINK_RAW, list(range(60)))); p += 1
    e.append(dignum(p, MIN_CX, Y_TIME, "101102", "imagelist_0000", 10)); p += 1
    # 心率（同行：图标 + 数字 + 标签）
    e.append(centered("image_0002", HR_ICON_CX, Y_HR_CY))
    e.append(dignum(p, HR_NUM_CX, Y_HR_CY - HR_CELL[1] // 2,
                    "082202", "imagelist_0004", 10)); p += 1
    e.append({"type": "element", "x": HR_LAB_X, "y": Y_HR_CY - 21, "image": "image_0003"})
    # 底部三列
    e.append(centered("image_0004", COL_BAT, Y_ICON_CY))
    e.append(dignum(p, COL_BAT, Y_NUM, "084103", "imagelist_0005", 10, show_zero=False)); p += 1
    e.append({"type": "element", "x": COL_BAT - 24, "y": Y_LAB_CY - 14, "image": "image_0005"})
    e.append(imagelist_el(p, COL_WEA - 22, Y_ICON_CY - 20, "3031", "imagelist_0006", 25,
                          RAW_WEATHER, WCODES)); p += 1
    e.append(dignum(p, COL_WEA, Y_NUM, "203103", "imagelist_0005", 11, show_zero=False)); p += 1
    e.append({"type": "element", "x": COL_WEA - 24, "y": Y_LAB_CY - 14, "image": "image_0008"})
    e.append(centered("image_0006", COL_STP, Y_ICON_CY))
    e.append(dignum(p, COL_STP, Y_NUM, "082105", "imagelist_0005", 10,
                    show_zero=False, spacing=254)); p += 1
    e.append({"type": "element", "x": COL_STP - 24, "y": Y_LAB_CY - 14, "image": "image_0007"})
    return e, p

els, np7 = build()
els_aod, _ = build(aod=True)
wf = {"name": "ElderS3_v1", "id": "000000000", "previewImg": "preview",
      "faceStyleCount": 4, "elementsNormal": els, "elementsAod": els_aod,
      "extraProp7Normal": [], "extraProp7Aod": [],
      "namedFaceRecords": True, "faceNames": ["样式1", "息屏"]}
json.dump(wf, open(os.path.join(ROOT, "wfDef.json"), "w"), ensure_ascii=False, indent=1)

# ---------------- 预览渲染 ----------------
def render(pal, src, els_list, hour=9, minute=41, bat=82, temp=24, hr=72,
           steps=2580, month=9, day=28, wday=1, weather_code=0, sec=41):
    im = Image.new("RGBA", (W, H), (12, 12, 13, 255))
    im.alpha_composite(Image.open(os.path.join(src, "image_0000.png")))
    for el in els_list:
        t = el["type"]
        if t == "element":
            im.alpha_composite(Image.open(os.path.join(src, el["image"] + ".png")).convert("RGBA"),
                               (el["x"], el["y"]))
        elif t == "widge_dignum":
            txt = {"081102": f"{hour:02d}", "101102": f"{minute:02d}",
                   "082202": f"{hr:02d}", "084103": str(bat),
                   "203103": str(temp), "082105": str(steps)}[el["dataSrc"]]
            cw = Image.open(os.path.join(src, el["imageList"][0] + ".png")).width
            x0 = el["x"] - cw * len(txt) // 2 if el.get("align") == 2 else el["x"]
            for k, ch in enumerate(txt):
                gi = 10 if ch == "-" else int(ch)
                g = Image.open(os.path.join(src, el["imageList"][gi] + ".png")).convert("RGBA")
                im.alpha_composite(g, (int(x0) + k * cw, el["y"]))
        elif t == "widge_imagelist":
            codes = el.get("imageIndexList", list(range(len(el["imageList"]))))
            if el["dataSrc"] == "1012":
                fi = codes.index(month)
            elif el["dataSrc"] == "1812":
                fi = codes.index(day)
            elif el["dataSrc"] == "2012":
                fi = codes.index(wday)
            else:
                fi = codes.index(weather_code)
            if el["dataSrc"] == "1811":
                fi = sec % 60
            g = Image.open(os.path.join(src, el["imageList"][fi] + ".png")).convert("RGBA")
            im.alpha_composite(g, (el["x"], el["y"]))
    return im

prev = render(C, IMG, els)
prev_aod = render(CA, IMG_AOD, els_aod, hour=21, minute=7, bat=60, hr=68,
                  steps=8642, month=9, day=28, wday=1, weather_code=4)
prev.convert("RGB").save(os.path.join(ROOT, "preview_render.png"))
render(C, IMG, els, sec=40).convert("RGB").save(os.path.join(ROOT, "preview_blink_on.png"))
render(C, IMG, els, sec=41).convert("RGB").save(os.path.join(ROOT, "preview_blink_off.png"))
prev_aod.convert("RGB").save(os.path.join(ROOT, "preview_render_aod.png"))
prev.convert("RGB").quantize(256).save(os.path.join(IMG, "preview.png"))

# ---------------- 圆形边界校验（内容 vs 骨架） ----------------
sk = Image.new("RGBA", (W, H), (12, 12, 13, 255))
sk.alpha_composite(Image.open(os.path.join(IMG, "image_0000.png")))
pp, sp = prev.convert("RGB").load(), sk.convert("RGB").load()
R2 = 227.0 ** 2
bad = [(x, y) for y in range(H) for x in range(W)
       if (x - 232) ** 2 + (y - 232) ** 2 > R2
       and sum(abs(a - b) for a, b in zip(pp[x, y], sp[x, y])) > 12]
if bad:
    xs = [b[0] for b in bad]; ys = [b[1] for b in bad]
    print(f"FAIL: {len(bad)} 内容像素越界 x{min(xs)}-{max(xs)} y{min(ys)}-{max(ys)}", file=sys.stderr)
    sys.exit(1)
print("circle-check OK (r=227)")

# ---------------- 显存预算 ----------------
tot = 0
for dirp in (IMG, IMG_AOD):
    for f in os.listdir(dirp):
        if f.endswith(".png") and f != "preview.png":
            im = Image.open(os.path.join(dirp, f))
            tot += im.width * im.height * 4
print(f"两套素材总解码显存 ≈ {tot/1024/1024:.2f} MB (每面 ≈ {tot/2/1024/1024:.2f} MB, 预算 4)")
print(f"OK 元素 {len(els)} prop7 {np7} | 日期行宽 {DATE_TOTAL} | 时间块 {TIME_BLOCK}")
