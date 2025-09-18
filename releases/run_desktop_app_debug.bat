@echo off
REM Run the desktop_app exe and capture stdout/stderr to debug_run.log, then pause so console stays open.
REM Usage: run_desktop_app_debug.bat [exe-name]

if "%~1"=="" (
  set "EXE=desktop_app.exe"
) else (
  set "EXE=%~1"
)

if not exist "%EXE%" (
  echo Executable "%EXE%" not found in %CD%
  echo Contents of folder:
  dir
  pause
  exit /b 1
)

necho Running "%EXE%" ...
"%EXE%" > debug_run.log 2>&1
echo Exit code: %ERRORLEVEL%
echo ====== debug_run.log ======
type debug_run.log
pause
