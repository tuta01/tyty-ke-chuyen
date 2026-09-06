#!/usr/bin/env python3
"""Dựng ảnh bìa cho video truyện audio — bản ngang YouTube và bản dọc TikTok.

Bám theo công thức của các kênh cùng thể loại: nền pastel, tên kênh trên đầu,
tiêu đề chữ to xếp nhiều dòng với vài chữ đổi màu để bắt mắt, chân dung nhân vật
hai bên, nhãn TRUYỆN AUDIO ở chân.

Đánh dấu chữ cần tô đỏ bằng *sao*:
    "Xuyên thành nữ phụ ác độc, ta chỉ muốn *nằm thẳng*"

Dùng:
    python scripts/make_thumbnail.py "Tiêu đề *nhấn mạnh*" out/thumb.jpg
    python scripts/make_thumbnail.py "..." out/cover.jpg --size tiktok
    python scripts/make_thumbnail.py "..." out/thumb.jpg --portrait a.png b.png

Không có ảnh chân dung thì hai panel bên vẫn được lấp bằng nền hoa văn, ảnh vẫn
dùng được — đỡ phải chờ có ảnh mới ra bìa.
"""
import re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CHANNEL = "TỶ TỶ KỂ CHUYỆN"
LABEL = "TRUYỆN AUDIO"

SIZES = {"youtube": (1280, 720), "tiktok": (1080, 1920)}
INK = (38, 30, 46)
ACCENT = (206, 42, 78)
CREAM = (255, 247, 244)
PINK_TOP = (252, 226, 232)
PINK_BOT = (243, 205, 220)

FONTS = ["/Library/Fonts/Arial Unicode.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def font(size):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def opt(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def gradient(w, h):
    """Nền dọc pastel + vài đốm sáng mờ cho đỡ phẳng."""
    bg = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line([(0, y), (w, y)],
               fill=tuple(round(a + (b - a) * t) for a, b in zip(PINK_TOP, PINK_BOT)))
    # Vài quầng sáng mờ cho nền đỡ phẳng
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for cx, cy, r in [(w * 0.20, h * 0.16, w * 0.20), (w * 0.82, h * 0.28, w * 0.15),
                      (w * 0.34, h * 0.90, w * 0.22)]:
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 252, 250))
    return Image.blend(bg, glow.filter(ImageFilter.GaussianBlur(w // 10)), 0.22)


def panel(img, box, src):
    """Dán ảnh chân dung vào ô, cắt phủ kín; không có ảnh thì để nền mờ."""
    x0, y0, x1, y1 = box
    pw, ph = x1 - x0, y1 - y0
    if src and Path(src).exists():
        p = Image.open(src).convert("RGB")
        s = max(pw / p.width, ph / p.height)
        p = p.resize((max(1, round(p.width * s)), max(1, round(p.height * s))), Image.LANCZOS)
        p = p.crop(((p.width - pw) // 2, 0, (p.width - pw) // 2 + pw, ph))
    else:
        p = img.crop(box).filter(ImageFilter.GaussianBlur(18))
        ImageDraw.Draw(p).rectangle([0, 0, pw, ph], outline=(255, 255, 255, 90), width=4)
    img.paste(p, (x0, y0))


def segments(line):
    """Tách '*abc*' thành các mảnh (chữ, có_nhấn_mạnh)."""
    return [(t.strip("*"), t.startswith("*")) for t in re.split(r"(\*[^*]+\*)", line) if t]


def wrap(d, title, fnt, max_w):
    """Xuống dòng theo bề rộng, giữ nguyên dấu * của từ được nhấn."""
    out, cur = [], ""
    for word in title.split():
        test = f"{cur} {word}".strip()
        if d.textlength(test.replace("*", ""), font=fnt) <= max_w or not cur:
            cur = test
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def draw_line(d, x, y, line, fnt, stroke):
    for txt, hot in segments(line):
        d.text((x, y), txt, font=fnt, fill=ACCENT if hot else INK,
               stroke_width=stroke, stroke_fill=CREAM)
        x += d.textlength(txt, font=fnt)


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    for flag in ("--size", "--channel"):
        if flag in sys.argv:
            v = sys.argv[sys.argv.index(flag) + 1]
            if v in pos:
                pos.remove(v)
    portraits = []
    if "--portrait" in sys.argv:
        for a in sys.argv[sys.argv.index("--portrait") + 1:]:
            if a.startswith("--"):
                break
            portraits.append(a)
            if a in pos:
                pos.remove(a)

    title = pos[0]
    dst = Path(pos[1] if len(pos) > 1 else "out/thumb.jpg")
    size = opt("--size", "youtube")
    channel = opt("--channel", CHANNEL)
    W, H = SIZES[size]
    tall = size == "tiktok"

    img = gradient(W, H).convert("RGB")

    # Hai panel chân dung: ngang thì đặt hai bên, dọc thì đặt trên và dưới.
    if tall:
        panel(img, (0, 0, W, round(H * 0.30)), portraits[0] if portraits else None)
        panel(img, (0, round(H * 0.74), W, H), portraits[1] if len(portraits) > 1 else None)
        band = (round(H * 0.30), round(H * 0.74))
    else:
        pw = round(W * 0.24)
        panel(img, (0, 0, pw, H), portraits[0] if portraits else None)
        panel(img, (W - pw, 0, W, H), portraits[1] if len(portraits) > 1 else None)
        band = (0, H)

    d = ImageDraw.Draw(img)
    inner_l = 0 if tall else round(W * 0.24)
    inner_r = W if tall else W - round(W * 0.24)
    cw = inner_r - inner_l

    # ── Băng tên kênh ──
    f_ch = font(round(W * (0.036 if not tall else 0.048)))
    chw = d.textlength(channel, font=f_ch)
    bh = f_ch.size * 1.9
    by = band[0] + (18 if tall else 16)
    d.rounded_rectangle([inner_l + (cw - chw) / 2 - 26, by, inner_l + (cw + chw) / 2 + 26, by + bh],
                        radius=round(bh / 2), fill=(255, 255, 255, 235))
    d.text((inner_l + (cw - chw) / 2, by + bh * 0.24), channel, font=f_ch, fill=(150, 60, 90))

    # ── Tiêu đề: giảm cỡ chữ tới khi vừa khung ──
    top = by + bh + (34 if tall else 26)
    bottom = band[1] - (round(H * 0.10) if tall else round(H * 0.14))
    maxw = cw - (72 if tall else 56)
    for fs in range(round(W * (0.115 if not tall else 0.105)), 18, -3):
        f_t = font(fs)
        lines = wrap(d, title, f_t, maxw)
        lh = fs * 1.20
        if len(lines) * lh <= bottom - top:
            break
    y = top + ((bottom - top) - len(lines) * lh) / 2
    stroke = max(2, round(fs * 0.045))
    for ln in lines:
        plain = ln.replace("*", "")
        draw_line(d, inner_l + (cw - d.textlength(plain, font=f_t)) / 2, y, ln, f_t, stroke)
        y += lh

    # ── Nhãn chân + huy hiệu FULL ──
    f_l = font(round(W * (0.026 if not tall else 0.032)))
    lw = d.textlength(LABEL, font=f_l)
    ly = band[1] - f_l.size * 2.6
    d.text((inner_l + (cw - lw) / 2, ly), LABEL, font=f_l, fill=(120, 88, 104))

    f_b = font(round(W * (0.030 if not tall else 0.036)))
    bw = d.textlength("FULL", font=f_b)
    bx = inner_l + 28
    byy = ly - (f_b.size * 1.8 - f_l.size) / 2
    d.rounded_rectangle([bx, byy, bx + bw + 34, byy + f_b.size * 1.8],
                        radius=8, fill=ACCENT)
    d.text((bx + 17, byy + f_b.size * 0.36), "FULL", font=f_b, fill=(255, 255, 255))

    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, quality=92)
    print(f"→ {dst}  {W}x{H}  ({dst.stat().st_size/1024:.0f} KB)"
          f"{'  [chưa có ảnh chân dung]' if not portraits else ''}")


if __name__ == "__main__":
    main()
