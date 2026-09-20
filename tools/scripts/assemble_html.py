#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RouletteS3 HTML wfDef 组装器 (含 v33 alpha-bbox 裁剪)
完全模仿 preview_v20.html 的效果，独立于 WorkBuddy 主线。

平滑关键 (v42 发现): 秒针 prop7Raw offset 8-9 = 0x0001 开启平滑扫秒。
此处直接使用 Google 轮盘·橙 已验证的 prop7Raw 值。
"""
import json, os
from PIL import Image as _PIL

# Google 轮盘·橙 已验证的 prop7Raw (平滑)
# offset 8-9: 0x0001 = 平滑秒针, 0x0003 = 平滑分针
PROP7RAW_SEC = "18110030000010000100000200000000003C0000E800E8000000100E00000000"
PROP7RAW_MIN = "101100300000E8030300000200000000003C0000E800E8000000100E00000000"

IMG = os.path.join(os.path.dirname(__file__), "out_html", "images")
OUT = os.path.dirname(IMG)

# 四弧动态填充规格
ARC_SPEC = [
    ("temp",    20,  70,  79, "sun",   "2031", 0,  50, 11),
    ("battery", 110, 160, 169,"bolt",  "0841", 0, 100, 21),
    ("calories",200, 250, 191,"flame", "0822", 0, 500, 21),
    ("steps",   290, 340, 281,"shoe",  "1021", 0, 100, 21),
]

def imglist(prefix, n):
    return [f"{prefix}_{i}" for i in range(n)]

def el(**kw):
    if kw.get('x') is not None:
        kw['x'] = int(round(kw['x']))
    if kw.get('y') is not None:
        kw['y'] = int(round(kw['y']))
    return {k:v for k,v in kw.items() if v is not None}

# dignum 锚点语义: x = 字串中心, y = 顶边
DIGH_W, DIGM_W, DIGS_W = 33, 15, 11

def dcx(old_x, n, cell_w):
    return old_x + n * cell_w / 2.0

# 元素列表
elements = []

# [0] 秒针 (widge_pointer ds=1811)
elements.append(el(
    type="widge_pointer",
    x=0, y=0,
    dataSrc="1811",
    image="ring_sec.png",
    interval=16,
    maxValue=60,
    allAngle=3600,
    imageRotateX=232,
    imageRotateY=232,
    pointerUnknow25=0,
    pointerUnknow26=0,
    prop7Index=12,
    prop7Raw=PROP7RAW_SEC,
))

# [1] 分针 (widge_pointer ds=1011)
elements.append(el(
    type="widge_pointer",
    x=0, y=0,
    dataSrc="1011",
    image="ring_min.png",
    interval=1000,
    maxValue=60,
    allAngle=3600,
    imageRotateX=232,
    imageRotateY=232,
    pointerUnknow25=0,
    pointerUnknow26=0,
    prop7Index=13,
    prop7Raw=PROP7RAW_MIN,
))

# [2] 透明前景覆盖层
elements.append(el(type="element", x=0, y=0, image="bg.png"))

# [3] 四弧(静态轨道+图标)
elements.append(el(type="element", x=0, y=0, image="arcs.png"))

# [3b] 动态填充进度弧 (仅步数 1021)
_ALLOWED_ARC_FILL = {"1021"}
for _name, _s, _e, _ia, _icon, _ds, _dmin, _dmax, _nlv in ARC_SPEC:
    if _ds not in _ALLOWED_ARC_FILL:
        continue
    _levels = [round(_dmin + (_dmax - _dmin) * i / (_nlv - 1)) for i in range(_nlv)]
    elements.append(el(
        type="widge_imagelist",
        x=0, y=0,
        dataSrc=_ds,
        imageList=[f"arcfill_{_name}_{i}" for i in range(_nlv)],
        imageIndexList=_levels,
    ))

# 5. 星期 (imagelist, ds=2012, 7帧)
elements.append(el(
    type="widge_imagelist",
    x=207, y=180,
    dataSrc="2012",
    imageList=imglist("wd", 7),
    imageIndexList=[0, 1, 2, 3, 4, 5, 6],
))

# 6. 大时 (dignum, ds=081102, 2位)
elements.append(el(
    type="widge_dignum",
    x=dcx(200, 2, DIGH_W), y=204,
    dataSrc="081102",
    showCount=2,
    align=2,
    showZero=True,
    spacing=0,
    imageList=imglist("digH", 10),
))

# 7. 月 (imagelist, ds=3012, 12帧)
elements.append(el(
    type="widge_imagelist",
    x=190, y=266,
    dataSrc="3012",
    imageList=imglist("mo", 12),
    imageIndexList=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
))

# 8. 斜杠
elements.append(el(type="element", x=236.5, y=267.5, image="slash.png"))

# 9. 日 (dignum, ds=381202, 2位)
elements.append(el(
    type="widge_dignum",
    x=dcx(252, 2, DIGS_W), y=267,
    dataSrc="381202",
    showCount=2,
    align=2,
    showZero=True,
    spacing=0,
    imageList=imglist("digS", 10),
))

# 10. 红色胶囊底图
elements.append(el(type="element", x=296, y=200, image="capsule_bg.png"))

# 11. 胶囊内分钟 (dignum, ds=101102, 2位)
elements.append(el(
    type="widge_dignum",
    x=dcx(316, 2, DIGM_W), y=223,
    dataSrc="101102",
    showCount=2,
    align=2,
    showZero=True,
    spacing=0,
    imageList=imglist("digM", 10),
))

# 12. 胶囊冒号
elements.append(el(type="element", x=357, y=231, image="colon.png"))

# 13. 胶囊内秒 (dignum, ds=181102, 2位)
elements.append(el(
    type="widge_dignum",
    x=dcx(380, 2, DIGM_W), y=222.5,
    dataSrc="181102",
    interval=16,
    showCount=2,
    align=2,
    showZero=True,
    spacing=0,
    imageList=imglist("digM", 10),
))

# 14-17. 四数据
# 温度 (TR)
elements.append(el(
    type="widge_dignum",
    x=dcx(247, 3, DIGS_W), y=28,
    dataSrc="203103",
    showCount=3,
    align=2,
    showZero=False,
    spacing=0,
    imageList=imglist("digS", 11),
))
elements.append(el(type="element", x=282, y=29, image="deg.png"))

# 电量 (BR)
elements.append(el(
    type="widge_dignum",
    x=dcx(412.3, 2, DIGS_W), y=263.8,
    dataSrc="084103",
    showCount=2,
    align=2,
    showZero=False,
    spacing=0,
    imageList=imglist("digS", 10),
))
elements.append(el(type="element", x=436.3, y=264.8, image="percent.png"))

# 卡路里 (BL)
elements.append(el(
    type="widge_dignum",
    x=dcx(18, 3, DIGS_W), y=264,
    dataSrc="082203",
    showCount=3,
    align=2,
    showZero=False,
    spacing=0,
    imageList=imglist("digS", 10),
))

# 步数 (TL)
elements.append(el(
    type="widge_dignum",
    x=dcx(166, 5, DIGS_W), y=28,
    dataSrc="082105",
    showCount=5,
    align=2,
    showZero=False,
    spacing=0,
    imageList=imglist("digS", 10),
))

# 点击热区
_HOTZONES = [
    ( 75, 121, "01001312"),
    (343,  75, "01000312"),
    (122, 390, "01005310"),
    (390, 344, "01003311"),
]
_HOTZONE_W, _HOTZONE_H = 80, 40
for _cx, _cy, _code in _HOTZONES:
    elements.append(el(
        type="element",
        x=int(round(_cx - _HOTZONE_W / 2)), y=int(round(_cy - _HOTZONE_H / 2)),
        image="hotzone.png",
        jumpCode=_code, jumpName="组1",
    ))

# === v33: alpha-bbox 裁剪 ===
_NO_CROP = {"ring_sec.png", "ring_min.png"}

def _fpath(name):
    for cand in (name, name + ".png"):
        p = os.path.join(IMG, cand)
        if os.path.exists(p):
            return p
    return os.path.join(IMG, name + ".png")

def _open(name):
    return _PIL.open(_fpath(name)).convert("RGBA")

def _group_key(e):
    if e.get("image"):
        return (e["image"],)
    if e.get("imageList"):
        return tuple(e["imageList"])
    return None

def _crop_pass(els):
    groups = {}
    for e in els:
        k = _group_key(e)
        if k:
            groups.setdefault(k, [_fpath(n) for n in k])
    off = {}
    for key, paths in groups.items():
        if len(key) == 1 and key[0] in _NO_CROP:
            off[key] = (0, 0)
            continue
        box = None
        sizes = []
        for p in paths:
            if not os.path.exists(p):
                continue
            im0 = _PIL.open(p)
            w, h = im0.size
            sizes.append((w, h))
            im0.close()
            b = _PIL.open(p).convert("RGBA").split()[3].getbbox()
            if b is None:
                continue
            box = b if box is None else (
                min(box[0], b[0]), min(box[1], b[1]),
                max(box[2], b[2]), max(box[3], b[3]))
        if box is None:
            off[key] = (0, 0)
            continue
        if sizes:
            uw, uh = box[2] - box[0], box[3] - box[1]
            max_frame_area = max(s[0] * s[1] for s in sizes)
            union_area = max(uw * uh, 1)
            if union_area > 4 * max_frame_area:
                off[key] = (0, 0)
                continue
        if any(n.startswith(("digS_", "digM_", "digH_", "digL_")) for n in key):
            off[key] = (0, 0)
            continue
        dx, dy = box[0], box[1]
        for p in paths:
            if os.path.exists(p):
                _PIL.open(p).convert("RGBA").crop(box).save(p)
        off[key] = (dx, dy)
    for e in els:
        k = _group_key(e)
        if k in off and (off[k][0] or off[k][1]):
            dx, dy = off[k]
            e["x"] = int(round(e.get("x", 0) + dx))
            e["y"] = int(round(e.get("y", 0) + dy))
            if e.get("type") == "widge_pointer":
                if e.get("imageRotateX") is not None:
                    e["imageRotateX"] = int(round(e["imageRotateX"] - dx))
                if e.get("imageRotateY") is not None:
                    e["imageRotateY"] = int(round(e["imageRotateY"] - dy))
    return els

# 合并相邻静态层: arcs.png 合成进 bg.png
_bg_p, _arcs_p = _fpath("bg.png"), _fpath("arcs.png")
if os.path.exists(_bg_p) and os.path.exists(_arcs_p) and _bg_p != _arcs_p:
    _m = _open("bg.png")
    _m.alpha_composite(_open("arcs.png"))
    _m.save(_bg_p)
    elements = [e for e in elements if e.get("image") != "arcs.png"]
    print("[html] merged arcs.png -> bg.png")

_crop_pass(elements)
print("[html] alpha-bbox crop applied")

# 删除未被任何元素引用的图片
_referenced = set()
def _walk_img(name):
    if not name: return
    _referenced.add(_fpath(name))
def _collect(els):
    for e in els:
        if e.get("image"): _walk_img(e["image"])
        for n in e.get("imageList", []): _walk_img(n)
_collect(elements)
_removed = 0
for _p in os.listdir(IMG):
    if not _p.lower().endswith(".png"): continue
    _fp = os.path.join(IMG, _p)
    if _fp not in _referenced and _p != "preview.png":
        os.remove(_fp)
        _removed += 1
print(f"[html] removed {_removed} unreferenced images")

# AOD 面 (去掉指针)
_face1_elements = [dict(_e) for _e in elements if _e.get("type") != "widge_pointer"]

# extraProp7 伴侣
_EP7_COMPANIONS = [
    {"idx": 6, "raw": "101202150000E803040000030000000000000000"},
    {"idx": 7, "raw": "181202150000E803040000030000000000000000"},
]

wfdef = {
    "name": "RouletteS3 HTML",
    "id": "000000032",
    "previewImg": "preview",
    "forceIndex256": True,
    "faceStyleCount": 4,
    "faces": [
        {
            "name": "完整样式",
            "imageDir": "images",
            "elements": elements,
            "extraProp7": _EP7_COMPANIONS,
        },
        {
            "name": "样式2(AOD数字)",
            "imageDir": "images",
            "elements": _face1_elements,
            "extraProp7": _EP7_COMPANIONS,
        },
    ],
}

path = os.path.join(OUT, "wfDef.json")
with open(path, "w") as f:
    json.dump(wfdef, f, ensure_ascii=False, indent=2)
print(f"wrote {path} ({len(elements)} elements)")
