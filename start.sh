#!/bin/bash

echo "🏙️ Vancouver Zoning Viewer - Client Deployment"
echo "=============================================="
echo ""
echo "Starting the Vancouver Zoning Analysis Platform..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Please start Docker Desktop and try again."
    echo ""
    echo "Need help? See DOCKER_DESKTOP_GUIDE.md"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Build and start the application
echo "🔧 Building and starting the application..."
echo "This may take 2-3 minutes on first run..."
echo ""

docker-compose down > /dev/null 2>&1
docker-compose up -d

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Vancouver Zoning Viewer is starting up!"
    echo ""
    echo "📍 Application will be available at: http://localhost:8081"
    echo ""
    echo "⏱️  Please wait 30-60 seconds for full startup"
    echo ""
    echo "🧪 Test with these Vancouver addresses:"
    echo "   • 212 E 38TH AV (Heritage property)"
    echo "   • 728 E 39TH AV (Standard residential)"
    echo ""
    echo "📖 For more help, see README.md"
    echo ""
    echo "🔧 To stop the application: docker-compose down"
else
    echo ""
    echo "❌ Failed to start the application"
    echo "Check Docker Desktop is running and try again"
    echo ""
    echo "For troubleshooting, see README.md"
fi
