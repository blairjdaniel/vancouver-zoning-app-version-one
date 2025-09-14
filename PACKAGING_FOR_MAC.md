Packaging for macOS (pywebview + PyInstaller)

This guide creates a single macOS executable that launches the backend and shows the React frontend in a native window.

1) Build the frontend

```bash
cd /Users/blairjdaniel/TOAD/vancouver-zoning-app-client-optimized/frontend
npm install
npm run build
```

2) Copy frontend build into backend

```bash
cd /Users/blairjdaniel/TOAD/vancouver-zoning-app-client-optimized
rm -rf backend/build
cp -R frontend/build backend/build
```

3) Create virtualenv and install Python deps

```bash
cd /Users/blairjdaniel/TOAD/vancouver-zoning-app-client-optimized
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install pywebview requests pyinstaller
```

4) Test locally (before packaging)

```bash
# from project root
source .venv/bin/activate
python3 backend/desktop_app.py
# A window should open. If not, check terminal logs for errors.
```

5) Create app icon (SVG -> PNG -> ICNS)

```bash
# from project root
# ensure imagemagick + iconutil installed (mac: brew install imagemagick)
mkdir -p build_icons
# render 512x512 PNG from SVG
convert -background none backend/assets/arch_icon.svg -resize 512x512 build_icons/arch_512.png
# create iconset folder
mkdir -p build_icons/Arch.iconset
# create required sizes
sips -z 16 16     build_icons/arch_512.png --out build_icons/Arch.iconset/icon_16x16.png
sips -z 32 32     build_icons/arch_512.png --out build_icons/Arch.iconset/icon_16x16@2x.png
sips -z 32 32     build_icons/arch_512.png --out build_icons/Arch.iconset/icon_32x32.png
sips -z 64 64     build_icons/arch_512.png --out build_icons/Arch.iconset/icon_32x32@2x.png
sips -z 128 128   build_icons/arch_512.png --out build_icons/Arch.iconset/icon_128x128.png
sips -z 256 256   build_icons/arch_512.png --out build_icons/Arch.iconset/icon_128x128@2x.png
sips -z 256 256   build_icons/arch_512.png --out build_icons/Arch.iconset/icon_256x256.png
sips -z 512 512   build_icons/arch_512.png --out build_icons/Arch.iconset/icon_256x256@2x.png
sips -z 512 512   build_icons/arch_512.png --out build_icons/Arch.iconset/icon_512x512.png
sips -z 1024 1024 build_icons/arch_512.png --out build_icons/Arch.iconset/icon_512x512@2x.png
# convert to icns
iconutil -c icns build_icons/Arch.iconset -o build_icons/Arch.icns
```

6) Package with PyInstaller (mac example)

```bash
# from project root
source .venv/bin/activate
pyinstaller --noconfirm --onefile \
  --add-data "backend/build:build" \
  --add-data "backend/models:models" \
  --add-data "backend/zoning_rules_extended.json:." \
  --icon build_icons/Arch.icns \
  backend/desktop_app.py

# The resulting single-file binary will be in dist/desktop_app
```

7) Create a macOS app bundle (optional)

You can wrap the binary into a .app bundle or create a DMG for distribution. Tools like `py2app`, `create-dmg`, or `pkgbuild` can help.

Notes
- PyInstaller must be run on macOS to create a macOS binary.
- Test the produced binary on a clean macOS machine.
- If the backend uses environment variables (OpenAI/HOUSKI), set them in the user's environment or embed defaults.
- For a nicer installer, notarize the .app and create a DMG.
