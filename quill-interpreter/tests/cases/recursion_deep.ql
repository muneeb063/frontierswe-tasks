fn sum(n) { if n == 0 { return 0; } return n + sum(n - 1); }
print(sum(1000));
fn depth(n, acc) { if n == 0 { return acc; } return depth(n - 1, acc + [n % 3]); }
print(len(depth(900, [])));
