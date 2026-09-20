#!/usr/bin/env bash
# 编译 Mi8WfBinTool 打包器
# 用法: ./build.sh
# 产物: Mi8WfBinTool.class（同目录，用 java -cp . Mi8WfBinTool ... 运行）
set -e
cd "$(dirname "$0")"
javac Mi8WfBinTool.java
echo "OK -> $(pwd)/Mi8WfBinTool.class"
echo "用法:"
echo "  java -cp . Mi8WfBinTool pack   <workDir> <out.bin> ws3   # workDir 内需有 wfDef.json + images/ (+ images_aod/)"
echo "  java -cp . Mi8WfBinTool unpack <in.bin>  <outDir> ws3"
