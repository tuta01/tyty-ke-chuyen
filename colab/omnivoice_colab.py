#!/usr/bin/env python3
"""Gen audio truyện bằng OmniVoice trên GPU Colab — chạy được cả tập, không chỉ 1 câu.

Cách dùng trong Colab (Runtime → Change runtime type → GPU: T4/L4/A100):

    !pip -q install omnivoice soundfile
    !B=https://raw.githubusercontent.com/tuta01/tyty-ke-chuyen/main && \
     wget -q $B/colab/ref.wav $B/colab/ref.txt $B/colab/omnivoice_colab.py

Kịch bản KHÔNG nằm trong repo — dán tay vào một cell riêng:

    %%writefile truyen.txt
    <dán kịch bản vào đây, các đoạn cách nhau bằng một dòng trống>

rồi chạy:

    !python omnivoice_colab.py truyen.txt out.mp3                     # fp32, an toàn
    !python omnivoice_colab.py truyen.txt out.mp3 --dtype bfloat16    # nhanh hơn, nghe thử

Vì sao phải cắt nhỏ: OmniVoice sinh cả đoạn dài một lần thì dễ trôi giọng và phình
VRAM. Cắt theo đoạn văn (<=MAX_CHARS) rồi ghép lại cho ổn định — giống hệt cách
pipeline Vbee đang làm, nên đổi qua lại giữa hai giọng không phải sửa gì khác.
"""
import re, subprocess, sys, time
from pathlib import Path

MAX_CHARS = 400          # OmniVoice chịu đoạn dài hơn Vbee, nhưng dài quá thì trôi giọng
GAP = 0.28               # khoảng nghỉ giữa hai đoạn, giây — khớp với pipeline Vbee
SR = 24000
REF_WAV, REF_TXT = "ref.wav", "ref.txt"   # đổi bằng cờ --ref / --reftext


def chunks(text):
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


def main():
    import soundfile as sf
    import torch
    from omnivoice import OmniVoice

    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    for flag in ("--dtype", "--ref", "--reftext"):
        if flag in sys.argv:
            v = sys.argv[sys.argv.index(flag) + 1]
            pos = [x for x in pos if x != v]

    def opt(flag, default):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

    ref_wav = opt("--ref", REF_WAV)
    ref_txt_file = opt("--reftext", REF_TXT)
    src, dst = Path(pos[0]), Path(pos[1])
    gpu = torch.cuda.is_available()
    if not gpu:
        print("!! Không thấy GPU — Runtime > Change runtime type > GPU. Chạy CPU sẽ rất chậm.")
    dev = "cuda" if gpu else "cpu"

    # ⚠️ KHÔNG dùng float16. Đã đo: fp16 làm bộ dự đoán độ dài trượt số — 72 ký tự
    # ra 1.6s thay vì 3.9s, phần sinh bị cắt cụt và phát ra nội dung của giọng mẫu
    # thay vì chữ cần đọc. fp32 đã kiểm chứng cho ra đúng chữ; bf16 cùng dải mũ với
    # fp32 nên về lý thuyết an toàn và nhanh hơn, nhưng hãy nghe thử trước khi tin.
    name = sys.argv[sys.argv.index("--dtype") + 1] if "--dtype" in sys.argv else "float32"
    dt = {"float32": torch.float32, "bfloat16": torch.bfloat16,
          "float16": torch.float16}[name]
    if name == "float16":
        print("!! float16 đã được đo là hỏng với model này — chỉ dùng để đối chứng.")

    ref_txt = Path(ref_txt_file).read_text(encoding="utf-8").strip()
    print(f"giọng mẫu: {ref_wav}  ·  {len(ref_txt)} ký tự lời")
    parts = chunks(src.read_text(encoding="utf-8"))
    total_chars = sum(len(p) for p in parts)
    print(f"{len(parts)} đoạn · {total_chars:,} ký tự · {dev} · {dt}")

    model = OmniVoice.from_pretrained("splendor1811/omnivoice-vietnamese",
                                      device_map=dev, dtype=dt)

    # Chạy nháp để nạp kernel CUDA — lần đầu luôn chậm, không tính vào đo tốc độ.
    model.generate(text="Xin chào.", ref_audio=ref_wav, ref_text=ref_txt,
                       language="vietnamese")
    if gpu:
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()

    tmp = Path("parts")
    tmp.mkdir(exist_ok=True)
    files, t0 = [], time.time()
    for i, p in enumerate(parts):
        t1 = time.time()
        audio = model.generate(text=p, ref_audio=ref_wav, ref_text=ref_txt,
                       language="vietnamese")
        if gpu:
            torch.cuda.synchronize()
        f = tmp / f"p{i:03d}.wav"
        sf.write(f, audio[0], SR)
        files.append(f)
        d = len(audio[0]) / SR
        # Giọng đọc bình thường ~1.200 ký tự/phút = 20 ký tự/giây. Ra ngắn hơn
        # nửa mức đó là dấu hiệu sinh bị cắt cụt (xem ghi chú về float16 ở trên).
        warn = "  ⚠️ NGẮN BẤT THƯỜNG" if d < len(p) / 40 else ""
        print(f"  [{i+1}/{len(parts)}] {len(p):4d} ký tự → {d:5.1f}s "
              f"trong {time.time()-t1:5.1f}s  {p[:44]}…{warn}", flush=True)
    gen = time.time() - t0

    # Cắt lặng hai đầu từng mảnh rồi chèn khoảng nghỉ cố định; chuẩn hoá -14 LUFS.
    trim = ("silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB:detection=peak,"
            "areverse,"
            "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB:detection=peak,"
            "areverse")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in files:
        cmd += ["-i", str(f)]
    n = len(files)
    filts = [f"[{i}:a]{trim}" + ("" if i == n - 1 else f",apad=pad_dur={GAP}") + f"[a{i}]"
             for i in range(n)]
    chain = "".join(f"[a{i}]" for i in range(n))
    cmd += ["-filter_complex",
            ";".join(filts) + f";{chain}concat=n={n}:v=0:a=1[c];"
            "[c]loudnorm=I=-14:TP=-1.5:LRA=11[a]",
            "-map", "[a]", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(dst)]
    subprocess.run(cmd, check=True)

    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(dst)]).decode())
    print(f"\n→ {dst}  {int(dur//60)}:{int(dur%60):02d}  ({total_chars/(dur/60):,.0f} ký tự/phút)")
    print(f"[sinh] {gen:.0f}s cho {dur:.0f}s audio → RTF {gen/dur:.2f}x")
    print(f"[ước tính] tập 35 phút ≈ {gen/dur*35/60:.1f} giờ")
    if gpu:
        print(f"[GPU] {torch.cuda.get_device_name(0)} · "
              f"VRAM đỉnh {torch.cuda.max_memory_allocated()/1e9:.2f} GB")


if __name__ == "__main__":
    main()
