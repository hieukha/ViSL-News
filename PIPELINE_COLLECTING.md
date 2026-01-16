# PIPELINE CHI TIẾT - CÔNG CỤ THU THẬP DỮ LIỆU ViSL

## TỔNG QUAN
Pipeline xử lý video từ YouTube để tạo dataset ngôn ngữ ký hiệu Việt Nam, bao gồm: tải video, phát hiện người ký hiệu, cắt vùng signer, transcribe, và chia thành các clip câu.

---

## LUỒNG XỬ LÝ TỔNG QUAN

```
User Input (YouTube URL) 
    ↓
[1] Download Video(s)
    ↓
[2] Signer Detection & Filtering
    ↓
[3] Crop Signer Region
    ↓
[4] Transcribe Audio (WhisperX)
    ↓
[5] Split into Sentence Clips
    ↓
[6] Create ZIP Archive
    ↓
Output (ZIP file với clips + metadata)
```

---

## CHI TIẾT TỪNG BƯỚC

### **BƯỚC 0: KHỞI TẠO (0-5%)**
- **Input**: YouTube URL, max_videos (số lượng video tối đa)
- **Hành động**:
  - Tạo work directory với UUID
  - Tạo các thư mục con:
    - `raw/` - Video gốc từ YouTube
    - `signer_clips/` - Video đã crop vùng signer
    - `transcripts/` - File JSON transcript
    - `sentence_clips/` - Các clip câu đã cắt
  - Khởi tạo progress callback
- **Output**: Work directory structure sẵn sàng
- **Progress**: 0-5%

---

### **BƯỚC 1: TẢI VIDEO TỪ YOUTUBE (5-15%)**

#### 1.1. Extract Video Info (5-8%)
- **Công cụ**: `yt-dlp`
- **Hành động**:
  - Kiểm tra URL là video đơn hay playlist
  - Extract metadata (title, video_id, duration)
  - Nếu playlist: lấy danh sách video (giới hạn max_videos)
- **Output**: Danh sách video entries cần tải

#### 1.2. Download Each Video (8-12%)
- **Công cụ**: `yt-dlp`
- **Cấu hình**:
  - Format: `best[ext=mp4]/best`
  - Output: `{video_id}_temp.{ext}` (tạm thời)
  - Quiet mode: True
- **Hành động**:
  - Tải từng video trong playlist/video đơn
  - Lưu file tạm với tên `{video_id}_temp.mp4`
- **Progress**: 10% + (idx * 2%) cho mỗi video

#### 1.3. Signer Detection Check (12-15%)
- **Công cụ**: OpenCV + Haar Cascade
- **Hành động**:
  - Với mỗi video đã tải:
    - Extract 3 frames tại timestamps: [2s, 10s, 20s]
    - Resize frame về 1920x1080 nếu cần
    - Crop ROI region: x=125, y=637, width=178, height=159
    - Chạy face detection trên ROI
    - **Chỉ chấp nhận video nếu CẢ 3 frames đều có người**
- **Kết quả**:
  - ✅ Có signer: Giữ lại video
  - ❌ Không có signer: Xóa file tạm, bỏ qua video
- **Progress**: 12% + (idx * 1%)

#### 1.4. Rename & Save (15%)
- **Hành động**:
  - Tạo slug từ title (ví dụ: "Coca-Cola Việt Nam..." → "coca-cola-viet-nam...")
  - Đổi tên từ `{video_id}_temp.mp4` → `{slug}.mp4`
  - Xử lý duplicate: thêm `-1`, `-2` nếu trùng tên
  - Lưu vào `raw/` directory
- **Output**: Danh sách video paths đã tải và có signer
- **Progress**: 15%

---

### **BƯỚC 2: CẮT VÙNG SIGNER (20-35%)**

#### 2.1. Crop Signer ROI (20-35%)
- **Công cụ**: FFmpeg
- **Input**: Video gốc từ `raw/`
- **ROI Coordinates**:
  - x = 50
  - y = 600
  - width = 327
  - height = 426
- **FFmpeg Command**:
  ```bash
  ffmpeg -y -i {input} \
    -filter:v "crop=327:426:50:600" \
    -c:a copy \
    -c:v libx264 \
    -preset fast \
    -crf 23 \
    {output}
  ```
- **Output**: Video đã crop vào `signer_clips/signer_{original_name}.mp4`
- **Progress**: 20-35%

---

### **BƯỚC 3: TRANSCRIBE AUDIO (40-65%)**

#### 3.1. Load WhisperX Model (40-50%)
- **Công cụ**: WhisperX (large-v3 model)
- **Hành động**:
  - Kiểm tra GPU/CUDA availability
  - Load model:
    - Device: `cuda` (nếu có) hoặc `cpu`
    - Compute type: `float16` (GPU) hoặc `int8` (CPU)
  - Model: `whisperx/large-v3`
- **Progress**: 40-50%

#### 3.2. Transcribe Audio (50-55%)
- **Công cụ**: WhisperX
- **Hành động**:
  - Load audio từ video đã crop
  - Transcribe với:
    - Batch size: 16
    - Language: "vi" (Vietnamese)
  - Kết quả: Segments với text và timestamps
- **Progress**: 50-55%

#### 3.3. Align Timestamps (55-60%)
- **Công cụ**: WhisperX Alignment Model
- **Hành động**:
  - Load alignment model cho tiếng Việt
  - Align transcript với audio để có timestamps chính xác
  - Fallback: Nếu không load được alignment model, dùng raw transcription
- **Progress**: 55-60%

#### 3.4. Save Transcript (60-65%)
- **Hành động**:
  - Lưu transcript dạng JSON vào `transcripts/{video_name}.json`
  - Format:
    ```json
    {
      "segments": [
        {
          "start": 0.5,
          "end": 5.2,
          "text": "Câu tiếng Việt..."
        },
        ...
      ]
    }
    ```
- **Cleanup**: Xóa model khỏi memory, clear GPU cache
- **Output**: File JSON transcript
- **Progress**: 60-65%

---

### **BƯỚC 4: CHIA THÀNH CLIP CÂU (70-85%)**

#### 4.1. Load Transcript & Video Info (70%)
- **Hành động**:
  - Đọc file JSON transcript
  - Lấy video duration bằng `ffprobe`
  - Parse segments từ transcript
- **Progress**: 70%

#### 4.2. Process Each Segment (70-85%)
- **Công cụ**: FFmpeg
- **Với mỗi segment**:
  
  **4.2.1. Tính toán thời gian**:
  - `start_original`: Thời gian bắt đầu từ transcript (giây, có thể lẻ)
  - `end_original`: Thời gian kết thúc từ transcript
  - `start_rounded`: Làm tròn lên `start_original` (math.ceil)
  - `end_rounded`: Làm tròn lên `end_original`
  - `end_with_buffer`: 
    - Nếu là segment cuối: `end_rounded`
    - Nếu không phải: `end_rounded + 2.0` (thêm 2 giây buffer)
  - `duration`: `end_with_buffer - start_rounded`

  **4.2.2. Cắt clip**:
  ```bash
  ffmpeg -y -i {signer_video} \
    -ss {start_rounded} \
    -t {duration} \
    -c:v libx264 \
    -preset fast \
    -crf 23 \
    -c:a copy \
    {output_clip}
  ```
  
  **4.2.3. Tạo metadata**:
  - Tên clip: `{base_name}-{idx}.mp4`
  - Lưu vào `sentence_clips/`
  - Metadata record:
    ```python
    {
      'name': '{base_name}-{idx}',
      'video_source': 'signer_{original}.mp4',
      'segment_id': idx,
      'start_original': 0.5,
      'start_rounded': 1,
      'end_original': 5.2,
      'end_rounded': 6,
      'end_with_buffer': 8.0,
      'duration': 7.0,
      'is_last_segment': False,
      'text': 'Câu tiếng Việt...',
      'status': 'success' or 'failed'
    }
    ```

- **Progress**: 70% + (idx / total_segments * 15%)

#### 4.3. Save Metadata CSV (85%)
- **Hành động**:
  - Gộp tất cả metadata từ các video
  - Lưu vào `sentence_clips_metadata.csv`
  - Columns:
    - name, video_source, segment_id
    - start_original, start_rounded
    - end_original, end_rounded, end_with_buffer
    - duration, is_last_segment, text, status
- **Output**: CSV file với metadata tất cả clips
- **Progress**: 85%

---

### **BƯỚC 5: TẠO FILE ZIP (90-95%)**

#### 5.1. Create ZIP Archive (90-95%)
- **Công cụ**: Python `zipfile`
- **Hành động**:
  - Tạo file `result.zip` trong work directory
  - Thêm tất cả files từ `sentence_clips/*.mp4` vào `sentence_clips/` trong ZIP
  - Thêm `sentence_clips_metadata.csv` vào root của ZIP
  - Compression: ZIP_DEFLATED
- **Output**: `{work_dir}/result.zip`
- **Progress**: 90-95%

---

### **BƯỚC 6: HOÀN TẤT (95-100%)**

#### 6.1. Update Database (95-100%)
- **Hành động**:
  - Cập nhật task status = "completed"
  - Lưu zip_path vào database
  - Ghi nhận completed_at timestamp
  - Progress = 100%
- **Output**: Task hoàn tất, sẵn sàng download

---

## XỬ LÝ NHIỀU VIDEO (PLAYLIST)

Khi xử lý playlist hoặc nhiều video:

1. **Download tất cả video** (Step 1) - mỗi video được check signer riêng
2. **Với mỗi video đã pass signer check**:
   - Crop signer (Step 2)
   - Transcribe (Step 3)
   - Split clips (Step 4)
3. **Gộp metadata** từ tất cả video vào 1 CSV
4. **Tạo 1 ZIP** chứa tất cả clips từ tất cả video

**Progress calculation cho nhiều video**:
- Base progress: `15 + (idx / total_videos * 70)`
- Mỗi step trong video: `base + step_offset`

---

## XỬ LÝ LỖI & EDGE CASES

### Signer Detection Fail
- Video không có signer → Xóa file tạm, bỏ qua
- Không extract được frame → Bỏ qua video

### Transcription Fail
- Không load được model → Return None, skip video
- Alignment fail → Dùng raw transcription (cảnh báo)

### Video Processing Fail
- FFmpeg error → Ghi status='failed' trong metadata, tiếp tục segment khác
- Video duration không lấy được → Dùng 9999s làm max

### Cancellation
- User hủy task → Set cancelled flag
- Pipeline check flag trong progress callback
- Cleanup work directory
- Update database status = "cancelled"

---

## CẤU TRÚC THƯ MỤC KẾT QUẢ

```
{work_dir}/
├── raw/
│   └── {slugified-title}.mp4
├── signer_clips/
│   └── signer_{slugified-title}.mp4
├── transcripts/
│   └── {slugified-title}.json
├── sentence_clips/
│   ├── {base_name}-0.mp4
│   ├── {base_name}-1.mp4
│   └── ...
├── sentence_clips_metadata.csv
└── result.zip
    ├── sentence_clips/
    │   ├── {base_name}-0.mp4
    │   └── ...
    └── sentence_clips_metadata.csv
```

---

## THAM SỐ KỸ THUẬT

### Signer Detection
- **ROI Config**: x=125, y=637, width=178, height=159
- **Test Timestamps**: [2s, 10s, 20s]
- **Face Detection**: Haar Cascade, minNeighbors=6, minSize=(40,40)

### Video Processing
- **Crop ROI**: x=50, y=600, width=327, height=426
- **FFmpeg Preset**: fast
- **CRF**: 23 (quality balance)

### Transcription
- **Model**: WhisperX large-v3
- **Language**: Vietnamese (vi)
- **Batch Size**: 16
- **Alignment**: Vietnamese alignment model

### Clip Splitting
- **Buffer**: 2.0 giây (trừ segment cuối)
- **Rounding**: Math.ceil cho start/end
- **Output Format**: MP4, H.264

---

## PROGRESS TRACKING

| Progress % | Stage | Description |
|------------|-------|-------------|
| 0-5% | Init | Khởi tạo work directory |
| 5-15% | Download | Tải video từ YouTube + Signer check |
| 15-35% | Crop | Cắt vùng signer (per video) |
| 35-65% | Transcribe | Transcribe audio (per video) |
| 65-85% | Split | Chia thành clips (per video) |
| 85-90% | Metadata | Lưu metadata CSV |
| 90-95% | ZIP | Tạo file ZIP |
| 95-100% | Complete | Hoàn tất, update database |

---

## DEPENDENCIES

- **yt-dlp**: Download YouTube videos
- **OpenCV**: Face detection, video processing
- **FFmpeg**: Video cutting, cropping
- **WhisperX**: Speech-to-text transcription
- **Python**: zipfile, json, csv, pathlib

---

## OUTPUT FORMAT

### Metadata CSV Columns:
1. `name` - Tên clip (không có extension)
2. `video_source` - Tên file video gốc
3. `segment_id` - ID segment trong video
4. `start_original` - Thời gian bắt đầu gốc (từ transcript)
5. `start_rounded` - Thời gian bắt đầu đã làm tròn
6. `end_original` - Thời gian kết thúc gốc
7. `end_rounded` - Thời gian kết thúc đã làm tròn
8. `end_with_buffer` - Thời gian kết thúc có buffer
9. `duration` - Độ dài clip (giây)
10. `is_last_segment` - Có phải segment cuối không
11. `text` - Transcript text
12. `status` - success/failed

---

## NOTES

- Pipeline chạy **background** (không block API)
- Progress được update **real-time** qua callback
- Task có thể **hủy** bất cứ lúc nào
- Work directory được **giữ lại** sau khi hoàn tất (để download)
- User có thể **download ZIP** qua API endpoint


