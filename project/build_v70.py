#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v70 构建器（在 v69 基础上）: 日期/星期字体升级
  - 星期 SUN..SAT / 月份 JAN..DEC / 日期 01..31 / 斜杠 全部换 DIN Alternate Bold（经典手表字体）
  - 配色: 星期 208 亮灰白 / 月份·斜杠 188 亮灰 / 日期 238 白（层次分明）
  - 帧尺寸变化后按"视觉中心锚定"重算元素 x/y（中心不变）
  - AOD 星期同步换字体, 颜色调暗 (~45%)
  - 注: 小时数字 prop7Raw b3=0x16 (align=2=中心锚点), 真机固件按 x=232 居中渲染,
        无需改 wfDef（预览脚本曾按左上角贴图造成"偏右"错觉）。
"""
import math, json
from PIL import Image, ImageDraw, ImageFont

WS3 = "/Users/admin/ai/watch/project/ws3"
FONT = "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf"

def render_frames(labels, sz, color):
    """DIN Alternate Bold 居中渲染, 返回 (frames, cell_w, cell_h)"""
    font = ImageFont.truetype(FONT, sz)
    mw = 0
    for lab in labels:
        bb = font.getbbox(lab)
        mw = max(mw, bb[2] - bb[0])
    cw, ch = mw + 8, int(sz * 1.35)
    frames = []
    for lab in labels:
        img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((cw // 2, ch // 2), lab, font=font, fill=color, anchor="mm")
        frames.append(img)
    return frames, cw, ch

def save_frames(frames, prefix, n_digits=4):
    for i, f in enumerate(frames):
        f.save(f"{WS3}/images/{prefix}_{i:0{n_digits}d}.png")

def anchor(e, cx, cy, cw, ch):
    e["x"], e["y"] = round(cx - cw / 2), round(cy - ch / 2)

wf = json.load(open(f"{WS3}/wfDef.json"))

# 1) 星期 (imagelist_0004, 7 帧, 中心 232.5,182.5)
wd, w, h = render_frames(["SUN","MON","TUE","WED","THU","FRI","SAT"], 21, (208,208,216,255))
save_frames(wd, "imagelist_0004")
for e in wf["elementsNormal"]:
    if e.get("dataSrc") == "2012" and e.get("type") == "widge_imagelist":
        anchor(e, 232.5, 182.5, w, h)
print(f"星期: DIN AB 21, cell {w}x{h}")

# 2) 月份 (imagelist_0006, 12 帧, 中心 198.5,281)
mo, w, h = render_frames(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"], 19, (188,188,196,255))
save_frames(mo, "imagelist_0006")
for e in wf["elementsNormal"]:
    if e.get("dataSrc") == "1012":
        anchor(e, 198.5, 281, w, h)
print(f"月份: DIN AB 19, cell {w}x{h}")

# 3) 日期 (imagelist_0007, 31 帧 01..31, 中心 255,281)
dy, w, h = render_frames([f"{i:02d}" for i in range(1, 32)], 21, (238,238,242,255))
save_frames(dy, "imagelist_0007")
for e in wf["elementsNormal"]:
    if e.get("dataSrc") == "1812":
        anchor(e, 255, 281, w, h)
print(f"日期: DIN AB 21, cell {w}x{h}")

# 4) 斜杠 (image_0003, 中心 232.5,281.5)
sl, w, h = render_frames(["/"], 19, (188,188,196,255))
sl[0].save(f"{WS3}/images/image_0003.png")
for e in wf["elementsNormal"]:
    if e.get("image") == "image_0003":
        anchor(e, 232.5, 281.5, w, h)
print(f"斜杠: DIN AB 19, cell {w}x{h}")

# 5) AOD 星期 (images_aod/imagelist_0002, 调暗 45%)
wd, w, h = render_frames(["SUN","MON","TUE","WED","THU","FRI","SAT"], 21, (94,94,100,255))
for i, f in enumerate(wd):
    f.save(f"{WS3}/images_aod/imagelist_0002_{i:04d}.png")
for e in wf["elementsAod"]:
    if e.get("dataSrc") == "2012":
        anchor(e, 232.5, 182.5, w, h)
print(f"AOD 星期: DIN AB 21 调暗, cell {w}x{h}")

wf["name"] = "RouletteS3_v70"
json.dump(wf, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
print("wfDef -> v70")
