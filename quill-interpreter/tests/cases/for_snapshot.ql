let xs = [1, 2, 3];
for x in xs { push(xs, x * 10); }
print(xs);
let m = {"a": 1, "b": 2};
for k in m { m[k + k] = 0; print(k); }
print(keys(m));
let s = "";
for ch in "héy" { s = s + "[" + ch + "]"; }
print(s);
for e in [] { print("never"); }
for q in {} { print("never"); }
