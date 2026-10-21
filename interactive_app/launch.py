"""Source and PyInstaller entry point."""
import os
from pathlib import Path

cache = Path.home() / "Library" / "Caches" / "LightInteraction" / "matplotlib"
cache.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(cache)
os.environ["MPLBACKEND"] = "Agg"

from interactive_app.app import main

if __name__ == "__main__":
    raise SystemExit(main())
