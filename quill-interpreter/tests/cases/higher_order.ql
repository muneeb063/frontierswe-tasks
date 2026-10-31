fn map(xs, f) { let out = []; for x in xs { push(out, f(x)); } return out; }
fn filter(xs, f) { let out = []; for x in xs { if f(x) { push(out, x); } } return out; }
fn reduce(xs, f, acc) { for x in xs { acc = f(acc, x); } return acc; }
let sq = map(range(6), fn(x) { return x * x; });
print(sq);
print(filter(sq, fn(x) { return x % 2 == 0; }));
print(reduce(sq, fn(a, b) { return a + b; }, 0));
print(map([[1], [1, 2], []], len));
let f = len;
print(f("abcd"), f, map, fn(x) { return x; });
print(type(len), type(map));
fn compose(f, g) { return fn(x) { return f(g(x)); }; }
print(compose(str, len)([1, 2, 3]) + "!");
