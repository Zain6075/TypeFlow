#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  TypeFlow - build a single-file executable with PyInstaller
#  (Linux/macOS development build; Windows users should use build_exe.bat)
#
#  Usage:  ./build_exe.sh
#  Result: dist/TypeFlow
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Creating virtual environment (.venv)"
[ -d .venv ] || "$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install "pyinstaller>=6.0"

echo "==> Running PyInstaller"
# On Windows the --add-data separator is ';' - PyInstaller accepts ':' elsewhere.
SEP=":"
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) SEP=";" ;;
esac

pyinstaller --noconfirm --clean \
    --onefile \
    --windowed \
    --name TypeFlow \
    --icon assets/icon.ico \
    --add-data "typing_app/data/lessons.json${SEP}typing_app/data" \
    --add-data "assets/icon.ico${SEP}assets" \
    --hidden-import PyQt6.QtMultimedia \
    run.py

echo "==> Build finished: dist/TypeFlow"
