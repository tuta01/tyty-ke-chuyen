#!/usr/bin/env python3
"""Sinh file phụ đề .ass chạy chữ karaoke từ timestamp của faster-whisper.

Whisper nghe sai vài từ (Xuyên→Suyên, tỷ→tỉ…), nên KHÔNG dùng chữ của whisper.
Chỉ mượn timestamp rồi ghép lên bản chữ gốc bằng difflib: từ nào khớp thì lấy
thời gian thật, từ nào whisper bỏ/nghe sai thì nội suy tuyến tính giữa hai mốc
khớp gần nhất.

Dùng:
    python scripts/make_karaoke.py content/tap01_hook.txt /tmp/hook_words.json out/hook01.ass
"""
import json, re, sys
from difflib import SequenceMatcher
from pathlib import Path

W, H = 1080, 1920
MAX_WORDS = 4            # số từ tối đa mỗi dòng phụ đề
MAX_CHARS = 24
FONT = "Lato Black"   # có trên x99, phủ đủ dấu tiếng Việt
SIZE = 78
MARGIN_V = 700           # đẩy chữ lên khỏi đáy, tránh khu nút của TikTok


def norm(w):
    return re.sub(r"[^\wàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
                  "", w.lower())


def ts(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def align(truth, heard):
    """Gán (start, end) cho từng từ trong `truth` dựa trên `heard` đã có thời gian."""
    sm = SequenceMatcher(None, [norm(w) for w in truth], [norm(h["w"]) for h in heard])
    times = [None] * len(truth)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            times[a + k] = (heard[b + k]["s"], heard[b + k]["e"])

    # Nội suy các từ chưa có mốc, dựa trên độ dài chữ để chia thời gian cho hợp lý.
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(times) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else 0.0
        hi = times[j][0] if j < len(times) else lo + 0.4 * (j - i)
        span = max(hi - lo, 0.12 * (j - i))
        weights = [len(truth[k]) + 1 for k in range(i, j)]
        tot = sum(weights)
        t = lo
        for k, wgt in zip(range(i, j), weights):
            d = span * wgt / tot
            times[k] = (t, t + d)
            t += d
        i = j
    return times


def lines(truth, times):
    """Gom từ thành dòng ngắn; ngắt thêm ở dấu câu và ở chỗ nghỉ dài."""
    out, cur = [], []
    for k, w in enumerate(truth):
        cur.append(k)
        txt = " ".join(truth[c] for c in cur)
        gap = (times[k + 1][0] - times[k][1]) if k + 1 < len(truth) else 9
        if (len(cur) >= MAX_WORDS or len(txt) >= MAX_CHARS
                or re.search(r"[.!?:,…]$", w) or gap > 0.35):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: K,{FONT},{SIZE},&H007AC5E8,&H00FFFFFF,&H00101010,&H00000000,0,0,0,0,100,100,0,0,1,7,3,2,70,70,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    src, wj, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    truth = src.read_text(encoding="utf-8").split()
    heard = json.loads(wj.read_text(encoding="utf-8"))
    times = align(truth, heard)

    ev = []
    for grp in lines(truth, times):
        start, end = times[grp[0]][0], times[grp[-1]][1]
        body = ""
        for k in grp:
            # \kf tô dần từ màu phụ (trắng) sang màu chính (vàng) đúng lúc đọc từ đó
            body += "{\\kf%d}%s " % (round((times[k][1] - times[k][0]) * 100), truth[k])
        ev.append(f"Dialogue: 0,{ts(start)},{ts(end + 0.06)},K,,0,0,0,,{body.strip()}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(HEAD + "\n".join(ev) + "\n", encoding="utf-8")
    matched = sum(1 for t in times if t)
    print(f"→ {dst}  {len(truth)} từ · {len(ev)} dòng · hết ở {times[-1][1]:.1f}s")


if __name__ == "__main__":
    main()
