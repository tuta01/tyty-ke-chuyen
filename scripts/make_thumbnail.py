#!/usr/bin/env python3
"""Dựng ảnh bìa video bằng HTML rồi chụp lại bằng Chrome headless.

Vì sao HTML thay vì vẽ bằng Pillow: kiểu chữ, đổ bóng, bo góc, gradient trong CSS
đẹp hơn hẳn và sửa nhanh hơn nhiều. Chrome chụp đúng pixel, không phải căn tay.

Đánh dấu chữ cần tô đỏ bằng *sao*, xuống dòng bằng |:
    "VẢ MẶT NHỎ|BẠN CÙNG PHÒNG|*THÍCH ĂN CHỰC*"

Dùng:
    python scripts/make_thumbnail.py "Dòng 1|Dòng 2|*Dòng nhấn*" out/thumb.jpg \
        --portrait assets/portraits/nu01.jpg
    python scripts/make_thumbnail.py "..." out/cover.jpg --size tiktok --portrait ...
    python scripts/make_thumbnail.py "..." out/t.jpg --keep-html   # giữ .html để chỉnh tay
"""
import base64, mimetypes, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHANNEL = "Tỷ Tỷ Kể Chuyện"
LABEL = "TRUYỆN AUDIO"
SIZES = {"youtube": (1280, 720), "tiktok": (1080, 1920)}


def opt(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def data_uri(p):
    p = Path(p)
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def title_html(title):
    out = []
    for line in title.split("|"):
        line = line.strip()
        hot = line.startswith("*") and line.endswith("*")
        out.append(f'<div class="tl{" hot" if hot else ""}">{line.strip("*")}</div>')
    return "\n".join(out)


def build(title, portrait, size, channel):
    W, H = SIZES[size]
    tall = size == "tiktok"
    img = f'<img class="por" src="{data_uri(portrait)}">' if portrait else '<div class="por ph"></div>'
    # Bản dọc xếp ảnh trên chữ dưới; bản ngang xếp ảnh trái chữ phải.
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@700;800;900&family=Dancing+Script:wght@700&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:{W}px; height:{H}px; overflow:hidden;
         font-family:'Be Vietnam Pro',Arial,sans-serif;
         background:linear-gradient(160deg,#fde8ef 0%,#f7d4e2 55%,#f3c6d8 100%); }}
  .card {{ position:absolute; {'inset:22px;' if not tall else 'top:26px; left:26px; right:26px; bottom:26px;'}
           background:linear-gradient(150deg,#fff6f9 0%,#fde6ee 60%,#fad7e5 100%);
           border:3px solid #fff; border-radius:{28 if not tall else 34}px;
           box-shadow:0 10px 40px rgba(190,110,140,.28);
           display:flex; flex-direction:{'column' if tall else 'row'};
           align-items:center; justify-content:{'flex-start' if tall else 'center'};
           padding:{'70px 34px 0' if tall else '26px 34px'}; gap:{22 if tall else 34}px; }}
  .label {{ position:absolute; top:{14 if not tall else 18}px; left:0; right:0; text-align:center;
            font-size:{15 if not tall else 20}px; letter-spacing:.22em; color:#b98098; font-weight:700; }}
  .por {{ width:{'34%' if not tall else '58%'}; aspect-ratio:1/1; object-fit:cover; flex:none;
          border-radius:{22 if not tall else 28}px; border:5px solid #fff;
          box-shadow:0 8px 26px rgba(180,100,130,.30); }}
  .ph {{ background:repeating-linear-gradient(45deg,#f6dae5,#f6dae5 14px,#f2cede 14px,#f2cede 28px); }}
  .right {{ {'flex:1;' if not tall else ''} display:flex; flex-direction:column;
            justify-content:center; align-items:center; text-align:center;
            gap:{6 if not tall else 8}px; width:100%; }}
  .ch {{ font-family:'Dancing Script',cursive; font-size:{40 if not tall else 54}px;
         color:#c2416b; line-height:1; margin-bottom:{8 if not tall else 14}px; }}
  .tl {{ font-weight:900; font-size:{62 if not tall else 76}px; line-height:1.08;
         color:#2b2230; letter-spacing:-.01em;
         text-shadow:0 2px 0 #fff, 0 4px 14px rgba(170,90,120,.20); }}
  .hot {{ color:#d61e50; }}
  .heart {{ position:absolute; {'bottom:14px;' if not tall else 'top:70%;'} left:0; right:0;
            text-align:center; font-size:{20 if not tall else 30}px; color:#e3628c; }}
</style></head><body>
  <div class="card">{img}
    <div class="right"><div class="ch">{channel}</div>{title_html(title)}</div>
  </div>
  <div class="label">{LABEL}</div>
  <div class="heart">♥ ♥ ♥</div>
</body></html>"""


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    for flag in ("--size", "--channel", "--portrait"):
        if flag in sys.argv:
            v = sys.argv[sys.argv.index(flag) + 1]
            if v in pos:
                pos.remove(v)

    title, dst = pos[0], Path(pos[1] if len(pos) > 1 else "out/thumb.jpg")
    size = opt("--size", "youtube")
    portrait = opt("--portrait")
    W, H = SIZES[size]

    if not Path(CHROME).exists():
        sys.exit(f"Không thấy Chrome ở {CHROME}")

    html = build(title, portrait, size, opt("--channel", CHANNEL))
    hp = (dst.with_suffix(".html") if "--keep-html" in sys.argv
          else Path(tempfile.mkdtemp()) / "thumb.html")
    hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text(html, encoding="utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    png = dst.with_suffix(".png")
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    f"--screenshot={png}", f"--window-size={W},{H}",
                    "--virtual-time-budget=3000",   # chờ webfont tải xong
                    f"file://{hp}"],
                   check=True, capture_output=True)
    if dst.suffix.lower() in (".jpg", ".jpeg"):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "88",
                        str(png), "--out", str(dst)], check=True, capture_output=True)
        png.unlink()
    print(f"→ {dst}  {W}x{H}  ({dst.stat().st_size/1024:.0f} KB)"
          + (f"  · html: {hp}" if "--keep-html" in sys.argv else ""))


if __name__ == "__main__":
    main()
