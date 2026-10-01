@echo off
REM ---------------------------------------------------------------------------
REM  TypeFlow - build a single-file Windows .exe with PyInstaller
REM
REM  Usage:  double-click build_exe.bat   (or run it from a terminal)
REM  Result: dist\TypeFlow.exe  -> upload to GitHub Releases
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   TypeFlow Windows build
echo ============================================

if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error
python -m pip install "pyinstaller>=6.0" || goto :error

echo [3/4] Running PyInstaller...
pyinstaller --noconfirm --clean ^
    --onefile ^
    --windowed ^
    --name TypeFlow ^
    --icon assets\icon.ico ^
    --add-data "typing_app\data\lessons.json;typing_app\data" ^
    --add-data "assets\icon.ico;assets" ^
    --hidden-import PyQt6.QtMultimedia ^
    run.py || goto :error

echo [4/4] Build finished.
echo.
echo   dist\TypeFlow.exe is ready - attach it to a GitHub Release.
echo.
pause
goto :eof

:error
echo.
echo BUILD FAILED - see the messages above.
pause
exit /b 1
