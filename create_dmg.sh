#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-Yoga Pose Coach}"
DIST_DIR="${DIST_DIR:-dist}"
APP_PATH="${APP_PATH:-${DIST_DIR}/${APP_NAME}.app}"
VOLUME_NAME="${VOLUME_NAME:-${APP_NAME}}"
DMG_PATH="${DMG_PATH:-${DIST_DIR}/${APP_NAME// /}.dmg}"
STAGING_DIR="${STAGING_DIR:-${DIST_DIR}/dmg-staging}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "App bundle not found:"
  echo "  ${APP_PATH}"
  echo
  echo "Build it first:"
  echo "  ./build_mac_app.sh"
  exit 1
fi

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

cp -R "${APP_PATH}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

rm -f "${DMG_PATH}"

hdiutil create \
  -volname "${VOLUME_NAME}" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

rm -rf "${STAGING_DIR}"

echo
echo "Created DMG:"
echo "  ${DMG_PATH}"
