print("before");
fn check(x) { if x > 2 { error("value too large: " + str(x)); } return x; }
print(check(1));
print(check(5));
print("after");
