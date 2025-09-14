#!/bin/bash

# Vancouver Zoning App - Automated Docker Registry Push
# This script automates the build and push process for CI/CD

set -e  # Exit on any error

echo "🚀 Vancouver Zoning App - Automated Registry Push"
echo "================================================="

# Load configuration from environment file
if [ -f ".env.docker-registry" ]; then
    source .env.docker-registry
    echo "✅ Loaded configuration from .env.docker-registry"
else
    echo "❌ Configuration file .env.docker-registry not found"
    echo "   Copy .env.docker-registry to .env and customize it"
    exit 1
fi

# Validate required variables
if [ -z "$DOCKER_USERNAME" ] || [ -z "$IMAGE_NAME" ]; then
    echo "❌ Missing required configuration:"
    echo "   DOCKER_USERNAME and IMAGE_NAME must be set"
    exit 1
fi

# Construct image names
if [ "$DOCKER_REGISTRY" = "docker.io" ]; then
    FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:$IMAGE_TAG"
    LATEST_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:latest"
else
    FULL_IMAGE_NAME="$DOCKER_REGISTRY/$DOCKER_USERNAME/$IMAGE_NAME:$IMAGE_TAG"
    LATEST_IMAGE_NAME="$DOCKER_REGISTRY/$DOCKER_USERNAME/$IMAGE_NAME:latest"
fi

echo "🏗️  Building images:"
echo "   Tagged: $FULL_IMAGE_NAME"
echo "   Latest: $LATEST_IMAGE_NAME"
echo ""

# Build the image
echo "🔨 Building Docker image..."
docker build -t $FULL_IMAGE_NAME -t $LATEST_IMAGE_NAME .

if [ $? -ne 0 ]; then
    echo "❌ Failed to build image"
    exit 1
fi

echo "✅ Image built successfully"

# Login to registry
echo "🔐 Logging into Docker registry..."
if [ -n "$DOCKER_PASSWORD" ]; then
    echo "$DOCKER_PASSWORD" | docker login $DOCKER_REGISTRY -u $DOCKER_USERNAME --password-stdin
else
    docker login $DOCKER_REGISTRY -u $DOCKER_USERNAME
fi

if [ $? -ne 0 ]; then
    echo "❌ Failed to login to registry"
    exit 1
fi

echo "✅ Login successful"

# Push both tags
echo "📤 Pushing tagged image..."
docker push $FULL_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "❌ Failed to push tagged image"
    exit 1
fi

echo "📤 Pushing latest image..."
docker push $LATEST_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "❌ Failed to push latest image"
    exit 1
fi

echo ""
echo "🎉 Images pushed successfully!"
echo ""
echo "📋 Pull commands:"
echo "   docker pull $FULL_IMAGE_NAME"
echo "   docker pull $LATEST_IMAGE_NAME"
echo ""
echo "🚀 Run command:"
echo "   docker run -d -p 8081:80 --name vancouver-zoning-app $LATEST_IMAGE_NAME"
echo ""
