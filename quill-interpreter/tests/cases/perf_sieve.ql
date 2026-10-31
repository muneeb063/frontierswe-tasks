let n = 100000;
let is = [];
for i in range(n + 1) { push(is, true); }
is[0] = false; is[1] = false;
let p = 2;
while p * p <= n {
  if is[p] { let m = p * p; while m <= n { is[m] = false; m = m + p; } }
  p = p + 1;
}
let count = 0; let last = 0;
for i in range(n + 1) { if is[i] { count = count + 1; last = i; } }
print(count, last);
