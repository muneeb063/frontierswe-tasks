let inner = {"n": 1};
let outer = [inner, inner];
outer[0]["n"] = 2;
print(outer, inner);
let grid = {};
for r in range(2) { grid[r] = {}; for c in range(2) { grid[r][c] = r * 2 + c; } }
print(grid);
fn mutate(m) { m["added"] = true; }
mutate(inner);
print(outer[1]);
