@echo off
echo 🏢 Setting up Vancouver Zoning Viewer...

echo 📋 Checking prerequisites...

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is required but not installed. Please install Node.js 16+ from https://nodejs.org/
    pause
    exit /b 1
)

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3 is required but not installed. Please install Python 3.8+
    pause
    exit /b 1
)

echo ✅ Node.js found
echo ✅ Python found

:: Setup Frontend
echo.
echo 🎨 Setting up React frontend...
cd frontend
call npm install
if errorlevel 1 (
    echo ❌ Frontend setup failed
    pause
    exit /b 1
)
echo ✅ Frontend dependencies installed
cd ..

:: Setup Backend  
echo.
echo 🔧 Setting up Flask backend...
cd backend

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating Python virtual environment...
    python -m venv venv
)

:: Activate virtual environment and install requirements
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Backend setup failed
    pause
    exit /b 1
)
echo ✅ Backend dependencies installed

cd ..

echo.
echo 🎉 Setup complete!
echo.
echo 🚀 To start the application:
echo.
echo 1. Start the backend (in one terminal):
echo    cd backend
echo    venv\Scripts\activate.bat
echo    python app.py
echo.
echo 2. Start the frontend (in another terminal):
echo    cd frontend
echo    npm start
echo.
echo 3. Open http://localhost:3000 in your browser
echo.
echo 💡 Optional: Set environment variables for enhanced features:
echo    set HOUSKI_API_KEY=your_key_here

pause
