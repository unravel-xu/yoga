# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)


project_root = Path(SPECPATH)

datas = [
    (
        str(project_root / "models" / "pose_landmarker_full.task"),
        "models",
    ),
    (
        str(project_root / "videos" / "daily_yoga.mp4"),
        "videos",
    ),
]
datas += collect_data_files("mediapipe")

hiddenimports = collect_submodules("mediapipe")


a = Analysis(
    ["desktop_app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(
    a.pure,
)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Yoga Pose Coach",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Yoga Pose Coach",
)
app = BUNDLE(
    coll,
    name="Yoga Pose Coach.app",
    icon=None,
    bundle_identifier="com.local.yogaposecoach",
    info_plist={
        "NSCameraUsageDescription": (
            "Yoga Pose Coach uses the camera to detect your posture."
        ),
    },
)
