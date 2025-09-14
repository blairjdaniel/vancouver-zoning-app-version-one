@echo off
echo 🏙️ Vancouver Zoning Viewer - Client Deployment
echo ==============================================
echo.
echo Starting the Vancouver Zoning Analysis Platform...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running!
    echo Please start Docker Desktop and try again.
    echo.
    echo Need help? See DOCKER_DESKTOP_GUIDE.md
    pause
    exit /b 1
)

echo ✅ Docker is running
echo.

REM Build and start the application
echo 🔧 Building and starting the application...
echo This may take 2-3 minutes on first run...
echo.

docker-compose down >nul 2>&1
docker-compose up -d

if %errorlevel% equ 0 (
    echo.
    echo 🎉 Vancouver Zoning Viewer is starting up!
    echo.
    echo 📍 Application will be available at: http://localhost:8081
    echo.
    echo ⏱️  Please wait 30-60 seconds for full startup
    echo.
    echo 🧪 Test with these Vancouver addresses:
    echo    • 212 E 38TH AV ^(Heritage property^)
    echo    • 728 E 39TH AV ^(Standard residential^)
    echo.
    echo 📖 For more help, see README.md
    echo.
    echo 🔧 To stop the application: docker-compose down
) else (
    echo.
    echo ❌ Failed to start the application
    echo Check Docker Desktop is running and try again
    echo.
    echo For troubleshooting, see README.md
)

echo.
pause
