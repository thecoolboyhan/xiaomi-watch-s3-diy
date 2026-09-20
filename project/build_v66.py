#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v66 builder（在 v65 基础上）:
  1. 秒/分盘数字重排（用户 v65 真机照片实测: 当前 = 00在12点、顺时针递增 A(v)=6v;
     正确 = 00在3点、逆时针递增 A(v)=90-6v —— 顺时针旋转 +6°/秒 时红框(90°)恰好指向当前值:
     A(v) + 6s = 90 -> v = s ✓）。
     实现: 每根辐条(数字+刻度)绕表心刚性顺时针旋转 delta(v) = (90-6v) - 6v = 90-12v 度,
     字形朝向由刚性旋转自动保持（不镜像）。
  2. 卡路里数字去倾斜: 寻路者 raw b14-15=DC00(22°倾斜, 它的槽位在斜角上) -> 0000;
     解挤压: spacing 252(-4) -> 0。
  3. 温度 ° 符号左移贴近数字 (showZero=false 时 "29" 比 3 位窄, 原 x=296 有 ~1 字宽空隙)。
"""
import sys, math, json
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
from PIL import Image, ImageDraw

WS3 = "/Users/admin/ai/watch/project/ws3"
CANVAS, C = 464, (232, 232)

# ---- 1. 双盘数字重排 ----
def build_wedge_mask(r0, r1, center_deg, half_width=15.0):
    m = Image.new("L", (CANVAS, CANVAS), 0)
    px = m.load()
    for y in range(CANVAS):
        for x in range(CANVAS):
            dx, dy = x - C[0], y - C[1]
            r = math.hypot(dx, dy)
            if r < r0 or r > r1:
                continue
            a = (math.degrees(math.atan2(dy, dx)) + 90) % 360
            d = abs(a - center_deg)
            d = d if d < 180 else 360 - d
            if d <= half_width:
                px[x, y] = 255
    return m

def transform_ring(name, r0, r1):
    path = f"{WS3}/images/{name}.png"
    orig = Image.open(path).convert("RGBA")
    new = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    blank = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    M0 = build_wedge_mask(r0, r1, 90.0)
    for v in range(0, 60, 5):
        delta = 90 - 12 * v                       # 顺时针旋转度数 (PIL rotate(-x)=顺时针x)
        rot = orig.rotate(-delta, center=C, resample=Image.BICUBIC)
        mask = M0.rotate(+6 * v, center=C, resample=Image.NEAREST)  # 楔形 -> 90-6v
        new = Image.alpha_composite(new, Image.composite(rot, blank, mask))
    new = G._to_palette_safe(new)
    new.save(path)
    print(f"{name}: 数字重排为 00@3点 逆时针递增 (A=90-6v)")

transform_ring("image_0000", 125, 190)   # 秒盘
transform_ring("image_0001", 76, 140)    # 分盘

# ---- 2 & 3. wfDef 修正 ----
wf = json.load(open(f"{WS3}/wfDef.json"))
for e in wf["elementsNormal"]:
    if e.get("dataSrc") == "082305" and e.get("type") == "widge_dignum":
        # 去倾斜(b14-15: DC00=22° -> 0000) + 解挤压(b13: FC=252(-4) -> 00)
        e["prop7Raw"] = "082305100000E803030000030000000000000000"
        e["spacing"] = 0
        print("卡路里数字: 去倾斜22° + spacing -4 -> 0")
    if e.get("image") == "image_0006" and e.get("type") == "element":
        e["x"] = 284
        print("温度°: x 296 -> 284 (贴近 2 位数字)")
json.dump(wf, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
wf["name"] and None
w2 = json.load(open(f"{WS3}/wfDef.json"))
w2["name"] = "RouletteS3_v66"
json.dump(w2, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
print("wfDef -> v66")
