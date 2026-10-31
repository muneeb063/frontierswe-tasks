fn is_even(n) { if n == 0 { return true; } return is_odd(n - 1); }
fn is_odd(n) { if n == 0 { return false; } return is_even(n - 1); }
print(is_even(10), is_odd(7), is_even(301));
fn ack(m, n) {
  if m == 0 { return n + 1; }
  if n == 0 { return ack(m - 1, 1); }
  return ack(m - 1, ack(m, n - 1));
}
print(ack(2, 3));
