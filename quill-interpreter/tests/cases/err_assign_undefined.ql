fn side() { print("rhs evaluated"); return 1; }
if true { let local = 1; }
local = side();
