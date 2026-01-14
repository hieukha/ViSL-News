#!/bin/bash
# Start ViSL Tool locally (without Docker)

echo "🚀 Starting ViSL Tool locally..."

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start PostgreSQL if using Docker for DB only
echo "📦 Checking PostgreSQL..."
docker ps | grep visl_db > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Starting PostgreSQL container..."
    docker run -d \
        --name visl_db \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=visl_tool \
        -p 5433:5432 \
        postgres:15-alpine
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5
fi

# Start Backend
echo ""
echo "🐍 Starting Backend..."
cd "$DIR/backend"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/visl_tool"
export VIDEO_DIR="/workspace/khanh/ViSL-News/data/sentence_clips"
export SIGNER_CLIPS_DIR="/workspace/khanh/ViSL-News/data/signer_clips"
export HF_HOME="/workspace/khanh/ViSL-News/cache"

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start Frontend
echo ""
echo "⚛️  Starting Frontend..."
cd "$DIR/frontend"
npm install 2>/dev/null || true
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ ViSL Tool is running!"
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle Ctrl+C
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# Wait
wait

