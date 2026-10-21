"""PyInstaller entry. Use an app-specific cache and no global environment edits."""
import os
from pathlib import Path
from interactive_app.platform_support import app_directory

cache = app_directory("cache")/"matplotlib"
cache.mkdir(parents=True,exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(cache)
os.environ["MPLBACKEND"] = "Agg"

from breathing_garden_app.app import main

if __name__ == "__main__":
    raise SystemExit(main())
