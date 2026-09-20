# Xiaomi Watch S3 Watchface Format (`ws3`) — Reverse-Engineering Notes

> All findings below were obtained by **byte-level diffing** of official watchface binaries
> against real-device behaviour on a Xiaomi Watch S3 (M2313W1) between 2026-09-03 and 2026-09-07.
> Every claim was verified on the physical watch — do not trust memory or guesswork over this document.
>
> 中文版说明散见于 [AGENTS.md](../AGENTS.md)；本文是面向所有开发者的格式参考。

## 0. Device & canvas

| Item | Value |
|---|---|
| Panel | 466×466 AMOLED |
| **Logical canvas** | **464×464** (images must fit this) |
| Center | (232, 232) |
| Texture budget | **≲ 4 MB per face** (exceeding it bricks rendering / can reboot the watch) |
| Color limit | **≤ 256 colors per image** (firmware decoder requirement; exceeding → instant reboot on install) |

## 1. Top-level header (0xA8 bytes)

| Offset | Meaning | Correct value for AOD two-face dials |
|---|---|---|
| 0x00–03 | magic | `5A A5 34 12` |
| **0x06** | **fractional-seconds / modern-render switch (smooth-sweep master switch)** | **1** — *the stock packer never writes it; must be patched* |
| 0x10 | AOD flag | u32 = `0x800` |
| **0x16** | reserved flag | **1** (official binaries have it) |
| 0x1C | faceCount | 2 (with AOD) / 1 |
| 0x1E | styleCount | 4 (write from `faceStyleCount`, do not hardcode) |
| 0x20 | previewOffset | u32, computed by packer |

## 2. Face record (0x58 bytes per face; main face @0xA8, AOD face @0x100) ★AOD life-or-death

- **u32@+0: official AOD two-face dials set `0x80000000` on BOTH faces; single-face dials keep 0.**
  Our packer originally never wrote +0x00 at all — this was the **root cause of AOD not displaying**
  (v60–v62 all died here). Only set it for AOD dials; never unconditionally.
- u32@+4 = previewOffset (0 on AOD face), u32@+8 = element count, section table starts at 0x08.
- Official binaries sometimes use a **named face** layout (0x58 face record + 0x48 name interleaved);
  there the main face sits @0xA8 and the AOD face @0x148.
- Byte-aligning the top header with official files is **not sufficient** for AOD — you must check the face record.

## 3. Smooth sweep-second recipe (missing any item → 1 Hz ticking)

1. `byte[6] = 1` (header patch, see §1).
2. Pointer elements: `[0]` ds=`1811` (second) interval=`16`, `[1]` ds=`1011` (minute) interval=`60000`,
   `imageRotateX/Y = 232`, `maxValue = 60`, `allAngle = 3600`, `pointerUnknown25/26 = 0`.
3. **★ The real switch = the `prop7Raw` channel bytes of every dignum/imagelist element:**
   - **dignum: bytes b6–b7 = refresh milliseconds (LE u16).** hour/minute/temp/calories/steps/battery
     = `E8 03` (1000 ms); capsule second = `10 00` (16 ms).
     **b6–b7 = 0000 is an illegal channel → the whole face's animation gets disabled → 1 Hz ticking.**
   - **imagelist with an imageIndexList: b12–b13 must be `00 02`**, otherwise arc/list channels die
     (the root cause of "temperature/steps have no progress arc"). Without an index table (e.g. weekday `2012`),
     b12–b13 = 0000 is fine.
   - b14–b15 = rotation × 0.1° (0000 = upright; `C9 FF` tilts by ~22°);
     b16+ = imageIndexList values (4 bytes each).
   - **⚠️ The biggest trap: `unpack` strips prop7Raw!** Re-packing from an unpacked wfDef = every channel
     illegal = ticking. The only reliable source of raw values is **extracting from a known-good binary's
     def table** (type==7, 16-byte defs: idx@0 / offset@8 / length@12 → the bytes at that offset are the prop7 block).
     See `project/build_v64.py` → `extract_idx()`; the canonical raw values are固化 in its `RAWS` table.
   - **Pointers must NOT get a prop7Raw** (the packer's 32-byte template was verified smooth without it).
4. **Acceptance check (mandatory since v64):** re-extract every widget's prop7 from the produced binary and verify
   dignum b6–b7 ≠ 0, imagelist-with-table b12–b13 = `00 02`, and exactly one occurrence each of the pointer
   signatures `18 11 00 30` / `10 11 00 30`.
5. Arc frames must be **cropped tiles (~141×143)** with the element x/y at the tile's top-left corner —
   never full-canvas 464×464 frames (texture budget, see §0).

## 4. Legal `dataSrc` table

**Authoritative source: [`reference/micreate_sources_official.json`](../reference/micreate_sources_official.json)**
(76 entries, from Mi-Create's `sources.json`, key `xiaomi_watch_s3`). It matches real-device behaviour exactly.

Key entries:

| id | Meaning | id | Meaning |
|---|---|---|---|
| 0811 / 1011 / 1811 | hour / minute / second (+Low/High split) | 0812 | Gregorian year |
| **1012** | **Gregorian month** ← use for date rows | 1112 / 1212 | month ones / tens |
| **1812** | **Gregorian day** ← use for date rows | 1912 / 1A12 | day ones / tens |
| 2012 | weekday | 2812 / 3012 / 3812 | **lunar** year/month/day (do NOT use for Gregorian!) |
| 0813 | AM/PM | 3031 / 2031 | weather icon (25 frames) / temperature ℃ |
| 0841 / 1041 | battery % / charging state | 0821 / 1021 | steps / steps % |
| 0822 | **heart rate** (NOT calories!) | 0823 / 1023 | **active calories / calories %** |
| 0824 / 1024 | stand count / % | 0825 | SpO₂ |
| 0826 | stress | 0828 / 1028 / 1828 | sleep duration / score / goal progress |
| 1832 / 2032 | today's high / low temp | 7831 | UV index |

Trailing byte = digit count / format (e.g. `081102` = hour 2 digits, `082305` = calories 5 digits).
Common variants: `081102` hour(2) · `101102` capsule-minute · `181102` capsule-second · `203103` temp(3) ·
`082305` calories(5) · `082105` steps(5, spacing=254) · `084103` battery%(3).

**Illegal IDs (we stepped on these):** `283103` (wrong calorie source), `381202` / `084102`
(contamination from an old packer's showCount bug).

### 4.1 Semantics confirmed the hard way

- `3012`/`3812` are **lunar** month/day (frame decoding + official tables agree). Gregorian = `1012`/`1812`.
- Calories: arc = `1023` (percent channel, table [0,10..100]), number = `082305`.
  `082203` is heart rate, not calories (real-device veto).
- Copying raw values from official dials carries two traps: b14–b15 = `DC 00` means a 22° tilt
  (their slots sit on diagonals — horizontal slots need `00 00`), and b13 = `FC` means spacing −4
  (digits will squash — set spacing 0).
  Corrected calorie raw: `082305100000E803030000030000000000000000`.
- Temperature with `showZero=false` renders 2 digits ("29") — the `°` element must follow the number's left edge
  or a ~1-glyph gap appears.

## 5. Packer bugs we already fixed (do not regress)

| Bug | Location | Fix |
|---|---|---|
| showCount overwrote dataSrc byte 3 | `writeProp7` (~L1888) | removed `b[p+2]=showCount` |
| styleCount hardcoded 6 | `writeHeader` AOD branch | `b[0x1E]=(byte)styleCount` |
| **AOD face record missing `0x80000000`** | `buildFaceHeader` (never wrote +0x00) | added `aodDial` parameter, set on both faces (AOD dials only) |
| **spacing overwrote imagelist b13** | `writeProp7` (~L1891) | b13=spacing only for dignum; imagelist b13 belongs to the `00 02` channel flag |

## 6. Asset-drawing pitfalls (PIL)

1. `d.arc(bbox, ..., width=W)` strokes **inward** from the bbox: mid-line radius = **R − W/2**.
   Round caps must be drawn centred at R − W/2, not R (else caps bulge ~5 px wider than the band).
2. ≤ 256 colors: white-ish art → premultiplied-white quantize; colored art → `FASTOCTREE`.
3. Canvas 464, center (232,232); watch "web angle" (0 = 12 o'clock, clockwise) → PIL rotation is **−90**;
   PIL `rotate(-x)` rotates clockwise by x.
4. **The packer never crops or rescales images** — unpacked sizes are the true packed sizes;
   when you change an image's size you must update the element's x/y in wfDef.

## 7. Build order (mandatory)

```
edit wfDef / assets → pack → patch_header 1 4 1 → unpack & verify (§3.4 / AGENTS §8) → install on watch
```

`pack` never writes `byte[6]` (smooth switch) or `0x16` — **always** run `patch_header.py` afterwards.
