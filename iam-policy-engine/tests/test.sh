#!/usr/bin/env bash
set -uo pipefail
VERIFIER_DIR="${VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"
# check.py runs the evaluator as the agent user; keep the hidden snapshots and answers unreadable to it
if [ "$(id -u)" = 0 ]; then chmod -R go-rwx /tests; fi
python3 /tests/check.py \
  --workspace /workspace \
  --data /tests/data \
  --expected /tests/expected.json \
  --out "$VERIFIER_DIR" || [ -f "$VERIFIER_DIR/reward.txt" ] || echo 0 > "$VERIFIER_DIR/reward.txt"
