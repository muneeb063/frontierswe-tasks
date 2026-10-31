let words = ["alpha", "beta", "gamma", "delta", "beta", "alpha", "beta"];
let parts = [];
for i in range(3000) { push(parts, words[i % len(words)]); }
let text = join(parts, " ");
let counts = {};
for w in split(text, " ") { if has(counts, w) { counts[w] = counts[w] + 1; } else { counts[w] = 1; } }
print(len(text), counts);
let rev = "";
let src = slice(text, 0, 2000);
let i = len(src) - 1;
while i >= 0 { rev = rev + src[i]; i = i - 1; }
print(slice(rev, 0, 20));
