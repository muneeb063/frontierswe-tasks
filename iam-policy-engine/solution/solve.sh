#!/usr/bin/env bash
# Reference solution: install the Python evaluator as /workspace/iam/iam-eval.
set -euo pipefail
cp /solution/iam_eval.py /workspace/iam/iam_eval.py
cat > /workspace/iam/iam-eval <<'EOF'
#!/bin/sh
exec python3 "$(dirname "$0")/iam_eval.py" "$@"
EOF
chmod 755 /workspace/iam/iam-eval /workspace/iam/iam_eval.py
