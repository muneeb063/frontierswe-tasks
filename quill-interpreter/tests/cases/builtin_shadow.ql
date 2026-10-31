let len = fn(x) { return 42; };
print(len([1]));
fn f() { let print = 5; return print; }
print(f());
let s = str;
let str = fn(x) { return "custom"; };
print(str(1), s(1));
print(len == len, s == s, print == print, s == print);
