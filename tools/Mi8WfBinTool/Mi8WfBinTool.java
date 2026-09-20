import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/**
 * Standalone Mi Band / Redmi Watch face BIN unpacker and packer.
 * <p>
 * Usage:
 * javac Mi8WfBinTool.java
 * java Mi8WfBinTool unpack watchface.bin out_dir mi8
 * java Mi8WfBinTool pack out_dir new.bin mi8
 * <p>
 * Supported element/image types follow Android_Source/WfWriter:
 * element, element_anim, widge_dignum, widge_imagelist, widge_pointer,
 * widge_process, JS resource blocks, editable groups, and mi8pro/rw4/N66 jumps.
 */
public class Mi8WfBinTool {
    static String DEVICE_TYPE = "mi8";
    static String DEVICE_TYPE_DETAIL = "";
    static boolean FORCE_INDEX256 = false;

    static void setDeviceType(String dev) {
        String d = dev.toLowerCase(Locale.ROOT);
        if ("rw4".equals(d) || "n66".equals(d) || "n67".equals(d) || "o65".equals(d) || "o66".equals(d) || "p65".equals(d) || "mi8pro".equals(d)) {
            DEVICE_TYPE = "mi8pro";
            if ("n66".equals(d)) {
                DEVICE_TYPE_DETAIL = "N66";
            } else {
                DEVICE_TYPE_DETAIL = "";
            }
        } else if ("o62".equals(d)) {
            DEVICE_TYPE = "O62";
            DEVICE_TYPE_DETAIL = "";
        } else if ("p62".equals(d)) {
            DEVICE_TYPE = "P62";
            DEVICE_TYPE_DETAIL = "";
        } else if ("mi7".equals(d) || "l66".equals(d)) {
            DEVICE_TYPE = "mi7";
            DEVICE_TYPE_DETAIL = "";
        } else {
            DEVICE_TYPE = d;
            DEVICE_TYPE_DETAIL = "";
        }
    }

    static boolean isZipFormat() {
        return "mi7".equals(DEVICE_TYPE);
    }

    static void unzip(Path zipFile, Path destDir) throws IOException {
        Files.createDirectories(destDir);
        try (java.util.zip.ZipInputStream zipIn = new java.util.zip.ZipInputStream(Files.newInputStream(zipFile))) {
            java.util.zip.ZipEntry entry;
            while ((entry = zipIn.getNextEntry()) != null) {
                Path filePath = destDir.resolve(entry.getName());
                if (!filePath.normalize().startsWith(destDir.normalize())) {
                    throw new IOException("Bad zip entry: " + entry.getName());
                }
                if (entry.isDirectory()) {
                    Files.createDirectories(filePath);
                } else {
                    Files.createDirectories(filePath.getParent());
                    try (OutputStream out = Files.newOutputStream(filePath)) {
                        byte[] buffer = new byte[4096];
                        int len;
                        while ((len = zipIn.read(buffer)) > 0) {
                            out.write(buffer, 0, len);
                        }
                    }
                }
                zipIn.closeEntry();
            }
        }
    }

    static byte[] zip(Path srcDir) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        try (java.util.zip.ZipOutputStream zipOut = new java.util.zip.ZipOutputStream(bos)) {
            Files.walk(srcDir).forEach(path -> {
                if (Files.isDirectory(path)) return;
                try {
                    String name = srcDir.relativize(path).toString().replace('\\', '/');
                    java.util.zip.ZipEntry zipEntry = new java.util.zip.ZipEntry(name);
                    zipOut.putNextEntry(zipEntry);
                    Files.copy(path, zipOut);
                    zipOut.closeEntry();
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });
        } catch (RuntimeException e) {
            if (e.getCause() instanceof IOException) {
                throw (IOException) e.getCause();
            }
            throw e;
        }
        return bos.toByteArray();
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            usage();
            return;
        }
        String cmd = args[0].toLowerCase(Locale.ROOT);
        if ("unpack".equals(cmd)) {
            if (args.length < 3) {
                usage();
                return;
            }
            if (args.length >= 4) setDeviceType(args[3]);
            if (isZipFormat()) {
                unzip(Paths.get(args[1]), Paths.get(args[2]));
                System.out.println("Unzipped ZIP-based watchface to " + args[2]);
            } else {
                WfUnpacker.unpack(Paths.get(args[1]), Paths.get(args[2]));
            }
        } else if ("pack".equals(cmd)) {
            if (args.length < 3) {
                usage();
                return;
            }
            if (args.length >= 4) setDeviceType(args[3]);
            byte[] bin;
            if (isZipFormat()) {
                bin = zip(Paths.get(args[1]));
            } else {
                bin = WfPacker.pack(Paths.get(args[1]));
            }
            Path outPath = Paths.get(args[2]);
            Path parent = outPath.toAbsolutePath().getParent();
            if (parent != null) Files.createDirectories(parent);
            Files.write(outPath, bin);
            System.out.println("Packed " + bin.length + " bytes -> " + args[2]);
        } else {
            usage();
        }
    }

    static void usage() {
        System.out.println("Mi8WfBinTool");
        System.out.println("  unpack <watchface.bin> <outDir> [device]");
        System.out.println("  pack <workDir> <out.bin> [device]");
        System.out.println("  supported devices: mi7 (l66), mi8, mi7pro, mi8pro, rw4, n66, n67, o65, o66, p65, ws3, ws4s, O62, P62");
    }

    static final class BU {
        static int u8(byte[] b, int o) {
            return b[o] & 0xFF;
        }

        static int i16(byte[] b, int o) {
            return u8(b, o) | (u8(b, o + 1) << 8);
        }

        static int i24(byte[] b, int o) {
            return u8(b, o) | (u8(b, o + 1) << 8) | (u8(b, o + 2) << 16);
        }

        static int i32(byte[] b, int o) {
            return u8(b, o) | (u8(b, o + 1) << 8) | (u8(b, o + 2) << 16) | (u8(b, o + 3) << 24);
        }

        static void w8(ByteArrayOutputStream out, int v) {
            out.write(v & 0xFF);
        }

        static void w16(byte[] b, int o, int v) {
            b[o] = (byte) v;
            b[o + 1] = (byte) (v >> 8);
        }

        static void w24(byte[] b, int o, int v) {
            b[o] = (byte) v;
            b[o + 1] = (byte) (v >> 8);
            b[o + 2] = (byte) (v >> 16);
        }

        static void w32(byte[] b, int o, int v) {
            b[o] = (byte) v;
            b[o + 1] = (byte) (v >> 8);
            b[o + 2] = (byte) (v >> 16);
            b[o + 3] = (byte) (v >> 24);
        }

        static byte[] slice(byte[] b, int o, int n) {
            return Arrays.copyOfRange(b, o, o + n);
        }

        static byte[] concat(byte[]... arrs) {
            int len = 0;
            for (byte[] a : arrs) len += a.length;
            byte[] r = new byte[len];
            int p = 0;
            for (byte[] a : arrs) {
                System.arraycopy(a, 0, r, p, a.length);
                p += a.length;
            }
            return r;
        }

        static String ascii(byte[] b, int o, int max) {
            int n = 0;
            while (n < max && o + n < b.length && b[o + n] != 0) n++;
            return new String(b, o, n, StandardCharsets.US_ASCII);
        }

        static String utf8(byte[] b, int o, int max) {
            int n = 0;
            while (n < max && o + n < b.length && b[o + n] != 0) n++;
            return new String(b, o, n, StandardCharsets.UTF_8);
        }

        static String getWfName(byte[] b) {
            if (b.length < 164) return "";
            boolean isAllFF = true;
            for (int i = 0; i < 4; i++) {
                if ((b[104 + i] & 0xFF) != 0xFF) {
                    isAllFF = false;
                    break;
                }
            }
            if (!isAllFF) {
                return utf8(b, 104, 60);
            }
            try {
                int readInt32 = i32(b, 116);
                int offset = readInt32 + 20 + i16(b, readInt32 + 8);
                int len = i16(b, readInt32 + 12);
                if (offset >= 0 && offset + len <= b.length) {
                    return new String(b, offset, len, StandardCharsets.UTF_8);
                }
            } catch (Exception ignored) {
            }
            return "";
        }
    }

    static final class Rle {
        static byte[] encV10(byte[] data, int bpp) {
            if (bpp == 3) return encFixed(data, 3);
            if (bpp == 4) return encFixed(data, 4);
            return encFixed(data, 2);
        }

        static byte[] encFixed(byte[] data, int bpp) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            int i = 0;
            while (i < data.length) {
                int count = 1;
                while (count < 0x7F && i + (count + 1) * bpp <= data.length) {
                    boolean same = true;
                    for (int k = 0; k < bpp; k++)
                        if (data[i + k] != data[i + count * bpp + k]) {
                            same = false;
                            break;
                        }
                    if (!same) break;
                    count++;
                }
                out.write(count);
                out.write(data, i, Math.min(bpp, data.length - i));
                for (int k = data.length - i; k < bpp; k++) out.write(0);
                i += count * bpp;
            }
            return out.toByteArray();
        }

        static byte[] encV11(byte[] data, int bpp) {
            if (bpp != 4) return encFixed(data, 2);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            int i = 0;
            while (i < data.length) {
                int count = 1;
                while (count <= 0x7F && i + (count + 1) * 4 <= data.length) {
                    boolean same = true;
                    for (int k = 0; k < 4; k++)
                        if (data[i + k] != data[i + count * 4 + k]) {
                            same = false;
                            break;
                        }
                    if (!same) break;
                    count++;
                }
                int flag = count - 1;
                if (flag > 0) flag |= 0x80;
                out.write(flag & 0xFF);
                out.write(data, i, Math.min(4, data.length - i));
                i += count * 4;
            }
            return out.toByteArray();
        }

        static byte[] encV20(byte[] data) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            int i = 0;
            while (i < data.length) {
                if (i == data.length - 1) {
                    out.write(1);
                    out.write(data[i] & 0xFF);
                    break;
                }
                if (data[i] == data[i + 1] && same(data, i, 3)) {
                    int c = 1;
                    while (c < 0x7F && i + c < data.length && data[i + c] == data[i]) c++;
                    out.write(c & 0x7F);
                    out.write(data[i] & 0xFF);
                    i += c;
                } else {
                    int c = 1;
                    while (c < 0x7F && i + c < data.length && !same(data, i + c, 3)) c++;
                    out.write((c | 0x80) & 0xFF);
                    out.write(data, i, c);
                    i += c;
                }
            }
            return out.toByteArray();
        }

        static boolean same(byte[] d, int p, int n) {
            if (p + n > d.length) return false;
            for (int i = 1; i < n; i++) if (d[p + i] != d[p]) return false;
            return true;
        }

        static byte[] decV10(byte[] enc, int len, int bpp) {
            byte[] out = new byte[len];
            int ip = 0, op = 0;
            while (ip < enc.length && op < out.length) {
                int c = enc[ip++] & 0xFF;
                if ((c & 0x80) == 0) {
                    int n = c & 0x7F;
                    byte[] px = BU.slice(enc, ip, Math.min(bpp, enc.length - ip));
                    ip += bpp;
                    for (int j = 0; j < n && op + bpp <= out.length; j++) {
                        System.arraycopy(px, 0, out, op, bpp);
                        op += bpp;
                    }
                } else {
                    int n = c & 0x7F;
                    for (int j = 0; j < n && op + bpp <= out.length && ip + bpp <= enc.length; j++) {
                        System.arraycopy(enc, ip, out, op, bpp);
                        ip += bpp;
                        op += bpp;
                    }
                }
            }
            return out;
        }

        static byte[] decV11(byte[] enc, int len, int bpp) {
            byte[] out = new byte[len];
            int ip = 0, op = 0;
            while (ip < enc.length && op < out.length) {
                int c = enc[ip++] & 0xFF;
                int n = (c & 0x7F) + 1;
                if ((c & 0x80) == 0) {
                    for (int j = 0; j < n && op + bpp <= out.length && ip + bpp <= enc.length; j++) {
                        System.arraycopy(enc, ip, out, op, bpp);
                        ip += bpp;
                        op += bpp;
                    }
                } else {
                    byte[] px = BU.slice(enc, ip, Math.min(bpp, enc.length - ip));
                    ip += bpp;
                    for (int j = 0; j < n && op + bpp <= out.length; j++) {
                        System.arraycopy(px, 0, out, op, bpp);
                        op += bpp;
                    }
                }
            }
            return out;
        }

        static byte[] decV20(byte[] enc, int len) {
            byte[] out = new byte[len];
            int ip = 0, op = 0;
            while (ip < enc.length && op < out.length) {
                int c = enc[ip++] & 0xFF;
                int n = c & 0x7F;
                if ((c & 0x80) != 0) {
                    for (int j = 0; j < n && op < out.length && ip < enc.length; j++) out[op++] = enc[ip++];
                } else {
                    if (ip >= enc.length) break;
                    byte v = enc[ip++];
                    for (int j = 0; j < n && op < out.length; j++) out[op++] = v;
                }
            }
            return out;
        }
    }

    static final class ImageCodec {
        static boolean isMi8ProFamily() {
            return DEVICE_TYPE.equals("mi8pro");
        }

        static boolean hasAlpha(BufferedImage img) {
            if (DEVICE_TYPE.equals("mi8pro")) return true;
            for (int y = 0; y < img.getHeight(); y++)
                for (int x = 0; x < img.getWidth(); x++) if (((img.getRGB(x, y) >>> 24) & 255) != 255) return true;
            return false;
        }

        static int colorCount(BufferedImage img) {
            HashSet<Integer> s = new HashSet<>();
            for (int y = 0; y < img.getHeight(); y++) for (int x = 0; x < img.getWidth(); x++) s.add(img.getRGB(x, y));
            return s.size();
        }

        static byte[] write16(BufferedImage img) {
            byte[] out = new byte[img.getWidth() * img.getHeight() * 2];
            int p = 0;
            for (int y = 0; y < img.getHeight(); y++)
                for (int x = 0; x < img.getWidth(); x++) {
                    int c = img.getRGB(x, y), r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255;
                    out[p++] = (byte) (((g & 0x1C) << 3) | ((b & 0xF8) >> 3));
                    out[p++] = (byte) ((r & 0xF8) | ((g & 0xE0) >> 5));
                }
            return out;
        }

        static byte[] write24(BufferedImage img) {
            byte[] out = new byte[img.getWidth() * img.getHeight() * 3];
            int p = 0;
            for (int y = 0; y < img.getHeight(); y++)
                for (int x = 0; x < img.getWidth(); x++) {
                    int c = img.getRGB(x, y), r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255, a = (c >>> 24) & 255;
                    out[p++] = (byte) (((g & 0x1C) << 3) | ((b & 0xF8) >> 3));
                    out[p++] = (byte) ((r & 0xF8) | ((g & 0xE0) >> 5));
                    out[p++] = (byte) a;
                }
            return out;
        }

        static byte[] write32(BufferedImage img) {
            byte[] out = new byte[img.getWidth() * img.getHeight() * 4];
            int p = 0;
            for (int y = 0; y < img.getHeight(); y++)
                for (int x = 0; x < img.getWidth(); x++) {
                    int c = img.getRGB(x, y);
                    out[p++] = (byte) (c & 255);
                    out[p++] = (byte) ((c >> 8) & 255);
                    out[p++] = (byte) ((c >> 16) & 255);
                    out[p++] = (byte) ((c >>> 24) & 255);
                }
            return out;
        }

        static byte[] writeIndex256(BufferedImage img) {
            return writeIndex256(img, 1024);
        }

        static byte[] writeIndex256(BufferedImage img, int offset) {
            byte[] out = new byte[img.getWidth() * img.getHeight() + offset];
            LinkedHashMap<Integer, Integer> map = new LinkedHashMap<>();
            int pp = 0;
            for (int y = 0; y < img.getHeight(); y++) {
                for (int x = 0; x < img.getWidth(); x++) {
                    int c = img.getRGB(x, y);
                    Integer idx = map.get(c);
                    if (idx == null) {
                        idx = map.size();
                        if (idx < 256) {
                            map.put(c, idx);
                            int p = idx * 4;
                            out[p] = (byte) (c & 255);
                            out[p + 1] = (byte) ((c >> 8) & 255);
                            out[p + 2] = (byte) ((c >> 16) & 255);
                            out[p + 3] = (byte) ((c >>> 24) & 255);
                        } else {
                            idx = 255;
                        }
                    }
                    out[offset + pp++] = (byte) (idx & 255);
                }
            }
            return out;
        }

        static boolean isGray(BufferedImage img) {
            int w = img.getWidth(), h = img.getHeight();
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rgb = img.getRGB(x, y);
                    int a = (rgb >>> 24) & 255;
                    int r = (rgb >>> 16) & 255;
                    int g = (rgb >>> 8) & 255;
                    int b = rgb & 255;
                    if (a != 255 || r != g || r != b) return false;
                }
            }
            return true;
        }

        static byte[] writeGray(BufferedImage img) {
            int w = img.getWidth(), h = img.getHeight();
            byte[] out = new byte[w * h];
            int p = 0;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    out[p++] = (byte) ((img.getRGB(x, y) >>> 16) & 255);
                }
            }
            return out;
        }

        static byte[] writeIndex16(BufferedImage img, int offset) {
            int w = img.getWidth(), h = img.getHeight();
            byte[] out = new byte[(w * h) / 2 + offset];
            LinkedHashMap<Integer, Integer> map = new LinkedHashMap<>();
            int i3 = 0;
            Integer firstPixel = null;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int pixel = img.getRGB(x, y);
                    if (!map.containsKey(pixel)) {
                        int idx = map.size();
                        if (idx < 16) {
                            map.put(pixel, idx);
                            int q = idx * 4;
                            out[q] = (byte) (pixel & 255);
                            out[q + 1] = (byte) ((pixel >>> 8) & 255);
                            out[q + 2] = (byte) ((pixel >>> 16) & 255);
                            out[q + 3] = (byte) ((pixel >>> 24) & 255);
                        } else {
                            map.put(pixel, 15);
                        }
                    }
                    if (firstPixel == null) {
                        firstPixel = pixel;
                    } else {
                        int idx1 = map.get(firstPixel);
                        int idx2 = map.get(pixel);
                        out[offset + i3] = (byte) (((idx1 & 15) << 4) | (idx2 & 15));
                        i3++;
                        firstPixel = null;
                    }
                }
            }
            return out;
        }

        static int judgeJSImageSign(BufferedImage img) {
            boolean isGray = isGray(img);
            int colorSize = colorCount(img);
            int width = img.getWidth();
            int height = img.getHeight();
            if (colorSize <= 256) {
                if (colorSize <= 16 && width % 2 == 0 && height % 2 == 0) {
                    return 9;
                } else if (isGray) {
                    return 14;
                } else {
                    return 10;
                }
            } else {
                return 5;
            }
        }

        static byte[] compileJSImage(BufferedImage img, String name) {
            boolean compress = name.endsWith(".rle");
            boolean isGray = isGray(img);
            int colorSize = colorCount(img);
            int width = img.getWidth();
            int height = img.getHeight();
            int sign;
            byte[] pix;
            boolean doCompress = false;
            if (compress) {
                if (colorSize <= 256) {
                    if (colorSize <= 16 && width % 2 == 0 && height % 2 == 0) {
                        pix = writeIndex16(img, 64);
                        sign = 9;
                    } else if (isGray) {
                        pix = writeGray(img);
                        sign = 14;
                    } else {
                        pix = writeIndex256(img, 1024);
                        sign = 10;
                    }
                    doCompress = true;
                } else {
                    pix = DEVICE_TYPE_DETAIL.equals("N66") ? write24(img) : write32(img);
                    sign = 5;
                    doCompress = false;
                }
            } else {
                boolean alpha = hasAlpha(img);
                if (isMi8ProFamily()) alpha = true;
                if (!alpha) {
                    pix = write16(img);
                    sign = 4;
                } else if (DEVICE_TYPE_DETAIL.equals("N66")) {
                    pix = write24(img);
                    sign = 5;
                } else {
                    pix = write32(img);
                    sign = 5;
                }
                doCompress = false;
            }
            byte[] payload = pix;
            if (doCompress) {
                byte[] enc = Rle.encV20(pix);
                payload = new byte[enc.length + 8];
                payload[0] = (byte) 0xE0;
                payload[1] = 0x21;
                payload[2] = (byte) 0xA5;
                payload[3] = 0x5A;
                BU.w32(payload, 4, (pix.length << 4) | 1);
                System.arraycopy(enc, 0, payload, 8, enc.length);
            }
            byte[] h = new byte[4];
            h[0] = (byte) sign;
            int dimFlags = (height << 13) | (width << 2);
            BU.w24(h, 1, dimFlags);
            return BU.concat(h, payload);
        }

        static int imgSign(BufferedImage img) {
            if (FORCE_INDEX256 && colorCount(img) <= 256) return 0x10;
            if (!isMi8ProFamily()) return 0;
            if (colorCount(img) <= 256) return 0x10;
            if (DEVICE_TYPE_DETAIL.equals("N66")) return 6;
            return 0;
        }

        static byte[] single(BufferedImage img, boolean compress) {
            boolean alpha = hasAlpha(img);
            if (DEVICE_TYPE.equals("mi7pro") || DEVICE_TYPE.equals("mi8pro")) alpha = true;
            int sign = imgSign(img);
            byte[] pix;
            int bpp;
            if (sign == 0x10) {
                pix = writeIndex256(img);
                bpp = 1;
            } else if (sign == 6) {
                pix = write24(img);
                bpp = 3;
            } else if (alpha) {
                pix = write32(img);
                bpp = 4;
            } else {
                pix = write16(img);
                bpp = 2;
            }
            byte[] payload = compress ? compressedPayload(pix, bpp, sign) : pix;
            byte[] h = new byte[12];
            h[0] = (byte) (sign != 0 ? sign : (!alpha ? 3 : 0));
            if (compress) h[1] = (byte) (DEVICE_TYPE.equals("mi7pro") ? 8 : 4);
            BU.w16(h, 4, img.getWidth());
            BU.w16(h, 6, img.getHeight());
            BU.w32(h, 8, payload.length);
            return BU.concat(h, payload);
        }

        static byte[] imageList(List<BufferedImage> imgs, boolean compress) {
            int sign = listSign(imgs);
            byte[] h = new byte[12];
            h[0] = (byte) (sign != 0 ? sign : 0);
            h[1] = (byte) imgs.size();
            if (compress) h[2] = (byte) (DEVICE_TYPE.equals("mi7pro") ? 8 : 4);
            BU.w16(h, 4, imgs.get(0).getWidth());
            BU.w16(h, 6, imgs.get(0).getHeight());
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            try {
                out.write(h);
                if (compress) out.write(new byte[imgs.size() * 4]);
            } catch (IOException ignored) {
            }
            int total = 0;
            ArrayList<byte[]> payloads = new ArrayList<>();
            for (BufferedImage img : imgs) {
                boolean alpha = true;
                if (DEVICE_TYPE.equals("mi7pro") || DEVICE_TYPE.equals("mi8pro")) alpha = true;
                int bpp;
                byte[] pix;
                if (sign == 0x10) {
                    pix = writeIndex256(img);
                    bpp = 1;
                } else if (sign == 6) {
                    pix = write24(img);
                    bpp = 3;
                } else if (alpha) {
                    pix = write32(img);
                    bpp = 4;
                } else {
                    pix = write16(img);
                    bpp = 2;
                }
                byte[] p = compress ? compressedPayload(pix, bpp, sign) : pix;
                payloads.add(p);
                total += p.length;
            }
            byte[] result = BU.concat(out.toByteArray(), concatList(payloads));
            BU.w32(result, 8, total + (compress ? imgs.size() * 4 : 0));
            for (int i = 0; i < payloads.size(); i++) BU.w32(result, 12 + i * 4, payloads.get(i).length);
            return result;
        }

        static byte[] concatList(List<byte[]> bs) {
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            try {
                for (byte[] b : bs) o.write(b);
            } catch (IOException ignored) {
            }
            return o.toByteArray();
        }

        static int listSign(List<BufferedImage> imgs) {
            if (FORCE_INDEX256) {
                boolean under = true;
                for (BufferedImage img : imgs) if (colorCount(img) > 256) under = false;
                if (under) return 0x10;
            }
            if (!isMi8ProFamily()) return 0;
            boolean under = true;
            for (BufferedImage img : imgs) if (colorCount(img) > 256) under = false;
            if (under) return 0x10;
            if (DEVICE_TYPE_DETAIL.equals("N66")) return 6;
            return 0;
        }

        static byte[] compressedPayload(byte[] pix, int bpp, int sign) {
            byte[] enc = (sign == 0x10 || sign == 9 || sign == 14) ? Rle.encV20(pix) : DEVICE_TYPE.equals("mi7pro") ? Rle.encV11(pix, bpp) : Rle.encV10(pix, bpp);
            byte[] r = new byte[enc.length + 8];
            r[0] = (byte) 0xE0;
            r[1] = 0x21;
            r[2] = (byte) 0xA5;
            r[3] = 0x5A;
            BU.w32(r, 4, (pix.length << 4) | bpp);
            System.arraycopy(enc, 0, r, 8, enc.length);
            return r;
        }

        static BufferedImage readImageBlock(byte[] block, int off) throws Exception {
            int sign = BU.u8(block, off);
            int width = BU.i16(block, off + 4), height = BU.i16(block, off + 6), len = BU.i32(block, off + 8);
            boolean alpha = sign != 3;
            return decodePixels(block, off + 12, len, width, height, alpha, sign);
        }

        static List<BufferedImage> readImageListBlock(byte[] block, int off) throws Exception {
            int sign = BU.u8(block, off), count = BU.u8(block, off + 1), width = BU.i16(block, off + 4), height = BU.i16(block, off + 6);
            boolean compressed = BU.u8(block, off + 2) == 4 || BU.u8(block, off + 2) == 8;
            ArrayList<BufferedImage> out = new ArrayList<>();
            int data = off + 12 + (compressed ? count * 4 : 0);
            int total = BU.i32(block, off + 8);
            for (int i = 0; i < count; i++) {
                int len = compressed ? BU.i32(block, off + 12 + i * 4) : total / Math.max(1, count);
                out.add(decodePixels(block, data, len, width, height, true, sign));
                data += len;
            }
            return out;
        }

        static BufferedImage decodePixels(byte[] b, int off, int len, int w, int h, boolean alpha, int sign) throws Exception {
            byte[] pix;
            int bpp = 0;
            if (BU.u8(b, off) == 0xE0 && BU.u8(b, off + 1) == 0x21 && BU.u8(b, off + 2) == 0xA5 && BU.u8(b, off + 3) == 0x5A) {
                int info = BU.i32(b, off + 4);
                bpp = info & 15;
                int rawLen = info >>> 4;
                byte[] enc = BU.slice(b, off + 8, len - 8);
                pix = (sign == 0x10 || bpp == 1) ? Rle.decV20(enc, rawLen) : DEVICE_TYPE.equals("mi7pro") ? Rle.decV11(enc, rawLen, bpp) : Rle.decV10(enc, rawLen, bpp);
            } else {
                pix = BU.slice(b, off, len);
                bpp = sign == 6 ? 3 : alpha ? 4 : 2;
            }
            BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
            int p = 0;
            if (sign == 9) {
                int[] pal = new int[16];
                for (int i = 0; i < 16; i++) {
                    int q = i * 4;
                    pal[i] = ((pix[q + 3] & 255) << 24) | ((pix[q + 2] & 255) << 16) | ((pix[q + 1] & 255) << 8) | (pix[q] & 255);
                }
                p = 64;
                int totalPixels = w * h;
                for (int i = 0; i < totalPixels; i++) {
                    int val = pix[p] & 255;
                    int idx = (i % 2 == 0) ? (val >>> 4) : (val & 15);
                    img.setRGB(i % w, i / w, pal[idx]);
                    if (i % 2 == 1) p++;
                }
            } else if (sign == 14) {
                p = 0;
                for (int y = 0; y < h; y++) {
                    for (int x = 0; x < w; x++) {
                        int gray = pix[p++] & 255;
                        img.setRGB(x, y, (255 << 24) | (gray << 16) | (gray << 8) | gray);
                    }
                }
            } else if (sign == 0x10 || sign == 10 || bpp == 1) {
                int[] pal = new int[256];
                for (int i = 0; i < 256; i++) {
                    int q = i * 4;
                    pal[i] = ((pix[q + 3] & 255) << 24) | ((pix[q + 2] & 255) << 16) | ((pix[q + 1] & 255) << 8) | (pix[q] & 255);
                }
                p = 1024;
                for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) img.setRGB(x, y, pal[pix[p++] & 255]);
            } else if (bpp == 4) {
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++) {
                        int bgra = ((pix[p + 3] & 255) << 24) | ((pix[p + 2] & 255) << 16) | ((pix[p + 1] & 255) << 8) | (pix[p] & 255);
                        img.setRGB(x, y, bgra);
                        p += 4;
                    }
            } else if (bpp == 3) {
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++) {
                        int lo = pix[p] & 255, hi = pix[p + 1] & 255, a = pix[p + 2] & 255;
                        p += 3;
                        img.setRGB(x, y, rgb565(lo, hi, a));
                    }
            } else {
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++) {
                        int lo = pix[p] & 255, hi = pix[p + 1] & 255;
                        p += 2;
                        img.setRGB(x, y, rgb565(lo, hi, 255));
                    }
            }
            return img;
        }

        static int rgb565(int lo, int hi, int a) {
            int r = (hi >> 3) << 3, g = (((hi & 7) << 3) | (lo >> 5)) << 2, b = (lo & 31) << 3;
            return (a << 24) | (r << 16) | (g << 8) | b;
        }
    }

    static final class ImgDef {
        String key, md5;
        int len, idx = -1;
        byte[] bytes;
    }

    static boolean isWidget(Map<String, Object> e) {
        String t = str(e.get("type"));
        return t.startsWith("widge");
    }

    static String str(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    static int num(Object o, int d) {
        if (o instanceof Number) return ((Number) o).intValue();
        if (o == null) return d;
        try {
            return Integer.parseInt(String.valueOf(o));
        } catch (Exception e) {
            return d;
        }
    }

    static boolean bool(Object o) {
        return o instanceof Boolean ? (Boolean) o : o != null && Boolean.parseBoolean(String.valueOf(o));
    }

    @SuppressWarnings("unchecked")
    static List<Object> arr(Object o) {
        return o instanceof List ? (List<Object>) o : new ArrayList<>();
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> obj(Object o) {
        return o instanceof Map ? (Map<String, Object>) o : new LinkedHashMap<>();
    }

    static String md5(byte[] b) throws Exception {
        MessageDigest md = MessageDigest.getInstance("MD5");
        byte[] d = md.digest(b);
        StringBuilder s = new StringBuilder();
        for (byte x : d) s.append(String.format("%02x", x & 255));
        return s.toString();
    }

    static String hex(byte[] b) {
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format("%02X", x & 255));
        return s.toString();
    }

    static byte[] unhex(String h) {
        if (h == null) return new byte[0];
        h = h.replaceAll("\\s+", "");
        if ((h.length() & 1) == 1) h = "0" + h;
        byte[] r = new byte[h.length() / 2];
        for (int i = 0; i < r.length; i++) r[i] = (byte) Integer.parseInt(h.substring(i * 2, i * 2 + 2), 16);
        return r;
    }

    static final class WfPacker {
        static byte[] pack(Path workDir) throws Exception {
            Path wfDef = workDir.resolve("wfDef.json");
            Path imageDir = workDir.resolve("images");
            Map<String, Object> wf = obj(Json.parse(new String(Files.readAllBytes(wfDef), StandardCharsets.UTF_8)));
            FORCE_INDEX256 = bool(wf.get("forceIndex256"));
            if (!arr(wf.get("faces")).isEmpty()) return packFaces(workDir, wf);
            List<Map<String, Object>> normal = mapList(wf.get("elementsNormal"));
            List<Map<String, Object>> aod = mapList(wf.get("elementsAod"));
            setElIndex(normal);
            setElIndex(aod);
            FaceData nf = buildFace(normal, imageDir);
            loadExtraProp7(nf, wf.get("extraProp7Normal"));
            loadExtraProp8(nf, wf.get("extraProp8Normal"));
            loadExtraProp9(nf, wf.get("extraProp9Normal"));
            assignWidgetIndices(nf.elements, nf.extraProp7);
            assignEditableIndices(nf.elements, nf.extraProp8);
            FaceData af = null;
            boolean hasAod = !aod.isEmpty();
            if (hasAod) {
                Path aodDir = imageDir.resolveSibling("images_aod");
                af = buildFace(aod, Files.exists(aodDir) ? aodDir : imageDir);
                loadExtraProp7(af, wf.get("extraProp7Aod"));
                loadExtraProp8(af, wf.get("extraProp8Aod"));
                loadExtraProp9(af, wf.get("extraProp9Aod"));
                assignWidgetIndices(af.elements, af.extraProp7);
                assignEditableIndices(af.elements, af.extraProp8);
            }
            BufferedImage preview = readImg(imageDir, str(wf.getOrDefault("previewImg", "preview")));
            byte[] previewBytes = ImageCodec.single(preview, true);
            int faceCount = hasAod ? 2 : 1;
            boolean namedFaces = bool(wf.get("namedFaceRecords")) || "named".equals(str(wf.get("faceLayout")));
            byte[] header = writeHeader(str(wf.getOrDefault("name", "Watchface")), str(wf.getOrDefault("id", "000000000")), hasAod, faceCount);
            int start = 0xA8 + faceCount * 0x58 + (namedFaces ? faceCount * 0x48 : 0);
            int normalDefSize = elementDefSize(nf.elements, nf);
            int normalPropSize = propSize(nf.elements, nf);
            int aodDefSize = hasAod ? elementDefSize(af.elements, af) : 0;
            int aodPropSize = hasAod ? propSize(af.elements, af) : 0;
            if (!namedFaces && hasAod) {
                int normalPropStart = start + normalDefSize;
                int previewOffset = normalPropStart + normalPropSize;
                int imageStart = previewOffset + previewBytes.length;
                Map<String, Integer> imageOffsets = imageMap(imageStart, nf);
                int aodStart = imageEnd(imageStart, nf);
                int aodPropStart = aodStart + aodDefSize;
                int aodImageStart = aodPropStart + aodPropSize;
                Map<String, Integer> aodOffsets = imageMap(aodImageStart, af);
                byte[] faceHeader = buildFaceHeader(nf, start, true);
                byte[] aodHeader = buildFaceHeader(af, aodStart, true);
                BU.w32(header, 0x20, previewOffset);
                BU.w32(faceHeader, 0x04, previewOffset);
                BU.w32(aodHeader, 0x04, 0);
                byte[] elements = writeElements(nf, imageOffsets, start, normalPropStart);
                byte[] aodElements = writeElements(af, aodOffsets, aodStart, aodPropStart);

                ByteArrayOutputStream out = new ByteArrayOutputStream();
                out.write(header);
                out.write(faceHeader);
                out.write(aodHeader);
                writeSplitElements(out, elements, normalDefSize, true);
                writeSplitElements(out, elements, normalDefSize, false);
                out.write(previewBytes);
                for (ImgDef u : nf.uniqueImages) out.write(u.bytes);
                writeSplitElements(out, aodElements, aodDefSize, true);
                writeSplitElements(out, aodElements, aodDefSize, false);
                for (ImgDef u : af.uniqueImages) out.write(u.bytes);
                return out.toByteArray();
            } else {
                int aodStart = hasAod ? start + normalDefSize : 0;
                int normalPropStart = start + normalDefSize + aodDefSize;
                int aodPropStart = hasAod ? normalPropStart + normalPropSize : 0;
                int previewOffset = normalPropStart + normalPropSize + aodPropSize;
                int imageStart = previewOffset + previewBytes.length;
                Map<String, Integer> imageOffsets = imageMap(imageStart, nf);
                int nextImageStart = imageEnd(imageStart, nf);
                Map<String, Integer> aodOffsets = hasAod ? imageMap(nextImageStart, af) : new LinkedHashMap<>();
                byte[] faceHeader = buildFaceHeader(nf, start, hasAod);
                BU.w32(header, 0x20, previewOffset);
                BU.w32(faceHeader, 0x04, previewOffset);
                byte[] elements = writeElements(nf, imageOffsets, start, normalPropStart);
                byte[] aodHeader = null, aodElements = null;
                if (hasAod) {
                    aodHeader = buildFaceHeader(af, aodStart, true);
                    aodElements = writeElements(af, aodOffsets, aodStart, aodPropStart);
                }
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                out.write(header);
                out.write(faceHeader);
                if (namedFaces) out.write(faceNameBlock(str(faceName(wf, 0)), 0));
                if (hasAod) {
                    out.write(aodHeader);
                    if (namedFaces) out.write(faceNameBlock(str(faceName(wf, 1)), 1));
                }
                writeSplitElements(out, elements, normalDefSize, true);
                if (hasAod) writeSplitElements(out, aodElements, aodDefSize, true);
                writeSplitElements(out, elements, normalDefSize, false);
                if (hasAod) writeSplitElements(out, aodElements, aodDefSize, false);
                out.write(previewBytes);
                for (ImgDef u : nf.uniqueImages) out.write(u.bytes);
                if (hasAod) for (ImgDef u : af.uniqueImages) out.write(u.bytes);
                return out.toByteArray();
            }
        }

        static byte[] packFaces(Path workDir, Map<String, Object> wf) throws Exception {
            List<Map<String, Object>> faceDefs = mapList(wf.get("faces"));
            FORCE_INDEX256 = bool(wf.get("forceIndex256"));
            ArrayList<FaceData> faces = new ArrayList<>();
            for (Map<String, Object> face : faceDefs) {
                List<Map<String, Object>> elements = mapList(face.get("elements"));
                setElIndex(elements);
                Path imgDir = workDir.resolve(str(face.getOrDefault("imageDir", "images")));
                List<Integer> imageDefOrder = intList(face.get("imageDefs"));
                List<Integer> imageListDefOrder = intList(face.get("imageListDefs"));
                FaceData fd = buildFace(elements, imgDir, intSet(face.get("imageDefs")), intSet(face.get("imageListDefs")));
                reorderFixedDefs(fd.singles, imageDefOrder);
                reorderFixedDefs(fd.lists, imageListDefOrder);
                loadExtraJs(fd, face.get("extraJs"), imgDir);
                reorderUniqueImages(fd);
                loadExtraProp7(fd, face.get("extraProp7"));
                loadExtraProp9(fd, face.get("extraProp9"));
                loadExtraProp8(fd, face.get("extraProp8"));
                assignWidgetIndices(fd.elements, fd.extraProp7);
                assignEditableIndices(fd.elements, fd.extraProp8);
                faces.add(fd);
            }

            int faceCount = faces.size();
            int styleCount = num(wf.get("faceStyleCount"), faceCount);
            if (styleCount <= 0) styleCount = faceCount;
            byte[] header = writeHeader(str(wf.getOrDefault("name", "Watchface")), str(wf.getOrDefault("id", "000000000")), true, faceCount, styleCount);
            ArrayList<byte[]> previewBytes = new ArrayList<>();
            for (int i = 0; i < faceCount; i++) {
                Map<String, Object> face = faceDefs.get(i);
                String previewName = i == 0 ? str(wf.getOrDefault("previewImg", "preview")) : str(face.get("previewImg"));
                if (previewName.isEmpty()) {
                    previewBytes.add(null);
                    continue;
                }
                Path imgDir = workDir.resolve(str(face.getOrDefault("imageDir", "images")));
                previewBytes.add(ImageCodec.single(readImg(imgDir, previewName), true));
            }

            int start = 0xA8 + faceCount * (0x58 + 0x48);
            int[] defStart = new int[faceCount], propStart = new int[faceCount], defSize = new int[faceCount], propSize = new int[faceCount];
            int cursor = start;
            for (int i = 0; i < faceCount; i++) {
                defStart[i] = cursor;
                defSize[i] = elementDefSize(faces.get(i).elements, faces.get(i));
                propSize[i] = propSize(faces.get(i).elements, faces.get(i));
                cursor += defSize[i];
            }
            for (int i = 0; i < faceCount; i++) {
                propStart[i] = cursor;
                cursor += propSize[i];
            }
            int[] previewOffset = new int[faceCount], imageStart = new int[faceCount];
            LinkedHashMap<String, Integer> globalImageOffsets = new LinkedHashMap<>();
            LinkedHashSet<String> emittedImages = new LinkedHashSet<>();
            for (int i = 0; i < faceCount; i++) {
                byte[] pv = previewBytes.get(i);
                if (pv != null) {
                    previewOffset[i] = cursor;
                    cursor += pv.length;
                }
                for (ImgDef d : faces.get(i).uniqueImages) {
                    if (!globalImageOffsets.containsKey(d.md5)) {
                        globalImageOffsets.put(d.md5, cursor);
                        cursor += d.len;
                    }
                }
            }

            ArrayList<Map<String, Integer>> imageMaps = new ArrayList<>();
            for (int i = 0; i < faceCount; i++) {
                FaceData face = faces.get(i);
                LinkedHashMap<String, Integer> mdOffsets = new LinkedHashMap<>();
                for (ImgDef d : face.uniqueImages) mdOffsets.put(d.md5, globalImageOffsets.get(d.md5));
                LinkedHashMap<String, Integer> offsets = new LinkedHashMap<>();
                for (List<ImgDef> group : Arrays.asList(face.singles, face.lists, face.js))
                    for (ImgDef d : group) offsets.put(d.key, mdOffsets.get(d.md5));
                imageMaps.add(offsets);
            }
            ArrayList<byte[]> faceHeaders = new ArrayList<>(), faceElements = new ArrayList<>();
            for (int i = 0; i < faceCount; i++) {
                byte[] fh = buildFaceHeader(faces.get(i), defStart[i]);
                BU.w32(fh, 0x04, previewOffset[i]);
                faceHeaders.add(fh);
                faceElements.add(writeElements(faces.get(i), imageMaps.get(i), defStart[i], propStart[i]));
            }
            BU.w32(header, 0x20, previewOffset[0]);

            ByteArrayOutputStream out = new ByteArrayOutputStream();
            out.write(header);
            for (int i = 0; i < faceCount; i++) {
                out.write(faceHeaders.get(i));
                out.write(faceNameBlock(str(faceDefs.get(i).get("name")), i == 0 ? 0 : i));
            }
            for (int i = 0; i < faceCount; i++) writeSplitElements(out, faceElements.get(i), defSize[i], true);
            for (int i = 0; i < faceCount; i++) writeSplitElements(out, faceElements.get(i), defSize[i], false);
            for (int i = 0; i < faceCount; i++) {
                byte[] pv = previewBytes.get(i);
                if (pv != null) out.write(pv);
                FaceData face = faces.get(i);
                for (ImgDef u : face.uniqueImages) {
                    if (emittedImages.add(u.md5)) out.write(u.bytes);
                }
            }
            return out.toByteArray();
        }

        static void prepareProp7Tail(FaceData face, int start, LinkedHashMap<String, byte[]> global, LinkedHashMap<String, Integer> offsets) throws Exception {
            for (Map<String, Object> e : filterWidgets(face.elements)) {
                byte[] b = prop7Bytes(e, face);
                String key = md5(b);
                if (!global.containsKey(key)) {
                    global.put(key, b);
                    offsets.put(key, start + tailSize(global) - b.length);
                }
                face.prop7ElementOffsets.put(e, offsets.get(key));
            }
            for (ExtraDef d : face.extraProp7) {
                String key = md5(d.bytes);
                if (!global.containsKey(key)) {
                    global.put(key, d.bytes);
                    offsets.put(key, start + tailSize(global) - d.bytes.length);
                }
                face.prop7ExtraOffsets.put(d, offsets.get(key));
            }
        }

        static void prepareProp9Tail(FaceData face, int start, LinkedHashMap<String, byte[]> global, LinkedHashMap<String, Integer> offsets) throws Exception {
            for (Map<String, Object> e : filterProp9Elements(face.elements)) {
                byte[] b = prop9Bytes(e, face);
                String key = md5(b);
                if (!global.containsKey(key)) {
                    global.put(key, b);
                    offsets.put(key, start + tailSize(global) - b.length);
                }
                face.prop9ElementOffsets.put(e, offsets.get(key));
            }
            for (ExtraDef d : face.extraProp9) {
                String key = md5(d.bytes);
                if (!global.containsKey(key)) {
                    global.put(key, d.bytes);
                    offsets.put(key, start + tailSize(global) - d.bytes.length);
                }
                face.prop9ExtraOffsets.put(d, offsets.get(key));
            }
        }

        static void prepareProp8Tail(FaceData face, int start, LinkedHashMap<String, byte[]> global, LinkedHashMap<String, Integer> offsets) throws Exception {
            for (ExtraDef d : face.extraProp8) {
                String key = md5(d.bytes);
                if (!global.containsKey(key)) {
                    global.put(key, d.bytes);
                    offsets.put(key, start + tailSize(global) - d.bytes.length);
                }
                face.prop8ExtraOffsets.put(d, offsets.get(key));
            }
        }

        static int tailSize(LinkedHashMap<String, byte[]> global) {
            int n = 0;
            for (byte[] b : global.values()) n += b.length;
            return n;
        }

        static void writeSplitElements(ByteArrayOutputStream out, byte[] elements, int defSize, boolean defs) throws IOException {
            if (defs) out.write(elements, 0, defSize);
            else out.write(elements, defSize, elements.length - defSize);
        }

        static Object faceName(Map<String, Object> wf, int i) {
            List<Object> names = arr(wf.get("faceNames"));
            return i < names.size() ? names.get(i) : "\u6837\u5F0F1";
        }

        static byte[] faceNameBlock(String name, int index) {
            byte[] b = new byte[0x48];
            byte[] nb = name.getBytes(StandardCharsets.UTF_8);
            System.arraycopy(nb, 0, b, 0, Math.min(nb.length, 0x40));
            if (index > 0) BU.w32(b, 0x44, index);
            return b;
        }

        static List<Map<String, Object>> mapList(Object o) {
            ArrayList<Map<String, Object>> r = new ArrayList<>();
            for (Object x : arr(o)) r.add(obj(x));
            return r;
        }

        static void setElIndex(List<Map<String, Object>> es) {
            for (int i = 0; i < es.size(); i++) es.get(i).put("elIndex", i);
        }

        static byte[] writeHeader(String name, String id, boolean aod, int faceCount) {
            return writeHeader(name, id, aod, faceCount, aod ? faceCount + 2 : faceCount);
        }

        static byte[] writeHeader(String name, String id, boolean aod, int faceCount, int styleCount) {
            byte[] b = new byte[0xA8];
            b[0] = 0x5A;
            b[1] = (byte) 0xA5;
            b[2] = 0x34;
            b[3] = 0x12;
            boolean pro = ImageCodec.isMi8ProFamily(), mi7 = DEVICE_TYPE.equals("mi7pro");
            if (pro) {
                BU.w32(b, 0x10, 0x800);
                BU.w16(b, 0x1E, styleCount);
            } else if (mi7) BU.w32(b, 0x10, 0x800);
            else if (aod) {
                BU.w32(b, 0x10, 0x800);
                b[0x1E] = (byte) styleCount;
            } else {
                b[0x10] = 1;
                b[0x11] = 7;
            }
            b[0x1C] = (byte) faceCount;
            byte[] idb = id.getBytes(StandardCharsets.US_ASCII);
            System.arraycopy(idb, 0, b, 0x28, Math.min(idb.length, 9));
            byte[] nb = name.getBytes(StandardCharsets.UTF_8);
            System.arraycopy(nb, 0, b, 0x68, Math.min(nb.length, 0x3C));
            return b;
        }

        static final class FaceData {
            List<Map<String, Object>> elements;
            List<ImgDef> singles = new ArrayList<>(), lists = new ArrayList<>(), js = new ArrayList<>();
            List<ImgDef> extraJs = new ArrayList<>();
            List<ExtraDef> extraProp7 = new ArrayList<>(), extraProp8 = new ArrayList<>(), extraProp9 = new ArrayList<>();
            List<ImgDef> uniqueImages = new ArrayList<>();
            IdentityHashMap<Map<String, Object>, Integer> prop7ElementOffsets = new IdentityHashMap<>();
            IdentityHashMap<ExtraDef, Integer> prop7ExtraOffsets = new IdentityHashMap<>();
            IdentityHashMap<ExtraDef, Integer> prop8ExtraOffsets = new IdentityHashMap<>();
            IdentityHashMap<Map<String, Object>, Integer> prop9ElementOffsets = new IdentityHashMap<>();
            IdentityHashMap<ExtraDef, Integer> prop9ExtraOffsets = new IdentityHashMap<>();
            byte[] elementBytes;
        }

        static final class ExtraDef {
            int idx, len;
            byte[] bytes;
        }

        static FaceData buildFace(List<Map<String, Object>> es, Path imgDir) throws Exception {
            return buildFace(es, imgDir, null, null);
        }

        static FaceData buildFace(List<Map<String, Object>> es, Path imgDir, Set<Integer> allowedSingles, Set<Integer> allowedLists) throws Exception {
            FaceData f = new FaceData();
            f.elements = es;
            LinkedHashSet<String> seen = new LinkedHashSet<>();
            HashSet<String> singleSeen = new HashSet<>(), listSeen = new HashSet<>();
            for (Map<String, Object> e : es) {
                String image = str(e.get("image"));
                if (!image.isEmpty()) {
                    int fixed = fixedImageIndex(image);
                    String key = fixed >= 0 ? image : image + "_" + num(e.get("elIndex"), 0);
                    if (fixed >= 0 && !singleSeen.add(key)) continue;
                    addSingle(f.singles, f.uniqueImages, seen, key, fixed, ImageCodec.single(readImg(imgDir, image), !(DEVICE_TYPE.equals("mi7pro") && "widge_pointer".equals(str(e.get("type"))))));
                }
            }
            for (Map<String, Object> e : es) {
                List<Object> il = arr(e.get("imageList"));
                if (il.isEmpty()) continue;
                String base = imageListBase(il);
                int fixed = fixedListIndex(base);
                String key = fixed >= 0 ? base : join(il) + "_" + num(e.get("elIndex"), 0);
                if (fixed >= 0 && !listSeen.add(key)) continue;
                ArrayList<BufferedImage> imgs = new ArrayList<>();
                for (Object n : il) imgs.add(readImg(imgDir, str(n)));
                addSingle(f.lists, f.uniqueImages, seen, key, fixed, ImageCodec.imageList(imgs, true));
            }
            for (Map<String, Object> e : es) {
                String jsName = str(e.get("jsFileName"));
                if (!jsName.isEmpty()) {
                    JSResourceBytes res = loadJSResource(imgDir, jsName);
                    addSingle(f.js, f.uniqueImages, seen, res.name + "_" + num(e.get("elIndex"), 0), -1, jsResource(res.name, res.bytes));
                }
                for (Object item : arr(e.get("jsImgList"))) {
                    String name = str(item);
                    if (name.isEmpty()) continue;
                    JSResourceBytes res = loadJSResource(imgDir, name);
                    addSingle(f.js, f.uniqueImages, seen, res.name + "_" + num(e.get("elIndex"), 0), -1, jsResource(res.name, res.bytes));
                }
            }
            addUnreferencedFixedResources(f, imgDir, singleSeen, listSeen, seen, allowedSingles, allowedLists);
            f.elementBytes = new byte[elementDefSize(es, f) + propSize(es, f)];
            return f;
        }

        static final class JSResourceBytes {
            String name;
            byte[] bytes;

            JSResourceBytes(String n, byte[] b) {
                this.name = n;
                this.bytes = b;
            }
        }

        static JSResourceBytes loadJSResource(Path imgDir, String name) throws IOException {
            Path p = imgDir.resolve(name);
            if (Files.exists(p)) {
                return new JSResourceBytes(name, Files.readAllBytes(p));
            }
            String base = name;
            int lastDot = name.lastIndexOf('.');
            if (lastDot > 0) {
                base = name.substring(0, lastDot);
            }
            Path pngPath = imgDir.resolve(base + ".png");
            if (Files.exists(pngPath)) {
                try {
                    BufferedImage img = ImageIO.read(pngPath.toFile());
                    if (img != null) {
                        byte[] compiled = ImageCodec.compileJSImage(img, name);
                        return new JSResourceBytes(name, compiled);
                    }
                } catch (Exception ex) {
                    System.err.println("Failed to compile JS image: " + pngPath + " " + ex.getMessage());
                }
            }
            if (!name.endsWith(".png")) {
                Path directPngPath = imgDir.resolve(name + ".png");
                if (Files.exists(directPngPath)) {
                    try {
                        BufferedImage img = ImageIO.read(directPngPath.toFile());
                        if (img != null) {
                            String targetName = name;
                            int judgeImgSign = ImageCodec.judgeJSImageSign(img);
                            if (judgeImgSign == 5) {
                                targetName = name + ".bin";
                            } else {
                                targetName = name + ".rle";
                            }
                            byte[] compiled = ImageCodec.compileJSImage(img, targetName);
                            return new JSResourceBytes(targetName, compiled);
                        }
                    } catch (Exception ex) {
                        System.err.println("Failed to compile JS image: " + directPngPath + " " + ex.getMessage());
                    }
                }
            }
            return new JSResourceBytes(name, new byte[0]);
        }

        static void addUnreferencedFixedResources(FaceData f, Path imgDir, Set<String> singleSeen, Set<String> listSeen, Set<String> md5Seen, Set<Integer> allowedSingles, Set<Integer> allowedLists) throws Exception {
            if (!Files.isDirectory(imgDir)) return;
            try (DirectoryStream<Path> ds = Files.newDirectoryStream(imgDir, "*.png")) {
                TreeSet<String> imageNames = new TreeSet<>(), listBases = new TreeSet<>();
                for (Path p : ds) {
                    String n = p.getFileName().toString();
                    if (n.endsWith(".png")) n = n.substring(0, n.length() - 4);
                    int imageIdx = fixedImageIndex(n);
                    if (imageIdx >= 0 && (allowedSingles == null || allowedSingles.contains(imageIdx)))
                        imageNames.add(n);
                    int u = n.lastIndexOf('_');
                    String base = u > 0 ? n.substring(0, u) : "";
                    int listIdx = fixedListIndex(base);
                    if (listIdx >= 0 && (allowedLists == null || allowedLists.contains(listIdx))) listBases.add(base);
                }
                for (String image : imageNames)
                    if (singleSeen.add(image))
                        addSingle(f.singles, f.uniqueImages, md5Seen, image, fixedImageIndex(image), ImageCodec.single(readImg(imgDir, image), true));
                for (String base : listBases)
                    if (listSeen.add(base)) {
                        ArrayList<BufferedImage> imgs = new ArrayList<>();
                        for (int i = 0; ; i++) {
                            Path p = imgDir.resolve(String.format("%s_%04d.png", base, i));
                            if (!Files.exists(p)) break;
                            imgs.add(readImg(imgDir, String.format("%s_%04d", base, i)));
                        }
                        if (!imgs.isEmpty())
                            addSingle(f.lists, f.uniqueImages, md5Seen, base, fixedListIndex(base), ImageCodec.imageList(imgs, true));
                    }
            }
        }

        static void loadExtraProp7(FaceData f, Object o) {
            loadExtraDefs(f.extraProp7, o);
            f.elementBytes = new byte[elementDefSize(f.elements, f) + propSize(f.elements, f)];
        }

        static void loadExtraJs(FaceData f, Object o, Path imgDir) throws Exception {
            for (Object item : arr(o)) {
                Map<String, Object> m = obj(item);
                String name = str(m.get("name"));
                byte[] raw = unhex(str(m.get("raw")));
                if (raw.length == 0 && !name.isEmpty()) {
                    JSResourceBytes res = loadJSResource(imgDir, name);
                    name = res.name;
                    raw = res.bytes;
                }
                ImgDef d = new ImgDef();
                d.idx = num(m.get("idx"), f.js.size() + f.extraJs.size());
                d.key = (name.isEmpty() ? "extra_js_" + d.idx : name) + "_extra_" + d.idx;
                d.bytes = jsResource(name.isEmpty() ? ("script_" + d.idx + ".bin") : name, raw);
                d.len = d.bytes.length;
                d.md5 = md5(d.bytes);
                f.extraJs.add(d);
                boolean seen = false;
                for (ImgDef u : f.uniqueImages) {
                    if (u.md5.equals(d.md5)) {
                        seen = true;
                        break;
                    }
                }
                if (!seen) f.uniqueImages.add(d);
            }
            f.elementBytes = new byte[elementDefSize(f.elements, f) + propSize(f.elements, f)];
        }

        static void loadExtraProp9(FaceData f, Object o) {
            loadExtraDefs(f.extraProp9, o);
            f.elementBytes = new byte[elementDefSize(f.elements, f) + propSize(f.elements, f)];
        }

        static void loadExtraProp8(FaceData f, Object o) {
            loadExtraDefs(f.extraProp8, o);
            f.elementBytes = new byte[elementDefSize(f.elements, f) + propSize(f.elements, f)];
        }

        static void loadExtraDefs(List<ExtraDef> out, Object o) {
            for (Object item : arr(o)) {
                Map<String, Object> m = obj(item);
                ExtraDef d = new ExtraDef();
                d.idx = num(m.get("idx"), out.size());
                d.bytes = unhex(str(m.get("raw")));
                d.len = d.bytes.length;
                out.add(d);
            }
        }

        static Set<Integer> intSet(Object o) {
            if (!(o instanceof List)) return null;
            LinkedHashSet<Integer> s = new LinkedHashSet<>();
            for (Object x : arr(o)) s.add(num(x, 0));
            return s;
        }

        static List<Integer> intList(Object o) {
            ArrayList<Integer> r = new ArrayList<>();
            if (!(o instanceof List)) return r;
            for (Object x : arr(o)) r.add(num(x, 0));
            return r;
        }

        static void reorderFixedDefs(List<ImgDef> defs, List<Integer> order) {
            if (defs.isEmpty() || order.isEmpty()) return;
            HashMap<Integer, Integer> pos = new HashMap<>();
            for (int i = 0; i < order.size(); i++) pos.putIfAbsent(order.get(i), i);
            defs.sort((a, b) -> {
                int pa = pos.getOrDefault(a.idx, Integer.MAX_VALUE);
                int pb = pos.getOrDefault(b.idx, Integer.MAX_VALUE);
                if (pa != pb) return Integer.compare(pa, pb);
                if (a.idx != b.idx) return Integer.compare(a.idx, b.idx);
                return a.key.compareTo(b.key);
            });
        }

        static void reorderUniqueImages(FaceData f) {
            if (f.uniqueImages.isEmpty()) return;
            LinkedHashMap<String, ImgDef> ordered = new LinkedHashMap<>();
            for (List<ImgDef> group : Arrays.asList(f.singles, f.lists, f.js, f.extraJs)) {
                for (ImgDef d : group) {
                    if (!ordered.containsKey(d.md5)) ordered.put(d.md5, d);
                }
            }
            for (ImgDef d : f.uniqueImages) {
                if (!ordered.containsKey(d.md5)) ordered.put(d.md5, d);
            }
            f.uniqueImages = new ArrayList<>(ordered.values());
        }

        static void addSingle(List<ImgDef> defs, List<ImgDef> uniques, Set<String> seen, String key, int idx, byte[] bytes) throws Exception {
            ImgDef d = new ImgDef();
            d.key = key;
            d.idx = idx;
            d.bytes = bytes;
            d.len = bytes.length;
            d.md5 = md5(bytes);
            defs.add(d);
            if (seen.add(d.md5)) uniques.add(d);
        }

        static int fixedImageIndex(String name) {
            if (name.matches("image_\\d{4}")) return Integer.parseInt(name.substring(6));
            return -1;
        }

        static int fixedListIndex(String base) {
            if (base.matches("imagelist_\\d{4}")) return Integer.parseInt(base.substring(10));
            return -1;
        }

        static String imageListBase(List<Object> names) {
            if (names.isEmpty()) return "";
            String n = str(names.get(0));
            int p = n.lastIndexOf('_');
            return p > 0 ? n.substring(0, p) : n;
        }

        static String join(List<Object> a) {
            StringBuilder s = new StringBuilder();
            for (int i = 0; i < a.size(); i++) {
                if (i > 0) s.append(',');
                s.append(str(a.get(i)));
            }
            return s.toString();
        }

        static BufferedImage readImg(Path dir, String name) throws IOException {
            ArrayList<Path> tries = new ArrayList<>();
            tries.add(dir.resolve(name));
            tries.add(dir.resolve(name + ".png"));
            for (Path p : tries) {
                if (!Files.exists(p)) continue;
                try (InputStream in = Files.newInputStream(p)) {
                    BufferedImage img = ImageIO.read(in);
                    if (img != null) return img;
                }
            }
            throw new IOException("Cannot read image: " + dir.resolve(name) + " or " + dir.resolve(name + ".png"));
        }

        static byte[] jsResource(String name, byte[] raw) {
            byte[] nb = name.getBytes(StandardCharsets.US_ASCII), h = new byte[0x14 + nb.length];
            BU.w24(h, 0, raw.length);
            h[3] = (byte) nb.length;
            System.arraycopy(nb, 0, h, 0x14, nb.length);
            return BU.concat(h, raw);
        }

        static int elementDefSize(List<Map<String, Object>> es, FaceData f) {
            return (filter0(es).size() + f.singles.size() + f.lists.size() + filterType(es, "element_anim").size() + f.js.size() + f.extraJs.size() + filterWidgets(es).size() + f.extraProp7.size() + filterEditableElements(es).size() + f.extraProp8.size() + filterProp9Elements(es).size() + f.extraProp9.size()) * 16;
        }

        static int propSize(List<Map<String, Object>> es, FaceData f) {
            int n = filter0(es).size() * 16 + filterType(es, "element_anim").size() * 12;
            for (Map<String, Object> e : filterWidgets(es)) n += prop7Size(e);
            for (Map<String, Object> e : filterEditableElements(es)) n += prop8Size(e);
            for (ExtraDef d : f.extraProp7) n += d.len;
            for (ExtraDef d : f.extraProp8) n += d.len;
            for (Map<String, Object> e : filterProp9Elements(es)) n += prop9Size(e);
            for (ExtraDef d : f.extraProp9) n += d.len;
            return n;
        }

        static List<Map<String, Object>> filter0(List<Map<String, Object>> es) {
            return es;
        }

        static void assignWidgetIndices(List<Map<String, Object>> elements, List<ExtraDef> extra) {
            HashSet<Integer> used = new HashSet<>();
            for (ExtraDef d : extra) used.add(d.idx);
            for (Map<String, Object> e : elements) {
                if (isWidget(e) && e.containsKey("prop7Index")) used.add(num(e.get("prop7Index"), 0));
            }
            int next = 0;
            for (Map<String, Object> e : elements) {
                if (isWidget(e) && !e.containsKey("prop7Index")) {
                    while (used.contains(next)) next++;
                    e.put("prop7Index", next);
                    used.add(next);
                }
            }
        }

        static void assignEditableIndices(List<Map<String, Object>> elements, List<ExtraDef> extra) {
            HashSet<Integer> used = new HashSet<>();
            for (ExtraDef d : extra) used.add(d.idx);
            for (Map<String, Object> e : elements) {
                if ("element_editable".equals(str(e.get("type"))) && e.containsKey("prop8Index"))
                    used.add(num(e.get("prop8Index"), 0));
            }
            int next = 0;
            for (Map<String, Object> e : elements) {
                if ("element_editable".equals(str(e.get("type"))) && !e.containsKey("prop8Index")) {
                    while (used.contains(next)) next++;
                    e.put("prop8Index", next);
                    used.add(next);
                }
            }
        }

        static List<Map<String, Object>> filterWidgets(List<Map<String, Object>> es) {
            ArrayList<Map<String, Object>> r = new ArrayList<>();
            for (Map<String, Object> e : es) if (isWidget(e)) r.add(e);
            return r;
        }

        static List<Map<String, Object>> filterEditableElements(List<Map<String, Object>> es) {
            ArrayList<Map<String, Object>> r = new ArrayList<>();
            for (Map<String, Object> e : es) if ("element_editable".equals(str(e.get("type")))) r.add(e);
            return r;
        }

        static boolean isProp9Element(Map<String, Object> e) {
            String type = str(e.get("type"));
            if (!str(e.get("jumpRaw")).isEmpty() || !str(e.get("prop9Raw")).isEmpty()) return true;
            if (!str(e.get("jumpCode")).isEmpty() && !str(e.get("jumpName")).isEmpty()) return true;
            if ("type_element_js".equals(type) && DEVICE_TYPE.equals("mi8")) return true;
            return "type_element_lua".equals(type) && bool(e.get("jumpFlag"));
        }

        static List<Map<String, Object>> filterProp9Elements(List<Map<String, Object>> es) {
            ArrayList<Map<String, Object>> r = new ArrayList<>();
            for (Map<String, Object> e : es)
                if (isProp9Element(e)) r.add(e);
            return r;
        }

        static List<Map<String, Object>> filterType(List<Map<String, Object>> es, String t) {
            ArrayList<Map<String, Object>> r = new ArrayList<>();
            for (Map<String, Object> e : es) if (t.equals(str(e.get("type")))) r.add(e);
            return r;
        }

        static int prop7Size(Map<String, Object> e) {
            int rawLen = num(e.get("prop7Length"), -1);
            if (rawLen > 0) return rawLen;
            String t = str(e.get("type"));
            if ("widge_pointer".equals(t)) return 0x20;
            if ("widge_process".equals(t)) return 0x28;
            if ("widge_imagelist".equals(t) && !arr(e.get("imageIndexList")).isEmpty())
                return 0x10 + arr(e.get("imageIndexList")).size() * 4;
            return 0x14;
        }

        static int prop8Size(Map<String, Object> e) {
            int rawLen = num(e.get("prop8Length"), -1);
            if (rawLen > 0) return rawLen;
            if (!arr(e.get("prop8Refs")).isEmpty()) return 4 + arr(e.get("prop8Refs")).size() * 4;
            if (!arr(e.get("editableConfigs")).isEmpty()) return 4 + arr(e.get("editableConfigs")).size() * 4;
            return unhex(str(e.get("prop8Raw"))).length;
        }

        static int prop9Size(Map<String, Object> e) {
            int rawLen = num(e.get("prop9Length"), -1);
            if (rawLen > 0) return rawLen;
            if ("type_element_js".equals(str(e.get("type"))) && DEVICE_TYPE.equals("mi8")) return 48;
            if (!arr(e.get("targetPairs")).isEmpty()) return 44 + arr(e.get("targetPairs")).size() * 8;
            return "01008223".equals(str(e.get("jumpCode"))) ? 56 : 52;
        }

        static byte[] buildFaceHeader(FaceData f, int start) {
            return buildFaceHeader(f, start, false);
        }

        // Official AOD dials (faceCount=2) set u32@+0 = 0x80000000 on BOTH face
        // records; 1-face dials leave it 0. Without it the firmware ignores the
        // AOD face entirely (v60-v62 "AOD 不显示" 根因之一).
        static byte[] buildFaceHeader(FaceData f, int start, boolean aodDial) {
            byte[] h = new byte[0x58];
            if (aodDial) BU.w32(h, 0, 0x80000000);
            int off = start;
            writeSec(h, 0x08, filter0(f.elements).size(), off);
            off += filter0(f.elements).size() * 16;
            writeSec(h, 0x10, 0, off);
            writeSec(h, 0x18, f.singles.size(), off);
            off += f.singles.size() * 16;
            writeSec(h, 0x20, f.lists.size(), off);
            off += f.lists.size() * 16;
            writeSec(h, 0x28, filterType(f.elements, "element_anim").size(), off);
            off += filterType(f.elements, "element_anim").size() * 16;
            writeSec(h, 0x30, f.js.size() + f.extraJs.size(), off);
            off += (f.js.size() + f.extraJs.size()) * 16;
            writeSec(h, 0x38, 0, off);
            writeSec(h, 0x40, filterWidgets(f.elements).size() + f.extraProp7.size(), off);
            off += (filterWidgets(f.elements).size() + f.extraProp7.size()) * 16;
            writeSec(h, 0x48, filterEditableElements(f.elements).size() + f.extraProp8.size(), off);
            off += (filterEditableElements(f.elements).size() + f.extraProp8.size()) * 16;
            writeSec(h, 0x50, filterProp9Elements(f.elements).size() + f.extraProp9.size(), off);
            return h;
        }

        static void writeSec(byte[] h, int o, int count, int off) {
            BU.w32(h, o, count);
            BU.w32(h, o + 4, off);
        }

        static Map<String, Integer> imageMap(int start, FaceData f) {
            HashMap<String, Integer> md = new HashMap<>();
            LinkedHashMap<String, Integer> m = new LinkedHashMap<>();
            int o = start;
            for (ImgDef u : f.uniqueImages) {
                md.put(u.md5, o);
                o += u.len;
            }
            for (List<ImgDef> l : Arrays.asList(f.singles, f.lists, f.js, f.extraJs))
                for (ImgDef d : l) m.put(d.key, md.get(d.md5));
            return m;
        }

        static int imageEnd(int start, FaceData f) {
            int o = start;
            for (ImgDef u : f.uniqueImages) o += u.len;
            return o;
        }

        static byte[] writeElements(FaceData f, Map<String, Integer> imgs, int start, int propStart) {
            int defSize = elementDefSize(f.elements, f), pos = 0, po = propStart;
            byte[] out = new byte[defSize + propSize(f.elements, f)];
            List<Map<String, Object>> base = filter0(f.elements), anim = filterType(f.elements, "element_anim"), widgets = filterWidgets(f.elements), editables = filterEditableElements(f.elements), jumps = filterProp9Elements(f.elements);
            for (int i = 0; i < base.size(); i++) {
                def(out, pos, i, 0, po, 16);
                pos += 16;
                po += 16;
            }
            for (int i = 0; i < f.singles.size(); i++) {
                ImgDef d = f.singles.get(i);
                def(out, pos, defIndex(d, i), 2, imgs.get(d.key), d.len);
                pos += 16;
            }
            for (int i = 0; i < f.lists.size(); i++) {
                ImgDef d = f.lists.get(i);
                def(out, pos, defIndex(d, i), 3, imgs.get(d.key), d.len);
                pos += 16;
            }
            for (int i = 0; i < anim.size(); i++) {
                def(out, pos, i, 4, po, 12);
                pos += 16;
                po += 12;
            }
            for (int i = 0; i < f.js.size(); i++) {
                ImgDef d = f.js.get(i);
                def(out, pos, defIndex(d, i), 5, imgs.get(d.key), d.len);
                pos += 16;
            }
            for (int i = 0; i < f.extraJs.size(); i++) {
                ImgDef d = f.extraJs.get(i);
                def(out, pos, defIndex(d, f.js.size() + i), 5, imgs.get(d.key), d.len);
                pos += 16;
            }
            for (int i = 0; i < widgets.size(); i++) {
                Map<String, Object> w = widgets.get(i);
                int sz = prop7Size(w);
                def(out, pos, num(w.get("prop7Index"), i), 7, po, sz);
                pos += 16;
                po += sz;
            }
            for (ExtraDef d : f.extraProp7) {
                def(out, pos, d.idx, 7, po, d.len);
                pos += 16;
                po += d.len;
            }
            for (int i = 0; i < editables.size(); i++) {
                Map<String, Object> editable = editables.get(i);
                int sz = prop8Size(editable);
                def(out, pos, num(editable.get("prop8Index"), i), 8, po, sz);
                pos += 16;
                po += sz;
            }
            for (ExtraDef d : f.extraProp8) {
                def(out, pos, d.idx, 8, po, d.len);
                pos += 16;
                po += d.len;
            }
            for (int i = 0; i < jumps.size(); i++) {
                Map<String, Object> jump = jumps.get(i);
                int sz = prop9Size(jump);
                def(out, pos, num(jump.get("prop9Index"), i), 9, po, sz);
                pos += 16;
                po += sz;
            }
            for (ExtraDef d : f.extraProp9) {
                def(out, pos, d.idx, 9, po, d.len);
                pos += 16;
                po += d.len;
            }
            int p = defSize;
            for (Map<String, Object> e : base) {
                writeProp0(out, p, e, f, anim, widgets, jumps);
                p += 16;
            }
            for (Map<String, Object> e : anim) {
                int idx = findList(f.lists, arr(e.get("imageList")), num(e.get("elIndex"), 0));
                BU.w24(out, p, idx);
                out[p + 3] = 3;
                BU.w16(out, p + 6, num(e.get("animInterval"), 72));
                BU.w16(out, p + 8, num(e.get("animRepeat"), 0));
                p += 12;
            }
            for (Map<String, Object> e : widgets) {
                byte[] b = prop7Bytes(e, f);
                System.arraycopy(b, 0, out, p, b.length);
                p += b.length;
            }
            for (ExtraDef d : f.extraProp7) {
                System.arraycopy(d.bytes, 0, out, p, d.len);
                p += d.len;
            }
            for (Map<String, Object> e : editables) {
                byte[] b = prop8Bytes(e);
                System.arraycopy(b, 0, out, p, b.length);
                p += b.length;
            }
            for (ExtraDef d : f.extraProp8) {
                System.arraycopy(d.bytes, 0, out, p, d.len);
                p += d.len;
            }
            for (Map<String, Object> e : jumps) {
                byte[] b = prop9Bytes(e, f);
                System.arraycopy(b, 0, out, p, b.length);
                p += b.length;
            }
            for (ExtraDef d : f.extraProp9) {
                System.arraycopy(d.bytes, 0, out, p, d.len);
                p += d.len;
            }
            return out;
        }

        static int faceProp7Offset(FaceData f, Map<String, Object> e) {
            Integer off = f.prop7ElementOffsets.get(e);
            return off == null ? 0 : off;
        }

        static int faceProp7Offset(FaceData f, ExtraDef d) {
            Integer off = f.prop7ExtraOffsets.get(d);
            return off == null ? 0 : off;
        }

        static int faceProp8Offset(FaceData f, ExtraDef d) {
            Integer off = f.prop8ExtraOffsets.get(d);
            return off == null ? 0 : off;
        }

        static int faceProp9Offset(FaceData f, Map<String, Object> e) {
            Integer off = f.prop9ElementOffsets.get(e);
            return off == null ? 0 : off;
        }

        static int faceProp9Offset(FaceData f, ExtraDef d) {
            Integer off = f.prop9ExtraOffsets.get(d);
            return off == null ? 0 : off;
        }

        static int defIndex(ImgDef d, int fallback) {
            return d.idx >= 0 ? d.idx : fallback;
        }

        static void def(byte[] b, int p, int i, int t, int off, int len) {
            BU.w16(b, p, i);
            b[p + 3] = (byte) t;
            BU.w32(b, p + 8, off);
            BU.w32(b, p + 12, len);
        }

        static void writeProp0(byte[] b, int p, Map<String, Object> e, FaceData f, List<Map<String, Object>> anim, List<Map<String, Object>> widgets, List<Map<String, Object>> jumps) {
            int t = 0, idx = 0;
            String type = str(e.get("type"));
            if (isWidget(e)) {
                t = 7;
                idx = num(e.get("prop7Index"), widgets.indexOf(e));
            } else if (jumps.contains(e)) {
                t = 9;
                idx = num(e.get("prop9Index"), jumps.indexOf(e));
            } else if ("element_editable".equals(type)) {
                t = 8;
                idx = num(e.get("prop8Index"), 0);
            } else if ("type_element_js".equals(type) || ("type_element_lua".equals(type) && !bool(e.get("jumpFlag")))) {
                t = 5;
                idx = findJs(f.js, str(e.get("jsFileName")), num(e.get("elIndex"), 0));
            } else if ("element_anim".equals(type)) {
                t = 4;
                idx = anim.indexOf(e);
            } else if ("element".equals(type)) {
                t = 2;
                idx = findSingle(f.singles, str(e.get("image")), num(e.get("elIndex"), 0));
            }
            BU.w24(b, p, idx);
            b[p + 3] = (byte) t;
            BU.w16(b, p + 4, num(e.get("x"), 0));
            BU.w16(b, p + 6, num(e.get("y"), 0));
        }

        static void writeProp7(byte[] b, int p, Map<String, Object> e, FaceData f) {
            byte[] raw = unhex(str(e.get("prop7Raw")));
            if (raw.length > 0) System.arraycopy(raw, 0, b, p, Math.min(raw.length, prop7Size(e)));
            byte[] ds = dataSrc(str(e.getOrDefault("dataSrc", "0000")));
            System.arraycopy(ds, 0, b, p, Math.min(3, ds.length));
            String type = str(e.get("type"));
            b[p + 3] = (byte) widgetType(e);
            if ("widge_dignum".equals(type) || "widge_imagelist".equals(type)) {
                // FIX: do NOT overwrite dataSrc 3rd byte (format code) with showCount.
                // showCount is a ROM-interpreted digit count; overriding b[p+2] corrupts
                // the dataSrc (e.g. 084103+showCount2 -> illegal 084102 -> whole-face jump).
                // v64 FIX: spacing 只属于 dignum（v58 真机取证：imagelist 的 b13 是
                // 0002 通道标志的一部分，被 spacing=0 覆写会导致弧/列表通道失效）。
                if ("widge_dignum".equals(type)) b[p + 13] = (byte) num(e.get("spacing"), 0);
                if (!str(e.get("image")).isEmpty()) {
                    BU.w24(b, p + 16, findSingle(f.singles, str(e.get("image")), num(e.get("elIndex"), 0)));
                    b[p + 19] = 2;
                }
                if (!arr(e.get("imageList")).isEmpty()) {
                    BU.w24(b, p + 8, findList(f.lists, arr(e.get("imageList")), num(e.get("elIndex"), 0)));
                    b[p + 11] = 3;
                }
                if ("widge_imagelist".equals(type) && !arr(e.get("imageIndexList")).isEmpty()) {
                    BU.w24(b, p + 12, 0x200);
                    List<Object> a = arr(e.get("imageIndexList"));
                    for (int i = 0; i < a.size(); i++) BU.w16(b, p + 16 + i * 4, num(a.get(i), 0));
                }
            } else if ("widge_pointer".equals(type)) {
                BU.w16(b, p + 6, Math.max(16, num(e.get("interval"), 1000)));
                BU.w24(b, p + 8, findSingle(f.singles, str(e.get("image")), num(e.get("elIndex"), 0)));
                b[p + 11] = 2;
                b[p + 17] = (byte) num(e.get("maxValue"), 0);
                BU.w16(b, p + 20, num(e.get("imageRotateX"), 0));
                BU.w16(b, p + 22, num(e.get("imageRotateY"), 0));
                b[p + 24] = (byte) num(e.get("pointerUnknow25"), 0);
                b[p + 25] = (byte) num(e.get("pointerUnknow26"), 0);
                BU.w16(b, p + 26, num(e.get("allAngle"), 360));
            } else if ("widge_process".equals(type)) {
                BU.w24(b, p + 8, findSingle(f.singles, str(e.get("image")), num(e.get("elIndex"), 0)));
                b[p + 11] = 2;
            }
        }

        static byte[] prop7Bytes(Map<String, Object> e, FaceData f) {
            byte[] b = new byte[prop7Size(e)];
            writeProp7(b, 0, e, f);
            return b;
        }

        static byte[] prop8Bytes(Map<String, Object> e) {
            int len = prop8Size(e);
            byte[] raw = unhex(str(e.get("prop8Raw")));
            if (raw.length > 0) return Arrays.copyOf(raw, Math.max(len, raw.length));
            byte[] b = new byte[len];
            List<Object> refs = !arr(e.get("prop8Refs")).isEmpty() ? arr(e.get("prop8Refs")) : arr(e.get("editableConfigs"));
            BU.w32(b, 0, refs.size());
            int p = 4;
            for (Object item : refs) {
                int idx;
                if (item instanceof Map) idx = num(obj(item).get("idx"), 0);
                else idx = num(item, 0);
                BU.w16(b, p, idx);
                b[p + 3] = 9;
                p += 4;
            }
            return b;
        }

        static void writeProp9(byte[] b, int p, Map<String, Object> e, FaceData f) {
            int len = prop9Size(e);
            String type = str(e.get("type"));
            byte[] raw = unhex(str(e.get("jumpRaw")));
            if (raw.length == 0) raw = unhex(str(e.get("prop9Raw")));
            if (raw.length > 0) System.arraycopy(raw, 0, b, p, Math.min(raw.length, len));
            if ("type_element_js".equals(type) && DEVICE_TYPE.equals("mi8") && len >= 48) {
                int img = findSingle(f.singles, str(e.get("image")), num(e.get("elIndex"), 0));
                if (!str(e.get("image")).isEmpty()) {
                    BU.w24(b, p + 32, img);
                    b[p + 35] = 2;
                }
                b[p + 40] = 0;
                b[p + 41] = 20;
                b[p + 42] = 114;
                b[p + 43] = 35;
                int js = findJs(f.js, str(e.get("jsFileName")), num(e.get("elIndex"), 0));
                BU.w24(b, p + 44, js);
                b[p + 47] = 5;
                return;
            }
            if (!arr(e.get("targetPairs")).isEmpty() && len >= 44) {
                List<Object> pairs = arr(e.get("targetPairs"));
                BU.w32(b, p + 40, pairs.size());
                int q = p + 44;
                for (Object item : pairs) {
                    Map<String, Object> m = obj(item);
                    BU.w16(b, q, num(m.get("x"), 0));
                    BU.w16(b, q + 2, num(m.get("y"), 0));
                    BU.w16(b, q + 4, num(m.get("groupIndex"), 0));
                    b[q + 7] = (byte) num(m.get("groupId"), 0);
                    q += 8;
                }
                return;
            }
            byte[] name = str(e.get("jumpName")).getBytes(StandardCharsets.UTF_8);
            if (name.length > 0) {
                Arrays.fill(b, p, p + Math.min(36, len), (byte) 0);
                System.arraycopy(name, 0, b, p, Math.min(name.length, Math.min(36, len)));
            }
            byte[] code = unhex(str(e.get("jumpCode")));
            if (code.length > 0 && len >= 44) System.arraycopy(code, 0, b, p + 40, Math.min(code.length, 4));
            int img = findSingle(f.singles, str(e.get("image")), num(e.get("elIndex"), 0));
            if (!str(e.get("image")).isEmpty()) {
                if (len >= 40) {
                    BU.w24(b, p + 36, img);
                    b[p + 39] = 2;
                }
                if (len >= 52) {
                    BU.w24(b, p + 48, img);
                    b[p + 51] = 2;
                }
            }
            String jumpCode = str(e.get("jumpCode"));
            if (len >= 56 && "01008223".equals(jumpCode)) {
                BU.w24(b, p + 52, 0);
                b[p + 55] = 5;
            }
        }

        static byte[] prop9Bytes(Map<String, Object> e, FaceData f) {
            byte[] b = new byte[prop9Size(e)];
            writeProp9(b, 0, e, f);
            return b;
        }

        static int widgetType(Map<String, Object> e) {
            String t = str(e.get("type"));
            if ("widge_dignum".equals(t))
                return 0x10 | ((bool(e.get("showZero")) ? 1 : 0) << 2) | num(e.get("align"), 0);
            if ("widge_imagelist".equals(t)) return 0x20;
            if ("widge_pointer".equals(t)) return 0x30;
            if ("widge_process".equals(t)) return 0x40;
            return 0;
        }

        static byte[] dataSrc(String hex) {
            byte[] r = new byte[3];
            for (int i = 0; i + 1 < hex.length() && i / 2 < 3; i += 2)
                r[i / 2] = (byte) Integer.parseInt(hex.substring(i, i + 2), 16);
            return r;
        }

        static String dataSrcHex(byte[] data, int p) {
            int b0 = BU.u8(data, p), b1 = BU.u8(data, p + 1), b2 = BU.u8(data, p + 2);
            return b2 == 0 ? String.format("%02X%02X", b0, b1) : String.format("%02X%02X%02X", b0, b1, b2);
        }

        static int findSingle(List<ImgDef> ds, String name, int el) {
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.equals(name)) return defIndex(ds.get(i), i);
            String k = name + "_" + el;
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.equals(k)) return defIndex(ds.get(i), i);
            return 0;
        }

        static int findList(List<ImgDef> ds, List<Object> names, int el) {
            String base = imageListBase(names);
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.equals(base)) return defIndex(ds.get(i), i);
            String k = join(names) + "_" + el;
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.equals(k)) return defIndex(ds.get(i), i);
            return 0;
        }

        static int findJs(List<ImgDef> ds, String name, int el) {
            String k = name + "_" + el;
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.equals(k)) return defIndex(ds.get(i), i);
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.equals(name)) return defIndex(ds.get(i), i);
            for (int i = 0; i < ds.size(); i++) if (ds.get(i).key.startsWith(name + "_")) return defIndex(ds.get(i), i);
            return 0;
        }
    }

    static final class WfUnpacker {
        static void unpack(Path bin, Path out) throws Exception {
            byte[] data = Files.readAllBytes(bin);
            Files.createDirectories(out.resolve("images"));
            Map<String, Object> wf = new LinkedHashMap<>();
            wf.put("name", BU.getWfName(data));
            wf.put("id", BU.ascii(data, 0x28, 9));
            wf.put("previewImg", "preview");
            int faceCount = Math.max(1, BU.i16(data, 0x1C));
            int previewOff = BU.i32(data, 0x20);
            int styleCount = Math.max(1, BU.i16(data, 0x1E));
            wf.put("faceStyleCount", styleCount);
            boolean namedFaces = hasNamedFaceRecords(data, faceCount);
            ImageIO.write(ImageCodec.readImageBlock(data, previewOff), "png", out.resolve("images/preview.png").toFile());
            ArrayList<Map<String, Object>> allFaces = new ArrayList<>();
            for (int i = 0; i < faceCount; i++) {
                boolean aodFace = isAodFaceIndex(i, styleCount, faceCount);
                String imageDirName = faceImageDir(i, aodFace);
                Path imgDir = out.resolve(imageDirName);
                Files.createDirectories(imgDir);
                int h = faceHeaderOffset(i, namedFaces);
                int facePreviewOff = BU.i32(data, h + 4);
                String facePreviewName = i == 0 ? "preview" : String.format("preview_face_%02d", i);
                if (facePreviewOff > 0 && facePreviewOff != previewOff)
                    ImageIO.write(ImageCodec.readImageBlock(data, facePreviewOff), "png", imgDir.resolve(facePreviewName + ".png").toFile());
                FaceRead face = readFace(data, h, imgDir, aodFace);
                if (!namedFaces) face.elements = simplifyLegacyElements(face.elements);
                Map<String, Object> faceJson = new LinkedHashMap<>();
                faceJson.put("name", readFaceName(data, h, i));
                faceJson.put("imageDir", imageDirName);
                if (facePreviewOff > 0 && facePreviewOff != previewOff) faceJson.put("previewImg", facePreviewName);
                faceJson.put("elements", face.elements);
                faceJson.put("imageDefs", face.imageDefs);
                faceJson.put("imageListDefs", face.imageListDefs);
                if (!face.extraJs.isEmpty()) faceJson.put("extraJs", face.extraJs);
                if (!face.extraProp7.isEmpty()) faceJson.put("extraProp7", face.extraProp7);
                if (!face.extraProp8.isEmpty()) faceJson.put("extraProp8", face.extraProp8);
                if (!face.extraProp9.isEmpty()) faceJson.put("extraProp9", face.extraProp9);
                allFaces.add(faceJson);
            }
            if (namedFaces) {
                wf.put("faces", allFaces);
            } else {
                boolean hasAnyAod = false;
                for (int i = 0; i < faceCount; i++) if (isAodFaceIndex(i, styleCount, faceCount)) hasAnyAod = true;

                FaceRead normal = readFace(data, faceHeaderOffset(0, namedFaces), out.resolve("images"), false);
                normal.elements = simplifyLegacyElements(normal.elements);
                wf.put("elementsNormal", normal.elements);
                if (!normal.extraProp7.isEmpty()) wf.put("extraProp7Normal", normal.extraProp7);
                if (!normal.extraProp8.isEmpty()) wf.put("extraProp8Normal", normal.extraProp8);
                if (!normal.extraProp9.isEmpty()) wf.put("extraProp9Normal", normal.extraProp9);
                if (!namedFaces || hasAnyAod) {
                    Files.createDirectories(out.resolve("images_aod"));
                    FaceRead aod = readFace(data, faceHeaderOffset(1, namedFaces), out.resolve("images_aod"), true);
                    aod.elements = simplifyLegacyElements(aod.elements);
                    wf.put("elementsAod", aod.elements);
                    if (!aod.extraProp7.isEmpty()) wf.put("extraProp7Aod", aod.extraProp7);
                    if (!aod.extraProp8.isEmpty()) wf.put("extraProp8Aod", aod.extraProp8);
                    if (!aod.extraProp9.isEmpty()) wf.put("extraProp9Aod", aod.extraProp9);
                } else wf.put("elementsAod", new ArrayList<>());
            }
            Files.write(out.resolve("wfDef.json"), Json.stringify(wf, 0).getBytes(StandardCharsets.UTF_8));
            System.out.println("Unpacked -> " + out);
        }

        static boolean isAodFaceIndex(int index, int styleCount, int faceCount) {
            if (faceCount <= styleCount) return false;
            if (index == 1) return faceCount > 1;
            return styleCount > 1 && index >= styleCount - 1;
        }

        static String readFaceName(byte[] data, int header, int index) {
            String name = BU.utf8(data, header + 0x58, 0x40);
            if (!name.isEmpty()) return name;
            return index == 0 ? "样式1" : String.format("样式%d", index + 1);
        }

        static boolean usesIndex256Images(byte[] data, int faceCount, boolean namedFaces) {
            for (int i = 0; i < faceCount; i++) {
                int h = faceHeaderOffset(i, namedFaces);
                for (int sec : new int[]{2, 3}) {
                    int c = BU.i32(data, h + 8 + sec * 8);
                    int o = BU.i32(data, h + 12 + sec * 8);
                    for (int j = 0; j < c; j++) {
                        int p = o + j * 16;
                        int img = BU.i32(data, p + 8);
                        if (img >= 0 && img < data.length && BU.u8(data, img) == 0x10) return true;
                    }
                }
            }
            return false;
        }

        static String faceImageDir(int index, boolean aodFace) {
            if (index == 0) return "images";
            if (index == 1 && aodFace) return "images_aod";
            return String.format(aodFace ? "images_aod_face_%02d" : "images_face_%02d", index);
        }

        static int faceHeaderOffset(int index, boolean named) {
            return 0xA8 + index * 0x58 + (named ? index * 0x48 : 0);
        }

        static ArrayList<String> readFaceNames(byte[] data, int faceCount) {
            ArrayList<String> names = new ArrayList<>();
            for (int i = 0; i < faceCount; i++) {
                names.add(BU.utf8(data, faceHeaderOffset(i, true) + 0x58, 0x40));
            }
            int styleCount = Math.max(faceCount, BU.i16(data, 0x1E));
            if (styleCount > faceCount) {
                for (int face = 0; face < faceCount; face++) {
                    for (int style = 2; style <= styleCount; style++) {
                        names.add("\u6837\u5F0F" + style);
                    }
                }
            }
            return names;
        }

        static boolean hasNamedFaceRecords(byte[] data, int faceCount) {
            int legacyEnd = 0xA8 + faceCount * 0x58;
            int namedEnd = 0xA8 + faceCount * (0x58 + 0x48);
            int firstElementOff = BU.i32(data, 0xA8 + 0x0C);
            if (faceCount > 1 && looksLikeFaceHeader(data, 0xA8 + 0x58 + 0x48)) return true;
            return firstElementOff >= namedEnd && namedEnd <= data.length && firstElementOff > legacyEnd;
        }

        static boolean looksLikeFaceHeader(byte[] data, int h) {
            if (h + 0x58 > data.length) return false;
            if (BU.u8(data, h + 3) != 0x80 && BU.u8(data, h + 3) != 0) return false;
            int last = 0;
            for (int off = 8; off <= 0x50; off += 8) {
                int count = BU.i32(data, h + off), ptr = BU.i32(data, h + off + 4);
                if (count > 0 && (ptr < 0xA8 || ptr >= data.length)) return false;
                if (ptr != 0 && ptr < last) return false;
                if (ptr != 0) last = ptr;
            }
            return true;
        }

        static final class Def {
            int idx, type, off, len;
            byte[] bytes;
        }

        static final class FaceRead {
            List<Map<String, Object>> elements = new ArrayList<>();
            List<Map<String, Object>> extraJs = new ArrayList<>();
            List<Map<String, Object>> extraProp7 = new ArrayList<>();
            List<Map<String, Object>> extraProp8 = new ArrayList<>();
            List<Map<String, Object>> extraProp9 = new ArrayList<>();
            List<Integer> imageDefs = new ArrayList<>();
            List<Integer> imageListDefs = new ArrayList<>();
        }

        static final class JsRead {
            String name;
            byte[] raw;
        }

        static final class Prop9Read {
            String kind = "";
            List<Map<String, Object>> targets = new ArrayList<>();
            String image = "";
            String jsFileName = "";
        }

        static FaceRead readFace(byte[] data, int h, Path imgDir, boolean aod) throws Exception {
            int c0 = BU.i32(data, h + 8), o0 = BU.i32(data, h + 12), c2 = BU.i32(data, h + 0x18), o2 = BU.i32(data, h + 0x1C), c3 = BU.i32(data, h + 0x20), o3 = BU.i32(data, h + 0x24), c4 = BU.i32(data, h + 0x28), o4 = BU.i32(data, h + 0x2C), c5 = BU.i32(data, h + 0x30), o5 = BU.i32(data, h + 0x34), c7 = BU.i32(data, h + 0x40), o7 = BU.i32(data, h + 0x44), c8 = BU.i32(data, h + 0x48), o8 = BU.i32(data, h + 0x4C), c9 = BU.i32(data, h + 0x50), o9 = BU.i32(data, h + 0x54);
            ArrayList<Def> d0 = defs(data, o0, c0), d2 = defs(data, o2, c2), d3 = defs(data, o3, c3), d4 = defs(data, o4, c4), d5 = defs(data, o5, c5), d7 = defs(data, o7, c7), d8 = defs(data, o8, c8), d9 = defs(data, o9, c9);
            Map<Integer, String> singleNames = new LinkedHashMap<>(), listNames = new LinkedHashMap<>();
            Map<Integer, Integer> listCounts = new LinkedHashMap<>();
            Map<Integer, String> jsNames = new LinkedHashMap<>();
            Map<Integer, Def> m4 = defMap(d4), m5 = defMap(d5), m7 = defMap(d7), m8 = defMap(d8), m9 = defMap(d9);
            HashSet<Integer> used5 = new HashSet<>(), used7 = new HashSet<>(), used8 = new HashSet<>(), used9 = new HashSet<>();
            for (Def d : d2) {
                String n = String.format("image_%04d", d.idx);
                singleNames.put(d.idx, n);
                ImageIO.write(ImageCodec.readImageBlock(data, d.off), "png", imgDir.resolve(n + ".png").toFile());
            }
            for (Def d : d3) {
                String base = String.format("imagelist_%04d", d.idx);
                listNames.put(d.idx, base);
                List<BufferedImage> imgs = ImageCodec.readImageListBlock(data, d.off);
                listCounts.put(d.idx, imgs.size());
                for (int j = 0; j < imgs.size(); j++)
                    ImageIO.write(imgs.get(j), "png", imgDir.resolve(String.format("%s_%04d.png", base, j)).toFile());
            }
            FaceRead fr = new FaceRead();
            for (Def d : d2) fr.imageDefs.add(d.idx);
            for (Def d : d3) fr.imageListDefs.add(d.idx);
            for (Def d : d5) {
                JsRead js = parseJsResource(data, d.off, d.len);
                jsNames.put(d.idx, js.name);
            }
            for (Def d : d0) {
                Map<String, Object> e = new LinkedHashMap<>();
                int p = d.off;
                int ref = BU.i24(data, p), rt = BU.u8(data, p + 3);
                e.put("x", BU.i16(data, p + 4));
                e.put("y", BU.i16(data, p + 6));
                if (rt == 2) {
                    e.put("type", "element");
                    if (singleNames.containsKey(ref)) e.put("image", singleNames.get(ref));
                } else if (rt == 4) {
                    e.put("type", "element_anim");
                    Def ad = m4.get(ref);
                    if (ad != null) readAnim(data, ad.off, e, listNames, listCounts);
                } else if (rt == 5) {
                    used5.add(ref);
                    Def jd = m5.get(ref);
                    if (jd != null) readJs(data, jd.off, jd.len, e, imgDir);
                    String jsType = str(e.get("type"));
                    if (jsType.isEmpty()) e.put("type", "type_element_js");
                } else if (rt == 7) {
                    used7.add(ref);
                    e.put("prop7Index", ref);
                    Def wd = m7.get(ref);
                    if (wd != null) readWidget(data, wd.idx, wd.off, wd.len, e, singleNames, listNames, listCounts);
                    else e.put("type", "widge_dignum");
                } else if (rt == 8) {
                    used8.add(ref);
                    e.put("type", "element_editable");
                    e.put("prop8Index", ref);
                    Def ed = m8.get(ref);
                    if (ed != null) readEditable(data, ed.off, ed.len, e, m9, singleNames, jsNames);
                } else if (rt == 9) {
                    used9.add(ref);
                    e.put("prop9Index", ref);
                    Def jd = m9.get(ref);
                    if (jd != null) readProp9Def(data, jd.off, jd.len, e, singleNames, jsNames);
                    if (str(e.get("type")).isEmpty()) e.put("type", "element");
                } else e.put("type", "element");
                fr.elements.add(e);
            }
            for (Def d : d5)
                if (!used5.contains(d.idx)) {
                    JsRead js = parseJsResource(data, d.off, d.len);
                    if (js.raw.length > 0) Files.write(imgDir.resolve(js.name), js.raw);
                    Map<String, Object> extra = new LinkedHashMap<>();
                    extra.put("idx", d.idx);
                    extra.put("name", js.name);
                    extra.put("raw", hex(js.raw));
                    fr.extraJs.add(extra);
                }
            for (Def d : d7)
                if (!used7.contains(d.idx)) {
                    Map<String, Object> extra = new LinkedHashMap<>();
                    extra.put("idx", d.idx);
                    extra.put("raw", hex(BU.slice(data, d.off, d.len)));
                    fr.extraProp7.add(extra);
                }
            for (Def d : d8)
                if (!used8.contains(d.idx)) {
                    Map<String, Object> extra = new LinkedHashMap<>();
                    extra.put("idx", d.idx);
                    extra.put("raw", hex(BU.slice(data, d.off, d.len)));
                    fr.extraProp8.add(extra);
                }
            for (Def d : d9)
                if (!used9.contains(d.idx)) {
                    Map<String, Object> extra = new LinkedHashMap<>();
                    extra.put("idx", d.idx);
                    extra.put("raw", hex(BU.slice(data, d.off, d.len)));
                    fr.extraProp9.add(extra);
                }
            return fr;
        }

        static ArrayList<Def> defs(byte[] data, int off, int count) {
            ArrayList<Def> r = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                Def d = new Def();
                int p = off + i * 16;
                d.idx = BU.i16(data, p);
                d.type = BU.u8(data, p + 3);
                d.off = BU.i32(data, p + 8);
                d.len = BU.i32(data, p + 12);
                r.add(d);
            }
            return r;
        }

        static Map<Integer, Def> defMap(List<Def> defs) {
            Map<Integer, Def> m = new LinkedHashMap<>();
            for (Def d : defs) m.put(d.idx, d);
            return m;
        }

        static void readAnim(byte[] data, int p, Map<String, Object> e, Map<Integer, String> lists, Map<Integer, Integer> counts) {
            int idx = BU.i24(data, p);
            e.put("imageList", expandList(idx, lists, counts));
            e.put("animInterval", BU.i16(data, p + 6));
            e.put("animRepeat", BU.i16(data, p + 8));
        }

        static void readWidget(byte[] data, int idx, int p, int len, Map<String, Object> e, Map<Integer, String> singles, Map<Integer, String> lists, Map<Integer, Integer> counts) {
            e.put("prop7Length", len);
            e.put("prop7Raw", hex(BU.slice(data, p, len)));
            int wt = BU.u8(data, p + 3) & 0xF0;
            e.put("dataSrc", WfPacker.dataSrcHex(data, p));
            if (wt == 0x10) {
                e.put("type", "widge_dignum");
                e.put("showZero", ((BU.u8(data, p + 3) >> 2) & 1) == 1);
                e.put("align", BU.u8(data, p + 3) & 3);
                e.put("showCount", BU.u8(data, p + 2));
                e.put("spacing", BU.u8(data, p + 13));
                int li = BU.i24(data, p + 8);
                if (BU.u8(data, p + 11) == 3) e.put("imageList", expandList(li, lists, counts));
                int si = BU.i24(data, p + 16);
                if (BU.u8(data, p + 19) == 2 && singles.containsKey(si)) e.put("image", singles.get(si));
            } else if (wt == 0x20) {
                e.put("type", "widge_imagelist");
                int li = BU.i24(data, p + 8);
                if (BU.u8(data, p + 11) == 3) e.put("imageList", expandList(li, lists, counts));
                ArrayList<Integer> imageIndexList = new ArrayList<>();
                for (int q = p + 16; q + 1 < p + len; q += 4) imageIndexList.add(BU.i16(data, q));
                e.put("imageIndexList", imageIndexList);
            } else if (wt == 0x30) {
                e.put("type", "widge_pointer");
                e.put("interval", BU.i16(data, p + 6));
                int si = BU.i24(data, p + 8);
                if (BU.u8(data, p + 11) == 2 && singles.containsKey(si)) e.put("image", singles.get(si));
                e.put("maxValue", BU.u8(data, p + 17));
                e.put("imageRotateX", BU.i16(data, p + 20));
                e.put("imageRotateY", BU.i16(data, p + 22));
                e.put("pointerUnknow25", BU.u8(data, p + 24));
                e.put("pointerUnknow26", BU.u8(data, p + 25));
                e.put("allAngle", BU.i16(data, p + 26));
            } else {
                e.put("type", "widge_process");
                int si = BU.i24(data, p + 8);
                if (BU.u8(data, p + 11) == 2 && singles.containsKey(si)) e.put("image", singles.get(si));
            }
        }

        static void readEditable(byte[] data, int p, int len, Map<String, Object> e, Map<Integer, Def> prop9Defs, Map<Integer, String> singles, Map<Integer, String> jsNames) {
            e.put("prop8Length", len);
            e.put("prop8Raw", hex(BU.slice(data, p, len)));
            if (len < 4) return;
            int count = BU.u8(data, p);
            ArrayList<Integer> refs = new ArrayList<>();
            ArrayList<Map<String, Object>> configs = new ArrayList<>();
            int q = p + 4;
            for (int i = 0; i < count && q + 3 < p + len; i++, q += 4) {
                int idx = BU.i16(data, q);
                int type = BU.u8(data, q + 3);
                refs.add(idx);
                if (type != 9) continue;
                Def d = prop9Defs.get(idx);
                if (d == null) continue;
                LinkedHashMap<String, Object> cfg = new LinkedHashMap<>();
                cfg.put("idx", idx);
                cfg.put("raw", hex(BU.slice(data, d.off, d.len)));
                Prop9Read pr = parseProp9(data, d.off, d.len, singles, jsNames);
                if ("editableTargets".equals(pr.kind)) {
                    cfg.put("kind", pr.kind);
                    cfg.put("targetPairs", pr.targets);
                } else if ("jsBinding".equals(pr.kind)) {
                    cfg.put("kind", pr.kind);
                    if (!pr.image.isEmpty()) cfg.put("image", pr.image);
                    if (!pr.jsFileName.isEmpty()) cfg.put("jsFileName", pr.jsFileName);
                }
                configs.add(cfg);
            }
            e.put("prop8Refs", refs);
            if (!configs.isEmpty()) e.put("editableConfigs", configs);
        }

        static List<Map<String, Object>> simplifyLegacyElements(List<Map<String, Object>> elements) {
            ArrayList<Map<String, Object>> out = new ArrayList<>();
            for (Map<String, Object> e : elements) {
                LinkedHashMap<String, Object> m = new LinkedHashMap<>();
                String type = str(e.get("type"));
                m.put("type", type);
                m.put("x", num(e.get("x"), 0));
                m.put("y", num(e.get("y"), 0));
                if ("element".equals(type)) {
                    if (!str(e.get("image")).isEmpty()) m.put("image", e.get("image"));
                } else if ("element_anim".equals(type)) {
                    if (!arr(e.get("imageList")).isEmpty()) m.put("imageList", e.get("imageList"));
                    m.put("animInterval", num(e.get("animInterval"), 72));
                    m.put("animRepeat", num(e.get("animRepeat"), 0));
                } else if ("widge_imagelist".equals(type)) {
                    m.put("dataSrc", str(e.get("dataSrc")));
                    if (!arr(e.get("imageList")).isEmpty()) m.put("imageList", e.get("imageList"));
                    if (!arr(e.get("imageIndexList")).isEmpty()) m.put("imageIndexList", e.get("imageIndexList"));
                } else if ("widge_dignum".equals(type)) {
                    m.put("showCount", num(e.get("showCount"), 1));
                    m.put("spacing", num(e.get("spacing"), 0));
                    m.put("align", num(e.get("align"), 0));
                    m.put("showZero", bool(e.get("showZero")));
                    m.put("dataSrc", str(e.get("dataSrc")));
                    if (!arr(e.get("imageList")).isEmpty()) m.put("imageList", e.get("imageList"));
                    if (!str(e.get("image")).isEmpty()) m.put("image", e.get("image"));
                } else if ("widge_pointer".equals(type)) {
                    m.put("dataSrc", str(e.get("dataSrc")));
                    if (!str(e.get("image")).isEmpty()) m.put("image", e.get("image"));
                    m.put("interval", num(e.get("interval"), 1000));
                    m.put("maxValue", num(e.get("maxValue"), 0));
                    m.put("imageRotateX", num(e.get("imageRotateX"), 0));
                    m.put("imageRotateY", num(e.get("imageRotateY"), 0));
                    m.put("pointerUnknow25", num(e.get("pointerUnknow25"), 0));
                    m.put("pointerUnknow26", num(e.get("pointerUnknow26"), 0));
                    m.put("allAngle", num(e.get("allAngle"), 0));
                } else if ("widge_process".equals(type)) {
                    m.put("dataSrc", str(e.get("dataSrc")));
                    if (!str(e.get("image")).isEmpty()) m.put("image", e.get("image"));
                } else {
                    m.putAll(e);
                }
                out.add(m);
            }
            return out;
        }

        static Prop9Read parseProp9(byte[] data, int p, int len, Map<Integer, String> singles, Map<Integer, String> jsNames) {
            Prop9Read r = new Prop9Read();
            if (len == 48 && BU.u8(data, p + 41) == 20 && BU.u8(data, p + 42) == 114 && BU.u8(data, p + 43) == 35) {
                r.kind = "jsBinding";
                int si = BU.u8(data, p + 35) == 2 ? BU.i24(data, p + 32) : -1;
                int ji = BU.u8(data, p + 47) == 5 ? BU.i24(data, p + 44) : -1;
                if (singles.containsKey(si)) r.image = singles.get(si);
                if (jsNames.containsKey(ji)) r.jsFileName = jsNames.get(ji);
                return r;
            }
            if (len >= 44) {
                int count = BU.i32(data, p + 40);
                if (count >= 0 && 44 + count * 8 == len) {
                    r.kind = "editableTargets";
                    int q = p + 44;
                    for (int i = 0; i < count; i++, q += 8) {
                        LinkedHashMap<String, Object> m = new LinkedHashMap<>();
                        m.put("x", BU.i16(data, q));
                        m.put("y", BU.i16(data, q + 2));
                        m.put("groupIndex", BU.i16(data, q + 4));
                        m.put("groupId", BU.u8(data, q + 7));
                        r.targets.add(m);
                    }
                }
            }
            return r;
        }

        static void readProp9Def(byte[] data, int p, int len, Map<String, Object> e, Map<Integer, String> singles, Map<Integer, String> jsNames) {
            e.put("prop9Length", len);
            Prop9Read pr = parseProp9(data, p, len, singles, jsNames);
            if ("jsBinding".equals(pr.kind)) {
                e.put("type", "type_element_js");
                e.put("prop9Raw", hex(BU.slice(data, p, len)));
                if (!pr.image.isEmpty()) e.put("image", pr.image);
                if (!pr.jsFileName.isEmpty()) e.put("jsFileName", pr.jsFileName);
                return;
            }
            if ("editableTargets".equals(pr.kind)) {
                e.put("prop9Raw", hex(BU.slice(data, p, len)));
                e.put("targetPairs", pr.targets);
                return;
            }
            e.put("jumpRaw", hex(BU.slice(data, p, len)));
            e.put("jumpName", BU.utf8(data, p, Math.min(36, len)));
            if (len >= 44) e.put("jumpCode", hex(BU.slice(data, p + 40, 4)));
            int si = -1;
            if (len >= 52 && BU.u8(data, p + 51) == 2) si = BU.i24(data, p + 48);
            else if (len >= 40 && BU.u8(data, p + 39) == 2) si = BU.i24(data, p + 36);
            if (singles.containsKey(si)) e.put("image", singles.get(si));
        }

        static void readJump(byte[] data, int p, int len, Map<String, Object> e, Map<Integer, String> singles) {
            readProp9Def(data, p, len, e, singles, new LinkedHashMap<>());
        }

        static void readJs(byte[] data, int p, int len, Map<String, Object> e, Path imgDir) throws Exception {
            JsRead js = parseJsResource(data, p, len);
            e.put("jsFileName", js.name);
            if (str(e.get("type")).isEmpty())
                e.put("type", js.name.toLowerCase(Locale.ROOT).endsWith(".lua") ? "type_element_lua" : "type_element_js");
            if (js.raw.length > 0) Files.write(imgDir.resolve(js.name), js.raw);
        }

        static JsRead parseJsResource(byte[] data, int p, int len) {
            JsRead js = new JsRead();
            int rawLen = len >= 3 ? BU.i24(data, p) : 0;
            int nameLen = len >= 4 ? BU.u8(data, p + 3) : 0;
            int nameOff = p + 0x14;
            int maxNameLen = Math.max(0, Math.min(nameLen, p + len - nameOff));
            js.name = maxNameLen > 0 ? new String(data, nameOff, maxNameLen, StandardCharsets.US_ASCII) : "script_" + p + ".bin";
            int rawOff = nameOff + maxNameLen;
            int maxRawLen = Math.max(0, Math.min(rawLen, p + len - rawOff));
            js.raw = maxRawLen > 0 ? BU.slice(data, rawOff, maxRawLen) : new byte[0];
            return js;
        }

        static ArrayList<String> expandList(int li, Map<Integer, String> lists, Map<Integer, Integer> counts) {
            ArrayList<String> a = new ArrayList<>();
            String base = lists.containsKey(li) ? lists.get(li) : "imagelist_" + li;
            int count = counts.containsKey(li) ? counts.get(li) : 10;
            for (int i = 0; i < count; i++) a.add(String.format("%s_%04d", base, i));
            return a;
        }
    }

    static final class Json {
        final String s;
        int p;

        Json(String s) {
            this.s = s;
        }

        static Object parse(String s) {
            return new Json(s).value();
        }

        void ws() {
            while (p < s.length() && Character.isWhitespace(s.charAt(p))) p++;
        }

        Object value() {
            ws();
            if (p >= s.length()) return null;
            char c = s.charAt(p);
            if (c == '{') return object();
            if (c == '[') return array();
            if (c == '"') return string();
            if (c == 't' || c == 'f') return boolv();
            if (c == 'n') {
                p += 4;
                return null;
            }
            return number();
        }

        Map<String, Object> object() {
            LinkedHashMap<String, Object> m = new LinkedHashMap<>();
            p++;
            ws();
            if (s.charAt(p) == '}') {
                p++;
                return m;
            }
            while (true) {
                ws();
                String k = string();
                ws();
                p++;
                Object v = value();
                m.put(k, v);
                ws();
                char c = s.charAt(p++);
                if (c == '}') break;
            }
            return m;
        }

        List<Object> array() {
            ArrayList<Object> a = new ArrayList<>();
            p++;
            ws();
            if (s.charAt(p) == ']') {
                p++;
                return a;
            }
            while (true) {
                ws();
                a.add(value());
                ws();
                char c = s.charAt(p++);
                if (c == ']') break;
            }
            return a;
        }

        String string() {
            StringBuilder b = new StringBuilder();
            p++;
            while (p < s.length()) {
                char c = s.charAt(p++);
                if (c == '"') break;
                if (c == '\\') {
                    char e = s.charAt(p++);
                    if (e == 'n') b.append('\n');
                    else if (e == 'r') b.append('\r');
                    else if (e == 't') b.append('\t');
                    else if (e == 'u') {
                        b.append((char) Integer.parseInt(s.substring(p, p + 4), 16));
                        p += 4;
                    } else b.append(e);
                } else b.append(c);
            }
            return b.toString();
        }

        Boolean boolv() {
            if (s.startsWith("true", p)) {
                p += 4;
                return true;
            }
            p += 5;
            return false;
        }

        Number number() {
            int st = p;
            while (p < s.length() && "-+.0123456789eE".indexOf(s.charAt(p)) >= 0) p++;
            String n = s.substring(st, p);
            if (n.isEmpty())
                throw new IllegalArgumentException("Invalid JSON token at " + st + ": " + s.substring(st, Math.min(s.length(), st + 20)).replace("\n", "\\n"));
            return (n.contains(".") || n.contains("e") || n.contains("E")) ? Double.parseDouble(n) : Long.parseLong(n);
        }

        static String stringify(Object o, int ind) {
            StringBuilder b = new StringBuilder();
            write(b, o, ind);
            return b.toString();
        }

        static void write(StringBuilder b, Object o, int ind) {
            if (o == null) b.append("null");
            else if (o instanceof String) b.append('"').append(esc((String) o)).append('"');
            else if (o instanceof Number || o instanceof Boolean) b.append(o);
            else if (o instanceof Map) {
                b.append("{\n");
                int i = 0;
                for (Object en : ((Map<?, ?>) o).entrySet()) {
                    Map.Entry<?, ?> e = (Map.Entry<?, ?>) en;
                    pad(b, ind + 2);
                    write(b, String.valueOf(e.getKey()), ind + 2);
                    b.append(": ");
                    write(b, e.getValue(), ind + 2);
                    if (++i < ((Map<?, ?>) o).size()) b.append(',');
                    b.append('\n');
                }
                pad(b, ind);
                b.append('}');
            } else if (o instanceof Iterable) {
                b.append("[\n");
                ArrayList<Object> a = new ArrayList<>();
                for (Object x : (Iterable<?>) o) a.add(x);
                for (int i = 0; i < a.size(); i++) {
                    pad(b, ind + 2);
                    write(b, a.get(i), ind + 2);
                    if (i + 1 < a.size()) b.append(',');
                    b.append('\n');
                }
                pad(b, ind);
                b.append(']');
            }
        }

        static void pad(StringBuilder b, int n) {
            for (int i = 0; i < n; i++) b.append(' ');
        }

        static String esc(String s) {
            return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
        }
    }
}

