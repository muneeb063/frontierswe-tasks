fn outer() {
  let total = 0;
  fn add(n) { total = total + n; }
  for i in range(5) { add(i); }
  fn get() { return total; }
  return get;
}
print(outer()());
fn make() { let v = "first"; let g = fn() { return v; }; v = "second"; return g; }
print(make()());
