#!/bin/bash

# Vancouver Zoning App - Docker Registry Test
# Quick test script to verify registry functionality

echo "🧪 Testing Docker Registry Setup"
echo "================================"

# Test configuration
TEST_USERNAME="test-user"
TEST_TAG="test-$(date +%s)"
LOCAL_IMAGE="vancouver-zoning-app:latest"

echo "📋 Test Configuration:"
echo "   Username: $TEST_USERNAME"
echo "   Tag: $TEST_TAG" 
echo "   Local Image: $LOCAL_IMAGE"
echo ""

# Step 1: Check if local image exists
echo "1️⃣  Checking local image..."
if docker images | grep -q "vancouver-zoning-app.*latest"; then
    echo "✅ Local image found"
else
    echo "❌ Local image not found. Building..."
    docker build -t $LOCAL_IMAGE .
    if [ $? -ne 0 ]; then
        echo "❌ Failed to build local image"
        exit 1
    fi
fi

# Step 2: Tag for registry
echo ""
echo "2️⃣  Tagging image for registry..."
TEST_IMAGE="$TEST_USERNAME/vancouver-zoning-app:$TEST_TAG"
docker tag $LOCAL_IMAGE $TEST_IMAGE
echo "✅ Tagged as: $TEST_IMAGE"

# Step 3: Test registry scripts exist
echo ""
echo "3️⃣  Checking registry scripts..."
scripts=("docker-registry.sh" "docker-push.sh" "docker-pull.sh")
for script in "${scripts[@]}"; do
    if [ -x "$script" ]; then
        echo "✅ $script is executable"
    else
        echo "❌ $script is not executable"
        chmod +x "$script"
        echo "🔧 Made $script executable"
    fi
done

# Step 4: Test configuration file
echo ""
echo "4️⃣  Checking configuration..."
if [ -f ".env.docker-registry" ]; then
    echo "✅ Configuration template exists"
    echo "💡 Copy .env.docker-registry to .env and customize"
else
    echo "❌ Configuration template missing"
fi

# Step 5: Test Docker Hub connectivity
echo ""
echo "5️⃣  Testing Docker Hub connectivity..."
if curl -s https://index.docker.io/v1/ > /dev/null; then
    echo "✅ Docker Hub is accessible"
else
    echo "❌ Cannot reach Docker Hub"
fi

# Step 6: Show example commands
echo ""
echo "6️⃣  Example Commands:"
echo ""
echo "📤 Push to Docker Hub:"
echo "   ./docker-push.sh"
echo ""
echo "📥 Pull from Docker Hub:"  
echo "   ./docker-pull.sh -u your-username"
echo ""
echo "🔧 Interactive setup:"
echo "   ./docker-registry.sh"
echo ""
echo "🏗️  Manual Docker commands:"
echo "   docker build -t your-username/vancouver-zoning-app ."
echo "   docker push your-username/vancouver-zoning-app"
echo "   docker pull your-username/vancouver-zoning-app"
echo "   docker run -d -p 8081:80 your-username/vancouver-zoning-app"
echo ""

# Cleanup test image
echo "🧹 Cleaning up test image..."
docker rmi $TEST_IMAGE >/dev/null 2>&1 || true

echo "✅ Docker Registry test completed!"
echo ""
echo "💡 Next steps:"
echo "   1. Create Docker Hub account (https://hub.docker.com)"
echo "   2. Copy .env.docker-registry to .env and customize"
echo "   3. Run ./docker-push.sh to publish your image"
echo ""
