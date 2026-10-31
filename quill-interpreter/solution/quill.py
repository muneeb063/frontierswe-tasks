#!/usr/bin/env python3
"""Reference interpreter for Quill (spec: /workspace/quill/SPEC.md). Tree-walking, stdlib only."""
import sys
import threading


class QuillError(Exception):
    pass


class QuillSyntax(Exception):
    pass


class BreakEx(Exception):
    pass


class ContinueEx(Exception):
    pass


class ReturnEx(Exception):
    def __init__(self, val):
        self.val = val


KEYWORDS = {"let", "fn", "if", "else", "while", "for", "in", "break", "continue", "return",
            "true", "false", "nil", "and", "or", "not"}
TWO = {"==", "!=", "<=", ">="}
ONE = set("()[]{},;:=<>+-*/%")
DIGITS = set("0123456789")
ID_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
ID_CHAR = ID_START | DIGITS
ESC = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


def lex(src):
    toks, i, line, n = [], 0, 1, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c in " \t\r":
            i += 1
        elif c == "#":
            while i < n and src[i] != "\n":
                i += 1
        elif c in DIGITS:
            j = i
            while j < n and src[j] in DIGITS:
                j += 1
            if j < n and src[j] in ID_START:
                raise QuillSyntax(f"line {line}: malformed number")
            toks.append(("int", int(src[i:j]), line))
            i = j
        elif c in ID_START:
            j = i
            while j < n and src[j] in ID_CHAR:
                j += 1
            word = src[i:j]
            toks.append((word, None, line) if word in KEYWORDS else ("id", word, line))
            i = j
        elif c == '"':
            j, buf = i + 1, []
            while True:
                if j >= n or src[j] == "\n":
                    raise QuillSyntax(f"line {line}: unterminated string")
                ch = src[j]
                if ch == '"':
                    break
                if ch == "\\":
                    e = src[j + 1] if j + 1 < n else ""
                    if e not in ESC:
                        raise QuillSyntax(f"line {line}: bad escape")
                    buf.append(ESC[e])
                    j += 2
                else:
                    buf.append(ch)
                    j += 1
            toks.append(("str", "".join(buf), line))
            i = j + 1
        elif src[i:i + 2] in TWO:
            toks.append((src[i:i + 2], None, line))
            i += 2
        elif c in ONE:
            toks.append((c, None, line))
            i += 1
        else:
            raise QuillSyntax(f"line {line}: unexpected character {c!r}")
    toks.append(("eof", None, line))
    return toks


# ---------------------------------------------------------------- values

class Closure:
    __slots__ = ("name", "params", "body", "env")

    def __init__(self, name, params, body, env):
        self.name, self.params, self.body, self.env = name, params, body, env


class Builtin:
    __slots__ = ("name", "arity", "fn")

    def __init__(self, name, arity, fn):
        self.name, self.arity, self.fn = name, arity, fn


class QMap:
    __slots__ = ("d",)  # tagged key -> value; tags keep true and 1 apart

    def __init__(self):
        self.d = {}


def hkey(k):
    t = type(k)
    if t is int:
        return ("i", k)
    if t is str:
        return ("s", k)
    if t is bool:
        return ("b", k)
    if k is None:
        return ("n", None)
    raise QuillError("unhashable key")


def truthy(v):
    if v is None or v is False:
        return False
    t = type(v)
    if t is int:
        return v != 0
    if t is str or t is list:
        return len(v) > 0
    if t is QMap:
        return len(v.d) > 0
    return True


def eq(a, b):
    ta = type(a)
    if ta is not type(b):
        return False
    if ta is list:
        return len(a) == len(b) and all(eq(x, y) for x, y in zip(a, b))
    if ta is QMap:
        return a.d.keys() == b.d.keys() and all(eq(a.d[k], b.d[k]) for k in a.d)
    if ta is Closure or ta is Builtin:
        return a is b
    return a == b


def quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def show(v, top=True):
    t = type(v)
    if v is None:
        return "nil"
    if t is bool:
        return "true" if v else "false"
    if t is int:
        return str(v)
    if t is str:
        return v if top else quote(v)
    if t is list:
        return "[" + ", ".join(show(x, False) for x in v) + "]"
    if t is QMap:
        return "{" + ", ".join(f"{show(k[1], False)}: {show(x, False)}" for k, x in v.d.items()) + "}"
    if t is Closure:
        return f"<fn {v.name}>" if v.name else "<fn>"
    return f"<builtin {v.name}>"


def type_name(v):
    t = type(v)
    if v is None:
        return "nil"
    return {bool: "bool", int: "int", str: "string", list: "list", QMap: "map",
            Closure: "function", Builtin: "function"}[t]


def need_int(*vs):
    for v in vs:
        if type(v) is not int:
            raise QuillError("type error")


# ---------------------------------------------------------------- environment

class Env:
    __slots__ = ("v", "p")

    def __init__(self, p):
        self.v = {}
        self.p = p

    def get(self, name):
        e = self
        while e is not None:
            v = e.v
            if name in v:
                return v[name]
            e = e.p
        raise QuillError(f"undefined variable: {name}")

    def set(self, name, val):
        e = self
        while e is not None:
            if name in e.v:
                e.v[name] = val
                return
            e = e.p
        raise QuillError(f"undefined variable: {name}")


def run_block(stmts, env):
    e = Env(env)
    for s in stmts:
        s.ex(e)


# ---------------------------------------------------------------- operators

def op_add(a, b):
    ta, tb = type(a), type(b)
    if ta is tb and (ta is int or ta is str or ta is list):
        return a + b
    raise QuillError("type error")


def op_sub(a, b):
    need_int(a, b)
    return a - b


def op_mul(a, b):
    need_int(a, b)
    return a * b


def op_div(a, b):
    need_int(a, b)
    if b == 0:
        raise QuillError("division by zero")
    return a // b


def op_mod(a, b):
    need_int(a, b)
    if b == 0:
        raise QuillError("division by zero")
    return a % b


def ordered(a, b):
    ta = type(a)
    if ta is not type(b) or not (ta is int or ta is str):
        raise QuillError("type error")


def op_lt(a, b):
    ordered(a, b)
    return a < b


def op_le(a, b):
    ordered(a, b)
    return a <= b


def op_gt(a, b):
    ordered(a, b)
    return a > b


def op_ge(a, b):
    ordered(a, b)
    return a >= b


OPS = {"+": op_add, "-": op_sub, "*": op_mul, "/": op_div, "%": op_mod,
       "<": op_lt, "<=": op_le, ">": op_gt, ">=": op_ge,
       "==": eq, "!=": lambda a, b: not eq(a, b)}


def index_get(obj, idx):
    t = type(obj)
    if t is list or t is str:
        need_int(idx)
        if 0 <= idx < len(obj):
            return obj[idx]
        raise QuillError("index out of range")
    if t is QMap:
        k = hkey(idx)
        if k in obj.d:
            return obj.d[k]
        raise QuillError("key not found")
    raise QuillError("type error")


# ---------------------------------------------------------------- AST

class Lit:
    __slots__ = ("val",)

    def __init__(self, val):
        self.val = val

    def ev(self, env):
        return self.val


class Var:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def ev(self, env):
        return env.get(self.name)


class ListLit:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items

    def ev(self, env):
        return [x.ev(env) for x in self.items]


class MapLit:
    __slots__ = ("pairs",)

    def __init__(self, pairs):
        self.pairs = pairs

    def ev(self, env):
        m = QMap()
        for k, v in self.pairs:
            key = k.ev(env)
            m.d[hkey(key)] = v.ev(env)
        return m


class FnLit:
    __slots__ = ("name", "params", "body")

    def __init__(self, name, params, body):
        self.name, self.params, self.body = name, params, body

    def ev(self, env):
        return Closure(self.name, self.params, self.body, env)


class Bin:
    __slots__ = ("f", "l", "r")

    def __init__(self, op, l, r):
        self.f, self.l, self.r = OPS[op], l, r

    def ev(self, env):
        return self.f(self.l.ev(env), self.r.ev(env))


class And:
    __slots__ = ("l", "r")

    def __init__(self, l, r):
        self.l, self.r = l, r

    def ev(self, env):
        a = self.l.ev(env)
        return self.r.ev(env) if truthy(a) else a


class Or:
    __slots__ = ("l", "r")

    def __init__(self, l, r):
        self.l, self.r = l, r

    def ev(self, env):
        a = self.l.ev(env)
        return a if truthy(a) else self.r.ev(env)


class Not:
    __slots__ = ("e",)

    def __init__(self, e):
        self.e = e

    def ev(self, env):
        return not truthy(self.e.ev(env))


class Neg:
    __slots__ = ("e",)

    def __init__(self, e):
        self.e = e

    def ev(self, env):
        v = self.e.ev(env)
        need_int(v)
        return -v


class Index:
    __slots__ = ("obj", "idx")

    def __init__(self, obj, idx):
        self.obj, self.idx = obj, idx

    def ev(self, env):
        return index_get(self.obj.ev(env), self.idx.ev(env))


class Call:
    __slots__ = ("callee", "args")

    def __init__(self, callee, args):
        self.callee, self.args = callee, args

    def ev(self, env):
        f = self.callee.ev(env)
        args = [a.ev(env) for a in self.args]
        t = type(f)
        if t is Closure:
            if len(args) != len(f.params):
                raise QuillError("arity mismatch")
            e = Env(f.env)
            e.v = dict(zip(f.params, args))
            try:
                for s in f.body:
                    s.ex(e)
            except ReturnEx as r:
                return r.val
            return None
        if t is Builtin:
            if len(args) not in f.arity:
                raise QuillError("arity mismatch")
            return f.fn(*args)
        raise QuillError("not callable")


class Let:
    __slots__ = ("name", "e")

    def __init__(self, name, e):
        self.name, self.e = name, e

    def ex(self, env):
        env.v[self.name] = self.e.ev(env)


class Assign:
    __slots__ = ("name", "e")

    def __init__(self, name, e):
        self.name, self.e = name, e

    def ex(self, env):
        env.set(self.name, self.e.ev(env))


class IndexAssign:
    __slots__ = ("obj", "idx", "e")

    def __init__(self, obj, idx, e):
        self.obj, self.idx, self.e = obj, idx, e

    def ex(self, env):
        obj = self.obj.ev(env)
        idx = self.idx.ev(env)
        val = self.e.ev(env)
        t = type(obj)
        if t is list:
            need_int(idx)
            if not 0 <= idx < len(obj):
                raise QuillError("index out of range")
            obj[idx] = val
        elif t is QMap:
            obj.d[hkey(idx)] = val
        else:
            raise QuillError("type error")


class ExprStmt:
    __slots__ = ("e",)

    def __init__(self, e):
        self.e = e

    def ex(self, env):
        self.e.ev(env)


class If:
    __slots__ = ("arms", "other")

    def __init__(self, arms, other):
        self.arms, self.other = arms, other

    def ex(self, env):
        for cond, body in self.arms:
            if truthy(cond.ev(env)):
                run_block(body, env)
                return
        if self.other is not None:
            run_block(self.other, env)


class While:
    __slots__ = ("cond", "body")

    def __init__(self, cond, body):
        self.cond, self.body = cond, body

    def ex(self, env):
        while truthy(self.cond.ev(env)):
            try:
                run_block(self.body, env)
            except BreakEx:
                break
            except ContinueEx:
                pass


class For:
    __slots__ = ("name", "it", "body")

    def __init__(self, name, it, body):
        self.name, self.it, self.body = name, it, body

    def ex(self, env):
        seq = self.it.ev(env)
        t = type(seq)
        if t is list or t is str:
            items = list(seq)
        elif t is QMap:
            items = [k[1] for k in seq.d]
        else:
            raise QuillError("type error")
        for x in items:
            e = Env(env)
            e.v[self.name] = x
            try:
                run_block(self.body, e)
            except BreakEx:
                break
            except ContinueEx:
                pass


class Break:
    __slots__ = ()

    def ex(self, env):
        raise BreakEx()


class Continue:
    __slots__ = ()

    def ex(self, env):
        raise ContinueEx()


class Return:
    __slots__ = ("e",)

    def __init__(self, e):
        self.e = e

    def ex(self, env):
        raise ReturnEx(None if self.e is None else self.e.ev(env))


# ---------------------------------------------------------------- parser

class Parser:
    def __init__(self, toks):
        self.toks, self.pos, self.fn_depth, self.loop_depth = toks, 0, 0, 0

    def peek(self, k=0):
        return self.toks[self.pos + k][0]

    def next(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind):
        tok = self.next()
        if tok[0] != kind:
            raise QuillSyntax(f"line {tok[2]}: expected {kind!r}, got {tok[0]!r}")
        return tok

    def fail(self):
        tok = self.toks[self.pos]
        raise QuillSyntax(f"line {tok[2]}: unexpected {tok[0]!r}")

    def program(self):
        stmts = []
        while self.peek() != "eof":
            stmts.append(self.stmt())
        return stmts

    def block(self):
        self.expect("{")
        stmts = []
        while self.peek() != "}":
            if self.peek() == "eof":
                self.fail()
            stmts.append(self.stmt())
        self.next()
        return stmts

    def stmt(self):
        k = self.peek()
        if k == "let":
            self.next()
            name = self.expect("id")[1]
            self.expect("=")
            e = self.expr()
            self.expect(";")
            return Let(name, e)
        if k == "fn" and self.peek(1) == "id":
            self.next()
            name = self.expect("id")[1]
            return Let(name, self.fn_rest(name))
        if k == "if":
            self.next()
            arms = [(self.expr(), self.block())]
            other = None
            while self.peek() == "else":
                self.next()
                if self.peek() == "if":
                    self.next()
                    arms.append((self.expr(), self.block()))
                else:
                    other = self.block()
                    break
            return If(arms, other)
        if k == "while":
            self.next()
            cond = self.expr()
            return While(cond, self.loop_body())
        if k == "for":
            self.next()
            name = self.expect("id")[1]
            self.expect("in")
            it = self.expr()
            return For(name, it, self.loop_body())
        if k in ("break", "continue"):
            if self.loop_depth == 0:
                self.fail()
            self.next()
            self.expect(";")
            return Break() if k == "break" else Continue()
        if k == "return":
            if self.fn_depth == 0:
                self.fail()
            self.next()
            e = None if self.peek() == ";" else self.expr()
            self.expect(";")
            return Return(e)
        e = self.expr()
        if self.peek() == "=":
            self.next()
            rhs = self.expr()
            self.expect(";")
            if type(e) is Var:
                return Assign(e.name, rhs)
            if type(e) is Index:
                return IndexAssign(e.obj, e.idx, rhs)
            raise QuillSyntax("invalid assignment target")
        self.expect(";")
        return ExprStmt(e)

    def loop_body(self):
        self.loop_depth += 1
        body = self.block()
        self.loop_depth -= 1
        return body

    def fn_rest(self, name):
        self.expect("(")
        params = []
        while self.peek() != ")":
            params.append(self.expect("id")[1])
            if self.peek() != ")":
                self.expect(",")
        self.next()
        if len(set(params)) != len(params):
            raise QuillSyntax("duplicate parameter")
        saved = self.loop_depth
        self.fn_depth += 1
        self.loop_depth = 0
        body = self.block()
        self.fn_depth -= 1
        self.loop_depth = saved
        return FnLit(name, params, body)

    def expr(self):
        e = self.and_expr()
        while self.peek() == "or":
            self.next()
            e = Or(e, self.and_expr())
        return e

    def and_expr(self):
        e = self.not_expr()
        while self.peek() == "and":
            self.next()
            e = And(e, self.not_expr())
        return e

    def not_expr(self):
        if self.peek() == "not":
            self.next()
            return Not(self.not_expr())
        return self.cmp()

    def cmp(self):
        e = self.add()
        while self.peek() in ("==", "!=", "<", "<=", ">", ">="):
            op = self.next()[0]
            e = Bin(op, e, self.add())
        return e

    def add(self):
        e = self.mul()
        while self.peek() in ("+", "-"):
            op = self.next()[0]
            e = Bin(op, e, self.mul())
        return e

    def mul(self):
        e = self.unary()
        while self.peek() in ("*", "/", "%"):
            op = self.next()[0]
            e = Bin(op, e, self.unary())
        return e

    def unary(self):
        if self.peek() == "-":
            self.next()
            return Neg(self.unary())
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            k = self.peek()
            if k == "(":
                self.next()
                e = Call(e, self.items(")"))
            elif k == "[":
                self.next()
                idx = self.expr()
                self.expect("]")
                e = Index(e, idx)
            else:
                return e

    def items(self, close):
        out = []
        while self.peek() != close:
            out.append(self.expr())
            if self.peek() != close:
                self.expect(",")
        self.next()
        return out

    def primary(self):
        kind, val, _ = self.toks[self.pos]
        if kind in ("int", "str"):
            self.next()
            return Lit(val)
        if kind in ("true", "false", "nil"):
            self.next()
            return Lit({"true": True, "false": False, "nil": None}[kind])
        if kind == "id":
            self.next()
            return Var(val)
        if kind == "(":
            self.next()
            e = self.expr()
            self.expect(")")
            return e
        if kind == "[":
            self.next()
            return ListLit(self.items("]"))
        if kind == "{":
            self.next()
            pairs = []
            while self.peek() != "}":
                k = self.expr()
                self.expect(":")
                pairs.append((k, self.expr()))
                if self.peek() != "}":
                    self.expect(",")
            self.next()
            return MapLit(pairs)
        if kind == "fn":
            self.next()
            return self.fn_rest(None)
        self.fail()


# ---------------------------------------------------------------- builtins

OUT = []


def b_print(*args):
    OUT.append(" ".join(show(a) for a in args) + "\n")


def b_len(x):
    t = type(x)
    if t is str or t is list:
        return len(x)
    if t is QMap:
        return len(x.d)
    raise QuillError("type error")


def need(v, t):
    if type(v) is not t:
        raise QuillError("type error")


def b_push(lst, v):
    need(lst, list)
    lst.append(v)


def b_pop(lst):
    need(lst, list)
    if not lst:
        raise QuillError("pop from empty list")
    return lst.pop()


def b_keys(m):
    need(m, QMap)
    return [k[1] for k in m.d]


def b_has(m, k):
    need(m, QMap)
    return hkey(k) in m.d


def b_int(x):
    if type(x) is int:
        return x
    need(x, str)
    body = x[1:] if x.startswith("-") else x
    if not body or any(c not in DIGITS for c in body):
        raise QuillError("invalid int")
    return int(x)


def b_range(a, b=None):
    if b is None:
        a, b = 0, a
    need_int(a, b)
    return list(range(a, b))


def b_slice(x, a, b):
    if type(x) not in (list, str):
        raise QuillError("type error")
    need_int(a, b)
    if not 0 <= a <= b <= len(x):
        raise QuillError("index out of range")
    return x[a:b]


def b_join(lst, sep):
    need(lst, list)
    need(sep, str)
    for x in lst:
        need(x, str)
    return sep.join(lst)


def b_split(s, sep):
    need(s, str)
    need(sep, str)
    return list(s) if sep == "" else s.split(sep)


def b_ord(s):
    need(s, str)
    if len(s) != 1:
        raise QuillError("type error")
    return ord(s)


def b_chr(n):
    need_int(n)
    if not 0 <= n <= 0x10FFFF:
        raise QuillError("type error")
    return chr(n)


def b_error(msg):
    need(msg, str)
    raise QuillError(msg)


BUILTINS = [
    ("print", None, b_print), ("len", {1}, b_len), ("push", {2}, b_push), ("pop", {1}, b_pop),
    ("keys", {1}, b_keys), ("has", {2}, b_has), ("str", {1}, show), ("int", {1}, b_int),
    ("type", {1}, type_name), ("range", {1, 2}, b_range), ("slice", {3}, b_slice),
    ("join", {2}, b_join), ("split", {2}, b_split), ("ord", {1}, b_ord), ("chr", {1}, b_chr),
    ("error", {1}, b_error),
]


class AnyArity:
    def __contains__(self, n):
        return True


def run(path, result):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    try:
        prog = Parser(lex(src)).program()
    except QuillSyntax as e:
        result.append((f"syntax error: {e}\n", 2))
        return
    glob = Env(None)
    for name, arity, fn in BUILTINS:
        glob.v[name] = Builtin(name, arity if arity is not None else AnyArity(), fn)
    code = 0
    try:
        run_block(prog, glob)
    except QuillError as e:
        OUT.append(f"runtime error: {e}\n")
        code = 1
    except RecursionError:
        OUT.append("runtime error: stack overflow\n")
        code = 1
    result.append(("".join(OUT), code))


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: quill FILE\n")
        sys.exit(2)
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(512 * 1024 * 1024)
    result = []
    t = threading.Thread(target=run, args=(sys.argv[1], result))
    t.start()
    t.join()
    out, code = result[0] if result else ("runtime error: internal\n", 1)
    sys.stdout.write(out)
    sys.stdout.flush()
    sys.exit(code)


if __name__ == "__main__":
    main()
