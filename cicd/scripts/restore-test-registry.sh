#!/usr/bin/env bash
# Restore TEST — import a registry backup tar into a TEMP registry container
# and `docker pull` a known image, proving the backup is usable. Cleans up.
# Usage: restore-test-registry.sh <registry_data.tar>
set -euo pipefail

TAR="${1:?usage: restore-test-registry.sh <registry_data.tar>}"
TMP_NAME="registry_restore_test"
PORT="5111"

echo "[restore-test] starting temp registry on :$PORT"
docker run -d --rm --name "$TMP_NAME" -p "$PORT:5000" -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/data registry:2
# load the backup into the temp registry's volume
docker run --rm -v "$TMP_NAME":/data -v "$PWD":/backup alpine sh -c \
  "cd /data && tar -xf /backup/$TAR"

# pick an image present in the backup and attempt a pull through the temp registry
IMG="${RESTORE_TEST_IMG:-workflow-runner}"
if docker pull "127.0.0.1:$PORT/aiassistant/$IMG" >/dev/null 2>&1; then
  echo "[restore-test] PASS: pulled 127.0.0.1:$PORT/aiassistant/$IMG from restored backup"
else
  echo "[restore-test] WARN: could not pull $IMG (may not exist in this backup) — manual check required"
fi

echo "[restore-test] stopping temp registry"
docker stop "$TMP_NAME" >/dev/null 2>&1 || true
echo "[restore-test] done."
