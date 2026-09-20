#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_header.py — 打包后回补 S3 表盘 bin 表头

两处修正 (均来自与小米官方平滑盘「谷歌轮盘·橙」「寻路者·黄」的二进制逐字节对照):

1. byte[6] = 0x01   ← 关键! 这是 Mi-Create 写入的"现代渲染/分数秒"能力位。
   官方平滑盘: 表头 @4..7 = 00 00 01 00 (bit16 置位)
   本开源工具产出: 00 00 00 00 (该位为 0) -> 固件走老路径, 秒针按整数秒 1Hz 跳。
   置 1 后固件开启分数秒 + 高频重绘, 与谷歌盘字节级一致的指针配置即可平滑扫秒。

2. 0x1E (u16 styleCount) := 1   (我们只有 1 个样式; 旧版曾误设为 0。
   注: 解包器读 styleCount=max(1,..) 会钳到 1, 故 0/1 功能等价, 这里写正确值 1)

保留项:
   0x16 (u8) := 1   对齐小米官方文件 (两个官方盘都是 1)
   0x1C (u8 faceCount) 不动 (本盘 = 1)

用法: python3 patch_header.py RouletteS3_vXX.bin
"""
import struct, sys, shutil, os

OFF_SMOOTH = 0x06          # byte[6] 现代渲染/分数秒能力位
OFF_FACECOUNT = 0x1C
OFF_STYLECOUNT = 0x1E
OFF_FLAG16 = 0x16


def patch(path, smooth=1, style_count=1, flag16=1, backup=True):
    data = bytearray(open(path, "rb").read())
    if data[0:4] != b"\x5a\xa5\x34\x12":
        raise SystemExit(f"[patch_header] {path} 不是 S3 表盘 bin (magic 不符)")

    face_count = struct.unpack_from("<H", data, OFF_FACECOUNT)[0]
    old_style = struct.unpack_from("<H", data, OFF_STYLECOUNT)[0]
    old_flag = data[OFF_FLAG16]
    old_smooth = data[OFF_SMOOTH]

    if backup:
        shutil.copy2(path, path + ".prepatch")

    data[OFF_SMOOTH] = smooth
    struct.pack_into("<H", data, OFF_STYLECOUNT, style_count)
    data[OFF_FLAG16] = flag16
    open(path, "wb").write(bytes(data))

    print(f"[patch_header] {os.path.basename(path)}")
    print(f"    smooth     0x06 = {old_smooth} -> {smooth}   ← 开启分数秒/平滑渲染 (关键)")
    print(f"    styleCount 0x1E = {old_style} -> {style_count}   (本盘 1 个样式)")
    print(f"    flag       0x16 = {old_flag} -> {flag16}   (对齐官方)")
    print(f"    faceCount  0x1C = {face_count}  (未改)")
    if face_count != 1:
        print(f"    ⚠ faceCount={face_count} != 1, 请检查 wfDef.json")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: patch_header.py <bin> [smooth] [styleCount] [flag16]")
    sm = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    sc = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    f16 = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    patch(sys.argv[1], sm, sc, f16)
