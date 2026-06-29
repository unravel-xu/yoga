#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"

"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install -r requirements.txt -r requirements-build.txt
"${PYTHON_BIN}" -m PyInstaller --clean --noconfirm YogaPoseCoach.spec

echo
echo "Built app:"
echo "  dist/Yoga Pose Coach.app"
