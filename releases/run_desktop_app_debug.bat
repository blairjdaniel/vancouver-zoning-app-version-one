@echo off
REM Improved debug wrapper for desktop_app.exe
REM - Writes stdout/stderr to a timestamped log
REM - Shows directory listing if exe missing and drops into an interactive shell
REM - Usage: run_desktop_app_debug.bat [exe-name]

setlocal enabledelayedexpansion

if "%~1"=="" (
  set "EXE=desktop_app.exe"
) else (
  set "EXE=%~1"
)

if not exist "%EXE%" (
  echo [ERROR] Executable "%EXE%" not found in %CD%
  echo Contents of folder:
  dir /b
  echo.
  echo If you intended to run the EXE from a different folder, drag-and-drop the EXE onto this script or run:
  echo     %~n0 full\\path\\to\\%EXE%
  echo.
  echo Press any key to open an interactive shell (so you can inspect files), or Ctrl+C to cancel...
  pause >nul
  cmd.exe
  exit /b 1
)

REM create a timestamped logfile to avoid stomping previous runs
for /f "tokens=1-6 delims=:-/. " %%a in ("%date% %time%") do (
  set YYYY=%%c
  set MM=%%a
  set DD=%%b
  set HH=%%d
  set Min=%%e
  set Sec=%%f
)
set LOGFILE=debug_run_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.log

echo [INFO] Running "%EXE%" and writing output to %LOGFILE%
echo ------- START: %DATE% %TIME% ------- > "%LOGFILE%"
"%EXE%" >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo ------- END: %DATE% %TIME% (exit code %RC%) ------- >> "%LOGFILE%"

echo Exit code: %RC%
echo ====== %LOGFILE% ======
type "%LOGFILE%"
echo.
echo The full log is saved as: %CD%\%LOGFILE%
echo Press any key to close this window.
pause >nul
