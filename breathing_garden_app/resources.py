"""Reproducible open-font resource; runtime never downloads anything."""
import hashlib
import logging
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

FONT = "NotoSansCJKsc-Regular.otf"
FONT_SHA256 = "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b"
LICENSE_SHA256 = "6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2"
BASE = "https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/"


def prepare_fonts():
    assets = Path(__file__).resolve().parent/"assets"
    assets.mkdir(exist_ok=True)
    font = assets/FONT
    if not font.exists():
        with tempfile.TemporaryDirectory(prefix="garden-font-") as temporary:
            downloaded = Path(temporary)/FONT
            urllib.request.urlretrieve(BASE+"Sans/OTF/SimplifiedChinese/"+FONT,downloaded)
            if hashlib.sha256(downloaded.read_bytes()).hexdigest() != FONT_SHA256:
                raise RuntimeError("Noto font checksum mismatch")
            shutil.copy2(downloaded,font)
    if hashlib.sha256(font.read_bytes()).hexdigest() != FONT_SHA256:
        raise RuntimeError("Noto font checksum mismatch")
    license_path = assets/"NotoSansCJK-OFL.txt"
    if not license_path.exists():
        urllib.request.urlretrieve(BASE+"LICENSE",license_path)
    if hashlib.sha256(license_path.read_bytes()).hexdigest() != LICENSE_SHA256:
        raise RuntimeError("Noto font license checksum mismatch")


def load_ui_font(application):
    from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
    root = Path(sys._MEIPASS)/"breathing_garden_app" if getattr(sys,"frozen",False) else Path(__file__).resolve().parent
    font = root/"assets"/FONT
    if not font.exists():
        logging.warning("Bundled CJK font unavailable; using system fallback. Build resources with python -m breathing_garden_app.resources")
        return {"family":None,"chinese_glyphs":False}
    font_id = QFontDatabase.addApplicationFont(str(font))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError("Cannot register bundled Chinese font")
    family = families[0]
    chosen = QFont(family,10)
    application.setFont(chosen)
    metrics = QFontMetrics(chosen)
    valid = all(metrics.inFontUcs4(ord(char)) for char in "呼吸的花园ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    if not valid:
        raise RuntimeError("Bundled font is missing required Chinese/Latin glyphs")
    return {"family":family,"chinese_glyphs":valid}


if __name__ == "__main__":
    prepare_fonts()
