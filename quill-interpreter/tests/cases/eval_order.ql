fn t(x) { print("t", x); return x; }
let r = t(1) + t(2) * t(3);
print(r);
fn three(a, b, c) { return [a, b, c]; }
print(t(three)(t("a"), t("b"), t("c")));
let m = {t("k1"): t("v1"), t("k2"): t("v2")};
let lst = [0, 0];
t(lst)[t(1)] = t("val");
print(lst);
print(t(nil) or t(0) or t("x"));
