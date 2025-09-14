#!/bin/bash

# Vancouver Zoning App - Docker Registry Setup
# This script helps you push/pull the application to/from Docker Hub or a private registry

echo "🐳 Vancouver Zoning App - Docker Registry Setup"
echo "================================================"
echo ""

# Configuration
APP_NAME="vancouver-zoning-app"
DEFAULT_REGISTRY="docker.io"
DEFAULT_USERNAME="your-dockerhub-username"

# Get registry configuration
read -p "Enter Docker registry URL (default: docker.io): " REGISTRY
REGISTRY=${REGISTRY:-$DEFAULT_REGISTRY}

read -p "Enter your Docker Hub username (or registry username): " USERNAME
USERNAME=${USERNAME:-$DEFAULT_USERNAME}

read -p "Enter image tag/version (default: latest): " TAG
TAG=${TAG:-latest}

# Construct full image name
if [ "$REGISTRY" = "docker.io" ]; then
    FULL_IMAGE_NAME="$USERNAME/$APP_NAME:$TAG"
else
    FULL_IMAGE_NAME="$REGISTRY/$USERNAME/$APP_NAME:$TAG"
fi

echo ""
echo "🏗️  Configuration:"
echo "   Registry: $REGISTRY"
echo "   Username: $USERNAME"
echo "   App Name: $APP_NAME"
echo "   Tag: $TAG"
echo "   Full Image: $FULL_IMAGE_NAME"
echo ""

# Function to build image
build_image() {
    echo "🔨 Building Docker image..."
    docker build -t $FULL_IMAGE_NAME .
    if [ $? -eq 0 ]; then
        echo "✅ Image built successfully: $FULL_IMAGE_NAME"
    else
        echo "❌ Failed to build image"
        exit 1
    fi
}

# Function to push image
push_image() {
    echo "📤 Pushing image to registry..."
    
    # Login if not already logged in
    echo "🔐 Logging into Docker registry..."
    if [ "$REGISTRY" = "docker.io" ]; then
        docker login
    else
        docker login $REGISTRY
    fi
    
    if [ $? -eq 0 ]; then
        echo "✅ Login successful"
        docker push $FULL_IMAGE_NAME
        if [ $? -eq 0 ]; then
            echo "✅ Image pushed successfully!"
            echo "📋 Pull command: docker pull $FULL_IMAGE_NAME"
        else
            echo "❌ Failed to push image"
            exit 1
        fi
    else
        echo "❌ Login failed"
        exit 1
    fi
}

# Function to pull image
pull_image() {
    echo "📥 Pulling image from registry..."
    docker pull $FULL_IMAGE_NAME
    if [ $? -eq 0 ]; then
        echo "✅ Image pulled successfully!"
    else
        echo "❌ Failed to pull image"
        exit 1
    fi
}

# Function to run pulled image
run_image() {
    echo "🚀 Running pulled image..."
    docker run -d -p 8081:80 --name vancouver-zoning-app-pulled $FULL_IMAGE_NAME
    if [ $? -eq 0 ]; then
        echo "✅ Container started successfully!"
        echo "🌐 Access at: http://localhost:8081"
    else
        echo "❌ Failed to start container"
        exit 1
    fi
}

# Main menu
echo "Select an action:"
echo "1) Build and push image to registry"
echo "2) Pull image from registry"
echo "3) Pull and run image"
echo "4) Just build image locally"
echo "5) Exit"
echo ""

read -p "Enter your choice (1-5): " CHOICE

case $CHOICE in
    1)
        build_image
        push_image
        ;;
    2)
        pull_image
        ;;
    3)
        pull_image
        run_image
        ;;
    4)
        build_image
        ;;
    5)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "🎉 Docker registry operation completed!"
echo ""
echo "💡 Useful commands:"
echo "   List images: docker images"
echo "   Remove image: docker rmi $FULL_IMAGE_NAME"
echo "   View containers: docker ps -a"
echo "   Stop container: docker stop vancouver-zoning-app-pulled"
echo ""
