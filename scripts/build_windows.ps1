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
$addDataArgs = @('--add-data','backend\\build;build','--add-data','backend\\models;models')

# Ensure PyInstaller writes output to the requested OutDir and uses a dedicated work path
$workPath = Join-Path -Path $OutDir -ChildPath 'build'
$distPath = $OutDir

# Build the argument array correctly and include hidden-imports
if (Test-Path .\desktop_app.spec) {
    Write-Host "desktop_app.spec found; using spec build (clean)"
    $args = @('-m','PyInstaller','--noconfirm','--clean','--distpath',$distPath,'--workpath',$workPath,'.\desktop_app.spec')
} else {
    $args = @('-m','PyInstaller','--noconfirm',$modeArg,'--distpath',$distPath,'--workpath',$workPath)
}
foreach ($hi in $hiddenImports) {
    $args += '--hidden-import'
    $args += $hi
}
$args += $addDataArgs
$args += @('--icon','build_icons/Arch.ico','backend\\desktop_app.py')

Write-Host "PyInstaller command: $PythonExe $($args -join ' ')"

# Ensure output directories exist so PyInstaller can write into them
if (-not (Test-Path -Path $OutDir)) {
    Write-Host "Creating output directory: $OutDir"
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

# Call Python directly so stdout/stderr show in CI logs and we can return the real exit code
& $PythonExe @args
$rc = $LASTEXITCODE
if ($rc -ne 0) {
    Write-Host "PyInstaller failed with exit code $rc"
    exit $rc
}

Write-Host "Build finished. If OneDir was used the output folder is: $OutDir\\desktop_app; if OneFile was used the artifact is: $OutDir\\desktop_app.exe"
