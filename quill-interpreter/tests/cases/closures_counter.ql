fn counter(start) {
  let n = start;
  fn inc() { n = n + 1; return n; }
  fn get() { return n; }
  return [inc, get];
}
let c = counter(10);
let inc = c[0]; let get = c[1];
inc(); inc();
print(get(), inc(), get());
let d = counter(0);
print(d[0](), get());
let shared = 0;
let bump = fn() { shared = shared + 100; };
bump(); bump();
print(shared);
