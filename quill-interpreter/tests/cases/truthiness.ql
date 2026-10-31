let vals = [false, nil, 0, "", [], {}, true, 1, -1, "0", " ", [0], {"a": nil}, print];
for v in vals {
  if v { print(type(v), "truthy"); } else { print(type(v), "falsy"); }
}
print(not 0, not "x", not not [], not nil);
