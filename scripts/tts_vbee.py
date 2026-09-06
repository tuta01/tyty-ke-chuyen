#!/usr/bin/env python3
"""Đọc file truyện .txt bằng Vbee TTS, ghép thành 1 file mp3 hoàn chỉnh.

Cần env VBEE_TOKEN + VBEE_APP_ID:  set -a && . ~/.vbee.env && set +a

Dùng:
    python scripts/tts_vbee.py content/tap01.txt out/tap01.mp3
    python scripts/tts_vbee.py content/tap01.txt out/tap01.mp3 --voice sg_female_thaotrinh_full_48k-fhg

Vbee chỉ có mode=async trong gói hiện tại: POST trả requestId → poll lấy audioLink.
webhookUrl là field bắt buộc dù ta poll chứ không dùng webhook.
Từng mảnh được cache theo md5 nên chạy lại chỉ tổng hợp phần đã đổi.
"""
import hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out/tts_cache"
API = "https://api.vbee.vn/v1/tts"
VOICE = "hn_female_ngochuyen_full_48k-fhg"
MAX_CHARS = 900          # mảnh dài hơn Vbee hay trả lỗi/cắt đuôi
GAP = 0.28               # khoảng nghỉ chèn giữa hai đoạn văn, giây
# speed 1.0 đo được 1.019 ký tự/phút, chậm hơn hai kênh tham chiếu (1.125 và 1.291).
SPEED = 1.15


def chunks(text):
    """Cắt theo đoạn văn; đoạn nào dài quá thì cắt tiếp ở ranh giới câu."""
    out = []
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        if len(para) <= MAX_CHARS:
            out.append(para)
            continue
        buf = ""
        for sent in re.split(r"(?<=[.!?…])\s+", para):
            if buf and len(buf) + len(sent) + 1 > MAX_CHARS:
                out.append(buf)
                buf = sent
            else:
                buf = f"{buf} {sent}".strip()
        if buf:
            out.append(buf)
    return out


def synth(text, voice, hdr):
    mp3 = CACHE / f"{hashlib.md5(f'{voice}|{SPEED}|{text}'.encode()).hexdigest()[:12]}.mp3"
    if mp3.exists():
        return mp3
    body = {"text": text, "mode": "async", "voiceCode": voice, "outputFormat": "mp3",
            "speed": SPEED, "webhookUrl": "https://example.com/vbee-hook"}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=hdr)
    try:
        res = json.loads(urllib.request.urlopen(req, timeout=90).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Vbee lỗi {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}\n  văn bản: {text[:80]}")
    res = res.get("result") or res.get("data") or res
    rid, link = res.get("requestId"), res.get("audioLink")
    for _ in range(60):
        if link:
            break
        time.sleep(2)
        pr = urllib.request.Request(f"{API}/requests/{rid}", headers=hdr)
        pb = json.loads(urllib.request.urlopen(pr, timeout=60).read())
        pb = pb.get("result") or pb.get("data") or pb
        if str(pb.get("status", "")).upper() in ("FAILED", "FAILURE", "ERROR"):
            sys.exit(f"Vbee xử lý thất bại: {json.dumps(pb)[:300]}")
        link = pb.get("audioLink")
    if not link:
        sys.exit("Vbee: hết thời gian chờ mà chưa có audioLink.")
    mp3.write_bytes(urllib.request.urlopen(link, timeout=180).read())
    return mp3


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    voice = VOICE
    if "--voice" in sys.argv:
        voice = sys.argv[sys.argv.index("--voice") + 1]
    src, dst = Path(args[0]), Path(args[1])

    tok, app = os.environ.get("VBEE_TOKEN"), os.environ.get("VBEE_APP_ID")
    if not tok:
        sys.exit("Thiếu VBEE_TOKEN — chạy: set -a && . ~/.vbee.env && set +a")
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    if app:
        hdr["App-Id"] = app

    CACHE.mkdir(parents=True, exist_ok=True)
    dst.parent.mkdir(parents=True, exist_ok=True)

    parts = chunks(src.read_text(encoding="utf-8"))
    total = sum(len(p) for p in parts)
    print(f"{len(parts)} mảnh, {total:,} ký tự, giọng {voice}")

    files = []
    for i, p in enumerate(parts, 1):
        f = synth(p, voice, hdr)
        files.append(f)
        print(f"  [{i}/{len(parts)}] {len(p):4d} ký tự  {p[:52]}…")

    # Mỗi mảnh TTS có sẵn khoảng lặng hai đầu; ghép thẳng thì lặng cộng dồn nghe rất trễ.
    # Cắt lặng hai đầu rồi chèn khoảng nghỉ cố định GAP giây.
    trim = ("silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB:detection=peak,"
            "areverse,"
            "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB:detection=peak,"
            "areverse")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in files:
        cmd += ["-i", str(f)]
    n = len(files)
    filts = [f"[{i}:a]{trim}" + ("" if i == n - 1 else f",apad=pad_dur={GAP}") + f"[a{i}]" for i in range(n)]
    chain = "".join(f"[a{i}]" for i in range(n))
    # loudnorm về -14 LUFS: chuẩn YouTube (2 video tham chiếu đo được -21.2 và -14.5).
    cmd += ["-filter_complex",
            ";".join(filts) + f";{chain}concat=n={n}:v=0:a=1[c];[c]loudnorm=I=-14:TP=-1.5:LRA=11[a]",
            "-map", "[a]", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(dst)]
    subprocess.run(cmd, check=True)

    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(dst)]).decode())
    print(f"→ {dst}  {int(dur // 60)}:{int(dur % 60):02d}  ({total / (dur / 60):,.0f} ký tự/phút)")


if __name__ == "__main__":
    main()
