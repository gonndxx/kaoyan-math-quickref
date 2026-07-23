# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "web" / "index.html"), "web"),
        (str(root / "web" / "style.css"), "web"),
        (str(root / "web" / "app.js"), "web"),
        (str(root / "web" / "vendor" / "katex"), "web/vendor/katex"),
    ],
    hiddenimports=[
        "webview.platforms.winforms",
        "clr",
        "clr_loader",
        "pythonnet",
        "pystray._win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["sympy", "tkinter", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="研数公式速查-2.1",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "app.ico"),
    version=str(root / "version_info.txt"),
)
