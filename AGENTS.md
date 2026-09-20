# AGENTS.md — 小米 Watch S3 轮盘表盘项目（AI 接手指南）

> 任何 AI 接手本项目的第一步：**通读本文件**。它凝结了 2026-09-03 ~ 09-07 多轮真机调试的全部血泪结论。
> 配套技能：`~/.workbuddy/skills/xiaomi-watch-s3-smooth-sweep/SKILL.md`（内容与本文件互为补充）。

## 0. 一句话背景

小米 Watch S3 (M2313W1) 的「轮盘」自定义表盘，从 Mi-Create 导出的 bin 起步，用自研 Java 打包器
`Mi8WfBinTool` 重打包 PNG 素材，实现**平滑扫秒**（非 1Hz 跳秒）+ 四角圆角进度弧 + AOD。
**真机反馈是唯一验收标准**——模型不能读图，一切改动都要装机验证。

## 1. 目录结构

> **自包含承诺（2026-09-07 净室验证）**：本项目不依赖任何 /tmp 或旧 WorkBuddy 工作区路径。
> 只用本项目内文件：编译打包器 → pack → patch_header → 产出与已交付 v64.bin **逐字节一致**。
> `project/*.py` 里的 prop7Raw 标准值来源 = `reference/RouletteS3_v58.bin`（扫秒✓真机验证）与 v60，
> 已随项目保存，extract_idx() 可随时重新提取。

```
ai/watch/
├── AGENTS.md            ← 本文件
├── README.md
├── tools/
│   ├── Mi8WfBinTool/    ← 打包器源码 + 编译好的 .class + build.sh（唯一真源）
│   └── scripts/         ← patch_header.py / gen_assets_html.py / gen_assets_v3.py / assemble_html.py
├── project/
│   ├── ws3/             ← 当前表盘工程源：wfDef.json（已含全部 prop7Raw）+ images/ + images_aod/
│   ├── build_v64.py     ← v64 构建：prop7Raw 注入 + 弧帧小图块重绘（含 extract_idx 提取器）
│   ├── regen_arcs.py    ← 重绘 4 弧×11 帧填充（圆角帽）
│   ├── regen_track.py   ← 重绘 image_0002 静态轨道（圆角帽）
│   └── flip_rings.py    ← 轮盘数字排布翻转工具（v62 用过，v63 已回退）
├── deliverables/        ← v60(基线) v61 v62 v63 v64 的 bin + 预览图
└── reference/           ← 官方对照盘（谷歌轮盘·橙/寻路者·黄）+ v58/v59/v60 自产基准盘
```

**出下一版的固定流程**：改 `project/ws3`（wfDef 或 images）→
`java -cp tools/Mi8WfBinTool Mi8WfBinTool pack project/ws3 out.bin ws3` →
`python3 tools/scripts/patch_header.py out.bin 1 4 1` → 反提取验证 prop7 通道（见 §8）→
存入 `deliverables/` 并保留 wfDef 中的 prop7Raw（**绝不要用 unpack 出来的 wfDef 覆盖项目里的**）。

## 2. 环境与命令

| 项 | 值 |
|---|---|
| 屏幕 | 466×466 AMOLED，**逻辑画布 464×464**，圆心 **C=(232,232)** |
| Python | `/Users/admin/.workbuddy/binaries/python/envs/watchface/bin/python3`（**无 numpy**，纯 PIL） |
| Java | 系统 `javac`/`java`（OpenJDK 25） |
| 编译打包器 | `bash tools/Mi8WfBinTool/build.sh` |
| 打包 | `java -cp tools/Mi8WfBinTool Mi8WfBinTool pack project/ws3 out.bin ws3` |
| 解包 | `java -cp tools/Mi8WfBinTool Mi8WfBinTool unpack out.bin /tmp/chk ws3` |
| 表头补丁 | `python3 tools/scripts/patch_header.py out.bin 1 4 1`（smooth=1, styleCount=4, flag16=1） |

**构建顺序（必须）**：改素材/改 wfDef → `pack` → `patch_header 1 4 1` → 解包回读验证 → 交付。
**pack 之后必须 patch_header**：packer 不写 `byte[6]`（分数秒开关）和 `0x16`。

## 3. 二进制格式关键知识（实测，勿凭记忆猜）

### 3.1 顶层表头（0xA8 字节）
| 偏移 | 含义 | AOD 双面盘正确值 |
|---|---|---|
| 0x00-03 | magic | `5A A5 34 12` |
| **0x06** | **分数秒/现代渲染开关（扫秒总开关）** | **1**（packer 不写，靠 patch_header） |
| 0x10 | AOD 标志 | u32 = 0x800 |
| **0x16** | 保留标志（官方=1） | **1**（patch_header 写） |
| 0x1C | faceCount | 2（有 AOD）/ 1 |
| 0x1E | styleCount | 4（packer 现已按 faceStyleCount 写，patch_header 再兜底） |
| 0x20 | previewOffset | u32，packer 自动算 |

### 3.2 face record（每面 0x58 字节，主面 @0xA8、AOD 面 @0x100）★AOD 生死线
- **u32@+0：官方 AOD 双面盘两个面都是 `0x80000000`；1-face 盘是 0。**
  打包器 `buildFaceHeader` 原本从不写 +0x00 → **AOD 不显示的真正根因**（v60~v62 都死在这）。
  现已加 `aodDial` 参数：AOD 盘两面都置位；**1-face 盘必须保持 0，不要无条件写**。
- u32@+4 = previewOffset（AOD 面 = 0），u32@+8 = 元素数，0x08 起是分节表。
- 官方 `谷歌轮盘·橙` 用 **named face** 布局（face record 0x58 + name 0x48 交错），
  定位官方 face record 时：主面 @0xA8，AOD 面 @0x148。
- 顶层表头逐字节对齐官方 ≠ AOD 正常，**必须查 face record**。

### 3.3 平滑扫秒硬清单（缺一即跳秒）★ 2026-09-07 v64 最终定论
1. `byte[6]=1`（patch_header 写）。
2. 指针元素：`[0]` ds=`1811` interval=`16`、`[1]` ds=`1011` interval=`60000`，
   `imageRotateX/Y=232`、`maxValue=60`、`allAngle=3600`、`pointerUnknow25/26=0`。
3. **★真正的开关 = 每个 dignum/imagelist 元素的 prop7Raw 通道字节**（v54/v50 真机实证，v64 取证定论）：
   - **dignum：b6-7 = 刷新毫秒（LE u16）**。时/分/温度/卡/步/电量 = `E8 03`(1000ms)，
     胶囊秒 = `10 00`(16ms)。**b6-7=0000 = 非法通道 → 整 face 动画被禁用 → 秒针 1Hz 跳秒**。
   - **imagelist：带 imageIndexList 时 b12-13 必须 = `0002`**，否则弧/列表通道失效（温度/步数无进度条的根因）。
     不带 index 表的（星期 2012）b12-13=0000 即可。
   - b14-15 = 旋转角×0.1°（0000=正，C9FF 会倾斜）；b16+ = imageIndexList 值表（4B/项）。
   - **⚠️ 最大的坑：unpack 会剥掉 prop7Raw！** 从解包 wfDef 直接重打包 = 全部通道非法 = 跳秒。
     v61~v63 就是这么坏的。raw 的唯一可靠来源：**从已知正常 bin 的 def 表提取**
     （type==7 的 16B def：idx@0 / off@8 / len@12 → 该偏移处即 prop7 字节）。
     工具：`project/build_v64.py` 的 `extract_idx()`。标准 raw 已固化在该脚本 `RAWS` 表。
   - 指针**不要给 prop7Raw**（打包器 32B 模板 v50 已验平滑）。
4. **验收（v64 起必做）**：从成品 bin 反提取每个 widget 的 prop7，核对
   dignum b6-7 非零、带表的 imagelist b12-13=0002、指针签名 `18 11 00 30`/`10 11 00 30` 各 1 次。
5. **纹理预算 ≲4MB/face**：v61 曾把 44 张弧帧做成 464×464 全画布 → 体积/显存爆掉。
   弧帧必须是**裁剪小图块**（~141×143）+ 元素 x/y=图块左上角（v58/v60 即如此）。
6. `buildFaceHeader` 的 face record u32@+0=0x80000000（AOD 双面盘必需，见 3.2）。

### 3.4 合法 dataSrc 表（★官方权威表 = Mi-Create sources.json）
**`reference/micreate_sources_official.json`**（来自 github.com/neizod/Mi-Create `src/data/sources.json`，
键 `xiaomi_watch_s3`，76 条 id_fprj）——这是最终权威，与真机行为完全吻合。关键条目：

| id | 语义 | id | 语义 |
|---|---|---|---|
| 0811/1011/1811 | 时/分/秒（+Low/High 拆位） | 0812 | 公历年 |
| **1012** | **公历月** ← 日期行用这个 | 1112/1212 | 公历月 个位/十位 |
| **1812** | **公历日** ← 日期行用这个 | 1912/1A12 | 公历日 个位/十位 |
| 2012 | 星期 | 2812/3012/3812 | **农历**年/月/日（别用于公历！） |
| 0813 | AM/PM | 3031 | 天气类型图标(25帧) / 2031=温度℃ |
| 0841 | 电量% / 1041=充电状态 | 0821/1021 | 步数 / 步数% |
| 0822 | **心率**（不是卡路里！v58"78"即心率） | 0823/1023 | **活动卡路里 / 卡路里%** |
| 0824/1024 | 站立次数 / % | 0825 | 血氧 |
| 0826 | 压力 | 0828/1028/1828 | 睡眠时长/评分/目标进度 |
| 1832/2032 | 今日最高/最低温 | 7831 | 紫外线指数 |

尾字节=位数/格式（如 081102=时2位、082305=卡路里5位）。变体 raw 模板见 `project/build_v64.py` RAWS 表。
`081102`时(2位) · `101102`胶囊分 · `181102`胶囊秒 · `203103`温度(3位) · `082203`卡路里(3位)
`082105`步数(5位,spacing=254 紧排) · `084103`电量%(3位) · `0841`电量等级(11帧)
`3012`月(12帧) · `3812`日(31帧) · `2012`星期(7帧) · `2031`温度弧 · `0821`步数弧 · `0822`卡路里弧 · `0841`电量弧
**非法（已踩坑）**：`283103`（v60 卡路里错源）、`381202`/`084102`（旧打包器 showCount 污染产物）。

## 4. 打包器已修 bug（改 packer 前先读，别回退）

| bug | 位置 | 修法 |
|---|---|---|
| showCount 覆盖 dataSrc 第三字节 | `writeProp7` ~L1888（注释 `FIX: do NOT overwrite...`） | 删 `b[p+2]=showCount` |
| 表头 styleCount 硬编码 6 | `writeHeader` AOD 分支 | `b[0x1E]=(byte)styleCount` |
| **AOD face record 缺 0x80000000** | `buildFaceHeader`（原从不写 +0x00） | 加 `aodDial` 参数置位（仅 AOD 盘） |
| **spacing 覆写 imagelist b13** | `writeProp7` ~L1891 | v64：b13=spacing 仅对 dignum 写（imagelist 的 b13 属于 0002 通道标志） |

## 3.5 dataSrc 语义补充（官方 4 盘取证 + 真机反馈）

- **`3012`/`3812` = 农历月/日**（Mi-Create 官方表 + 帧破译双重实锤；寻路者月份帧是中文"七月/九月"）。
  **公历月/日 = `1012`/`1812`**（v67 起日期行已换用）。我们的月帧[1..12]/日帧[1..31] 恰好匹配公历。
- **卡路里（用户指认寻路者右上角槽位）**：弧 = **`1023`**（百分比通道，表 [0,10..100]），数字 = **`082305`**（sc=5）。
  v65 真机：**卡路里数据 ✓ 正确**（1023/082305 定论）。但注意寻路者 raw 两个坑：
  **b14-15=DC00 = 22° 倾斜**（它的槽位在斜角上，水平槽位必须改 0000，否则数字歪 22°）；
  **b13=FC = spacing -4**（我们的字会挤在一起，改 spacing=0）。
  修正后 raw：`082305100000E803030000030000000000000000`（b6-7=E803 ✓）。
- `082203` ≠ 卡路里（用户 v65 否决）；`283103` 也不是（v60 真机否）。
- **温度 ° 位置**：203103 dignum showZero=false → 2 位显示（如"29"），° 元素要跟着左移
  （v66: x 296→284），否则中间空出 ~1 字宽。
- **★轮盘数字排列（v66 定论，来自真机照片逐数字核对）**：
  - v60 系 ring 图实际是 **A(v)=6v（00 在 12 点、顺时针递增）**——与 gen_assets_html 的
    `a_img=90-6n` 不符！build_v60.py 的 ring 生成器用了另一套角度公式（半径一致、角度公式不同）。
  - **正确排列 = A(v)=90-6v（00 在 3 点、逆时针递增）**：顺时针旋转 +6°/秒时，
    数字 v 出现在 90-6v+6s ≡ 90 → v=s，红框恰好显示当前值（用户要求"从小到大逆时针排列"）。
  - 变换：每根辐条绕表心刚性顺时针转 delta(v)=90-12v 度（PIL rotate(-delta)），
    楔形掩膜取目标角 90-6v。刚性旋转保持字形正立。工具：`project/build_v66.py transform_ring()`。
- **日期 = 农历（v66 帧破译铁证）**：我们月份帧 frame 8 = "SEP"、frame 6 = "JUL"（ASCII 解码确认标签正确），
  但 9/7 固件给 3012 的值 = 7 → 显示 JUL。**寻路者月份帧是中文"七月/九月"**（同样值驱动）
  → 五个参考盘全部显示农历，这套固件无公历月/日 dataSrc。
- `082203` ≠ 卡路里（用户 v65 否决）；`283103` 也不是（v60 真机否）。
- `3031`（25 帧 + index 表）三盘都有，语义未破译（疑似月相/某 25 级量），非必需。
- **ep7 隐形伴侣**：谷歌两个面都挂 idx6/7（ds=1012/1812，raw=`101202150000E803040000030000000000000000`/
  `1812...`），指针 prop7Index = 伴侣 idx+6（12/13）。v64 无伴侣扫秒已正常（说明非扫秒必需），
  v65 起补上 = 对齐谷歌结构，作为 AOD 修复尝试。wfDef 键：`extraProp7Normal`/`extraProp7Aod`，
  条目格式 `{"idx":6,"raw":"..."}`；assignWidgetIndices 会自动跳过 6/7，不会冲突。

## 5. 素材绘制坑（PIL）

1. **`d.arc(bbox,…,width=W)` 从 bbox 向【内】描边**：bbox 半径=色带外边缘，**中线 = R − W/2**。
   画圆角端帽时帽圆心必须放 `R − W/2`，放 R 会在端部鼓包（v61 实测端部 16.4px vs 中段 11.4px）。
2. **限色 ≤256**：固件解码器要求；白系用预乘白化、彩系 FASTOCTREE（见 `gen_assets_*.py` 的 `save()`）。
   超限 → 装机即重启。
3. 画布 464、圆心 (232,232)；web 角度（0=12点顺时针）转 PIL 要 **−90**；PIL `rotate(-x)`=顺时针 x。
4. **打包器不裁剪图片**：解包出的尺寸就是打包时的真实尺寸，改图尺寸必须同步改 wfDef 的 x/y。

## 6. 转向与数字排布的耦合（改转向前必读）

数字 n 在像角 A(n)，固件每单位转 X 度，3 点红框显示当前值需满足 `A(n) + value·X ≡ 90`。
- **顺时针(+6°/单位) + A(n)=90−6n → value=n ✅**（v60/v63 现状，官方同款）
- 逆时针(−6°/单位) 必须改 A(n)=90+6n，否则显示 60−n（倒走）
- 逆时针需 `allAngle=−3600`，但**官方盘无负 sweep 先例**，且 `BU.i16` 实为无符号
  （−3600 解包显示 61936），固件是否认负数**未证实**——v62 试过被用户放弃，改回顺时针。
- 翻转排布的实现见 `project/flip_rings.py`（逐辐条绕表心刚性旋转 12n°，保持字形正立不被镜像）。

## 7. 轮盘素材的真实来源

**`tools/scripts/gen_assets_html.py` 才是 v60 轮盘图的真源**：
`ring_min Rnum=99/RtIn=119/RtOut=128`、`ring_sec Rnum=148/RtIn=168/RtOut=177`（与实盘半径逐一对上）。
`gen_assets_v3.py` 的 200/214/230 与实盘**对不上**，别拿它当依据。

## 8. 验证流程（每次出包必做）

```bash
java -cp tools/Mi8WfBinTool Mi8WfBinTool unpack out.bin /tmp/chk ws3
```
检查清单：`byte[6]=1`、`0x10=0x800`、`0x16=1`、`faceCount=2`、`styleCount=4`、
两个 face record u32@+0=`0x80000000`、prop7 签名各 1 次、
`082203` 在且 `283103` 无、4 弧元素 x/y=(0,0) 且各 11 帧、
解包回读 dataSrc/x/y/allAngle 与预期一致、体积 < 4MB。
像素级几何校验思路：用亮度/alpha 阈值取点 → 算 web 角与半径 → 对照预期象限/弧段。

## 9. 对比官方盘（排错金标准）

`reference/` 两个官方盘 AOD、扫秒、走时全部正常。排错套路：
**同类字段逐字节 diff**（顶层表头 → face record → 元素定义），
diff 到差异字节再回打包器找"谁没写/写错"。AOD 根因就是这么找到的。

## 10. 当前状态（v74）与待办

- **v73 真机照片：对角线消失 ✓、时长摆正 ✓、进度条比例 ✓** — 三修全部生效。
- **v74（2026-09-07）**：
  ① 睡眠时长移到竖条正下方 (173,228) + **align=2 走 JSON 字段**（改 raw b3 会被打包器按
    JSON showZero/align 重算覆盖 — 改对齐必须改 JSON 字段级）。
  ② 四角数据数字沿各自极角外移：temp/°/steps +8px, battery/calories +5px（电池 align=2
    中心锚点, "100" 3 位数不裁边）。
  ③ 天气图标 36→42px, r=216→214 @(421,170)。
  859,771B。
- 新坑：° (image_0006) 是 element+image 字段（无 imageList），radial 平移脚本要兼容两种键。
- **待真机验收**：① 四角数字外移观感 ② 时长位置 ③ 天气图标大小 ④ 4 热区跳转
  （卡路里→010C6F03 仍待验证）⑤ 温度需 Mi Fitness 同步天气。
- 迭代规则：**一版一验证**，出 bin+PNG 预览，等真机反馈再动下一版。

## 11. 复用边界（新表盘能不能用本工程生成）

**通用可复用的**：`Mi8WfBinTool` 打包器、二进制格式全部知识（表头/face record/prop7Raw 通道/dataSrc 表）、
已修 bug、验证流程（§8）。任何小米 Watch S3 表盘的 pack/unpack 都能用这套工具链。

**不能直接做的**：本工程**没有「设计图 → 表盘」全自动生成管线**。给一张新表盘图片，仍需：
拆解元素 → 在 wfDef.json 手写布局/数据源/角度/字体 → 切分绘制素材 PNG → pack。
这一步目前是手工；`regen_arcs.py`/`regen_track.py`/`flip_rings.py` 等**仅轮盘专用**，新风格一般要新写绘制脚本。

**分场景**：
- **同款轮盘换皮肤/配色/替换某张素材图** → 直接改 `project/ws3` 重打包（极低成本）。
- **Mi-Create 导出的新 bin 想改细节** → unpack 改 wfDef 再 pack（警惕：unpack 会剥 prop7Raw，
  重打包前务必用项目里的 wfDef 兜底 prop7Raw）。
- **全新风格表盘（数字/指针/拟物）** → 复用工具链+格式知识，但 wfDef 骨架从头设计，
  相当于一次新项目；因有现成逆向血泪结论，显著快于从零。
