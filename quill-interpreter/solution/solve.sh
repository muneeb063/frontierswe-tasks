#!/usr/bin/env bash
# Reference solution: install the tree-walking interpreter as /workspace/quill/quill.
set -euo pipefail
cp /solution/quill.py /workspace/quill/quill.py
cat > /workspace/quill/quill <<'EOF'
#!/bin/sh
exec python3 "$(dirname "$0")/quill.py" "$@"
EOF
chmod 755 /workspace/quill/quill /workspace/quill/quill.py
