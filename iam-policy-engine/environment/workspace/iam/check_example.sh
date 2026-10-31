#!/usr/bin/env bash
# Runs ./iam-eval on the example account and diffs its decisions against the expected ones.
cd "$(dirname "$0")"
./iam-eval examples/example.json examples/example.jsonl > /tmp/example.out || { echo "iam-eval exited $?"; exit 1; }
if diff -u examples/example.expected.jsonl /tmp/example.out; then echo "example: all decisions match"; fi
