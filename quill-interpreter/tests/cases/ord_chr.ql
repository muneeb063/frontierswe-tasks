print(ord("A"), ord("é"), ord("😀"), chr(97), chr(233), chr(128512));
let s = "";
for i in range(5) { s = s + chr(ord("a") + i); }
print(s, len("😀"), "😀"[0] == chr(128512));
