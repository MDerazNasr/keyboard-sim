#!/bin/zsh
# Build "Keyboard Sim.app" (macOS) from gui.py without modifying any source files.
# Usage: ./build_app.sh        -> dist/Keyboard Sim.app
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY -m pip install -q pyinstaller
rm -rf build dist "Keyboard Sim.spec"
$PY -m PyInstaller --noconfirm --windowed \
  --name "Keyboard Sim" \
  --osx-bundle-identifier com.keyboardsim.app \
  --hidden-import black \
  --collect-submodules black \
  gui.py
# Ad-hoc sign so macOS keeps one stable identity for the Accessibility permission.
codesign --force --deep --sign - "dist/Keyboard Sim.app"
echo "Built: $(pwd)/dist/Keyboard Sim.app"
