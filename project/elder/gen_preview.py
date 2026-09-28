#!/usr/bin/env python3
"""老人盘（ElderS3）设计预览 v2 —— 单一深色配色 + 圆形边界校验。
布局（464x464 逻辑画布，圆心 232,232，可视半径 232）：
  顶部   日期「9月28日 周一」(y=62, 40px)
  中上   大时间 HH:MM (y=146, 118px Bold)
  中部   ❤ 72 心率（同行标签）(y=262)
  底部三列（内收）：电量 / 天气 / 步数
         图标 y=346、数值 y=386 (40px)、标签 y=416 (24px)
所有元素必须整体落在半径 230 的圆内（自动逐像素校验）。
"""
from PIL import Image, ImageDraw, ImageFont
import math
import sys

S = 2                      # 2x 超采样
W = H = 464 * S
CXS = 232 * S              # 已缩放坐标（手绘几何用）
CX = 232                   # 逻辑坐标（ctext 自动缩放）
FONT_CN = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_NUM = "/System/Library/Fonts/SFNS.ttf"


def fnum(size, weight="Semibold"):
    f = ImageFont.truetype(FONT_NUM, size * S)
    f.set_variation_by_name(weight)
    return f


def fcn(size):
    return ImageFont.truetype(FONT_CN, size * S, index=0)


def ctext(d, cx, y, text, font, fill, anchor="mm"):
    d.text((cx * S, y * S), text, font=font, fill=fill, anchor=anchor)


def draw_heart(d, cx, cy, s, color):
    r = s * 0.30
    off = s * 0.26
    d.ellipse([cx - off - r, cy - off - r, cx - off + r, cy - off + r], fill=color)
    d.ellipse([cx + off - r, cy - off - r, cx + off + r, cy - off + r], fill=color)
    d.polygon([
        (cx - off - r * 0.98, cy - off + r * 0.55),
        (cx + off + r * 0.98, cy - off + r * 0.55),
        (cx, cy + s * 0.46),
    ], fill=color)


def draw_sun(d, cx, cy, s, color):
    r = s * 0.30
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    for i in range(8):
        a = math.pi / 4 * i
        d.line([cx + math.cos(a) * s * 0.42, cy + math.sin(a) * s * 0.42,
                cx + math.cos(a) * s * 0.60, cy + math.sin(a) * s * 0.60],
               fill=color, width=int(s * 0.10))


def draw_battery(d, cx, cy, s, body, fill_color, pct=0.82):
    w, h = s * 1.05, s * 0.52
    x0, y0 = cx - w / 2, cy - h / 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=s * 0.10,
                        outline=body, width=int(s * 0.09))
    d.rounded_rectangle([x0 + w, cy - h * 0.18, x0 + w + s * 0.10, cy + h * 0.18],
                        radius=s * 0.04, fill=body)
    fw = (w - s * 0.20) * pct
    d.rounded_rectangle([x0 + s * 0.10, y0 + s * 0.10, x0 + s * 0.10 + fw, y0 + h - s * 0.10],
                        radius=s * 0.05, fill=fill_color)


def draw_steps_icon(d, cx, cy, s, color):
    d.rounded_rectangle([cx - s * 0.42, cy - s * 0.42, cx - s * 0.10, cy + s * 0.12],
                        radius=s * 0.16, fill=color)
    d.rounded_rectangle([cx + s * 0.10, cy - s * 0.12, cx + s * 0.42, cy + s * 0.42],
                        radius=s * 0.16, fill=color)


def render(path, with_content=True):
    bg, ring = (0, 0, 0, 255), (58, 58, 60, 255)
    back = (24, 24, 27, 255)
    c_date = (235, 235, 240, 255)
    c_time = (255, 255, 255, 255)
    c_hr = (255, 69, 58, 255)
    c_label = (185, 185, 190, 255)   # 标签提亮，老人可读
    c_val = (255, 255, 255, 255)
    c_batt = (48, 209, 88, 255)
    c_sun = (255, 204, 0, 255)
    c_step = (100, 160, 255, 255)

    img = Image.new("RGBA", (W, H), back)
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, W - 1, H - 1], fill=bg, outline=ring, width=2 * S)
    if not with_content:
        return img.resize((464, 464), Image.LANCZOS)

    # 顶部日期
    ctext(d, CX, 62, "9月28日  周一", fcn(40), c_date)
    # 大时间
    ctext(d, CX, 146, "09:41", fnum(118, "Bold"), c_time)
    # 心率：❤ 72 心率（标签同行）
    hr_v = "72"
    f_hr = fnum(92, "Bold")
    f_lab = fcn(34)
    hw = d.textlength(hr_v, font=f_hr)
    lw = d.textlength("心率", font=f_lab)
    icon_s = 50 * S
    total = icon_s + 14 * S + hw + 18 * S + lw
    x0 = CXS - total / 2
    draw_heart(d, x0 + icon_s / 2, 262 * S, icon_s, c_hr)
    d.text((x0 + icon_s + 14 * S, 262 * S), hr_v, font=f_hr, fill=c_hr, anchor="lm")
    d.text((x0 + icon_s + 14 * S + hw + 18 * S, 262 * S), "心率", font=f_lab,
           fill=c_label, anchor="lm")
    # 底部三列（内收到圆内）
    cols = [(134, "电量", "82%", c_batt, "battery"),
            (232, "天气", "24°", c_sun, "sun"),
            (330, "步数", "2580", c_step, "steps")]
    for cx, lab, val, color, icon in cols:
        if icon == "battery":
            draw_battery(d, cx * S, 346 * S, 30 * S, c_label, color)
        elif icon == "sun":
            draw_sun(d, cx * S, 346 * S, 30 * S, color)
        else:
            draw_steps_icon(d, cx * S, 346 * S, 30 * S, color)
        ctext(d, cx, 384, val, fnum(40, "Semibold"), c_val)
        ctext(d, cx, 412, lab, fcn(24), c_label)

    out = img.resize((464, 464), Image.LANCZOS)

    # ---- 圆形边界校验：与无内容骨架图差分，内容像素必须全部在半径227圆内 ----
    skeleton = render("/tmp/_skeleton.png", with_content=False)
    sp, px = skeleton.load(), out.load()
    R = 227.0
    bad = []
    for y in range(464):
        for x in range(464):
            if (x - 232) ** 2 + (y - 232) ** 2 > R * R:
                p, q = px[x, y], sp[x, y]
                if abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2]) > 12:
                    bad.append((x, y))
    if bad:
        xs = [b[0] for b in bad]; ys = [b[1] for b in bad]
        print(f"FAIL: {len(bad)} 个内容像素越界，范围 x{min(xs)}-{max(xs)} y{min(ys)}-{max(ys)}",
              file=sys.stderr)
        sys.exit(1)
    print("circle-check OK: 所有内容均在半径227圆内")

    out.save(path)
    print("saved", path)


if __name__ == "__main__":
    render("/Users/admin/ai/watch/project/elder/preview_elder_dark.png")
