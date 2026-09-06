# Tỷ Tỷ Kể Chuyện — pipeline video truyện audio

Dựng video truyện audio (xuyên không / cổ trang) từ kịch bản text: sinh giọng đọc,
kéo footage nền, ghép video ngang cho YouTube và video dọc có chữ chạy cho TikTok.

## Cần gì

- `ffmpeg` + `ffprobe`. Bản dựng TikTok cần ffmpeg **có libass** (`subtitles` filter) —
  ffmpeg cài qua Homebrew trên macOS thường **không** có, phải render trên máy Linux.
- Python 3 (chỉ dùng thư viện chuẩn, riêng `make_overlay.py` cần Pillow).
- Giọng đọc: tài khoản Vbee (`VBEE_TOKEN`, `VBEE_APP_ID` trong `~/.vbee.env`),
  hoặc OmniVoice trên GPU — xem `colab/`.
- Footage: API key Pexels (env `PEXELS_API_KEY`).

## Quy trình

```bash
set -a && . ~/.vbee.env && set +a

# 1. Kịch bản → giọng đọc (cache theo md5 từng đoạn, sửa vài câu không tốn lại quota)
python scripts/tts_vbee.py content/tap01.txt out/tap01.mp3

# 2. Kéo footage dọc về (bỏ qua nếu đã có cooking_source/)
python scripts/fetch_pexels.py

# 3. Lớp overlay cho bản ngang
python scripts/make_overlay.py "Tên tập" assets/overlay.png

# 4. Video ngang 1920x1080 cho YouTube
python scripts/compose.py out/tap01.mp3 out/tap01.mp4 --footage cooking_source --seg 40
```

Bản dọc cho TikTok, có chữ chạy karaoke:

```bash
# Cắt phần hook rồi sinh giọng (trúng cache của tập đầy đủ)
python scripts/tts_vbee.py content/tap01_hook.txt out/hook01.mp3

# Lấy timestamp từng từ (faster-whisper, nên chạy trên máy có nhiều nhân)
# rồi ghép timestamp lên chữ gốc — whisper nghe sai thì chữ vẫn đúng chính tả
python scripts/make_karaoke.py content/tap01_hook.txt hook_words.json out/hook01.ass

python scripts/compose_tiktok.py out/hook01.mp3 out/hook01.ass out/tiktok01.mp4
```

## Các lựa chọn đã chốt và lý do

| Chỗ | Chốt | Vì sao |
|---|---|---|
| Tốc độ đọc | Vbee speed 1.15 | Speed 1.0 chỉ được 1.019 ký tự/phút, chậm hơn thấy rõ so với các kênh cùng thể loại (1.125–1.291) |
| Âm lượng | −14 LUFS | Chuẩn YouTube |
| Nghỉ giữa đoạn | Cắt lặng hai đầu + chèn 0.28s | Mảnh TTS nào cũng có lặng thừa hai đầu; ghép thẳng thì lặng cộng dồn, nghe trễ nhịp |
| Đổi clip nền | 40s (ngang) / 15s (dọc) | Một clip lặp suốt tập dễ bị YouTube xếp vào "repetitious content" |
| Chữ karaoke | Timestamp của whisper + chữ của kịch bản | Whisper nghe sai ("Suyên" thay "Xuyên"); chỉ mượn thời gian, chữ lấy từ bản gốc |
| Font phụ đề | Lato Black, `Bold=0` | Lato Black vốn đã đậm; bật Bold nữa thì libass tô đậm giả, chữ bết dấu |

## Bản quyền footage

Toàn bộ clip nền lấy từ Pexels (dùng thương mại được, không cần xin phép).
`footage/SOURCES.json` ghi tác giả + link từng clip để dán vào mô tả video.
File `.mp4` không đẩy lên git — chạy `scripts/fetch_pexels.py` để kéo lại.

## Sinh giọng bằng OmniVoice trên GPU

Xem `colab/omnivoice_colab.py`. OmniVoice là **zero-shot voice cloning** — không cần
train, chỉ cần một đoạn giọng mẫu kèm đúng phần lời của đoạn đó.

Kịch bản trong `content/` không đẩy lên git (nội dung của kênh); trên Colab thì dán
tay vào bằng `%%writefile truyen.txt`.

Tốc độ đo được trên CPU (2× Xeon E5-2680 v4):

| Độ dài mẫu | RTF | Tập 6,5 phút | Tập 35 phút |
|---|---|---|---|
| 31 giây | 18.8x | 2 giờ | 11 giờ |
| 8 giây | 9.0x | 59 phút | 5,3 giờ |

Mẫu ngắn nhanh gấp đôi — model khuyến nghị 3–10 giây. CPU vẫn quá chậm để chạy đều,
nên dùng GPU (Colab) hoặc chỉ dùng OmniVoice cho intro/outro ngắn.
