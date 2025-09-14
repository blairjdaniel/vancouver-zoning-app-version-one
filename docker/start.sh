#!/bin/bash
set -e

echo "🚀 Starting Vancouver Zoning App..."

# Create log directories (we're already running as root in the start process)
mkdir -p /var/log/supervisor

# Initialize the backend environment
cd /app/backend
export FLASK_APP=app.py
export FLASK_ENV=production
export PYTHONPATH=/app

echo "✅ Environment configured"

# Start supervisor (which starts both nginx and the Flask backend)
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
