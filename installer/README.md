# Installer

`TypeFlow.iss` is the [Inno Setup 6](https://jrsoftware.org/isinfo.php) script
that packages the PyInstaller build into a normal Windows installer:

* installs per-user into `%LOCALAPPDATA%\Programs\TypeFlow` (no UAC prompt),
* creates a Start-menu group and an optional desktop icon,
* registers itself in *Settings → Apps* so it can be uninstalled normally,
* offers to launch TypeFlow when it finishes.

## Build locally (Windows)

```bat
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name TypeFlow --icon assets\icon.ico ^
    --add-data "typing_app\data\lessons.json;typing_app\data" ^
    --add-data "assets\icon.ico;assets" ^
    --hidden-import PyQt6.QtMultimedia run.py

"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\TypeFlow.iss
```

The result is `installer\Output\TypeFlowSetup-<version>.exe`.

## Build automatically

`.github/workflows/build-windows.yml` runs the same steps on a GitHub-hosted
Windows runner and uploads both `TypeFlow-<version>-portable.exe` and
`TypeFlowSetup-<version>.exe` — either as run artifacts or as assets of the
GitHub Release that triggered the run.
