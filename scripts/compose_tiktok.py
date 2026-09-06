#!/usr/bin/env python3
"""Ghép bản TikTok dọc 1080x1920: clip nấu ăn + chữ chạy karaoke + watermark + thẻ outro.

Khác bản dài 16:9 ở ba chỗ: khung dọc full màn (không có panel hai bên), có phụ đề
chạy chữ (TikTok không phụ đề thì giữ chân rất kém), và cuối video chèn thẻ
"nghe full tại kênh".

Dùng:
    python scripts/compose_tiktok.py out/hook01.mp3 out/hook01.ass out/tiktok01.mp4
"""
import random, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
SEG = 15                 # đổi clip nhanh hơn bản dài (40s) cho hợp nhịp TikTok
OUTRO = 3.5              # giây thẻ outro ở cuối
SEED = 7


def duration(f):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(f)]).decode())


def main():
    audio, ass, out = (Path(a) for a in sys.argv[1:4])
    fdir = ROOT / "cooking_source"
    wm, card = ROOT / "assets/tiktok_wm.png", ROOT / "assets/tiktok_outro.png"
    for p in (audio, ass, wm, card):
        if not p.exists():
            sys.exit(f"Thiếu {p}")

    spoken = duration(audio)
    total = spoken + OUTRO
    clips = sorted(fdir.glob("*.mp4"))
    n = int(total // SEG) + 1
    print(f"thoại {spoken:.1f}s + outro {OUTRO}s = {total:.1f}s · {n} đoạn × {SEG}s")

    order, rnd = [], random.Random(SEED)
    while len(order) < n:
        b = clips[:]
        rnd.shuffle(b)
        if order and b[0] == order[-1] and len(b) > 1:
            b[0], b[1] = b[1], b[0]
        order += b
    order = order[:n]

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".matnao_tt_", dir=out.parent))
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},fps={FPS},setsar=1")
    parts = []
    for i, c in enumerate(order):
        p = tmp / f"s{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
                        "-t", str(SEG), "-i", str(c), "-vf", vf, "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(p)],
                       check=True)
        parts.append(p)
    lst = tmp / "l.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    reel = tmp / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(reel)], check=True)

    # Audio: nối thêm khoảng lặng để thẻ outro có chỗ đứng.
    apad = tmp / "a.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio),
                    "-af", f"apad=pad_dur={OUTRO}", "-t", str(total),
                    "-c:a", "aac", "-b:a", "192k", str(apad)], check=True)

    # libass cần đường dẫn escape: ':' và '\' là ký tự đặc biệt trong chuỗi filter.
    ap = str(ass.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    # fontsdir chỉ cần trên macOS; trên x99 fontconfig tự tìm ra Lato Black.
    fd = ":fontsdir=/Library/Fonts" if Path("/Library/Fonts").exists() else ""
    fc = (
        f"[0:v]eq=brightness=-0.10:saturation=0.95,"
        f"subtitles=filename='{ap}'{fd}[sub];"
        f"[sub][1:v]overlay=0:0[wm];"
        f"[2:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1,"
        f"setpts=PTS-STARTPTS+{spoken + 0.15}/TB[card];"
        f"[wm][card]overlay=0:0:enable='gte(t,{spoken + 0.15})'[v]"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stats",
                    "-i", str(reel), "-loop", "1", "-i", str(wm), "-loop", "1", "-i", str(card),
                    "-i", str(apad), "-filter_complex", fc,
                    "-map", "[v]", "-map", "3:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", str(total),
                    "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    print(f"\n→ {out}  {out.stat().st_size / 1e6:.0f} MB  {duration(out):.1f}s")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
