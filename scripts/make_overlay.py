#!/usr/bin/env python3
"""Dựng lớp overlay PNG 1920x1080 (nền trong suốt) dán đè lên video.

Chừa trống đúng ô 608x1080 ở giữa — chỗ đặt clip dọc. Hai bên là panel: trái để
tên tập + nút LIKE/SUBSCRIBE/SHARE, phải để tên kênh.

Dùng:
    python scripts/make_overlay.py "TÊN TẬP" assets/overlay.png
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
PORTRAIT_W = 608                      # 1080 * 9/16, ô video dọc ở giữa
LEFT = (W - PORTRAIT_W) // 2          # 656 — mép trái ô video

CHANNEL = "TỶ TỶ KỂ CHUYỆN"
GOLD = (232, 197, 122, 255)
RED = (196, 48, 48, 255)
WHITE = (255, 255, 255, 255)

FONTS = ["/Library/Fonts/Arial Unicode.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def font(size):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def pill(draw, box, fill, text, fnt, fg=WHITE):
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    tw = draw.textlength(text, font=fnt)
    draw.text(((box[0] + box[2] - tw) / 2, (box[1] + box[3]) / 2 - fnt.size * 0.62),
              text, font=fnt, fill=fg)


def main():
    title = sys.argv[1] if len(sys.argv) > 1 else "TẬP 1"
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "assets/overlay.png")

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Viền vàng mảnh quanh ô video dọc — tách clip khỏi nền blur cho gọn mắt.
    d.rectangle([LEFT - 3, 0, LEFT + PORTRAIT_W + 2, H - 1], outline=GOLD, width=3)

    # ── Panel trái: tên tập + nút ──
    pad, maxw = 56, LEFT - 112
    f_title, f_btn, f_small = font(44), font(30), font(24)

    d.text((pad, 150), "TRUYỆN AUDIO", font=f_small, fill=GOLD)
    y = 196
    for line in wrap(d, title.upper(), f_title, maxw):
        d.text((pad, y), line, font=f_title, fill=WHITE)
        y += 58

    y += 40
    for label, col in [("LIKE", RED), ("SUBSCRIBE", RED), ("SHARE", (60, 60, 60, 235))]:
        pill(d, (pad, y, pad + 250, y + 58), col, label, f_btn)
        y += 76

    # ── Panel phải: tên kênh ──
    f_ch = font(38)
    rx = LEFT + PORTRAIT_W + 56
    d.text((rx, 150), CHANNEL, font=f_ch, fill=GOLD)
    d.line([rx, 205, rx + 260, 205], fill=GOLD, width=2)
    d.text((rx, 224), "Muội cứ nằm, tỷ kể cho nghe", font=f_small, fill=(210, 210, 210, 255))

    # ── Watermark mờ trên đầu ô video ──
    f_wm = font(30)
    tw = d.textlength(CHANNEL, font=f_wm)
    d.text((LEFT + (PORTRAIT_W - tw) / 2, 34), CHANNEL, font=f_wm, fill=(255, 255, 255, 120))

    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)
    print(f"→ {dst}  {W}x{H}  (ô video dọc: x={LEFT}..{LEFT + PORTRAIT_W})")


if __name__ == "__main__":
    main()
