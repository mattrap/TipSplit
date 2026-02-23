#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_NAME="TipSplit"
VERSION="$(python3 scripts/get_version.py)"
DMG_NAME="${APP_NAME}-${VERSION}-mac.dmg"
DMG_FIXED="${APP_NAME}-mac.dmg"

rm -rf "dist/${APP_NAME}.app" "dist/${APP_NAME}" "dist/${DMG_NAME}" "dist/dmg"

python3 scripts/set_version.py
python3 -m PyInstaller --noconfirm MainApp.spec

if [[ ! -d "dist/${APP_NAME}.app" ]]; then
  echo "Expected dist/${APP_NAME}.app to exist after PyInstaller." >&2
  exit 1
fi

mkdir -p dist/dmg
cp -R "dist/${APP_NAME}.app" "dist/dmg/"
ln -s /Applications "dist/dmg/Applications"

hdiutil create -volname "${APP_NAME}" -srcfolder "dist/dmg" -ov -format UDZO "dist/${DMG_NAME}"
cp -f "dist/${DMG_NAME}" "dist/${DMG_FIXED}"

echo "Created dist/${DMG_NAME}"
echo "Created dist/${DMG_FIXED}"
