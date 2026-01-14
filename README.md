# ViSL Tool v2.0

**Vietnamese Sign Language Tool** - Công cụ tích hợp thu thập, xử lý và gán nhãn video ngôn ngữ ký hiệu Việt Nam.

## 🌟 Tính năng

### 1. Thu thập Video (Collecting)
- Tải video từ YouTube (đơn lẻ hoặc playlist)
- Tự động phát hiện và cắt vùng người ký hiệu (signer)
- Transcribe âm thanh bằng WhisperX AI
- Chia video thành các đoạn câu
- Xuất ZIP chứa clips và metadata

### 2. Gán nhãn Dữ liệu (Labeling)
- Giao diện video player với timeline
- Căn chỉnh start/end time
- Thêm gloss sequence
- Quản lý trạng thái (raw, in_progress, expert_labeled, reviewed)
- Thống kê tiến độ real-time

### 3. Xác thực (Auth)
- Đăng ký / Đăng nhập
- JWT token authentication
- Phân quyền (admin, annotator)

## 📁 Cấu trúc dự án

```
ViSL_tool/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── core/              # Config, Database, Security
│   │   ├── models/            # SQLAlchemy Models
│   │   ├── modules/           # Modular Monolith
│   │   │   ├── auth/          # Authentication
│   │   │   ├── collecting/    # Video Processing
│   │   │   └── labeling/      # Annotation Management
│   │   └── main.py            # FastAPI App
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # Next.js Frontend
│   ├── app/
│   │   ├── page.tsx           # Home
│   │   ├── collecting/        # Video Collection UI
│   │   ├── labeling/          # Annotation UI
│   │   └── login/             # Auth UI
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── start.sh                   # Docker start script
├── start-local.sh             # Local development script
└── README.md
```

## 🚀 Cách chạy

### Option 1: Docker (Recommended)

```bash
# Start all services
./start.sh

# Or manually
docker-compose up --build
```

Truy cập:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Local Development

```bash
# Start with local script
./start-local.sh
```

Hoặc chạy thủ công:

```bash
# Terminal 1: Start PostgreSQL
docker run -d --name visl_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=visl_tool \
  -p 5433:5432 \
  postgres:15-alpine

# Terminal 2: Start Backend
cd backend
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/visl_tool"
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# Terminal 3: Start Frontend
cd frontend
npm install
npm run dev
```

## 📡 API Endpoints

### Auth
- `POST /api/auth/register` - Đăng ký
- `POST /api/auth/login` - Đăng nhập
- `GET /api/auth/me` - Thông tin user

### Collecting (Video Processing)
- `POST /api/collecting/process` - Bắt đầu xử lý video
- `GET /api/collecting/status/{task_id}` - Kiểm tra tiến độ
- `GET /api/collecting/download/{task_id}` - Tải kết quả
- `DELETE /api/collecting/task/{task_id}` - Xóa task

### Labeling (Annotation)
- `GET /api/labeling/segments` - Danh sách segments
- `GET /api/labeling/segments/{id}` - Chi tiết segment
- `POST /api/labeling/annotations` - Tạo annotation
- `GET /api/labeling/stats` - Thống kê

## 🔧 Cấu hình

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/visl_tool

# Auth
SECRET_KEY=your-secret-key

# Video directories
VIDEO_DIR=/path/to/sentence_clips
SIGNER_CLIPS_DIR=/path/to/signer_clips

# AI Cache
HF_HOME=/path/to/cache
```

## 📦 Tech Stack

### Backend
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **PostgreSQL** - Database
- **python-jose** - JWT
- **WhisperX** - Speech-to-text
- **yt-dlp** - YouTube download
- **OpenCV** - Video processing
- **FFmpeg** - Video manipulation

### Frontend
- **Next.js 14** - React framework
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **TypeScript** - Type safety

## 📝 License

MIT License

