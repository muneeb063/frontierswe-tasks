let inventory = {"apples": 3};
inventory["pears"] = 2;
inventory["apples"] = inventory["apples"] + 1;
print(inventory, len(inventory), has(inventory, "plums"));
let xs = [5, 3, 8];
push(xs, 1);
print(xs, pop(xs), slice(xs, 1, 3), xs + ["end"]);
print(["say \"hi\"", "tab\there"]);
print(split("a-b-c", "-"), join(["x", "y"], "+"));
