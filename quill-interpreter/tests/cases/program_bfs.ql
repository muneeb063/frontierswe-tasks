let maze = [
  "S.#.......",
  ".##.####.#",
  "....#....#",
  "#.#.#.##.#",
  "..#...#..E"
];
let rows = len(maze); let cols = len(maze[0]);
let start = nil; let goal = nil;
for r in range(rows) { for c in range(cols) {
  if maze[r][c] == "S" { start = [r, c]; }
  if maze[r][c] == "E" { goal = [r, c]; }
} }
let dist = {}; dist[str(start)] = 0;
let queue = [start]; let head = 0;
while head < len(queue) {
  let cur = queue[head]; head = head + 1;
  for d in [[0, 1], [1, 0], [0, -1], [-1, 0]] {
    let nr = cur[0] + d[0]; let nc = cur[1] + d[1];
    if nr >= 0 and nr < rows and nc >= 0 and nc < cols and maze[nr][nc] != "#" {
      let key = str([nr, nc]);
      if not has(dist, key) { dist[key] = dist[str(cur)] + 1; push(queue, [nr, nc]); }
    }
  }
}
print("start", start, "goal", goal, "steps", dist[str(goal)], "visited", len(dist));
