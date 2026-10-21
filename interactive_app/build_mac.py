#!/usr/bin/env python3
"""Build a self-contained arm64 .app and drag-to-Applications DMG."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import distribution
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODELS = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"),
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"),
}


def prepare_models():
    folder = HERE / "models"
    folder.mkdir(exist_ok=True)
    for name,(url,expected) in MODELS.items():
        target = folder/name
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix="light-model-") as temp:
                download = Path(temp)/name
                urllib.request.urlretrieve(url,download)
                if hashlib.sha256(download.read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Model checksum mismatch: " + name)
                shutil.copy2(download,target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Model checksum mismatch: " + name)


def prepare_licenses():
    folder = HERE/"assets"/"licenses"
    folder.mkdir(parents=True,exist_ok=True)
    names = ["numpy","opencv-contrib-python","mediapipe","PySide6-Essentials","shiboken6"]
    names += ["pyobjc-core"] if sys.platform == "darwin" else ["pygrabber","comtypes"]
    for name in names:
        package = distribution(name)
        for file in package.files or []:
            if file.name.lower().startswith(("license","copying","notice")) and file.suffix.lower() in ("", ".txt", ".md", ".rst"):
                source = Path(package.locate_file(file))
                if source.is_file():
                    destination = folder/name/file.name
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,destination)
    # The Qt wheel does not include the complete license texts.
    for license_name in ("LGPL-3.0-only.txt","GPL-3.0-only.txt"):
        target = folder/license_name
        if not target.exists():
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/qt/qtbase/v6.10.2/LICENSES/"+license_name,target)
    target = folder/"PyObjC-LICENSE.txt"
    if sys.platform == "darwin" and not target.exists():
        urllib.request.urlretrieve("https://raw.githubusercontent.com/ronaldoussoren/pyobjc/v12.1/pyobjc-core/License.txt",target)


def prepare_icon():
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QLinearGradient, QRadialGradient
    assets = HERE/"assets"
    assets.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="light-icon-") as temp:
        folder = Path(temp)/"AppIcon.iconset"
        folder.mkdir()
        for size in (16,32,64,128,256,512,1024):
            image = QImage(size,size,QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(size/1024,size/1024)
            bg = QLinearGradient(0,0,1024,1024)
            bg.setColorAt(0,QColor("#1e324d"))
            bg.setColorAt(1,QColor("#0a1020"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(30,30,964,964),210,210)
            glow = QRadialGradient(QPointF(512,470),380)
            glow.setColorAt(0,QColor(99,232,220,130))
            glow.setColorAt(1,QColor(60,154,225,0))
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(512,470),380,380)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#80ebe1"),22))
            painter.drawEllipse(QPointF(512,460),230,230)
            painter.setPen(QPen(QColor(118,192,252,120),8))
            painter.drawEllipse(QPointF(512,460),290,290)
            painter.setPen(QPen(QColor("#92bfff"),12,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(192,706),QPointF(350,650))
            painter.drawLine(QPointF(678,654),QPointF(816,742))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ecffff"))
            painter.drawEllipse(QPointF(350,650),33,33)
            painter.drawEllipse(QPointF(678,654),33,33)
            painter.end()
            # iconutil requires conventional 1x and 2x representations.
            if size <= 512:
                image.save(str(folder/f"icon_{size}x{size}.png"))
            if size >= 32:
                half = size//2
                image.save(str(folder/f"icon_{half}x{half}@2x.png"))
        subprocess.run(["iconutil","-c","icns",str(folder),"-o",str(assets/"AppIcon.icns")],check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-only",action="store_true")
    args = parser.parse_args()
    prepare_models()
    prepare_licenses()
    prepare_icon()
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm",str(HERE/"LightInteraction.spec")],cwd=ROOT,check=True)
    app = ROOT/"dist"/"Light Interaction.app"
    subprocess.run(["codesign","--verify","--deep","--strict",str(app)],check=True)
    if not args.app_only:
        with tempfile.TemporaryDirectory(prefix="light-dmg-") as temp:
            staging = Path(temp)
            shutil.copytree(app,staging/app.name,symlinks=True)
            (staging/"Applications").symlink_to("/Applications")
            shutil.copy2(HERE/"README.md",staging/"使用说明.md")
            subprocess.run(["hdiutil","create","-volname","Light Interaction","-srcfolder",str(staging),
                            "-ov","-format","UDZO",str(ROOT/"dist"/"LightInteraction.dmg")],check=True)
    print("Ready:",app)


if __name__ == "__main__":
    main()
