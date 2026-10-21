"""Build a separate garden .app/.dmg; leave Light Interaction untouched."""
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from interactive_app.build_mac import prepare_models,prepare_licenses


def icon():
    from PySide6.QtCore import QPointF,QRectF,Qt
    from PySide6.QtGui import QColor,QImage,QPainter,QPen,QPainterPath
    assets = ROOT/"breathing_garden_app/assets"
    assets.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="garden-icon-") as temp:
        folder = Path(temp)/"AppIcon.iconset"
        folder.mkdir()
        for size in (16,32,64,128,256,512,1024):
            image = QImage(size,size,QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            p = QPainter(image)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.scale(size/1024,size/1024)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#071519"))
            p.drawRoundedRect(QRectF(30,30,964,964),205,205)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#69CDBB"),12,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            for a,b,c in (((512,820),(500,450),(600,260)),((505,650),(280,600),(270,390)),((525,530),(745,490),(775,350))):
                path = QPainterPath(QPointF(*a))
                path.quadTo(QPointF(*b),QPointF(*c))
                p.drawPath(path)
            p.setPen(QPen(QColor("#D9FFF1"),7))
            for x,y in ((600,250),(270,380),(775,340)):
                for petal in range(6):
                    path = QPainterPath()
                    for j in range(17):
                        t = j*math.tau/16
                        a = petal*math.tau/6
                        along,across = 44*(1-math.cos(t)),20*math.sin(t)
                        point = QPointF(x+math.cos(a)*along-math.sin(a)*across,
                                        y+math.sin(a)*along+math.cos(a)*across)
                        if j:
                            path.lineTo(point)
                        else:
                            path.moveTo(point)
                    p.drawPath(path)
            p.end()
            if size<=512:
                image.save(str(folder/f"icon_{size}x{size}.png"))
            if size>=32:
                half = size//2
                image.save(str(folder/f"icon_{half}x{half}@2x.png"))
        subprocess.run(["iconutil","-c","icns",str(folder),"-o",str(assets/"AppIcon.icns")],check=True)


def main():
    if sys.platform!="darwin":
        raise SystemExit("Run on an Apple Silicon Mac with the existing pinned interactive_app venv.")
    prepare_models()
    prepare_licenses()
    icon()
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm",
                    str(ROOT/"breathing_garden_app/BreathingGarden.spec")],cwd=ROOT,check=True)
    app = ROOT/"dist/Breathing Garden.app"
    subprocess.run(["codesign","--verify","--deep","--strict",str(app)],check=True)
    with tempfile.TemporaryDirectory(prefix="garden-dmg-") as temp:
        folder = Path(temp)
        shutil.copytree(app,folder/app.name,symlinks=True)
        (folder/"Applications").symlink_to("/Applications")
        shutil.copy2(ROOT/"breathing_garden_app/README.md",folder/"使用说明.md")
        subprocess.run(["hdiutil","create","-volname","Breathing Garden","-srcfolder",str(folder),
                        "-ov","-format","UDZO",str(ROOT/"dist/BreathingGarden.dmg")],check=True)
    print("Ready:",app)


if __name__ == "__main__":
    main()
