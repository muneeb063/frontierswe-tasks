let x = 1;
if true { let x = 2; print(x); if true { x = 3; print(x); } print(x); }
print(x);
let x = 10;
print(x);
let y = 5;
fn f() { let y = 6; return y; }
print(f(), y);
while x > 8 { let z = x; x = x - 1; print(z); }
print(x);
