#!/bin/bash
# Script to manage DBeaver container for ViSL Tool

case "$1" in
  start)
    echo "🚀 Starting DBeaver..."
    # Check if network exists
    docker network inspect visl_network >/dev/null 2>&1 || docker network create visl_network
    
    # Connect visl_db to network if not already connected
    docker network connect visl_network visl_db 2>/dev/null || true
    
    # Start DBeaver container
    docker start dbeaver 2>/dev/null || docker run -d \
      --name dbeaver \
      --network visl_network \
      -p 5431:8978 \
      -e JAVA_OPTS="-Xmx2048m" \
      dbeaver/cloudbeaver:latest
    
    echo "✅ DBeaver is running on http://localhost:5431"
    echo ""
    echo "📝 Default credentials:"
    echo "   Username: admin"
    echo "   Password: admin"
    echo ""
    echo "🔗 To connect to PostgreSQL:"
    echo "   Host: visl_db"
    echo "   Port: 5432"
    echo "   Database: visl_tool"
    echo "   Username: postgres"
    echo "   Password: postgres"
    ;;
  stop)
    echo "🛑 Stopping DBeaver..."
    docker stop dbeaver
    echo "✅ DBeaver stopped"
    ;;
  restart)
    echo "🔄 Restarting DBeaver..."
    docker restart dbeaver
    echo "✅ DBeaver restarted"
    ;;
  logs)
    docker logs -f dbeaver
    ;;
  status)
    if docker ps | grep -q dbeaver; then
      echo "✅ DBeaver is running"
      echo "📍 URL: http://localhost:5431"
    else
      echo "❌ DBeaver is not running"
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|logs|status}"
    exit 1
    ;;
esac

