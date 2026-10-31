#!/usr/bin/env bash
# Runs ./quill on every examples/*.ql and compares stdout and exit status with the .out/.code files.
# For a syntax error (exit 2) only the "syntax error" prefix of the single output line is compared.
cd "$(dirname "$0")"
out=$(mktemp); trap 'rm -f "$out"' EXIT
pass=0; total=0
for src in examples/*.ql; do
  base="${src%.ql}"; total=$((total + 1))
  want=$(cat "$base.code")
  timeout 10 ./quill "$src" > "$out" 2>/dev/null; got=$?
  if [ "$want" = 2 ]; then
    [ "$got" = 2 ] && [ "$(wc -l < "$out")" -le 1 ] && head -c 12 "$out" | grep -q '^syntax error$' && ok=1 || ok=0
  else
    [ "$got" = "$want" ] && cmp -s "$out" "$base.out" && ok=1 || ok=0
  fi
  if [ "$ok" = 1 ]; then pass=$((pass + 1)); echo "PASS $src"; else echo "FAIL $src (exit $got, want $want)"; fi
done
echo "$pass/$total examples pass"
