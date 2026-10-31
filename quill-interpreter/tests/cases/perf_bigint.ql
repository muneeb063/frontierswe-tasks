let f = 1;
for i in range(1, 301) { f = f * i; }
let digits = str(f); let total = 0;
for d in digits { total = total + int(d); }
print(len(digits), total);
let a = 0; let b = 1;
for i in range(1000) { let t = a + b; a = b; b = t; }
print(slice(str(a), 0, 15), len(str(a)));
