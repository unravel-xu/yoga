"""Build the actual Windows x64 portable package; run on Windows, not macOS."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows build requires Windows x64 / Python 3.11. Use the GitHub Actions workflow on macOS.")
    sys.path.insert(0,str(ROOT))
    from interactive_app.build_mac import prepare_models, prepare_licenses
    from PIL import Image, ImageDraw
    prepare_models()
    prepare_licenses()
    assets = ROOT/"breathing_garden_app/assets"
    assets.mkdir(exist_ok=True)
    icon = Image.new("RGBA",(256,256),(2,6,11,255))
    draw = ImageDraw.Draw(icon)
    draw.line([(128,215),(128,130),(93,96),(76,61)],fill="#69CDBB",width=5)
    draw.line([(128,173),(164,136),(186,86)],fill="#69CDBB",width=4)
    draw.line([(128,147),(147,106)],fill="#69CDBB",width=3)
    for cx,cy in ((76,61),(186,86),(147,106)):
        for dx,dy in ((-10,0),(10,0),(-5,-9),(5,-9),(-5,9),(5,9)):
            draw.ellipse((cx+dx-7,cy+dy-7,cx+dx+7,cy+dy+7),fill="#A1ECD3")
        draw.ellipse((cx-4,cy-4,cx+4,cy+4),fill="#E6C999")
    icon.save(assets/"AppIcon.ico",sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])
    subprocess.run([sys.executable,"-m","PyInstaller","--clean","--noconfirm",
                    str(ROOT/"breathing_garden_app/BreathingGardenWindows.spec")],cwd=ROOT,check=True)
    folder = ROOT/"dist/BreathingGarden"
    shutil.copy2(ROOT/"breathing_garden_app/README.md",folder/"README-使用说明.md")
    shutil.copy2(ROOT/"interactive_app/THIRD_PARTY_NOTICES.md",folder/"THIRD_PARTY_NOTICES.md")
    archive = Path(shutil.make_archive(str(ROOT/"dist/BreathingGarden-Windows-x64"),"zip",
                                      root_dir=folder.parent,base_dir=folder.name))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest+"  "+archive.name+"\n",encoding="utf-8")
    compiler = shutil.which("ISCC") or str(Path(os.environ.get("ProgramFiles(x86)","C:/Program Files (x86)"))/"Inno Setup 6/ISCC.exe")
    if not Path(compiler).is_file():
        raise SystemExit("Portable ZIP built; install Inno Setup 6 to generate the single setup EXE.")
    subprocess.run([compiler,str(ROOT/"breathing_garden_app/installer_windows.iss")],
                   env={**os.environ,"GARDEN_REPO_ROOT":str(ROOT)},check=True)
    setup = ROOT/"dist/BreathingGarden-Windows-x64-Setup.exe"
    setup.with_suffix(".exe.sha256").write_text(hashlib.sha256(setup.read_bytes()).hexdigest()+"  "+setup.name+"\n",encoding="utf-8")
    print("Ready:",folder/"BreathingGarden.exe")
    print("Share the whole ZIP:",archive)
    print("SHA-256:",digest)
    print("Single-file installer:",setup)


if __name__ == "__main__":
    main()
