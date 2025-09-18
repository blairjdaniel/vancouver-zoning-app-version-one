<##
# Helper script to build the Windows onefile executable locally using PyInstaller.
# Run from PowerShell on Windows with an activated venv.
##>
param(
    [string]$PythonExe = "python",
    [string]$OutDir = "dist",
    [switch]$OneDir # if set, build --onedir for easier debugging
)

Write-Host "Installing build deps..."
Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList '-m','pip','install','--upgrade','pip' -Wait
Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList '-m','pip','install','pyinstaller==5.10.1','keyring','yelpapi','openai' -Wait

# Common hidden imports that PyInstaller may miss (ipaddress, keyring import hooks, etc.)
$hiddenImports = @(
    'ipaddress',
    'keyring',
    'yelpapi',
    'openai',
    'pkg_resources.py2_warn'
)

$hiddenArg = $hiddenImports | ForEach-Object { "--hidden-import=$_" } | Join-String ' '

Write-Host "Running PyInstaller... (OneDir=$OneDir)"

$modeArg = if ($OneDir) { '--onedir' } else { '--onefile' }

# Ensure add-data paths are correct for Windows builds (source;dest)
$addDataArgs = '--add-data','backend\\build;build','--add-data','backend\\models;models'


# Ensure PyInstaller writes output to the requested OutDir and uses a dedicated work path
$workPath = Join-Path -Path $OutDir -ChildPath 'build'
$distPath = $OutDir

$args = @('-m','PyInstaller','--noconfirm',$modeArg,'--distpath',$distPath,'--workpath',$workPath) + $hiddenImports | ForEach-Object { @('--hidden-import', $_) } + $addDataArgs + @('--icon','build_icons/Arch.ico','backend\\desktop_app.py')

Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList $args -Wait

Write-Host "Build finished. If OneDir was used the output folder is: $OutDir\\desktop_app; if OneFile was used the artifact is: $OutDir\\desktop_app.exe"
