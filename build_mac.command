#!/bin/bash

set -e

cd "$(dirname "$0")"

APP_NAME="Microbee PCG Character Editor"
SOURCE_FILE="microbee_pcg_editor.py"

echo "Building $APP_NAME for macOS..."
echo

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
    echo "PyInstaller is not installed for this Python 3 installation."
    echo "Install it with: python3 -m pip install pyinstaller"
    echo
    read -r -p "Press Return to close..."
    exit 1
fi

rm -rf "build" "dist/$APP_NAME.app"

python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    --osx-bundle-identifier "com.anthonygasson.microbeepcgeditor" \
    "$SOURCE_FILE"

echo
echo "Build complete:"
echo "$(pwd)/dist/$APP_NAME.app"
echo
echo "Finder will now open the dist folder."
open "dist"
echo
read -r -p "Press Return to close..."
