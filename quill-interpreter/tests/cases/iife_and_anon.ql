fn(x) { print("iife", x); }(21);
print(fn() { return 1; }());
let table = {"double": fn(x) { return x * 2; }, "neg": fn(x) { return -x; }};
print(table["double"](table["neg"](4)));
let adders = [];
for n in [1, 10, 100] { push(adders, fn(x) { return x + n; }); }
print(adders[2](adders[1](adders[0](0))));
