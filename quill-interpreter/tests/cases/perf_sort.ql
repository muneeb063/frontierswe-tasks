let seed = 12345;
fn rnd() { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % 100000; }
let xs = [];
for i in range(10000) { push(xs, rnd()); }
fn msort(a) {
  if len(a) <= 1 { return a; }
  let mid = len(a) / 2;
  let l = msort(slice(a, 0, mid)); let r = msort(slice(a, mid, len(a)));
  let out = []; let i = 0; let j = 0;
  while i < len(l) and j < len(r) { if l[i] <= r[j] { push(out, l[i]); i = i + 1; } else { push(out, r[j]); j = j + 1; } }
  while i < len(l) { push(out, l[i]); i = i + 1; }
  while j < len(r) { push(out, r[j]); j = j + 1; }
  return out;
}
let s = msort(xs);
let ok = true;
for i in range(len(s) - 1) { if s[i] > s[i + 1] { ok = false; } }
let check = 0;
for i in range(len(s)) { check = (check * 31 + s[i]) % 1000000007; }
print(ok, s[0], s[len(s) - 1], check);
