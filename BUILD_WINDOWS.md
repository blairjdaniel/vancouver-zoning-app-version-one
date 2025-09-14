Building a Windows executable (onefile) for vancouver-zoning-app

Local (Windows) steps
1. Install Python 3.11 and create/activate a virtualenv.
2. From PowerShell, run:

```powershell
# activate your venv then
.\scripts\build_windows.ps1 -PythonExe python
```

This runs PyInstaller to create `dist\desktop_app.exe`.

CI (GitHub Actions)
- A workflow `.github/workflows/build-windows.yml` is provided; it runs on `windows-latest`, installs PyInstaller, and uploads `dist/desktop_app.exe` as an artifact.

Code signing for Windows distribution
- Obtain an EV Code Signing certificate from a CA (recommended for best UX).
- Use Microsoft's `signtool.exe` to sign the executable and timestamp it:

```powershell
# Example (replace with your cert/key info)
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 /v dist\desktop_app.exe
```

Notes
- Test the built exe on a clean Windows VM before publishing.
- For user-friendly distribution, wrap the exe in an installer (.msi or .exe) and sign the installer as well.
