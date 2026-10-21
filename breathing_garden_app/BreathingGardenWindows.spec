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
        ".test" not in name and not name.endswith("_test") and ".genai" not in name)
        + collect_submodules("comtypes") + ["pygrabber.dshow_graph"],
    hookspath=[],hooksconfig={"matplotlib":{"backends":["Agg"]}},runtime_hooks=[],
    excludes=["tkinter","IPython","pytest","torch","tensorflow","jax","jaxlib","scipy","AVFoundation","Foundation"],
    noarchive=False,optimize=0)
pyz = PYZ(a.pure)
# Portable directory keeps Qt DLLs dynamically replaceable (LGPL). Ship the
# complete ZIP, not the EXE alone; Python and both offline models are included.
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name="BreathingGarden",debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    icon=str(root/"breathing_garden_app/assets/AppIcon.ico"))
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name="BreathingGarden")
