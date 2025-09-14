# Docker Registry Setup and Usage Guide

## Overview
This guide helps you set up a Docker registry for push/pull operations with the Vancouver Zoning App.

## Quick Start

### 1. Docker Hub Setup (Recommended)
```bash
# 1. Create Docker Hub account at https://hub.docker.com
# 2. Configure your credentials
cp .env.docker-registry .env
# Edit .env with your Docker Hub username

# 3. Build and push to Docker Hub
chmod +x docker-push.sh
./docker-push.sh
```

### 2. Pull and Deploy
```bash
# On any machine with Docker
chmod +x docker-pull.sh
./docker-pull.sh -u your-dockerhub-username
```

## Configuration Files

### `.env.docker-registry`
Template for registry configuration. Copy to `.env` and customize:
```bash
DOCKER_REGISTRY=docker.io
DOCKER_USERNAME=your-dockerhub-username
DOCKER_PASSWORD=your-access-token
IMAGE_NAME=vancouver-zoning-app
IMAGE_TAG=latest
```

## Scripts

### `docker-registry.sh` - Interactive Setup
Interactive script for one-time setup and testing:
```bash
chmod +x docker-registry.sh
./docker-registry.sh
```

Features:
- Prompts for registry configuration
- Build, push, pull, and run operations
- Support for Docker Hub and private registries

### `docker-push.sh` - Automated Push
Automated script for CI/CD pipelines:
```bash
chmod +x docker-push.sh
./docker-push.sh
```

Features:
- Reads configuration from `.env.docker-registry`
- Builds and pushes both tagged and latest versions
- Suitable for automated deployments

### `docker-pull.sh` - Pull and Deploy
Deployment script for production servers:
```bash
chmod +x docker-pull.sh
./docker-pull.sh -u your-username -t v1.0.0
```

Features:
- Command-line configuration options
- Automatic container management (stop old, start new)
- Health checks and deployment verification

## Registry Options

### Docker Hub (Public)
- **Registry**: `docker.io`
- **Image Format**: `username/vancouver-zoning-app:tag`
- **Free**: Public repositories
- **Paid**: Private repositories

### Docker Hub (Private)
Same as public, but with private repository access.

### AWS ECR (Private)
```bash
# Configuration
DOCKER_REGISTRY=123456789012.dkr.ecr.us-west-2.amazonaws.com
DOCKER_USERNAME=AWS
# Use AWS CLI for authentication
```

### Azure Container Registry
```bash
# Configuration  
DOCKER_REGISTRY=yourregistry.azurecr.io
DOCKER_USERNAME=yourregistry
DOCKER_PASSWORD=your-access-token
```

### Google Container Registry
```bash
# Configuration
DOCKER_REGISTRY=gcr.io
DOCKER_USERNAME=_json_key
DOCKER_PASSWORD=your-service-account-json
```

### Self-Hosted Registry
```bash
# Configuration
DOCKER_REGISTRY=your-registry.company.com:5000
DOCKER_USERNAME=your-username
DOCKER_PASSWORD=your-password
```

## Usage Examples

### Developer Workflow
```bash
# 1. Make changes to the application
# 2. Build and push new version
./docker-push.sh

# 3. Test deployment
./docker-pull.sh -t latest
```

### Production Deployment
```bash
# 1. Pull specific version
./docker-pull.sh -u mycompany -t v1.2.3

# 2. Verify deployment
curl http://localhost:8081/api/health
```

### CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Build and Push
  run: |
    cp .env.docker-registry .env
    ./docker-push.sh
  env:
    DOCKER_USERNAME: ${{ secrets.DOCKER_USERNAME }}
    DOCKER_PASSWORD: ${{ secrets.DOCKER_PASSWORD }}
```

## Security Best Practices

### Access Tokens
Use Docker Hub access tokens instead of passwords:
1. Go to Docker Hub → Account Settings → Security
2. Create new access token
3. Use token as password in configuration

### Environment Variables
Store sensitive data in environment variables:
```bash
export DOCKER_USERNAME=myusername
export DOCKER_PASSWORD=mytoken
./docker-push.sh
```

### Private Registries
For production deployments, use private registries:
- Better security control
- Faster pulls (regional)
- Custom authentication

## Troubleshooting

### Authentication Issues
```bash
# Clear Docker credentials
docker logout

# Re-login manually
docker login
```

### Push/Pull Failures
```bash
# Check Docker daemon status
docker info

# Verify image exists locally
docker images | grep vancouver-zoning-app

# Check registry connectivity
curl -I https://index.docker.io/v1/
```

### Container Issues
```bash
# View container logs
docker logs vancouver-zoning-app

# Check container status
docker ps -a

# Enter container for debugging
docker exec -it vancouver-zoning-app /bin/bash
```

## Image Management

### Tagging Strategy
- `latest`: Current development version
- `v1.0.0`: Stable release versions
- `staging`: Pre-production testing
- `production`: Production-ready releases

### Cleanup
```bash
# Remove old images
docker image prune

# Remove specific version
docker rmi username/vancouver-zoning-app:old-tag
```

## Monitoring

### Registry Usage
- Monitor image pull counts
- Track storage usage
- Set up alerts for failed deployments

### Application Health
```bash
# Automated health checks
while true; do
  curl -f http://localhost:8081/api/health || echo "Health check failed"
  sleep 60
done
```
