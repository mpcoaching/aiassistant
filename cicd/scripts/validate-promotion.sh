#!/usr/bin/env bash
# Pre-deploy validation gate: reject any PROMOTED service that uses a moving
# `latest` tag or a `build:` block. Promotion MUST use an immutable <git-sha>.
# Services declared under a disabled profile (e.g. profiles: ["disabled"]) are
# not part of the promoted set and are skipped.
set -euo pipefail

COMPOSE_FILE="${1:?usage: validate-promotion.sh <compose-file>}"
echo "[validate] checking $COMPOSE_FILE for mutable tags / build blocks"

python3 - "$COMPOSE_FILE" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path).read()
lines = text.splitlines()

disabled = set()
current = None
for ln in lines:
    m = re.match(r'^  ([A-Za-z0-9_-]+):\s*(#.*)?$', ln)
    if m:
        current = m.group(1)
    if re.search(r'profiles:', ln) and 'disabled' in ln and current:
        disabled.add(current)

violations = 0
current = None
for ln in lines:
    m = re.match(r'^  ([A-Za-z0-9_-]+):\s*(#.*)?$', ln)
    if m:
        current = m.group(1)
    im = re.match(r'^\s+image:\s*([^\s#]+)', ln)
    if im:
        tag = im.group(1).strip().strip('"\'')
        if current in disabled:
            print(f"  [skip] {current} (disabled profile)")
            continue
        if tag == 'latest' or tag.endswith(':latest'):
            print(f"  [FAIL] {current} uses :latest")
            violations += 1

if re.search(r'^\s+build:', text, re.M):
    print("  [FAIL] compose contains build: blocks (promoted services must use image: only)")
    violations += 1

if violations:
    print(f"[validate] FAILED: {violations} mutable-reference violation(s). Aborting promotion.")
    sys.exit(1)
print("[validate] OK: all promoted services use immutable references.")
PY
