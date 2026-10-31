let fs = [];
for i in range(4) { push(fs, fn() { return i * i; }); }
let out = [];
for f in fs { push(out, f()); }
print(out);
let gs = [];
let k = 0;
while k < 3 { let j = k; push(gs, fn() { return j; }); k = k + 1; }
print(gs[0](), gs[1](), gs[2]());
let hs = [];
let m = 0;
while m < 3 { push(hs, fn() { return m; }); m = m + 1; }
print(hs[0](), hs[2]());
