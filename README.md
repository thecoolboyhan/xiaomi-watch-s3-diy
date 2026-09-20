# Custom Watchfaces for Xiaomi Watch S3 (RouletteS3 / MinimalS3 / daynight)

English | [简体中文](README.zh-CN.md)

Reverse-engineering notes and a homegrown packaging toolchain for the Xiaomi Watch S3 (M2313W1)
watchface format (`ws3`), used to build custom dials with **smooth sweep seconds, an AOD
(always-on display) face, and rounded corner progress arcs**.

![Previews](docs/preview_banner.png)

## What is this

- Target device: Xiaomi Watch S3 (M2313W1), 466×466 AMOLED, logical canvas 464×464, center (232,232)
- Three finished dials:
  - **RouletteS3**: Google Pixel Watch-style roulette dial — smooth sweep seconds + AOD + four rounded progress arcs (latest v74)
  - **MinimalS3**: digital dial with time-aware greetings, 1 Hz colon blink and a clean AOD transition (latest v5_fix)
  - **daynight**: auto day/night background switching (day/night-enhanced MinimalS3, shipped as MinimalS3_v5_fix)
- **Mi8WfBinTool**, our own Java packer: builds installable `.bin` files from `wfDef.json` + PNG assets

## Features

- Smooth sweep seconds (firmware sub-second interpolation, not 1 Hz ticking)
- AOD face (dual-face dial, black background / grayscale)
- Four rounded corner progress arcs (steps / calories / battery / temperature)
- Digital dial: 24 greeting frames + 1 Hz colon blink (compatible with auto day/night backgrounds)
- Tap hot-zones (weather / heart rate / steps / alarms, via prop9)

## Legal & copyright (read this first)

- This project contains **reverse-engineered** analysis of Xiaomi's official watchface binaries,
  for **personal study and research only**.
- The third-party official closed-source dials in `reference/` (`谷歌轮盘·橙.bin`, `寻路者·黄.bin`)
  are **excluded from this repository** by default (see `.gitignore`); they belong to their original owners.
- The packer builds on knowledge from the open-source project **ooflet/Mi-Create** (MIT).
- **Source code** is released under the [MIT License](LICENSE). **Compiled dial `.bin` files and their
  embedded artwork are personal creative works and are NOT covered by the MIT license** (all rights
  reserved). Xiaomi firmware / official dials and trademarks are out of scope.
- **Do not redistribute any of this commercially.** You assume all legal responsibility for your use.

## Requirements

- macOS / Linux
- JDK (verified with OpenJDK 25; `javac` / `java` on PATH)
- Python 3 + Pillow: `pip install -r requirements.txt` (pure PIL, no numpy)
- Asset-generation scripts use the macOS system font (`/System/Library/Fonts/SFNS.ttf`);
  on Linux, adjust the font path
- A real Xiaomi Watch S3 + the Mi Fitness app to install and verify — **on-device feedback is the
  only acceptance test**

## Repository layout

```
├── README.md            ← this file
├── README.zh-CN.md      ← Chinese readme
├── AGENTS.md            ← AI handover guide (toolchain, fixed bugs, checklists, status)
├── LICENSE              ← MIT (source code only; excludes bins/artwork)
├── docs/
│   └── FORMAT.md        ← ws3 binary format reference (header / face record / prop7Raw / dataSrc)
├── tools/
│   ├── Mi8WfBinTool/    ← packer source (Java) + build.sh  ← single source of truth (no .class in repo)
│   └── scripts/         ← patch_header.py / gen_assets_*.py / assemble_*.py
├── project/
│   ├── ws3/             ← roulette dial sources: wfDef.json (with all prop7Raw) + images/ + images_aod/
│   ├── build_v64.py …   ← per-version build / asset-redraw scripts
│   ├── minimal/         ← digital dial project
│   └── daynight_v5/     ← day/night dial project
├── deliverables/        ← latest .bin + previews (older versions on GitHub Releases)
└── reference/           ← official data-source JSON + our baseline dials (official bins gitignored)
```

## Quick start (rebuild RouletteS3 v74)

```bash
# 0. Python dependencies
pip install -r requirements.txt

# 1. Build the packer
cd tools/Mi8WfBinTool && bash build.sh && cd ../..

# 2. Pack the current dial sources
java -cp tools/Mi8WfBinTool Mi8WfBinTool pack project/ws3 out.bin ws3

# 3. Patch the header (smooth switch byte[6], flag 0x16, styleCount)
python3 tools/scripts/patch_header.py out.bin 1 4 1

# 4. Unpack and verify (see AGENTS.md §8 checklist)
java -cp tools/Mi8WfBinTool Mi8WfBinTool unpack out.bin /tmp/chk ws3

# 5. Install: copy out.bin to the watch → Mi Fitness → Watch faces → Custom → Import
```

> Notes: every script under `project/` resolves paths relative to the repository root
> (it walks up until it finds `tools/`), so clones work from anywhere.
> The digital/day-night `gen_assets.py` scripts expect a 2048×2048 design reference image
> (not in the repo); point the `WF_REF_IMAGE` environment variable at your local copy.

## Toolchain

| Tool | Purpose |
|---|---|
| `Mi8WfBinTool` (Java) | `pack <dir> <out> ws3` / `unpack <bin> <out> ws3`; the gold standard for byte-level diffing |
| `patch_header.py` | Restores `byte[6]=1` (smooth switch), `0x16=1`, `styleCount=4` |
| `gen_assets_*.py` | PIL-based asset generation (roulette rings / digit glyphs / arc frames) |
| `assemble_*.py` | wfDef.json assembly |
| `preview*.py` / `build*.py` | Static previews and one-shot pipelines |

## Key technical findings (read before touching the format)

Full format reference: **[docs/FORMAT.md](docs/FORMAT.md)**; debug history in **AGENTS.md**. TL;DR:

- **The real smooth-seconds recipe**: pointers occupy the first two main elements (`[0]/[1]`,
  ds=1811 seconds / 1011 minutes, prop7Index 12/13) **plus** a valid `prop7Raw` channel block on every
  dignum/imagelist element (b6–b7 = refresh milliseconds, must be non-zero).
- **AOD life-or-death line**: face record `u32@+0 = 0x80000000` (set on both faces of AOD dials only;
  keep 0 on single-face dials).
- **Legal dataSrc table**: see `reference/micreate_sources_official.json` (76 official entries from Mi-Create).
  Watch out: `381202`/`084102` are illegal sources produced by an old packer bug and disable face animation.
- **4 packer bugs fixed**: showCount overwriting dataSrc byte 3, hardcoded styleCount 6, missing AOD
  `0x80000000`, spacing overwriting imagelist b13. Read AGENTS.md §4 before changing packer source.

## Reuse boundaries

- **Re-skin / re-color / swap an asset of the same dial** → edit `project/ws3` and re-pack (very cheap).
- **Tweak a bin exported from Mi-Create** → `unpack`, edit `wfDef`, `pack` (careful: unpack strips prop7Raw —
  always backfill prop7Raw from the project's wfDef before re-packing).
- **A brand-new dial style** → reuse the toolchain + format knowledge, but design the wfDef skeleton
  from scratch (much faster than starting blind, thanks to the reverse-engineering notes).

## Verification checklist (every release)

- `byte[6]=1`, `0x10=0x800`, `0x16=1`, `faceCount=2`, `styleCount=4`
- Both face records: `u32@+0 = 0x80000000`
- Pointer signatures `18110030` / `10110030` exactly once each
- 4 arc elements at x/y=(0,0) with 11 frames each; size < 4 MB
- Pixel-level: threshold brightness/alpha sampling → compute web angle & radius → compare against expected quadrant

## Changelog

See [CHANGELOG.md](CHANGELOG.md); older `.bin` releases on [GitHub Releases](../../releases).

## Credits

- [ooflet/Mi-Create](https://github.com/ooflet/Mi-Create) (MIT — the reverse-engineering starting point and source of `jump_codes`)
- Xiaomi official dials (gitignored, used locally for byte-level comparison only)

## License

Source code: [MIT](LICENSE). Compiled dial `.bin` files and artwork are **not** covered (all rights reserved).
Xiaomi firmware / official dials / trademarks belong to their original owners. Evaluate compliance yourself
before any commercial redistribution.
