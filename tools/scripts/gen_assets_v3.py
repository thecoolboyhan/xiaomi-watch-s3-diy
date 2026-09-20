#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RouletteS3 v7 素材生成器
基于 v6 的修复版本，主要改动：
  1. **数字字形统一宽度 (cell_w)** —— S3 固件在 dignum 渲染时按 cell_w 横向步进
     推进（参考 wheel_v5 preview.py: cell_w = load(names[0]).width），
     因此所有同组数字必须宽度一致。v6 的 digH/digM 各字宽度不同（1 偏窄），
     会导致 12:31 之类数字错位。
  2. **冒号 / 斜杠尺寸收紧** —— 胶囊内冒号 12x12（与 digM 字号 24 视觉等高），
     中央斜杠 12x14（与 digS 字号 16 等高），避免与同行数字高度失衡。
  3. **百分号尺寸** —— 14x13（与 digS 等高）。

输出目录: out_v3/images/
坐标系: 466x466, 中心 C=(233,233)。网页 640 坐标 * S(=466/640=0.7281) 缩放。
"""
import math, os
from PIL import Image, ImageDraw, ImageFont, ImageChops

OUT = os.path.join(os.path.dirname(__file__), "out_v3", "images")
os.makedirs(OUT, exist_ok=True)

S = 466/640.0

# === v24: 画布从 466 改 464, 中心从 233 改 232 ==============================
# 依据 (谷歌轮盘·橙 逐块实测):
#   谷歌全部满屏图 (两枚转盘 image_0001/0003 + 覆盖层 image_0005) 均为 464x464,
#   且 widge_pointer 的 imageRotateX/Y = 232 —— 恰为 464/2, 即【图像精确中心】。
#   我们 v23 在 466 画布上填 232, 旋转中心偏心 1px, 秒盘转起来会轻微摆动。
#   另: 464 = 16x29 (16 字节对齐), 466 不是 16 的倍数 —— 对齐后固件走 DMA/GPU
#   快路径, 是把扫秒帧率喂满的必要条件之一。
CANVAS = 464
C = (CANVAS // 2, CANVAS // 2)   # (232, 232)
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"

def fnt(sz, bold=False):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()

def rr(deg):  # 网页角度(0=12点,顺时针) -> 弧度
    return math.radians(deg)

def pt(r, deg):  # 半径r, 角度deg(0=12点顺时针) -> 屏幕坐标
    a = rr(deg)
    return (C[0] + r*math.sin(a), C[1] - r*math.cos(a))

def new_layer(size=None):
    if size is None:
        size = (CANVAS, CANVAS)
    return Image.new("RGBA", size, (0,0,0,0))

def draw_text_rotated(img, xy, text, font, fill, angle_deg, anchor="mm"):
    """在 img 上以 xy 为中心, 文字整体旋转 angle_deg(PIL CCW 正) 绘制。"""
    bbox = font.getbbox(text)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    pad = 8
    layer = Image.new("RGBA", (tw+pad*2, th+pad*2), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    d.text((pad, pad), text, font=font, fill=fill)
    # 旋转: 让文字"顶部"指向 outward 方向
    rot = layer.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
    ix = int(round(xy[0] - rot.width/2))
    iy = int(round(xy[1] - rot.height/2))
    img.alpha_composite(rot, (ix, iy))

# ---------------------------------------------------------------------------
# 限色工具（关键修复：v9 装机重启根因）
# S3 固件图片解码器要求 sign=10（256 色索引 + RLE V2.0）。任何 >256 色的图片会让
# 打包器(Mi8WfBinTool)的调色板溢出 / 退化成私有头 → 实机装机即重启。
# 因此所有生成素材在落盘前必须量化到 <=256 色（保留 alpha）。
# 策略复刻工程既有 optimize_assets.py：
#   - 白色系图 → 预乘白化（RGB 归一为白，亮度预乘进 alpha，黑底视觉无损）
#   - 彩色/黑色图 → FASTOCTREE 量化到 256 色（保留真实颜色与 alpha）
# ---------------------------------------------------------------------------
MAX_COLORS = 256
WHITE_MIN_LUMA = 200.0
COLOR_MAX_RATIO = 0.15

def _img_stats(im):
    """返回 (颜色数, 不透明像素均亮度, 彩色像素占比)"""
    im = im.convert("RGBA")
    px = list(im.getdata())
    cols = len(set(px))
    op = [q for q in px if q[3] > 200]
    if op:
        luma = sum(r + g + b for r, g, b, a in op) / len(op) / 3
        colored = sum(1 for r, g, b, a in op if max(r, g, b) - min(r, g, b) > 18)
        ratio = colored / len(op)
    else:
        luma, ratio = 0.0, 0.0
    return cols, luma, ratio

def _premultiply_whiten(im):
    """白色系图 → RGB 归一为白，亮度预乘进 alpha（黑底视觉无损）。"""
    im = im.convert("RGBA")
    gray = im.convert("L")
    a = im.getchannel("A")
    new_a = ImageChops.multiply(gray, a)
    white = Image.new("L", im.size, 255)
    return Image.merge("RGBA", (white, white, white, new_a))

def _quantize_256(im):
    """彩色图 → FASTOCTREE 量化到 256 色（保留真实颜色与 alpha）。"""
    im = im.convert("RGBA")
    try:
        q = im.quantize(colors=MAX_COLORS, method=Image.FASTOCTREE)
    except Exception:
        q = im.quantize(colors=MAX_COLORS, method=Image.MEDIANCUT)
    return q.convert("RGBA")

def _to_palette_safe(img):
    """把图像量化到 <= MAX_COLORS 色，返回 RGBA。"""
    im = img.convert("RGBA")
    cols, luma, ratio = _img_stats(im)
    if cols <= MAX_COLORS:
        return im  # 已满足，保留原始（打包器自行索引化，安全）
    if luma > WHITE_MIN_LUMA and ratio < COLOR_MAX_RATIO:
        out = _premultiply_whiten(im)
    else:
        out = _quantize_256(im)
    # 兜底：极端情况下（如白化后 alpha 级仍过多）再强制 256 色量化
    if len(set(out.getdata())) > MAX_COLORS:
        out = _quantize_256(im)
    return out

def save(img, name):
    p = os.path.join(OUT, name)
    out = _to_palette_safe(img)
    out.save(p)
    # 限色校验（以落盘文件为准，防止回归）
    final = Image.open(p).convert("RGBA")
    ncol = len(set(final.getdata()))
    if ncol > MAX_COLORS:
        raise RuntimeError(
            f"[color-limit] {name} 仍有 {ncol} 色(>={MAX_COLORS})，"
            f"打包将致固件调色板溢出 → 装机重启！请检查生成逻辑。")
    print(f"  {name:28s} {out.size} colors={ncol}")
    return p

# ---------------------------------------------------------------------------
# 1. 背景 bg.png : 纯黑 + 外圈淡环 + 双轮盘轨道淡环 + 3点方向红色读数刻度
# ---------------------------------------------------------------------------
#
# === v23 架构反转 (依据谷歌轮盘·橙 逐像素实测) =============================
# 对谷歌盘 3 张主图做了 alpha-vs-半径 剖面 + 连通域分析, 结论与我们旧版完全相反:
#
#   谷歌 image_0001 (秒针 widge_pointer ds=1811, 元素[0]):
#       alpha: r<171 = 0.00 | r=174..230 = 1.00 (完全不透明!)
#       内容 : 黑底(0,0,0) + 12 个浅灰(~200)数字, 半径 r≈198, 径向排布, 间隔 30°
#       => 秒圈是一枚【不透明黑色圆环盘】, 数字烧在盘上, 整盘旋转。
#
#   谷歌 image_0003 (分针 widge_pointer ds=1011, 元素[1]):
#       alpha: r<177 = 1.00 (完全不透明圆盘) | r>179 ≈ 0
#       内容 : 黑底 + 12 个浅灰数字, 半径 r≈131, 径向排布
#       => 分圈是一枚【不透明黑色实心盘】, 盖住秒盘中心。
#
#   谷歌 image_0005 (element, 元素[2] 压在两枚指针【之上】):
#       平均 alpha 仅 0.10~0.20, 中心 r<70 全透明
#       内容 : 橙色(204,115,0) 读数窗 + 弧段 + 图标
#       => bg 根本不是"背景", 而是一层【透明前景覆盖层】!
#
# 我们 v22 及以前是: bg=不透明底盘 + 指针=透明细环压在上面 —— 层级完全颠倒。
# 后果: 指针不是最底层 => 固件每帧都要把指针与下层做 alpha 合成 => 放弃亚秒插值,
#       退化成 1Hz 整秒跳变 (用户实拍视频实证)。
#
# v23 改为完全对齐谷歌:
#   bg.png       -> 纯透明覆盖层 (只有外圈线/轨道细线/3点红标), 不再有实心底盘
#   ring_sec.png -> 不透明黑盘 (r<=231) + 刻度 + 数字   [元素 0, 底层, 62fps 旋转]
#   ring_min.png -> 不透明黑盘 (r<=136) + 刻度 + 数字   [元素 1, 盖住秒盘中心]
# ---------------------------------------------------------------------------
PLATE_BLACK = (0, 0, 0, 255)   # 转盘底色 (与谷歌一致: 纯黑不透明)
R_PLATE_SEC = 231              # 秒盘半径 (谷歌外缘 231)
R_PLATE_MIN = 136              # 分盘半径 (盖住秒盘中心, 露出秒盘 r>136 的数字带)
R_HOLE = 185                   # v39: plate 中心透明洞半径 — 覆盖 extraProp7 指针
                               #   (ring_sec max r=180, 留 5px 余量, 防亚像素裁剪裁到指针)

def gen_bg():
    """v23: bg 退化为【透明前景覆盖层】(对齐谷歌 image_0005 的 mean-alpha≈0.15)。
    不再绘制实心底盘 —— 底色由 ring_sec/ring_min 两枚不透明转盘提供。"""
    img = new_layer()
    d = ImageDraw.Draw(img)
    # 外圈环 (轮盘外缘) — 压在秒盘之上的一圈亮边
    # v24: 改为按 C 居中(旧硬编码 [6,6,459,459] 在 464 画布上会偏心 2px)
    d.ellipse([C[0]-226, C[1]-226, C[0]+226, C[1]+226],
              outline=(70,70,80,255), width=2)
    # 2 条淡轨道环 (标示两枚轮盘的读数半径)
    d.ellipse([C[0]-164, C[1]-164, C[0]+164, C[1]+164], outline=(42,42,50,255), width=2)  # sec 轨道
    d.ellipse([C[0]-111, C[1]-111, C[0]+111, C[1]+111], outline=(42,42,50,255), width=2)  # min 轨道
    # 分/秒盘交界细线 (让两枚转盘边界清晰, 替代原来的实心底差异)
    d.ellipse([C[0]-R_PLATE_MIN, C[1]-R_PLATE_MIN,
               C[0]+R_PLATE_MIN, C[1]+R_PLATE_MIN], outline=(52,52,62,255), width=2)
    # 3 点方向红色读数刻度 (轮盘当前值读取位) — 小而克制
    tip = pt(183, 90); base1 = pt(170, 86); base2 = pt(170, 94)
    d.polygon([tip, base1, base2], fill=(255,60,60,210))
    save(img, "bg.png")

# ---------------------------------------------------------------------------
# 2. 轮盘环 ring_min / ring_sec : 60 刻度 + 每5格数字 00-55(径向), pivot=中心
#    ★ v18 恢复 v16 密集环 (真机验证: v16 环可见, v17 稀疏12刻度→widge_pointer不渲染)
#    数字 n 画在图像角 (90 - 6n) [0=12点顺时针], 使 widge_pointer 旋转 value*6 后
#    数字 value 落在 3 点方向(90°).
#    对齐目标图实测: 秒圈墨量=1185px(含数字+60刻度), 分圈=1165px.
# ---------------------------------------------------------------------------
def gen_ring(name, Rnum, RtIn, RtOut, num_font_sz, tick_col, num_col, num_bold,
             plate_r_in=None, plate_r_out=None):
    img = new_layer()
    d = ImageDraw.Draw(img)
    # ★ v41: 不透明【环形带】(对齐对照 bin image_0001/0003 的不透明指针图)。
    #   指针图本身不透明 + 位于元素[0]/[1] 最前 -> 固件直接 blit 旋转, 无需逐帧 alpha 合成 -> 平滑。
    #   用环形带(中心透明)而非整盘, 保留 V5 开放中心观感(大时/红窗居于中心)。
    if plate_r_out:
        d.ellipse([C[0]-plate_r_out, C[1]-plate_r_out, C[0]+plate_r_out, C[1]+plate_r_out],
                  fill=PLATE_BLACK)
        if plate_r_in:
            d.ellipse([C[0]-plate_r_in, C[1]-plate_r_in, C[0]+plate_r_in, C[1]+plate_r_in],
                      fill=(0, 0, 0, 0))
    font = fnt(num_font_sz, num_bold)
    for n in range(60):
        # 数字/刻度画在图像角 (90 - 6n): 经固件旋转 value*6 后, 数字 value 落在 3 点(90°)
        a_img = (90 - 6*n)
        # ★ v24: 去掉 48 条细淡次刻度。用户反馈"刻度内有虚线" —— 正是这 48 条
        #   width=1 的暗线在 r=RtIn..RtOut 之间形成的一圈虚线感。
        #   同时也更贴近谷歌盘实测(其转盘只有 12 个数字, 无密集刻度带)。
        if n % 5 != 0:
            continue
        d.line([pt(RtIn - 4, a_img), pt(RtOut, a_img)],
               fill=(230,230,236,255), width=4)
        px, py = pt(Rnum, a_img)
        # 文字顶部指向 outward(=图像角 a_img, 顺时针); PIL 旋转 = -a_img
        draw_text_rotated(img, (px, py), f"{n:02d}", font, num_col, -a_img)
    save(img, name)

# ---------------------------------------------------------------------------
# 3. 数字图集 digits : 大(时) / 中(胶囊) / 小(弧/电量/温/日)
#    **v7 修复：所有同组字形宽度统一 = cell_w**，保证 dignum 横向步进对齐
#    字高 sz*0.75, 字宽取所有数字 bbox 最大值再加少量 padding。
# ---------------------------------------------------------------------------
def gen_digits(prefix, sz, bold, with_blank=False):
    font = fnt(sz, bold)
    # 1) 先量每个数字的 bbox 宽度，取最大作为 cell_w
    max_w = 0
    for i in range(10):
        bbox = font.getbbox(str(i))
        w = bbox[2] - bbox[0]
        if w > max_w:
            max_w = w
    cell_w = max_w + 2  # 少量 padding
    # 2) 用统一 cell_w 渲染每个数字（居中放在 cell 内）
    cell_h = int(sz * 0.95)  # 字高
    for i in range(10):
        tmp = new_layer((cell_w, cell_h))
        d = ImageDraw.Draw(tmp)
        d.text((cell_w//2, cell_h//2), str(i), font=font,
               fill=(255,255,255,255), anchor="mm")
        save(tmp, f"{prefix}_{i}.png")
    if with_blank:
        img = new_layer((cell_w, cell_h))
        save(img, f"{prefix}_10.png")
    return cell_w, cell_h  # 返回供 assemble 引用

# ---------------------------------------------------------------------------
# 4. 星期 / 月份 图集 (imagelist 帧)
#    文字宽度不强制统一（每帧独立），但尽量给足够水平空间避免裁剪
# ---------------------------------------------------------------------------
def gen_text_frames(prefix, labels, sz):
    font = fnt(sz, False)
    # 测量最宽 label
    max_w = 0
    for lab in labels:
        bbox = font.getbbox(lab)
        w = bbox[2] - bbox[0]
        if w > max_w:
            max_w = w
    cell_w = max_w + 4
    cell_h = int(sz * 1.05)
    for i, lab in enumerate(labels):
        tmp = new_layer((cell_w, cell_h))
        d = ImageDraw.Draw(tmp)
        col = (170,170,178,255)
        d.text((cell_w//2, cell_h//2), lab, font=font, fill=col, anchor="mm")
        save(tmp, f"{prefix}_{i}.png")
    return cell_w, cell_h

# ---------------------------------------------------------------------------
# 5. 冒号 + 斜杠 + 百分号 静态图  (v7 修复: 尺寸与对应行高匹配)
# ---------------------------------------------------------------------------
def gen_punct():
    # 5a. 胶囊内冒号 - 12x12 (与 digM 字号 24 视觉等高, 两点间距适中)
    img = new_layer((12, 12))
    d = ImageDraw.Draw(img)
    d.ellipse([4,1,8,5], fill=(255,255,255,255))     # 上点
    d.ellipse([4,7,8,11], fill=(255,255,255,255))    # 下点
    save(img, "colon.png")

    # 5b. 中央斜杠 - 12x14 (与 month/day 行等高, 居中显示)
    img = new_layer((12, 14))
    d = ImageDraw.Draw(img)
    d.line([(3,11), (9,3)], fill=(160,160,168,255), width=2)  # 短斜线 "/"
    save(img, "slash.png")

    # 5c. 百分号 - 12x13 (与 digS 字号 16 等高, 用于电量)
    img = new_layer((12, 13))
    d = ImageDraw.Draw(img)
    d.text((6, 6), "%", font=fnt(13, True), fill=(235,235,240,255), anchor="mm")
    save(img, "percent.png")

    # 5d. 温度度数符号 ° - 14x14 (用于温度)
    img = new_layer((14, 14))
    d = ImageDraw.Draw(img)
    d.ellipse([3,2,11,10], outline=(235,235,240,255), width=2)
    save(img, "deg.png")

# ---------------------------------------------------------------------------
# 6. 红色胶囊底图 (3点方向) : 干净圆角红胶囊 128x57, 透明底, 无大辉光
#    对齐目标图 (像素核验: 红胶囊 bbox 128x57, 中心(360,233))
# ---------------------------------------------------------------------------
def gen_capsule():
    w, h = 128, 57
    img = new_layer((w+8, h+8))
    d = ImageDraw.Draw(img)
    ox, oy = 4, 4
    # 干净圆角红胶囊: 深红填充 + 红描边, 形状与目标一致 (pill, radius=h/2)
    d.rounded_rectangle([ox, oy, ox+w, oy+h], radius=h//2,
                        fill=(16,4,6,255), outline=(255,60,60,255), width=4)
    save(img, "capsule_bg.png")

# ---------------------------------------------------------------------------
# 7. 四弧 arcs.png (静态) : 轨道 + 白色填充(静态美观值) + 图标, 四象限
#    角度: 右上20-70天气 / 右下110-160电量 / 左下200-250卡路里 / 左上290-340步数
#    R=201(网页276*S). 图标用白色描边风格。
# ---------------------------------------------------------------------------
# 四弧统一规格 (v19): 每弧 = 静态轨道(arcs.png) + 动态填充帧(arcfill_*) 两层。
#   (s, e, 图标角, 图标, dataSrc, 数据下限, 数据上限, 帧数)
#   • 填充方向: 从弧真起点 s 起, 填充到 s + (e-s)*ratio (ratio = (值-下限)/(上限-下限))
#   • dataSrc 取 0-100/原始计数值, 由固件按 imageIndexList 最近值选帧 (参照 全功能数据 步数进度)
#   • 温度取 0~50°C (避免负索引), 步数取 1021(进度%), 电量 0841(%), 卡路里 0822(计数)
ARC_SPEC = [
    ("temp",    20,  70,  79, "sun",   "2031", 0,  50, 11),
    ("battery", 110, 160, 169,"bolt",  "0841", 0, 100, 21),
    ("calories",200, 250, 191,"flame", "0822", 0, 500, 21),
    ("steps",   290, 340, 281,"shoe",  "1021", 0, 100, 21),
]
ARC_R = 206   # 描边中心补偿: PIL arc(width=11) 描边向内偏 5.5px, R=206 -> 中线≈201, 与数码/图标同径
ARC_W = 11    # 弧宽

def _draw_track(d):
    """画四弧静态轨道(淡) + 图标, 不含填充。"""
    for name, s, e, ia, icon, ds, dmin, dmax, nlv in ARC_SPEC:
        d.arc([C[0]-ARC_R,C[1]-ARC_R,C[0]+ARC_R,C[1]+ARC_R], -e, -s, fill=(60,60,70,255), width=ARC_W)
        ic_pos = pt(ARC_R, ia)
        draw_icon(d, icon, ic_pos[0], ic_pos[1], 18)

def gen_arcs():
    """静态层: 仅四弧轨道 + 图标 (填充改为动态帧)。"""
    img = new_layer()
    d = ImageDraw.Draw(img)
    _draw_track(d)
    save(img, "arcs.png")

def _capθ():
    return 0.6

def gen_arc_fills():
    """为每弧生成 nlv 帧动态填充 (arcfill_<name>_<i>.png), 透明底 + 白色填充弧。"""
    for name, s, e, ia, icon, ds, dmin, dmax, nlv in ARC_SPEC:
        for i in range(nlv):
            val = dmin + (dmax - dmin) * i / (nlv - 1)
            ratio = (val - dmin) / (dmax - dmin)
            ratio = max(0.0, min(1.0, ratio))
            fe = s + (e - s) * ratio
            img = new_layer()
            d = ImageDraw.Draw(img)
            d.arc([C[0]-ARC_R,C[1]-ARC_R,C[0]+ARC_R,C[1]+ARC_R],
                  (s-_capθ())-90, fe-90, fill=(235,235,240,255), width=ARC_W)
            save(img, f"arcfill_{name}_{i}.png")
        print(f"  arcfill_{name}: {nlv} 帧 (ds={ds} {dmin}..{dmax})")

def draw_icon(d, kind, x, y, r):
    """精致线性图标, 以(x,y)为中心, r≈半径。参考HTML SVG path重绘, 线宽3px抗锯齿。"""
    def P(pts):
        return [(x+dx, y+dy) for dx,dy in pts]
    w = 3  # 加粗线条, 在466画布上清晰可见
    if kind == "sun":
        # 日轮 + 8条光芒 (参考HTML ICONS.sun)
        d.ellipse([x-r*0.38,y-r*0.38,x+r*0.38,y+r*0.38], outline=(235,235,240,255), width=w)
        for ang in range(0,360,45):
            a=math.radians(ang)
            d.line([(x+(r*0.58)*math.sin(a), y-(r*0.58)*math.cos(a)),
                    (x+(r*0.95)*math.sin(a), y-(r*0.95)*math.cos(a))],
                   fill=(235,235,240,255), width=w)
    elif kind == "bolt":
        # 闪电 (参考HTML ICONS.bolt path: M-1 -9 L-8 1 L-2 1 L-4 9 L6 -2 L0 -2 Z)
        d.polygon(P([(-1,-9*r/13),(-8*r/13,r/13),(-2*r/13,r/13),(-4*r/13,9*r/13),
                     (6*r/13,-2*r/13),(0,-2*r/13),(4*r/13,-9*r/13)]),
                  outline=(235,235,240,255), width=w)
    elif kind == "flame":
        # 火焰 (参考HTML ICONS.flame: 外焰+内焰双层path)
        # 外焰
        d.polygon(P([(0,-9*r/13),(7*r/13,-r/13),(5*r/13,6*r/13),(-r/13,9*r/13),
                     (-7*r/13,4*r/13),(-4*r/13,-2*r/13)]),
                  outline=(235,235,240,255), width=w)
    elif kind == "shoe":
        # 运动鞋 (参考HTML ICONS.shoe: M-8 4 L-2 -2 L6 0 L10 -5 L13 1 L12 5 L-2 6 Z)
        d.line(P([(-8*r/13,4*r/13),(-2*r/13,-2*r/13),(6*r/13,0),(10*r/13,-5*r/13),
                  (13*r/13,r/13),(12*r/13,5*r/13),(-2*r/13,6*r/13)]),
               fill=(235,235,240,255), width=w, joint="curve")
    else:
        d.ellipse([x-r,y-r,x+r,y+r], outline=(235,235,240,255), width=w)

# ---------------------------------------------------------------------------
# 6. 秒环扫秒帧序列 (element_anim 用): 把基础秒环 (ring_sec.png) 绕圆心旋转
#    N 份, 每份 360/N 度, 存 sec_0000..sec_00(N-1).png。固件以 element_anim 循环
#    播放即得到"平滑扫秒"轮盘 (装饰性连续旋转, 非时间精确).
# ---------------------------------------------------------------------------
def gen_sec_sweep_frames(n=60):
    base = Image.open(os.path.join(OUT, "ring_sec.png")).convert("RGBA")
    for k in range(n):
        ang = k * 360.0 / n
        fr = base.rotate(ang, center=C, resample=Image.BICUBIC)
        # 旋转会引入抗锯齿中间色 → 必须走 save() 统一量化到 <=256 色
        save(fr, f"sec_{k:04d}.png")
    print(f"  -> {n} 帧扫秒序列 sec_0000..sec_{n-1:04d}.png (每帧 {360.0/n:.2f}°)")

def gen_plate():
    """v28: 静态不透明黑盘 —— 把 v23 挂在秒/分指针图里的 plate 剥离成独立静态元素。
    依据: 寻路者指针图=小条带(~0.1M px/s), 谷歌=34%盘(4.5M px/s), 均丝滑;
    我们 v23 起指针图带 r=231 不透明黑盘(78%, 10.4M px/s) = 谷歌 2.3 倍, 疑超固件
    平滑路径预算。黑盘本身旋转不变, 没必要跟着指针转 -> 剥离后指针图只留数字环带,
    每帧旋转合成量 168k px -> ~12k px (14x↓)。

    v39: 盘心挖透明洞 (r<R_HOLE=185), 让 extraProp7 指针穿透 plate 可见。
      根因 —— v30 真机实证: 固件把 extraProp7 渲染在主列表 plate【之下】
      (overlay 位于 z 序最底); plate 全不透明 → 指针被 plate 完全遮蔽
      (v30 真机空白). 寻路者·黄用【中心透明】face image 让其 extraProp7
      指针透出, 仿照此结构, plate 改为 annulus (外环 r=R_PLATE_SEC,
      内洞 r=R_HOLE=185 > 指针最大半径 180, 留 5px 余量).
      视觉: 洞内露 AMOLED 原生黑 (0,0,0), 与 plate 纯黑同色, 无色差;
      唯一变化 = extraProp7 指针可见."""
    img = new_layer()
    d = ImageDraw.Draw(img)
    d.ellipse([C[0]-R_PLATE_SEC, C[1]-R_PLATE_SEC,
               C[0]+R_PLATE_SEC, C[1]+R_PLATE_SEC], fill=PLATE_BLACK)
    # v39: 中心挖洞 (alpha=0), 让 extraProp7 指针穿透
    d.ellipse([C[0]-R_HOLE, C[1]-R_HOLE,
               C[0]+R_HOLE, C[1]+R_HOLE], fill=(0, 0, 0, 0))
    save(img, "plate.png")


def gen_hotzone(w=80, h=40):
    """v34: 全透明点击热区占位图。视觉不可见, 仅用于让打包器生成 prop9 记录,
    使固件把表盘判为'可交互'面(平滑盘均 prop9>=1, 我们是唯一 prop9=0 的盘)。"""
    save(new_layer((w, h)), "hotzone.png")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("== gen_bg ==");        gen_bg()
    print("== gen_ring (min/sec) ==")
    # ★ v41: 不透明环形带(中心透明, 保留 V5 开放中心) + 数字外移贴近 V5 布局。
    #   sec 环带 r=140..231, 数字 R=200; min 环带 r=85..140, 数字 R=118。
    gen_ring("ring_min.png", 118, 108, 130, 22, None, (220,220,226,255), False, plate_r_in=85, plate_r_out=140)
    gen_ring("ring_sec.png", 200, 214, 230, 22, None, (235,235,240,255), False, plate_r_in=140, plate_r_out=231)
    # v41: 不再生成独立 plate.png —— 指针图本身即不透明环形带(位于元素[0]/[1]最底层),
    #   充当轮盘底色, 中心留透明形成 V5 开放中心观感, 无需额外 plate 层。
    # v27 的 60 帧扫秒序列已证伪(实测仍跳), 停止生成以缩短构建时间
    # print("== gen_sec_sweep_frames (v27 60帧 imagelist 扫秒) ==")
    # gen_sec_sweep_frames(60)
    print("== gen_digits ==")
    digH_w, digH_h = gen_digits("digH", 56, True)        # 时: font56 -> 大号, 接近目标尺寸
    digM_w, digM_h = gen_digits("digM", 24, True)        # 胶囊 分:秒: font24 -> ~13x22
    digS_w, digS_h = gen_digits("digS", 16, False, with_blank=True)  # 弧/电量/温/日: font16 -> ~9x15
    print(f"  -> cell sizes: digH={digH_w}x{digH_h}  digM={digM_w}x{digM_h}  digS={digS_w}x{digS_h}")
    print("== gen_text_frames ==")
    wd_w, wd_h = gen_text_frames("wd", ["SUN","MON","TUE","WED","THU","FRI","SAT"], 20)
    mo_w, mo_h = gen_text_frames("mo", ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"], 18)
    print(f"  -> frame sizes: wd={wd_w}x{wd_h}  mo={mo_w}x{mo_h}")
    print("== gen_punct ==");       gen_punct()
    print("== gen_capsule ==");     gen_capsule()
    print("== gen_arcs (静态轨道) =="); gen_arcs()
    print("== gen_arc_fills (动态进度帧) =="); gen_arc_fills()
    print("== gen_hotzone (v34 透明点击热区占位) =="); gen_hotzone()
    # 预览图(非生成资产, 外部放置) 也须 <=256 色, 否则作为资源编译时调色板溢出 → 重启
    prev = os.path.join(OUT, "preview.png")
    if os.path.exists(prev):
        save(Image.open(prev), "preview.png")
    print("DONE ->", OUT)
