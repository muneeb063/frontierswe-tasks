fn make_acc(total) {
  return fn(n) { total = total + n; return total; };
}
let acc = make_acc(100);
acc(10);
print(acc(5));
let fs = [];
for i in [1, 2, 3] { push(fs, fn() { return i * 10; }); }
print(fs[0](), fs[1](), fs[2]());
