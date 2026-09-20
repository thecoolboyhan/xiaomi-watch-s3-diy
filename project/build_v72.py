#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v72 构建器（在 v71 基础上）:
  1. 天气图标 → 白色线稿纯色风: 25 帧全部重绘 (DIN 线稿语言, 4x 超采样, 36×36)
     天气码映射 [0,1,2,3,4,5,6,7,8,9,10,13,14,15,16,17,18,19,20,29,30,33,53,99,301]
  2. 睡眠: 时数字左侧竖直进度条 (1828 睡眠目标进度, 自绘 11 帧 12×52, prop7Raw 寻路者 verbatim)
     + 睡眠时长 082814 (12 帧专用格式, 寻路者 verbatim)
  3. 点击热区 4 个 (prop9/jumpRaw, 布局=元素x/y + raw内嵌W×H):
     天气弧→天气 01001312 / 步数弧→运动 01003311 / 卡路里弧→元气值 010C6F03(社区表,待验)
     时数字→睡眠 0100C310
"""
import sys, math, json, glob, os, shutil
import os as _os
ROOT = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isdir(_os.path.join(ROOT, "tools")):
    ROOT = _os.path.dirname(ROOT)
sys.path.insert(0, _os.path.join(ROOT, "tools/scripts"))
import gen_assets_v3 as G
from PIL import Image, ImageDraw, ImageFont

WS3 = _os.path.join(ROOT, "project/ws3")
CANVAS = 464
SCALE, SS = 36, 4           # 天气图标 36px 盒, 4x 超采样
LINE = (235, 235, 240, 255)
FONT_DIN = "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf"

# ================================================================ 1. 天气图标
def bezier(p0,p1,p2,p3,n=14):
    out=[]
    for i in range(n+1):
        t=i/n; mt=1-t
        out.append((mt**3*p0[0]+3*mt*mt*t*p1[0]+3*mt*t*t*p2[0]+t**3*p3[0],
                    mt**3*p0[1]+3*mt*mt*t*p1[1]+3*mt*t*t*p2[1]+t**3*p3[1]))
    return out

def draw_path(d, pts, w):
    d.line(pts, fill=LINE, width=w, joint="curve")
    for px,py in (pts[0], pts[-1]):
        d.ellipse([px-w/2,py-w/2,px+w/2,py+w/2], fill=LINE)

def cloud(d, cx, cy, S, w, sc=1.0):
    """云轮廓 (unit -1..1, 底边平)"""
    s = S*sc
    b1=bezier((-0.62,0.28),(-1.05,0.02),(-0.95,-0.42),(-0.5,-0.44))
    b2=bezier((-0.5,-0.44),(-0.1,-0.85),(0.35,-0.75),(0.5,-0.36))
    b3=bezier((0.5,-0.36),(0.9,-0.28),(1.05,0.05),(0.62,0.28))
    path=b1+b2+b3+[(-0.62*s+cx, 0.28*s+cy)]
    pts=[(cx+x*s, cy+y*s) for x,y in path]
    draw_path(d, pts, w)

def sun_core(d, cx, cy, r, w, rays=8, ray_in=1.5, ray_out=1.9):
    d.ellipse([cx-r,cy-r,cx+r,cy+r], outline=LINE, width=w)
    for k in range(rays):
        a=math.radians(k*360/rays)
        x1,y1=cx+ray_in*r*math.cos(a), cy+ray_in*r*math.sin(a)
        x2,y2=cx+ray_out*r*math.cos(a), cy+ray_out*r*math.sin(a)
        d.line([x1,y1,x2,y2], fill=LINE, width=w)
        d.ellipse([x2-w/2,y2-w/2,x2+w/2,y2+w/2], fill=LINE)

def drops(d, cx, cy, S, n, slant=0.0):
    s=S
    for i in range(n):
        dx = (i-(n-1)/2)*0.3*s
        x0,y0 = cx+dx+slant*s*0.4, cy+0.18*s
        x1,y1 = cx+dx+slant*s*0.15, cy+0.55*s
        d.line([x0,y0,x1,y1], fill=LINE, width=10)
        d.ellipse([x1-5,y1-5,x1+5,y1+5], fill=LINE)

def flakes(d, cx, cy, S, n):
    s=S; r=0.09*s
    for i in range(n):
        dx=(i-(n-1)/2)*0.3*s; x0,y0=cx+dx,cy+0.42*s
        for k in range(3):
            a=math.radians(k*60)
            d.line([x0-r*math.cos(a),y0-r*math.sin(a),x0+r*math.cos(a),y0+r*math.sin(a)],
                   fill=LINE, width=8)

def bolt_small(d, cx, cy, S):
    s=S*0.5
    pts=[(0.05,-0.5),(-0.35,0.1),(-0.08,0.1),(-0.2,0.6),(0.35,-0.1),(0.08,-0.1),(0.28,-0.5),(0.05,-0.5)]
    d.line([(cx+px*s, cy+py*s+0.35*S) for px,py in pts], fill=LINE, width=10, joint="curve")

def dots(d, cx, cy, S, n, y=0.5):
    for i in range(n):
        dx=(i-(n-1)/2)*0.3*S
        d.ellipse([cx+dx-5, cy+y*S-5, cx+dx+5, cy+y*S+5], fill=LINE)

def hlines(d, cx, cy, S, rows):
    for j,yy in enumerate(rows):
        off = 0.15*S if j%2 else -0.1*S
        d.line([cx-0.55*S+off, cy+yy*S, cx+0.55*S+off, cy+yy*S], fill=LINE, width=10)

W3 = lambda S: 10   # 4x 线宽 = 2.5px@1x

def ico_sun(d,cx,cy,S):        sun_core(d,cx,cy,0.32*S,W3(S))
def ico_cloud_sun(d,cx,cy,S):
    sun_core(d,cx+0.32*S,cy-0.38*S,0.2*S,W3(S),rays=5,ray_in=1.55,ray_out=1.95)
    cloud(d,cx-0.1*S,cy+0.12*S,S,W3(S),sc=0.8)
def ico_cloud(d,cx,cy,S):      cloud(d,cx,cy+0.05*S,S,W3(S))
def ico_rain(d,cx,cy,S,n,slant=0.0): cloud(d,cx,cy-0.22*S,S,W3(S),sc=0.85); drops(d,cx,cy+0.1*S,S,n,slant)
def ico_thunder(d,cx,cy,S,hail=False):
    cloud(d,cx,cy-0.25*S,S,W3(S),sc=0.85); bolt_small(d,cx-0.05*S,cy,S)
    if hail: dots(d,cx+0.35*S,cy,S,2)
def ico_snow(d,cx,cy,S,n):     cloud(d,cx,cy-0.22*S,S,W3(S),sc=0.85); flakes(d,cx,cy+0.1*S,S,n)
def ico_fog(d,cx,cy,S):        cloud(d,cx,cy-0.28*S,S,W3(S),sc=0.8); hlines(d,cx,cy+0.25*S,S,[0,0.28])
def ico_sleet(d,cx,cy,S):
    cloud(d,cx,cy-0.22*S,S,W3(S),sc=0.85)
    drops(d,cx-0.18*S,cy+0.1*S,S,1); flakes(d,cx+0.22*S,cy+0.1*S,S,1)
def ico_dust(d,cx,cy,S):       hlines(d,cx,cy-0.1*S,S,[-0.15,0.1,0.35]); dots(d,cx,cy,S,3,y=-0.5)
def ico_haze(d,cx,cy,S):
    for j,(dx,ln) in enumerate(((-0.3,0.4),(0.05,0.5),(-0.15,0.45))):
        x0=cx+dx*S-0.5*ln*S; x1=cx+dx*S+0.5*ln*S
        yy=cy+(j-1)*0.4*S
        d.line([x0,yy,x1,yy],fill=LINE,width=10)
def ico_unknown(d,cx,cy,S):
    cloud(d,cx,cy-0.2*S,S,W3(S),sc=0.85)
    f=ImageFont.truetype(FONT_DIN, int(0.55*S))
    d.text((cx+0.02*S, cy+0.5*S), "?", font=f, fill=LINE, anchor="mm")

CODES=[0,1,2,3,4,5,6,7,8,9,10,13,14,15,16,17,18,19,20,29,30,33,53,99,301]
DESIGN={0:ico_sun, 1:ico_cloud_sun, 2:ico_cloud, 3:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,2),
        4:ico_thunder, 5:lambda d,cx,cy,S: ico_thunder(d,cx,cy,S,hail=True),
        6:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,1), 7:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,3),
        8:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,4,slant=0.6), 9:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,5,slant=0.6),
        10:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,5,slant=0.9),
        13:lambda d,cx,cy,S: ico_snow(d,cx,cy,S,2), 14:lambda d,cx,cy,S: ico_snow(d,cx,cy,S,3),
        15:lambda d,cx,cy,S: ico_snow(d,cx,cy,S,4), 16:lambda d,cx,cy,S: ico_snow(d,cx,cy,S,5),
        17:ico_fog, 18:ico_sleet, 19:ico_dust, 20:lambda d,cx,cy,S: ico_rain(d,cx,cy,S,2),
        29:ico_dust, 30:ico_dust, 33:ico_haze, 53:ico_haze, 99:ico_unknown, 301:ico_unknown}

IB = 36   # 图标盒 36×36
for i,code in enumerate(CODES):
    big=Image.new("RGBA",(IB*SCALE,IB*SCALE),(0,0,0,0))
    d=ImageDraw.Draw(big)
    DESIGN[code](d, IB*SCALE/2, IB*SCALE/2, IB*SCALE*0.44)
    G._to_palette_safe(big.resize((IB,IB),Image.LANCZOS)).save(f"{WS3}/images/imagelist_0014_{i:04d}.png")
print(f"天气图标: {len(CODES)} 帧白色线稿重绘完成")

# ================================================================ 2. 睡眠竖条 + 时长
BW,BH,SCALE2 = 12, 52, 4     # 竖条 12×52
for i in range(11):
    big=Image.new("RGBA",(BW*SCALE2,BH*SCALE2),(0,0,0,0))
    d=ImageDraw.Draw(big)
    w2=int(2.5*SCALE2)
    d.rounded_rectangle([w2//2, w2//2, BW*SCALE2-w2//2, BH*SCALE2-w2//2],
                        radius=3*SCALE2, outline=LINE, width=w2)
    frac=i/10
    ih=int((BH-8)*SCALE2*frac)
    if ih>0:
        d.rounded_rectangle([3*SCALE2, BH*SCALE2-4*SCALE2-ih, BW*SCALE2-3*SCALE2, BH*SCALE2-4*SCALE2],
                            radius=2*SCALE2, fill=LINE)
    G._to_palette_safe(big.resize((BW,BH),Image.LANCZOS)).save(f"{WS3}/images/imagelist_0015_{i:04d}.png")
print("睡眠竖条: 11 帧重绘 (12×52)")

# 时长 12 帧从寻路者 verbatim
srcs={os.path.basename(p):p for p in glob.glob("/tmp/ref_p/**/*.png",recursive=True)}
pwf=json.load(open("/tmp/ref_p/wfDef.json"))
pel={str(e.get("dataSrc")):e for e in pwf["faces"][0]["elements"]}
for i,f in enumerate(pel["082814"]["imageList"]):
    shutil.copy(srcs.get(f) or srcs.get(f+".png"), f"{WS3}/images/imagelist_0016_{i:04d}.png")
RAW_1828 = pel["1828"]["prop7Raw"]
RAW_082814 = pel["082814"]["prop7Raw"]
print("睡眠时长 12 帧移植, raw 获取 OK")

# ================================================================ 3. wfDef
wf=json.load(open(f"{WS3}/wfDef.json"))
els=wf["elementsNormal"]
# 移除旧 3031 元素重建 (帧已重绘, 元素保留原配置即可 — 检查存在)

# 睡眠竖条 + 时长 (先去重, 脚本可重入)
els[:] = [e for e in els if str(e.get("dataSrc")) not in ("1828","082814")
          and not e.get("jumpRaw") and str(e.get("dataSrc"))!="3031"]
if not any(str(e.get("dataSrc"))=="3031" for e in els):
    wx,wy=232+216*math.sin(math.radians(79)), 232-216*math.cos(math.radians(79))
    els.append({"type":"widge_imagelist","x":round(wx-18),"y":round(wy-18),"dataSrc":"3031",
                "imageList":[f"imagelist_0014_{i:04d}" for i in range(25)],
                "imageIndexList":[0,1,2,3,4,5,6,7,8,9,10,13,14,15,16,17,18,19,20,29,30,33,53,99,301],
                "prop7Raw":"30310020000000000600000300020000000000000100000002000000030000000400000005000000060000000700000008000000090000000A0000000D0000000E0000000F00000010000000110000001200000013000000140000001D0000001E0000002100000035000000630000002D010000"})
els.append({"type":"widge_imagelist","x":167,"y":168,"dataSrc":"1828",
            "imageList":[f"imagelist_0015_{i:04d}" for i in range(11)],
            "prop7Raw":RAW_1828})
els.append({"type":"widge_dignum","x":153,"y":226,"dataSrc":"082814",
            "imageList":[f"imagelist_0016_{i:04d}" for i in range(12)],
            "prop7Raw":RAW_082814})
# 热区 4 个
base_raw=bytes.fromhex(pel["082814"].get("jumpRaw","") or "") or None
# 用寻路者任一 56B raw 做模板
tpl=None
for e in pwf["faces"][0]["elements"]:
    if e.get("jumpRaw") and len(e["jumpRaw"])==112:
        tpl=bytes.fromhex(e["jumpRaw"]); break
def mk_jump(code, x, y, w, h):
    raw=bytearray(tpl)
    raw[3]=0x31
    raw[34:38]=bytes.fromhex(code)
    raw[52:54]=w.to_bytes(2,"little")
    raw[54:56]=h.to_bytes(2,"little")
    return {"type":"element","x":x,"y":y,"jumpRaw":raw.hex(),
            "jumpCode":code,"jumpName":"","prop9Length":56}
els.append(mk_jump("01001312", 304, 22, 138, 136))   # 天气弧 → 天气
els.append(mk_jump("01003311",  22, 22, 136, 136))   # 步数弧 → 运动/步数
els.append(mk_jump("010C6F03",  24,308, 132, 132))   # 卡路里弧 → 元气值(活力)
els.append(mk_jump("0100C310", 182,155, 104, 112))   # 时数字 → 睡眠
wf["name"]="RouletteS3_v72"
json.dump(wf,open(f"{WS3}/wfDef.json","w"),ensure_ascii=False,indent=2)
print("wfDef -> v72 (睡眠条+时长+4热区)")
