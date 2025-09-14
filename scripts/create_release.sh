#!/usr/bin/env bash
# Create a release tarball containing the PyInstaller-built binary and supporting files.
# Usage: scripts/create_release.sh v1.0.0

set -euo pipefail
VERSION=${1:-dev}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/releases"
mkdir -p "$OUT_DIR"

BIN="$ROOT/dist/desktop_app"
if [ ! -f "$BIN" ]; then
  echo "Built binary not found at $BIN"
  exit 1
fi

RELEASE_NAME="vancouver-zoning-app-${VERSION}-mac-arm64.tar.gz"
TEMP_DIR=$(mktemp -d)
cp "$BIN" "$TEMP_DIR/desktop_app"
chmod +x "$TEMP_DIR/desktop_app"

# Include a small README
cat > "$TEMP_DIR/README.txt" <<'EOF'
Vancouver Zoning App - macOS binary

Usage:
  chmod +x ./desktop_app
  ./desktop_app

Place API keys using the first-run GUI or by running:
  python3 scripts/set_env.py --openai <OPENAI_KEY> --yelp <YELP_KEY>

EOF

tar -C "$TEMP_DIR" -czf "$OUT_DIR/$RELEASE_NAME" .
echo "Created $OUT_DIR/$RELEASE_NAME"
rm -rf "$TEMP_DIR"
