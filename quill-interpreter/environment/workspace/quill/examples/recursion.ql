fn hanoi(n, from, to, via, moves) {
  if n == 0 { return moves; }
  hanoi(n - 1, from, via, to, moves);
  push(moves, from + to);
  return hanoi(n - 1, via, to, from, moves);
}
let m = hanoi(4, "A", "C", "B", []);
print(len(m), slice(m, 0, 5));
