fn avg(xs) { let s = 0; for x in xs { s = s + x; } return s / len(xs); }
print(avg([1, 2, 3]));
print(avg([]));
