#!/bin/bash

# Vancouver Zoning App - Docker Pull and Deploy
# This script pulls the latest image from registry and deploys it

set -e  # Exit on any error

echo "📥 Vancouver Zoning App - Pull and Deploy"
echo "========================================"

# Default configuration
DEFAULT_REGISTRY="docker.io"
DEFAULT_USERNAME="your-dockerhub-username"
DEFAULT_IMAGE="vancouver-zoning-app"
DEFAULT_TAG="latest"

# Get configuration from user or environment
REGISTRY=${DOCKER_REGISTRY:-$DEFAULT_REGISTRY}
USERNAME=${DOCKER_USERNAME:-$DEFAULT_USERNAME}
IMAGE_NAME=${IMAGE_NAME:-$DEFAULT_IMAGE}
TAG=${IMAGE_TAG:-$DEFAULT_TAG}

# Allow command line overrides
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -r, --registry    Docker registry (default: docker.io)"
            echo "  -u, --username    Registry username"
            echo "  -i, --image       Image name (default: vancouver-zoning-app)"
            echo "  -t, --tag         Image tag (default: latest)"
            echo "  -h, --help        Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Construct full image name
if [ "$REGISTRY" = "docker.io" ]; then
    FULL_IMAGE_NAME="$USERNAME/$IMAGE_NAME:$TAG"
else
    FULL_IMAGE_NAME="$REGISTRY/$USERNAME/$IMAGE_NAME:$TAG"
fi

echo "📋 Configuration:"
echo "   Registry: $REGISTRY"
echo "   Username: $USERNAME"
echo "   Image: $IMAGE_NAME"
echo "   Tag: $TAG"
echo "   Full Image: $FULL_IMAGE_NAME"
echo ""

# Stop existing container if running
echo "🛑 Stopping existing container..."
docker stop vancouver-zoning-app 2>/dev/null || echo "   No existing container to stop"
docker rm vancouver-zoning-app 2>/dev/null || echo "   No existing container to remove"

# Pull latest image
echo "📥 Pulling latest image..."
docker pull $FULL_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull image"
    echo "💡 Make sure you have access to the registry and the image exists"
    exit 1
fi

echo "✅ Image pulled successfully"

# Run the container
echo "🚀 Starting new container..."
docker run -d \
    --name vancouver-zoning-app \
    -p 8081:80 \
    --restart unless-stopped \
    $FULL_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "❌ Failed to start container"
    exit 1
fi

# Wait for container to be ready
echo "⏱️  Waiting for application to start..."
sleep 10

# Health check
echo "🏥 Checking application health..."
HEALTH_URL="http://localhost:8081/api/health"
for i in {1..30}; do
    if curl -f $HEALTH_URL >/dev/null 2>&1; then
        echo "✅ Application is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Application health check failed"
        echo "🔍 Check container logs: docker logs vancouver-zoning-app"
        exit 1
    fi
    sleep 2
done

echo ""
echo "🎉 Vancouver Zoning App deployed successfully!"
echo ""
echo "🌐 Access the application at: http://localhost:8081"
echo ""
echo "🔧 Useful commands:"
echo "   View logs: docker logs vancouver-zoning-app"
echo "   Stop app:  docker stop vancouver-zoning-app"
echo "   Restart:   docker restart vancouver-zoning-app"
echo ""
