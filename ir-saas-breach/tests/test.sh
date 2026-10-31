#!/usr/bin/env bash
set -uo pipefail
VERIFIER_DIR="${VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"
python3 /tests/check.py \
  --workspace /workspace \
  --expected /tests/expected.json \
  --out "$VERIFIER_DIR" || [ -f "$VERIFIER_DIR/reward.txt" ] || echo 0 > "$VERIFIER_DIR/reward.txt"
