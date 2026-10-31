fn f() { return 1; }
fn g() { return 1; }
let h = f;
print(f == f, f == g, h == f, len == len, len == print, [f] == [h], {"k": f} == {"k": g});
