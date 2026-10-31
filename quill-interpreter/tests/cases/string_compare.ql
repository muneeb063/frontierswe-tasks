print("apple" < "banana", "Z" < "a", "" < "a", "abc" < "abd", "ab" < "abc", "b" > "abc");
print("é" > "z", "a" <= "a", "b" >= "c");
let words = ["pear", "Apple", "fig", "apple"];
fn sort(xs) {
  let n = len(xs); let i = 0;
  while i < n { let j = 0; while j < n - 1 - i { if xs[j] > xs[j + 1] { let t = xs[j]; xs[j] = xs[j + 1]; xs[j + 1] = t; } j = j + 1; } i = i + 1; }
  return xs;
}
print(sort(words));
