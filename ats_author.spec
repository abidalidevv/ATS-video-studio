# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

BASE_DIR = Path(os.path.abspath(".")).resolve()

# Collect all hidden imports for FastAPI, Uvicorn, and backend modules
hidden_imports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.middleware.cors",
    "fastapi.responses",
    "starlette",
    "starlette.staticfiles",
    "starlette.middleware.cors",
    "starlette.responses",
    "pydantic",
    "pydantic_core",
    "pydantic.deprecated.decorator",
    "httpx",
    "httpcore",
    "h11",
    "aiohttp",
    "aiofiles",
    "multipart",
    "python_multipart",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageFilter",
    "PIL.ImageEnhance",
    "backend",
    "backend.config",
    "backend.server",
    "backend.local_pool",
    "backend.avatar_processor",
    "backend.fast_renderer",
    "backend.subtitle_generator",
    "backend.adaptive_subtitles",
    "backend.audio_dsp",
    "backend.transcriber",
    "backend.visualizer_generator",
]

hidden_imports += collect_submodules("backend")
hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("starlette")
hidden_imports += collect_submodules("fastapi")
hidden_imports += collect_submodules("webview")
hidden_imports += ["clr_loader", "pythonnet", "cffi"]

# Collect static web assets, fonts, and clean data assets
datas = [
    (str(BASE_DIR / "frontend"), "frontend"),
]
datas += collect_data_files("webview")
datas += collect_data_files("clr_loader")
if (BASE_DIR / "backend" / "assets").exists():
    datas.append((str(BASE_DIR / "backend" / "assets"), "backend/assets"))
if (BASE_DIR / "bin").exists():
    datas.append((str(BASE_DIR / "bin"), "bin"))
if (BASE_DIR / "data" / "settings.json").exists():
    datas.append((str(BASE_DIR / "data" / "settings.json"), "data"))

icon_path = str(BASE_DIR / "frontend" / "favicon.ico") if (BASE_DIR / "frontend" / "favicon.ico").exists() else None

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=list(set(hidden_imports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook", "IPython", "torch", "torchvision"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ATSAuthor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    icon=icon_path,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ATSAuthor",
)
