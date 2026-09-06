#!/usr/bin/env python3
"""Ghép video 16:9 từ: audio truyện + kho clip DỌC + lớp overlay PNG.

Layout (bám theo 2 video tham chiếu):
    nền   = chính clip đó, phóng to phủ 1920x1080, blur mạnh + tối đi
    giữa  = clip dọc gốc, cao 1080 → rộng 608
    trên  = overlay.png (tên tập, nút LIKE/SUB/SHARE, watermark)

Dùng:
    python scripts/compose.py out/tap01.mp3 out/tap01.mp4
    python scripts/compose.py out/tap01.mp3 out/tap01.mp4 --footage cooking_source --seg 40

Vì sao cắt sẵn từng đoạn rồi mới concat: clip nguồn dài 9–34s, ngắn hơn đoạn cần
thì hình đứng chết ở frame cuối. `-stream_loop -1 -t SEG` cho ra đoạn dài đúng SEG.
"""
import json, random, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 1920, 1080
PORTRAIT_W, PORTRAIT_H = 1080, 1920
FPS = 30
SEG = 40                 # giây mỗi clip trước khi đổi sang clip khác
SEED = 7                 # cố định để chạy lại ra đúng thứ tự cũ


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def duration(f):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(f)]).decode())


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    # bỏ các giá trị đi kèm cờ ra khỏi danh sách tham số vị trí
    for flag in ("--footage", "--seg", "--overlay"):
        if flag in sys.argv:
            v = sys.argv[sys.argv.index(flag) + 1]
            if v in pos:
                pos.remove(v)
    audio, out = Path(pos[0]), Path(pos[1])
    fdir = ROOT / arg("--footage", "cooking_source")
    overlay = ROOT / arg("--overlay", "assets/overlay.png")
    seg = float(arg("--seg", SEG))

    clips = sorted(fdir.glob("*.mp4"))
    if not clips:
        sys.exit(f"Không có clip nào trong {fdir}")
    if not overlay.exists():
        sys.exit(f"Thiếu overlay: {overlay} — chạy scripts/make_overlay.py trước")

    total = duration(audio)
    n = int(total // seg) + 1
    print(f"audio {int(total//60)}:{int(total%60):02d} · {len(clips)} clip nguồn · "
          f"{n} đoạn × {seg:.0f}s · {fdir.name}")

    # Xáo trộn rồi lặp lại danh sách, tránh hai đoạn liền nhau trùng clip.
    order = []
    rnd = random.Random(SEED)
    while len(order) < n:
        batch = clips[:]
        rnd.shuffle(batch)
        if order and batch[0] == order[-1] and len(batch) > 1:
            batch[0], batch[1] = batch[1], batch[0]
        order += batch
    order = order[:n]

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".matnao_", dir=out.parent))
    parts = []
    # scale phủ kín khung dọc rồi crop — clip nguồn nào lệch tỉ lệ cũng không bị méo
    vf = (f"scale={PORTRAIT_W}:{PORTRAIT_H}:force_original_aspect_ratio=increase,"
          f"crop={PORTRAIT_W}:{PORTRAIT_H},fps={FPS},setsar=1")
    for i, c in enumerate(order):
        p = tmp / f"seg{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
                        "-t", str(seg), "-i", str(c), "-vf", vf, "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(p)],
                       check=True)
        parts.append(p)
        print(f"  đoạn {i+1}/{n}  {c.name}")

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    reel = tmp / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(reel)], check=True)

    fg_w = round(H * PORTRAIT_W / PORTRAIT_H / 2) * 2          # 608
    fc = (f"[0:v]split=2[b][f];"
          f"[b]scale={W}:-2,crop={W}:{H},boxblur=42:2,eq=brightness=-0.16:saturation=0.65[bg];"
          f"[f]scale={fg_w}:{H}[fg];"
          f"[bg][fg]overlay=(W-w)/2:0[v0];"
          f"[v0][1:v]overlay=0:0[v]")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stats",
                    "-i", str(reel), "-i", str(overlay), "-i", str(audio),
                    "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)

    print(f"\n→ {out}  {out.stat().st_size / 1e6:.0f} MB  "
          f"{int(duration(out)//60)}:{int(duration(out)%60):02d}")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
