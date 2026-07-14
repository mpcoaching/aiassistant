#!/usr/bin/env bash
# Pre-deploy validation gate: reject any promoted service that uses a moving
# `latest` tag or a `build:` block. Promotion MUST use an immutable <git-sha>.
set -euo pipefail

COMPOSE_FILE="${1:?usage: validate-promotion.sh <compose-file>}"
echo "[validate] checking $COMPOSE_FILE for mutable tags / build blocks"

violations=0
while IFS= read -r line; do
  svc=$(echo "$line" | cut -d: -f1)
  tag=$(echo "$line" | cut -d: -f2-)
  if [[ "$tag" == *":latest" || "$tag" == "latest" ]]; then
    echo "  [FAIL] $svc uses :latest"; violations=$((violations+1))
  fi
done < <(grep -E "^[[:space:]]+image:" "$COMPOSE_FILE" | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["'\'']//g' | awk -F'[/:]' '{print $0}')

if grep -nE "^[[:space:]]+build:" "$COMPOSE_FILE" >/dev/null; then
  echo "  [FAIL] compose contains build: blocks (promoted services must use image: only)"
  violations=$((violations+1))
fi

if [[ "$violations" -gt 0 ]]; then
  echo "[validate] FAILED: $violations mutable-reference violation(s). Aborting promotion."
  exit 1
fi
echo "[validate] OK: all promoted services use immutable references."
