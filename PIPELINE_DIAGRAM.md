# SƠ ĐỒ PIPELINE - CÔNG CỤ THU THẬP DỮ LIỆU ViSL

## SƠ ĐỒ TỔNG QUAN (Mermaid)

```mermaid
flowchart TD
    Start([User nhập YouTube URL]) --> Init[Khởi tạo Work Directory]
    Init --> Download[Tải Video từ YouTube]
    Download --> CheckSigner{Phát hiện Signer?}
    CheckSigner -->|Không có| Delete[Xóa video tạm]
    CheckSigner -->|Có| Rename[Đổi tên và lưu]
    Delete --> NextVideo{Video tiếp theo?}
    Rename --> Crop[Cắt vùng Signer ROI]
    Crop --> Transcribe[Transcribe bằng WhisperX]
    Transcribe --> Split[Chia thành Clip câu]
    Split --> NextVideo
    NextVideo -->|Còn| Download
    NextVideo -->|Hết| Metadata[Gộp Metadata CSV]
    Metadata --> ZIP[Tạo file ZIP]
    ZIP --> Complete([Hoàn tất - Sẵn sàng Download])
    
    style Start fill:#e1f5ff
    style Complete fill:#c8e6c9
    style CheckSigner fill:#fff9c4
    style Delete fill:#ffcdd2
```

---

## SƠ ĐỒ CHI TIẾT TỪNG BƯỚC

### BƯỚC 1: DOWNLOAD & SIGNER DETECTION

```mermaid
flowchart LR
    A[YouTube URL] --> B[yt-dlp Extract Info]
    B --> C{Playlist?}
    C -->|Có| D[Lấy danh sách video]
    C -->|Không| E[Single video]
    D --> F[Tải video 1]
    E --> F
    F --> G[Lưu temp file]
    G --> H[Extract 3 frames<br/>2s, 10s, 20s]
    H --> I[Face Detection<br/>trên ROI]
    I --> J{3/3 frames<br/>có signer?}
    J -->|Không| K[Xóa temp file]
    J -->|Có| L[Đổi tên slug]
    L --> M[Lưu vào raw/]
    K --> N[Bỏ qua video]
    M --> O[Video tiếp theo]
    N --> O
```

---

### BƯỚC 2: CROP SIGNER

```mermaid
flowchart LR
    A[Video gốc<br/>raw/] --> B[FFmpeg Crop]
    B --> C[ROI: 327x426<br/>x=50, y=600]
    C --> D[Video đã crop<br/>signer_clips/]
```

---

### BƯỚC 3: TRANSCRIBE

```mermaid
flowchart TD
    A[Video đã crop] --> B[Load WhisperX Model<br/>large-v3]
    B --> C{GPU available?}
    C -->|Có| D[Device: CUDA<br/>Compute: float16]
    C -->|Không| E[Device: CPU<br/>Compute: int8]
    D --> F[Load Audio]
    E --> F
    F --> G[Transcribe<br/>batch_size=16, lang=vi]
    G --> H[Load Alignment Model]
    H --> I[Align Timestamps]
    I --> J[Save JSON<br/>transcripts/]
    J --> K[Cleanup Memory]
```

---

### BƯỚC 4: SPLIT CLIPS

```mermaid
flowchart TD
    A[Load Transcript JSON] --> B[Get Video Duration]
    B --> C[Loop qua mỗi Segment]
    C --> D[Tính toán thời gian:<br/>start_rounded, end_with_buffer]
    D --> E[FFmpeg Cut Clip]
    E --> F[Lưu clip vào<br/>sentence_clips/]
    F --> G[Tạo Metadata Record]
    G --> H{Segment cuối?}
    H -->|Không| C
    H -->|Có| I[Save Metadata CSV]
```

---

### BƯỚC 5: CREATE ZIP

```mermaid
flowchart LR
    A[sentence_clips/*.mp4] --> C[Tạo ZIP]
    B[sentence_clips_metadata.csv] --> C
    C --> D[result.zip]
```

---

## SƠ ĐỒ XỬ LÝ NHIỀU VIDEO

```mermaid
flowchart TD
    Start([YouTube URL<br/>max_videos=N]) --> DownloadAll[Tải tất cả video]
    DownloadAll --> Filter[Lọc video có signer]
    Filter --> Video1[Video 1]
    Filter --> Video2[Video 2]
    Filter --> VideoN[Video N]
    
    Video1 --> Process1[Crop → Transcribe → Split]
    Video2 --> Process2[Crop → Transcribe → Split]
    VideoN --> ProcessN[Crop → Transcribe → Split]
    
    Process1 --> Merge[Gộp Metadata]
    Process2 --> Merge
    ProcessN --> Merge
    
    Merge --> ZIP[Tạo ZIP chứa tất cả clips]
    ZIP --> Complete([Hoàn tất])
```

---

## SƠ ĐỒ PROGRESS TRACKING

```mermaid
gantt
    title Pipeline Progress Timeline
    dateFormat X
    axisFormat %s
    
    section Init
    Khởi tạo Work Dir    :0, 5
    
    section Download
    Extract Info         :5, 3
    Download Videos      :8, 4
    Signer Detection     :12, 3
    
    section Process
    Crop Signer          :15, 20
    Transcribe           :35, 30
    Split Clips          :65, 20
    
    section Finalize
    Save Metadata        :85, 5
    Create ZIP           :90, 5
    Complete             :95, 5
```

---

## SƠ ĐỒ XỬ LÝ LỖI

```mermaid
flowchart TD
    Start[Start Pipeline] --> Try[Try Block]
    Try --> Process[Process Video]
    Process --> Success{Success?}
    Success -->|Có| UpdateDB[Update DB: completed]
    Success -->|Không| Error[Exception]
    
    Error --> CheckCancel{Cancelled?}
    CheckCancel -->|Có| Cancel[Update DB: cancelled<br/>Cleanup work_dir]
    CheckCancel -->|Không| Fail[Update DB: failed<br/>Save error message]
    
    UpdateDB --> End([End])
    Cancel --> End
    Fail --> End
    
    Process -.->|User Cancel| CancelFlag[Set cancelled flag]
    CancelFlag -.->|Check in callback| CheckCancel
```

---

## SƠ ĐỒ CẤU TRÚC DỮ LIỆU

```mermaid
graph TD
    A[Work Directory] --> B[raw/]
    A --> C[signer_clips/]
    A --> D[transcripts/]
    A --> E[sentence_clips/]
    A --> F[metadata.csv]
    A --> G[result.zip]
    
    B --> B1[video1.mp4]
    B --> B2[video2.mp4]
    
    C --> C1[signer_video1.mp4]
    C --> C2[signer_video2.mp4]
    
    D --> D1[video1.json]
    D --> D2[video2.json]
    
    E --> E1[video1-0.mp4]
    E --> E2[video1-1.mp4]
    E --> E3[video2-0.mp4]
    
    G --> G1[sentence_clips/]
    G --> G2[metadata.csv]
    
    G1 --> G1A[video1-0.mp4]
    G1 --> G1B[video1-1.mp4]
```

---

## SƠ ĐỒ API FLOW

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Background
    participant Pipeline
    participant Database
    
    User->>Frontend: Nhập YouTube URL
    Frontend->>API: POST /api/collecting/process
    API->>Database: Tạo CollectingTask (pending)
    API->>Background: Start process_video_task()
    API-->>Frontend: Return task_id
    
    Background->>Database: Update status = processing
    Background->>Pipeline: Run pipeline
    Pipeline->>Pipeline: Download videos
    Pipeline->>Pipeline: Signer detection
    Pipeline->>Pipeline: Crop signer
    Pipeline->>Pipeline: Transcribe
    Pipeline->>Pipeline: Split clips
    Pipeline->>Pipeline: Create ZIP
    Pipeline-->>Background: Return zip_path
    
    Background->>Database: Update status = completed
    
    Frontend->>API: GET /api/collecting/status/{task_id}
    API-->>Frontend: Return progress & status
    
    Frontend->>API: GET /api/collecting/download/{task_id}
    API-->>Frontend: Return ZIP file
```

---

## SƠ ĐỒ SIGNER DETECTION CHI TIẾT

```mermaid
flowchart TD
    A[Video tạm] --> B[Extract Frame tại 2s]
    A --> C[Extract Frame tại 10s]
    A --> D[Extract Frame tại 20s]
    
    B --> E[Resize về 1920x1080]
    C --> F[Resize về 1920x1080]
    D --> G[Resize về 1920x1080]
    
    E --> H[Crop ROI<br/>x=125, y=637<br/>w=178, h=159]
    F --> I[Crop ROI]
    G --> J[Crop ROI]
    
    H --> K[Face Detection<br/>Haar Cascade]
    I --> L[Face Detection]
    J --> M[Face Detection]
    
    K --> N{Has Face?}
    L --> O{Has Face?}
    M --> P{Has Face?}
    
    N --> Q[Result 1]
    O --> R[Result 2]
    P --> S[Result 3]
    
    Q --> T{All 3 = True?}
    R --> T
    S --> T
    
    T -->|Có| U[✓ PASS - Giữ video]
    T -->|Không| V[✗ FAIL - Xóa video]
```

---

## GHI CHÚ VẼ DIAGRAM

### Màu sắc đề xuất:
- **Xanh dương nhạt**: Bắt đầu (Start)
- **Xanh lá**: Hoàn tất (Complete/Success)
- **Vàng**: Kiểm tra điều kiện (Decision)
- **Đỏ**: Lỗi/Xóa (Error/Delete)
- **Xám**: Xử lý trung gian (Process)

### Ký hiệu:
- Hình thoi: Decision/Check
- Hình chữ nhật: Process/Action
- Hình tròn: Start/End
- Mũi tên đứt nét: Callback/Event

### Layout:
- **Top to Bottom**: Flow chính
- **Left to Right**: Parallel processing
- **Sequence Diagram**: API interactions


