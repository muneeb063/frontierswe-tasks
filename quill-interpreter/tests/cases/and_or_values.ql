fn loud(x) { print("eval", x); return x; }
print(1 and 2, 0 and 2, nil or "d", "a" or "b", [] or {}, false and loud(1));
print(loud(0) or loud(5));
print(loud(1) and loud(nil));
let r = loud("") and loud("never");
print(r == "");
print(nil or false or 0 or "last");
print(1 and 2 and 3 and nil and 4);
