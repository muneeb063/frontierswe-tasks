fn fact(n) { if n <= 1 { return 1; } return n * fact(n - 1); }
print(fact(60));
let p = 1; let i = 0;
while i < 200 { p = p * 2; i = i + 1; }
print(p);
print(p - p - 1);
print(str(fact(25)) + "!");
