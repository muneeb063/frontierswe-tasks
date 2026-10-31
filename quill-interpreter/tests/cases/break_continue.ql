let out = [];
for i in range(5) {
  if i == 1 { continue; }
  for j in range(5) {
    if j > i { break; }
    if j == 1 { continue; }
    push(out, str(i) + str(j));
  }
  if i == 3 { break; }
}
print(out);
let n = 0;
while true { n = n + 1; if n % 2 == 0 { continue; } if n > 7 { break; } }
print(n);
