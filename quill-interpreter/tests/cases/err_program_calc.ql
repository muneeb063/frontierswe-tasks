# a tiny recursive-descent calculator written in Quill
fn tokenize(s) {
  let toks = []; let i = 0;
  while i < len(s) {
    let c = s[i];
    if c == " " { i = i + 1; continue; }
    if c >= "0" and c <= "9" {
      let j = i;
      while j < len(s) and s[j] >= "0" and s[j] <= "9" { j = j + 1; }
      push(toks, int(slice(s, i, j))); i = j; continue;
    }
    push(toks, c); i = i + 1;
  }
  return toks;
}
fn parse(toks) {
  let pos = 0;
  fn peek() { if pos < len(toks) { return toks[pos]; } return nil; }
  fn next() { let t = toks[pos]; pos = pos + 1; return t; }
  let expr = nil;
  fn atom() {
    let t = next();
    if t == "(" { let v = expr(); next(); return v; }
    if t == "-" { return -atom(); }
    return t;
  }
  fn term() {
    let v = atom();
    while peek() == "*" or peek() == "/" { let op = next(); let r = atom(); if op == "*" { v = v * r; } else { v = v / r; } }
    return v;
  }
  expr = fn() {
    let v = term();
    while peek() == "+" or peek() == "-" { let op = next(); let r = term(); if op == "+" { v = v + r; } else { v = v - r; } }
    return v;
  };
  return expr();
}
for src in ["1 + 2 * 3", "(1 + 2) * 3", "100 / 7 - -3", "2 * (3 + (4 - 1)) / 2", "99999999999 * 99999999999"] {
  print(src, "=", parse(tokenize(src)));
}
print(parse(tokenize("1 / (2 - 2)")));
