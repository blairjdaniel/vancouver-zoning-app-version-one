#!/bin/bash

# Vancouver Zoning Viewer - Setup Script
echo "🏢 Setting up Vancouver Zoning Viewer..."

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed. Please install Node.js 16+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    echo "❌ Node.js 16+ is required. Current version: $(node --version)"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✅ Node.js $(node --version) found"
echo "✅ Python $(python3 --version) found"

# Setup Frontend
echo ""
echo "🎨 Setting up React frontend..."
cd frontend
npm install
if [ $? -ne 0 ]; then
    echo "❌ Frontend setup failed"
    exit 1
fi
echo "✅ Frontend dependencies installed"
cd ..

# Setup Backend
echo ""
echo "🔧 Setting up Flask backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Backend setup failed"
    exit 1
fi
echo "✅ Backend dependencies installed"

cd ..

echo ""
echo "🎉 Setup complete!"
echo ""
echo "🚀 To start the application:"
echo ""
echo "1. Start the backend (in one terminal):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "2. Start the frontend (in another terminal):"
echo "   cd frontend" 
echo "   npm start"
echo ""
echo "3. Open http://localhost:3000 in your browser"
echo ""
echo "💡 Optional: Set environment variables for enhanced features:"
echo "   export HOUSKI_API_KEY=\"your_key_here\""
