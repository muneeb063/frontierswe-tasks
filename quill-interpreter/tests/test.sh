#!/usr/bin/env bash
set -uo pipefail
VERIFIER_DIR="${VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"
# check.py runs the interpreter as the agent user; keep the hidden programs and answers unreadable to it
if [ "$(id -u)" = 0 ]; then chmod -R go-rwx /tests; fi
python3 /tests/check.py \
  --workspace /workspace \
  --cases /tests/cases \
  --expected /tests/expected.json \
  --out "$VERIFIER_DIR" || [ -f "$VERIFIER_DIR/reward.txt" ] || echo 0 > "$VERIFIER_DIR/reward.txt"
