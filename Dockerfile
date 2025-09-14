# Vancouver Zoning App - Multi-stage Docker Build
# Production-ready container with both frontend and backend

# Stage 1: Build the React frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./
COPY frontend/yarn.lock* ./

# Install dependencies
RUN npm install

# Copy source code
COPY frontend/ ./

# Build the React app
RUN npm run build

# Stage 2: Build the Python backend environment
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gdal-bin \
    libgdal-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libspatialindex-dev \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy built frontend
COPY --from=frontend-builder /app/frontend/build /app/frontend/build

# Copy backend code and dependencies
COPY backend /app/backend
COPY files /app/files
COPY processed /app/processed
COPY configs /app/configs
COPY utils /app/utils

# Copy configuration files
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/start.sh /app/start.sh

# Make start script executable
RUN chmod +x /app/start.sh

# Create non-root user for backend
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Expose ports
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/ || exit 1

# Start the application (run as root for nginx)
CMD ["/app/start.sh"]
