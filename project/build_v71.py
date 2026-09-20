#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v71 构建器（在 v70 基础上）:
  1. 轮盘小刻度回归: v60 实测 = 60 根刻度(主刻度亮 w4 / 小刻度暗灰(110,110,115) 细线等长),
     v69 重绘时 gen_ring 的 n%5 过滤丢了 48 根小刻度 → 自写循环补齐(主+小), 数字仍每5格
  2. 天气动态图标: 移植寻路者 3031 (25 帧 36×36 + imageIndexList + prop7Raw verbatim),
     放在原 sun 图标位 (中心 r=216, 79°), image_0002 不再画 sun → 天气类型驱动图标变化
     注: 温度数字 203103 配置与两块参考盘完全一致, 显示 0 = 手表侧天气未同步(Mi Fitness)
  3. AOD: 背景补双圈刻度环(暗) + 整体调亮 (轨道/图标 16%→30%, 红框 42%→55%,
     时/分数字位图 ×1.5, 星期色 94→140)
"""
import sys, math, json, shutil, glob, os
import os as _os
ROOT = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isdir(_os.path.join(ROOT, "tools")):
    ROOT = _os.path.dirname(ROOT)
sys.path.insert(0, _os.path.join(ROOT, "tools/scripts"))
import gen_assets_v3 as G
import gen_assets_html as G2
from PIL import Image, ImageDraw, ImageFont

WS3 = _os.path.join(ROOT, "project/ws3")
CANVAS, C = 464, (232, 232)
ARC_R, ARC_W, SCALE = 218, 11, 4
TRACK = (60, 60, 70, 255)
LINE  = (235, 235, 240, 255)
K = 1.06

ARCS = [("temp", 20, 70, 79, None),          # sun 移除 → 3031 动态天气图标
        ("battery", 110, 160, 169, "bolt"),
        ("calories", 200, 250, 191, "flame"),
        ("steps", 290, 340, 281, "shoe")]

def web2pil(t): return t - 90.0
def pt_(r, deg):
    a = math.radians(deg)
    return (C[0] + r*math.sin(a), C[1] - r*math.cos(a))

# ------------------------------------------------ A. 图标 (v68 线稿风, 无 sun)
def rcap(d, x, y, w):
    r = w/2
    d.ellipse([x-r, y-r, x+r, y+r], fill=LINE)
def icon_bolt(d, cx, cy, R, w):
    k = R/13.0
    pts = [(0,-9*k), (-8*k,1*k), (-2*k,1*k), (-4*k,9*k), (6*k,-2*k), (0,-2*k), (4*k,-9*k), (0,-9*k)]
    d.line([(cx+px, cy+py) for px, py in pts], fill=LINE, width=w, joint="curve")
    rcap(d, cx, cy-9*k, w)
def _bezier(p0,p1,p2,p3,n=16):
    out=[]
    for i in range(n+1):
        t=i/n; mt=1-t
        out.append((mt**3*p0[0]+3*mt*mt*t*p1[0]+3*mt*t*t*p2[0]+t**3*p3[0],
                    mt**3*p0[1]+3*mt*mt*t*p1[1]+3*mt*mt*t*p2[1]+t**3*p3[1]))
    return out
def icon_flame(d, cx, cy, R, w):
    s=0.92*R
    r1=_bezier((0.10,-1.0),(0.42,-0.66),(0.64,-0.34),(0.54,0.10))
    r2=_bezier((0.54,0.10),(0.47,0.52),(0.27,0.80),(0,0.86))
    path=r1+r2+[(-x,y) for x,y in (r1+r2[1:])[::-1]]
    pts=[(cx+x*s,cy+y*s) for x,y in path]
    d.line(pts,fill=LINE,width=w,joint="curve"); rcap(d,*pts[0],w); rcap(d,*pts[-1],w)
    i1=_bezier((0,-0.10),(0.16,-0.02),(0.24,0.16),(0.20,0.34))
    i2=_bezier((0.20,0.34),(0.15,0.52),(0.08,0.58),(0,0.58))
    ip=i1+i2+[(-x,y) for x,y in (i1+i2[1:])[::-1]]
    ipts=[(cx+x*s,cy+y*s) for x,y in ip]
    d.line(ipts,fill=LINE,width=w,joint="curve"); rcap(d,*ipts[0],w)
def icon_shoe(d, cx, cy, R, w):
    s=0.92*R
    d.ellipse([cx-0.40*s, cy-0.82*s, cx+0.40*s, cy+0.18*s], outline=LINE, width=w)
    hr=0.30*s; hx,hy=cx+0.08*s, cy+0.58*s
    d.ellipse([hx-hr,hy-hr,hx+hr,hy+hr], outline=LINE, width=w)
ICONS={"bolt":icon_bolt,"flame":icon_flame,"shoe":icon_shoe}

# ------------------------------------------------ B. 静态层 (轨道@218 + 3 图标, 无 sun)
big=Image.new("RGBA",(CANVAS*SCALE,CANVAS*SCALE),(0,0,0,0))
d=ImageDraw.Draw(big)
for name,s,e,ia,icon in ARCS:
    d.arc([C[0]*SCALE-ARC_R*SCALE, C[1]*SCALE-ARC_R*SCALE,
           C[0]*SCALE+ARC_R*SCALE, C[1]*SCALE+ARC_R*SCALE],
          web2pil(s-0.6), web2pil(e), fill=TRACK, width=ARC_W*SCALE)
    rw=ARC_W/2*SCALE
    for th in (s-0.6, e):
        a=math.radians(th-90)
        x=C[0]*SCALE+(ARC_R-ARC_W/2)*SCALE*math.cos(a)
        y=C[1]*SCALE+(ARC_R-ARC_W/2)*SCALE*math.sin(a)
        d.ellipse([x-rw,y-rw,x+rw,y+rw],fill=TRACK)
for name,s,e,ia,icon in ARCS:
    if not icon: continue
    ic=(C[0]*SCALE+(ARC_R-2)*SCALE*math.sin(math.radians(ia)),
        C[1]*SCALE-(ARC_R-2)*SCALE*math.cos(math.radians(ia)))
    ICONS[icon](d, ic[0], ic[1], 18*SCALE, 3*SCALE)
canvas=big.resize((CANVAS,CANVAS),Image.LANCZOS)
G._to_palette_safe(canvas).save(f"{WS3}/images/image_0002.png")
print("image_0002: 轨道@218 + 3 图标 (sun 移除, 由 3031 动态天气图标替代)")

# ------------------------------------------------ C. 双轮盘重绘 (60 刻度: 主+小)
def gen_ring_full(Rnum, RtIn, RtOut, num_sz, num_col):
    img=Image.new("RGBA",(CANVAS,CANVAS),(0,0,0,0))
    d=ImageDraw.Draw(img)
    font=G2.fnt(num_sz, False)
    for n in range(60):
        a_img=90-6*n
        if n%5==0:
            d.line([pt_(RtIn-4,a_img), pt_(RtOut,a_img)], fill=(230,230,236,255), width=4)
            px,py=pt_(Rnum,a_img)
            G2.draw_text_rotated(img,(px,py),f"{n:02d}",font,num_col,-a_img)
        else:
            d.line([pt_(RtIn,a_img), pt_(RtOut,a_img)], fill=(110,110,115,255), width=2)
    return img
G._to_palette_safe(gen_ring_full(105,126,136,23,(220,220,226,255))).save(f"{WS3}/images/image_0001.png")
G._to_palette_safe(gen_ring_full(157,178,188,23,(235,235,240,255))).save(f"{WS3}/images/image_0000.png")
print("双轮盘重绘: 60 刻度 (12 主 + 48 小暗) + 数字每5格")

# ------------------------------------------------ D. 天气图标 3031 (移植寻路者)
REF_P="/tmp/ref_p"
srcs={os.path.basename(p):p for p in glob.glob(REF_P+"/**/*.png",recursive=True)}
pwf=json.load(open(REF_P+"/wfDef.json"))
pel=[e for e in pwf["faces"][0]["elements"] if str(e.get("dataSrc"))=="3031"][0]
idx_list=pel["imageIndexList"]
raw=pel["prop7Raw"]
for i,f in enumerate(pel["imageList"]):
    p=srcs.get(f) or srcs.get(f+".png")
    shutil.copy(p, f"{WS3}/images/imagelist_0014_{i:04d}.png")
print(f"天气图标: 25 帧 36×36 已移植 (映射 {idx_list[:6]}...)")

# ------------------------------------------------ E. wfDef
wf=json.load(open(f"{WS3}/wfDef.json"))
# 弧 x/y 不变 (v69 已回写); 追加天气元素
frames=[f"imagelist_0014_{i:04d}.png" for i in range(25)]
wx,wy=pt_(216,79)   # 原 sun 图标中心
wf["elementsNormal"].append({
    "type":"widge_imagelist","x":round(wx-18),"y":round(wy-18),
    "dataSrc":"3031","imageList":frames,"imageIndexList":idx_list,
    "prop7Raw":raw})
print(f"天气元素追加 @({round(wx-18)},{round(wy-18)})")
wf["name"]="RouletteS3_v71"
json.dump(wf,open(f"{WS3}/wfDef.json","w"),ensure_ascii=False,indent=2)

# ------------------------------------------------ F. AOD: 补圈 + 调亮
aod=Image.new("RGBA",(CANVAS,CANVAS),(0,0,0,0))
# 1) 轨道+图标 调暗 30%
t=Image.open(f"{WS3}/images/image_0002.png").convert("RGBA")
tp=t.load()
for y in range(CANVAS):
    for x in range(CANVAS):
        r,g,b,a=tp[x,y]
        if a>0: tp[x,y]=(int(r*0.30),int(g*0.30),int(b*0.30),a)
aod.alpha_composite(t)
# 2) 双圈刻度环 (暗): 分盘 126/136, 秒盘 178/188
dd=ImageDraw.Draw(aod)
for RtIn,RtOut in ((126,136),(178,188)):
    for n in range(60):
        a_img=90-6*n
        if n%5==0:
            dd.line([pt_(RtIn-3,a_img),pt_(RtOut,a_img)],fill=(58,58,64,255),width=3)
        else:
            dd.line([pt_(RtIn,a_img),pt_(RtOut,a_img)],fill=(40,40,46,255),width=2)
# 3) 暗红读数窗 55%
cap=Image.open(f"{WS3}/images/image_0004.png").convert("RGBA")
cp=cap.load()
for y in range(cap.size[1]):
    for x in range(cap.size[0]):
        r,g,b,a=cp[x,y]
        if a>0: cp[x,y]=(int(r*0.55),int(g*0.15),int(b*0.15),a)
aod.alpha_composite(cap,(303,202))
G._to_palette_safe(aod).save(f"{WS3}/images_aod/image_0000.png")
print("AOD 背景: 轨道30% + 双圈刻度环 + 红框55%")
# 4) 时/分数字位图 ×1.5
for pre,cnt in (("imagelist_0000",10),("imagelist_0001",10)):
    for i in range(cnt):
        p=f"{WS3}/images_aod/{pre}_{i:04d}.png"
        im=Image.open(p).convert("RGBA")
        px=im.load()
        for y in range(im.size[1]):
            for x in range(im.size[0]):
                r,g,b,a=px[x,y]
                if a>0: px[x,y]=(min(255,int(r*1.5)),min(255,int(g*1.5)),min(255,int(b*1.5)),a)
        im.save(p)
print("AOD 时/分数字 ×1.5 调亮")
# 5) AOD 星期提亮 (DIN 21, 140)
font=ImageFont.truetype("/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf",21)
labels=["SUN","MON","TUE","WED","THU","FRI","SAT"]
mw=max(font.getbbox(l)[2]-font.getbbox(l)[0] for l in labels)
cw,ch=mw+8,int(21*1.35)
for i,lab in enumerate(labels):
    img=Image.new("RGBA",(cw,ch),(0,0,0,0))
    dd=ImageDraw.Draw(img)
    dd.text((cw//2,ch//2),lab,font=font,fill=(140,140,146,255),anchor="mm")
    img.save(f"{WS3}/images_aod/imagelist_0002_{i:04d}.png")
for e in wf["elementsAod"]:
    if e.get("dataSrc")=="2012":
        e["x"],e["y"]=round(232.5-cw/2),round(182.5-ch/2)
json.dump(wf,open(f"{WS3}/wfDef.json","w"),ensure_ascii=False,indent=2)
print(f"AOD 星期提亮 (140), cell {cw}x{ch}")
