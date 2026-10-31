fn a() {}
fn b() { return; }
fn c(x) { if x { return "yes"; } }
print(a(), b(), c(true), c(false));
print(push([], 1), print());
