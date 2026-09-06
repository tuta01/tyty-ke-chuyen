#!/usr/bin/env python3
"""Kéo footage dọc từ Pexels về footage/ + ghi manifest để dán credit vào mô tả video.

Key: env PEXELS_API_KEY, hoặc ../한국어/video-generator/pexels_key.txt (dùng chung với dự án tiếng Hàn).

Dùng:
    python scripts/fetch_pexels.py                    # kéo theo bộ truy vấn mặc định
    python scripts/fetch_pexels.py "ink in water" "silk fabric"

Chỉ lấy clip DỌC (cao > rộng) và dài >= MIN_SECS, vì layout đặt clip dọc vào giữa
khung 16:9 — clip ngang nhét vào sẽ hở hai bên và trông như lỗi.
"""
import json, os, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "footage"
MANIFEST = OUT / "SOURCES.json"
MIN_SECS = 8
PER_QUERY = 3
# Pexels trả 403 cho User-Agent mặc định của urllib — phải giả trình duyệt.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Tông cổ trang Á Đông — nhìn có chủ đích hơn là clip ngẫu nhiên, mà vẫn không
# tranh sự chú ý với giọng đọc (không mặt người, không chữ, chuyển động chậm).
QUERIES = [
    "ink in water", "silk fabric flowing", "paper lantern night",
    "pouring tea closeup", "incense smoke", "bamboo forest",
    "koi fish pond", "candle flame dark", "rain on window",
    "cherry blossom branch",
]


def key():
    k = os.environ.get("PEXELS_API_KEY")
    if k:
        return k
    f = ROOT.parent / "한국어/video-generator/pexels_key.txt"
    if not f.exists():
        sys.exit("Thiếu key: đặt env PEXELS_API_KEY hoặc 한국어/video-generator/pexels_key.txt")
    return f.read_text().strip()


def search(q, k):
    url = ("https://api.pexels.com/videos/search?"
           + urllib.parse.urlencode({"query": q, "orientation": "portrait",
                                     "size": "medium", "per_page": 15}))
    req = urllib.request.Request(url, headers={"Authorization": k, "User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=60).read()).get("videos", [])


def best_file(v):
    """File dọc, độ phân giải cao nhất nhưng không quá 1920 chiều cao — 4K chỉ tổ
    nặng, vì cuối cùng cũng scale về 1080 chiều cao trong khung 16:9."""
    ok = [f for f in v["video_files"]
          if f.get("height") and f.get("width") and f["height"] > f["width"]]
    if not ok:
        return None
    ok.sort(key=lambda f: (f["height"] > 1920, -f["height"]))
    return ok[0]


def main():
    queries = sys.argv[1:] or QUERIES
    k = key()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

    for q in queries:
        taken = 0
        for v in search(q, k):
            if taken >= PER_QUERY or v["duration"] < MIN_SECS:
                continue
            vid = str(v["id"])
            dst = OUT / f"{vid}.mp4"
            if dst.exists():
                taken += 1
                continue
            f = best_file(v)
            if not f:
                continue
            print(f"  [{q}] #{vid} {f['width']}x{f['height']} {v['duration']}s …", flush=True)
            dst.write_bytes(urllib.request.urlopen(urllib.request.Request(f["link"], headers={"User-Agent": UA}), timeout=300).read())
            manifest[vid] = {"query": q, "url": v["url"], "author": v["user"]["name"],
                             "author_url": v["user"]["url"], "duration": v["duration"],
                             "size": [f["width"], f["height"]]}
            taken += 1

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\n{len(manifest)} clip trong {OUT}")
    print("Credit dán vào mô tả video:")
    for vid, m in manifest.items():
        print(f"  {m['author']} — {m['url']}")


if __name__ == "__main__":
    main()
