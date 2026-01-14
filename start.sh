#!/bin/bash
# Start ViSL Tool with Docker

echo "🚀 Starting ViSL Tool..."

# Build and start containers
docker-compose up --build -d

echo ""
echo "✅ ViSL Tool is running!"
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "To stop: docker-compose down"

