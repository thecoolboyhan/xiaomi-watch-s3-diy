#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v64 builder: 修跳秒 + 弧通道 + 显存超预算

根因（v58(扫秒OK) vs v63(跳秒) 二进制取证）:
1. 解包器会剥掉 prop7Raw -> v61~v63 重打包后所有 dignum/imagelist 的 prop7 b6-7(刷新ms)
   变 0000 = 非法通道 -> 整 face 动画禁用 -> 跳秒 (v54 真机实证机制)。
2. 带 imageIndexList 的 imagelist 需要 b12-13=0002 标志，否则弧通道失效 -> 温度/步数无进度条。
3. v61 把 44 张弧帧改成 464x464 全画布 -> 纹理预算(铁律 ≲4MB/face)爆掉；v58 弧是 136x136 小块。
4. AOD 面的 dignum 同样需要合法 prop7Raw，否则 AOD 面被固件拒绝。

本脚本:
  A. 用 v58/v60 bin 里逐字节提取的 prop7Raw 注入 wfDef（normal + aod 两个面）
  B. 星期 imagelist 去掉 imageIndexList（对齐 v58，v58 无表也能显示）
  C. 重绘 44 张弧帧为"圆角帽 + 裁剪小图块"，并回写弧元素 x/y = 裁剪框左上角
"""
import json, math, struct, sys
sys.path.insert(0, "/Users/admin/ai/watch/tools/scripts")
import gen_assets_v3 as G
from PIL import Image, ImageDraw

WS3 = "/Users/admin/ai/watch/project/ws3"
V58 = "/Users/admin/ai/watch/reference/RouletteS3_v58.bin"
V60 = "/Users/admin/ai/watch/reference/RouletteS3_v60.bin"

# ---------------------------------------------------------------- A. prop7Raw
def extract_idx(binp, want_idx):
    """从 bin 的 def 表(type==7)提取指定 idx 的 prop7 块 hex"""
    d = open(binp, "rb").read()
    start = 0xA8 + 2 * 0x58
    fh = d[0xA8:0xA8+0x58]
    counts = [struct.unpack_from("<I", fh, o)[0] for o in (0x08,0x18,0x20,0x28,0x30,0x40)]
    out = {}
    for k in range(sum(counts)):
        rec = d[start+k*16:start+k*16+16]
        if rec[3] == 7:
            idx = rec[0] | rec[1]<<8 | rec[2]<<16
            off, blen = struct.unpack_from("<II", rec, 8)
            if 0 < off < len(d) and 0 < blen <= 256:
                out[idx] = d[off:off+blen].hex().upper()
    return out

v58 = extract_idx(V58, None)
v60 = extract_idx(V60, None)
# v58 idx: 0=081102 1=101102 2=181102 3=203103 4=082203 5=082105 6=3012 7=3812 8=084103 9=2012 10=0841弧 12/13=指针
# v60 idx: 14=0821弧 15=0822弧 16=2031弧
RAWS = {
    "081102": v58[0],  "101102": v58[1],  "181102": v58[2],
    "203103": v58[3],  "082203": v58[4],  "082105": v58[5],
    "3012":   v58[6],  "3812":   v58[7],  "084103": v58[8],
    "2012":   v58[9],  "0841":   v58[10],
    "0821":   v60[14], "0822":   v60[15], "2031":   v60[16],
}
print("== 注入 prop7Raw（按 dataSrc 匹配，两个面都注入）==")
for k, v in sorted(RAWS.items()):
    print(f"  {k}: len={len(v)//2} {v[:40]}...")

wf = json.load(open(f"{WS3}/wfDef.json"))
changed = 0
for face in ("elementsNormal", "elementsAod"):
    for e in wf[face]:
        ds = e.get("dataSrc")
        if ds in RAWS and e.get("type") in ("widge_dignum", "widge_imagelist"):
            raw = RAWS[ds]
            e["prop7Raw"] = raw
            e["prop7Length"] = len(raw) // 2
            changed += 1
        # B. 星期 imagelist 去掉 imageIndexList（对齐 v58 实证配置）
        if ds == "2012" and "imageIndexList" in e:
            del e["imageIndexList"]
            print("  [weekday] 移除 imageIndexList（对齐 v58）")
print(f"  注入 {changed} 个元素")

# ---------------------------------------------------------------- C. 弧帧小图块
CANVAS, C = 464, (232, 232)
ARC_R, ARC_W, SCALE, N = 206, 11, 4, 11
FILL = (235, 235, 240, 255)
ARCS = [(0, 110, 160), (1, 290, 340), (2, 200, 250), (3, 20, 70)]  # battery/steps/cal/temp

def web2pil(t): return t - 90.0
def endpoint(theta, sc):
    pil = math.radians(web2pil(theta))
    r = (ARC_R - ARC_W / 2) * sc           # 帽圆心在色带中线（PIL 向内描边）
    return C[0]*sc + r*math.cos(pil), C[1]*sc + r*math.sin(pil)

def render(s, e, ratio):
    if ratio <= 0:
        return Image.new("RGBA", (CANVAS, CANVAS), (0,0,0,0)), None
    big = Image.new("RGBA", (CANVAS*SCALE, CANVAS*SCALE), (0,0,0,0))
    d = ImageDraw.Draw(big)
    fe = s + (e - s) * ratio
    bbox = [C[0]*sc-ARC_R*sc, C[1]*sc-ARC_R*sc, C[0]*sc+ARC_R*sc, C[1]*sc+ARC_R*sc] if (sc:=SCALE) else None
    d.arc(bbox, web2pil(s-0.6), web2pil(fe), fill=FILL, width=ARC_W*SCALE)
    rw = ARC_W/2*SCALE
    for th in (s-0.6, fe):
        x, y = endpoint(th, SCALE)
        d.ellipse([x-rw, y-rw, x+rw, y+rw], fill=FILL)
    return big.resize((CANVAS, CANVAS), Image.LANCZOS), None

print("\n== 重绘 44 张弧帧（圆角帽 + 裁剪小图块）==")
boxes = {}
for li, s, e in ARCS:
    frames = []
    for i in range(N):
        img, _ = render(s, e, i / (N - 1))
        frames.append(G._to_palette_safe(img))
    # 用满弧帧(frame10)求 union bbox（含圆角帽），+2px 余量
    bb = frames[N-1].getbbox()
    pad = 2
    x0, y0 = max(0, bb[0]-pad), max(0, bb[1]-pad)
    x1, y1 = min(CANVAS, bb[2]+pad), min(CANVAS, bb[3]+pad)
    boxes[li] = (x0, y0, x1-x0, y1-y0)
    for i in range(N):
        frames[i].crop((x0, y0, x1, y1)).save(f"{WS3}/images/imagelist_000{li}_{i:04d}.png")
    print(f"  arc{li} (web {s}-{e}): tile {x1-x0}x{y1-y0} @({x0},{y0})")

# 回写弧元素 x/y（按 dataSrc 匹配）
XY = {"0841": boxes[0], "0821": boxes[1], "0822": boxes[2], "2031": boxes[3]}
for e in wf["elementsNormal"]:
    if e.get("dataSrc") in XY and e.get("type") == "widge_imagelist":
        x0, y0, w, h = XY[e["dataSrc"]]
        e["x"], e["y"] = x0, y0
        print(f"  弧 {e['dataSrc']}: x/y -> ({x0},{y0}) tile {w}x{h}")

json.dump(wf, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
print("\nwfDef.json 已更新")
