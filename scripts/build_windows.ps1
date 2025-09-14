<##
# Helper script to build the Windows onefile executable locally using PyInstaller.
# Run from PowerShell on Windows with an activated venv.
##>
param(
    [string]$PythonExe = "python",
    [string]$OutDir = "dist"
)

Write-Host "Installing build deps..."
Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList '-m','pip','install','--upgrade','pip' -Wait
Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList '-m','pip','install','pyinstaller==5.10.1','keyring' -Wait

Write-Host "Running PyInstaller..."
Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList '-m','PyInstaller','--noconfirm','--onefile','--add-data','backend\\build;build','--add-data','backend\\models;models','--icon','build_icons/Arch.ico','backend\\desktop_app.py' -Wait

Write-Host "Build finished. Artifact: $OutDir\\desktop_app.exe"
