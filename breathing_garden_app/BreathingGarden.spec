# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
datas = [(str(root/"interactive_app/models"),"interactive_app/models")]
datas += collect_data_files("mediapipe")
datas += [(str(root/"interactive_app/THIRD_PARTY_NOTICES.md"),"interactive_app")]
datas += [(str(root/"interactive_app/assets/licenses"),"licenses")]
a = Analysis([str(root/"breathing_garden_app/launch.py")],pathex=[str(root)],
    binaries=[],datas=datas,
    hiddenimports=collect_submodules("mediapipe",filter=lambda name:
        ".test" not in name and not name.endswith("_test") and ".genai" not in name),
    hookspath=[],hooksconfig={"matplotlib":{"backends":["Agg"]}},runtime_hooks=[],
    excludes=["tkinter","IPython","pytest","torch","tensorflow","jax","jaxlib","scipy"],
    noarchive=False,optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name="Breathing Garden",debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    argv_emulation=False,target_arch="arm64",codesign_identity=None,entitlements_file=None)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name="Breathing Garden")
app = BUNDLE(coll,name="Breathing Garden.app",icon=str(root/"breathing_garden_app/assets/AppIcon.icns"),
    bundle_identifier="com.local.breathinggarden",info_plist={
        "CFBundleDisplayName":"呼吸的花园",
        "CFBundleShortVersionString":"1.1.0","CFBundleVersion":"2",
        "LSMinimumSystemVersion":"14.5","NSHighResolutionCapable":True,
        "NSCameraUsageDescription":"呼吸的花园使用摄像头，在本机识别食指、捏合和面部动作，驱动实时植物生长。画面不录制、不上传。",
        "NSHumanReadableCopyright":"The Breathing Garden · MediaPipe / Qt / OpenCV"})
