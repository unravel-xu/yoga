"""Native camera/settings helpers. Importing this module never opens a camera."""
import os
from pathlib import Path
import sys


def app_directory(kind, name="BreathingGarden"):
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData/Local")))
        return base/name/({"logs":"Logs", "cache":"Cache"}[kind])
    if sys.platform == "darwin":
        return Path.home()/"Library"/({"logs":"Logs", "cache":"Caches"}[kind])/name
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home()/".cache")))
    return base/name/kind


def capture_backend():
    import cv2
    if sys.platform == "win32":
        # Keep the backend identical to the device enumeration order.
        return cv2.CAP_DSHOW
    return cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_V4L2


def windows_camera_devices():
    from pygrabber.dshow_graph import FilterGraph
    # Enumerates DirectShow device names without opening capture streams.
    graph = FilterGraph()
    names = graph.get_input_devices()
    return [(index, str(name), f"dshow:{index}:{name}") for index,name in enumerate(names)]


def camera_settings_urls():
    if sys.platform == "win32":
        return ("ms-settings:privacy-webcam", "ms-settings:privacy")
    return ("x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
            "x-apple.systempreferences:com.apple.preference.security")
