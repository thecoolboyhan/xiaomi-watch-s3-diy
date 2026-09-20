#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v65 builder（在 v64 基础上）:
  1. 卡路里对齐寻路者·黄右上角槽位（用户指认 = 卡路里）:
     弧   0822 -> 1023 (百分比进度通道, 表 [0,10..100], prop7Raw 逐字节取自寻路者)
     数字 082203 -> 082305 (sc=5, spacing=252, prop7Raw 取自寻路者)
  2. AOD: 两个面都加 ep7 隐形伴侣 idx6/7 (ds=1012/1812, v41 记录的谷歌原样 raw),
     指针 prop7Index 显式 12/13 (= 伴侣 idx + 6, v41 铁律) —— 对齐谷歌 AOD 结构。
  3. 日期 3012/3812 保持不动（全功能/寻路者同款源，实为农历，见 AGENTS.md §3.5）。
"""
import json

WS3 = "/Users/admin/ai/watch/project/ws3"
wf = json.load(open(f"{WS3}/wfDef.json"))

# ---- 1. 卡路里槽位（按 v64 时的 dataSrc 定位：数字 082203 / 弧 0822）----
CAL_NUM_RAW = "082305100000E8030300000300FCDC0000000000"   # 寻路者 [11] verbatim
CAL_ARC_RAW = ("1023002000000000020000030002080000000000"
               "0A000000140000001E00000028000000320000003C000000"
               "46000000500000005A00000064000000")          # 寻路者 [10] verbatim
PCT = list(range(0, 101, 10))

for e in wf["elementsNormal"]:
    if e.get("dataSrc") == "082203" and e.get("type") == "widge_dignum":
        e["dataSrc"] = "082305"
        e["showCount"] = 5
        e["spacing"] = 252
        e["prop7Raw"] = CAL_NUM_RAW
        e["prop7Length"] = len(CAL_NUM_RAW) // 2
        print("数字: 082203 -> 082305 (sc=5, spacing=252)")
    if e.get("dataSrc") == "0822" and e.get("type") == "widge_imagelist":
        e["dataSrc"] = "1023"
        e["imageIndexList"] = PCT
        e["prop7Raw"] = CAL_ARC_RAW
        e["prop7Length"] = len(CAL_ARC_RAW) // 2
        print("弧:   0822 -> 1023 (表 [0,10..100])")

# ---- 2. ep7 伴侣（两个面）+ 指针 prop7Index 12/13 ----
COMP = [{"idx": 6, "raw": "101202150000E803040000030000000000000000"},
        {"idx": 7, "raw": "181202150000E803040000030000000000000000"}]
wf["extraProp7Normal"] = COMP
wf["extraProp7Aod"] = COMP
for e in wf["elementsNormal"]:
    if e.get("type") == "widge_pointer":
        e["prop7Index"] = 12 if e.get("dataSrc") == "1811" else 13
for e in wf["elementsAod"]:
    if e.get("type") == "widge_pointer":
        e["prop7Index"] = 12 if e.get("dataSrc") == "1811" else 13
print("ep7 伴侣 idx6/7 已加到两个面; 指针 prop7Index=12/13")

wf["name"] = "RouletteS3_v65"
json.dump(wf, open(f"{WS3}/wfDef.json", "w"), ensure_ascii=False, indent=2)
print("wfDef.json 已更新 -> v65")
