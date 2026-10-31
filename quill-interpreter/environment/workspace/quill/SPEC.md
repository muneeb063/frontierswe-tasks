# The Quill language, version 1

Quill is a small dynamically typed scripting language. This document is the complete
definition: anything a program can observe (its standard output and exit status) is fixed
here. Where this document says behaviour is unspecified, no test depends on it.

## 1. Running a program

```
quill FILE
```

`FILE` is UTF-8 source. The whole file is parsed before anything runs.

| Outcome | Standard output | Exit status |
|---|---|---|
| Program finishes | everything it printed | 0 |
| Syntax error | exactly one line that starts with `syntax error` (any text may follow), nothing else | 2 |
| Runtime error | everything printed before the error, then one line `runtime error: MESSAGE` | 1 |

Nothing is ever required on standard error. `MESSAGE` is one of the messages listed in
section 9, or the string passed to `error()`.

## 2. Lexical structure

* Whitespace (space, tab, carriage return, newline) separates tokens and is otherwise ignored.
* `#` starts a comment that runs to the end of the line.
* Identifiers: an ASCII letter or `_`, followed by ASCII letters, digits or `_`.
* Keywords (not usable as identifiers):
  `let fn if else while for in break continue return true false nil and or not`
* Integer literals: one or more ASCII digits, decimal, leading zeros allowed (`007` is 7).
  There are no negative literals; `-5` is unary minus applied to 5. A digit sequence directly
  followed by a letter or `_` (such as `12ab`) is a syntax error.
* String literals: double quotes, on one line. Escapes: `\n` `\t` `\\` `\"`. Any other
  backslash sequence, a raw newline inside the string, or a missing closing quote is a
  syntax error. Any other Unicode character stands for itself.
* Operators and punctuation: `( ) [ ] { } , ; : = == != < <= > >= + - * / %`
* Any other character outside a string or comment is a syntax error.

## 3. Values

| Type | `type(x)` | Notes |
|---|---|---|
| integer | `"int"` | arbitrary precision, never overflows |
| string | `"string"` | immutable sequence of Unicode code points |
| boolean | `"bool"` | `true`, `false` |
| nil | `"nil"` | `nil` |
| list | `"list"` | mutable, ordered, shared by reference |
| map | `"map"` | mutable, keeps insertion order, shared by reference |
| function | `"function"` | user functions and builtins |

Map keys must be integers, strings, booleans or nil. Using any other value as a key
(including for lookup or `has`) is the runtime error `unhashable key`. `1`, `true` and `"1"`
are three different keys. Storing to a key that already exists replaces its value and keeps
its original position in the order.

**Truthiness.** `false`, `nil`, `0`, `""`, `[]` and an empty map are falsy. Everything else
is truthy, including all functions.

## 4. Grammar

```
program    := stmt*
block      := "{" stmt* "}"
stmt       := "let" IDENT "=" expr ";"
            | "fn" IDENT "(" params ")" block
            | "if" expr block ("else" "if" expr block)* ("else" block)?
            | "while" expr block
            | "for" IDENT "in" expr block
            | "break" ";" | "continue" ";"
            | "return" expr? ";"
            | expr "=" expr ";"            # target must be IDENT or an index expression
            | expr ";"
params     := (IDENT ("," IDENT)*)?        # names must be distinct
expr       := or
or         := and ("or" and)*
and        := not ("and" not)*
not        := "not" not | cmp
cmp        := add (("==" | "!=" | "<" | "<=" | ">" | ">=") add)*
add        := mul (("+" | "-") mul)*
mul        := unary (("*" | "/" | "%") unary)*
unary      := "-" unary | postfix
postfix    := primary ("(" args ")" | "[" expr "]")*
args       := (expr ("," expr)*)?
primary    := INT | STRING | "true" | "false" | "nil" | IDENT | "(" expr ")"
            | "[" (expr ("," expr)* ","?)? "]"
            | "{" (expr ":" expr ("," expr ":" expr)* ","?)? "}"
            | "fn" "(" params ")" block
```

All binary operators are left-associative, so `1 < 2 < 3` means `(1 < 2) < 3`, a type error
at run time. A statement that starts with `fn` followed by an identifier is a function
declaration; `fn` followed by `(` starts an expression (an anonymous function).

These are syntax errors, found before the program runs: anything not matching the grammar,
an assignment whose target is not a variable or an index expression, duplicate parameter
names, `break` or `continue` that is not inside a loop body of the same function, and
`return` outside any function body.

## 5. Scope and variables

* Scoping is lexical. The builtins live in an outermost scope; the program's top level is a
  scope inside it.
* Each block (`if`/`else` arm, loop body, function body) opens a new scope. A while body gets
  a fresh scope on every iteration. A for body gets a fresh scope on every iteration, and the
  loop variable is bound in that scope, so a function created in iteration *k* sees that
  iteration's value.
* A function's parameters live in the same scope as its body.
* `let x = e;` evaluates `e` and binds `x` in the current scope. Re-declaring a name already
  bound in the same scope simply rebinds it; declaring it in an inner scope shadows it.
  Builtins can be shadowed like any name.
* `fn name(...) { ... }` behaves exactly like `let name = fn(...) { ... };` except that the
  function's display name is `name`. A function can call itself recursively by name.
* Reading a name that is not bound in any enclosing scope is `undefined variable: NAME`.
* `x = e;` evaluates `e`, then assigns to the nearest enclosing binding of `x`. If there is
  none, it is `undefined variable: x` (after `e` was evaluated).
* Closures capture variables by reference: assignments made after a closure was created are
  visible to it, and assignments it makes are visible outside.

## 6. Statements

* **if**: conditions are tested in order using truthiness; the first truthy arm runs. If none
  is truthy and there is an `else`, it runs.
* **while**: tests the condition before each iteration.
* **for x in e**: `e` is evaluated once. A list iterates over its elements, a string over its
  characters (one-character strings), a map over its keys in insertion order. The sequence is
  snapshotted when the loop starts: changing the list or map inside the body does not change
  which items the loop visits. Any other type is `type error`.
* **break** / **continue** act on the innermost enclosing loop.
* **return** leaves the current function with the value of the expression, or `nil` if there
  is none. A function that runs off the end of its body returns `nil`.
* **Index assignment** `t[i] = v;` evaluates `t`, then `i`, then `v`. For a list, `i` must be
  an integer with `0 <= i < len(t)` (otherwise `type error` / `index out of range`). For a
  map, it inserts or replaces key `i`. Any other `t` (including strings) is `type error`.
* An expression statement evaluates the expression and discards the result.

## 7. Expressions

Operands are evaluated left to right. A call evaluates the callee, then the arguments left
to right. Map literals evaluate key then value, pair by pair.

| Operator | Operands | Result |
|---|---|---|
| `+` | int, int / string, string / list, list | sum / concatenation (a new string or list) |
| `-` `*` | int, int | difference, product |
| `/` | int, int | floor division (`-7 / 2` is `-4`) |
| `%` | int, int | remainder with the sign of the divisor (`-7 % 2` is `1`, `7 % -2` is `-1`) |
| unary `-` | int | negation |
| `<` `<=` `>` `>=` | int, int / string, string | boolean; strings compare by code point, lexicographically |
| `==` `!=` | any, any | deep equality, never an error (see below) |
| `and` | any, any | if the left value is falsy, it is the result and the right side is not evaluated; otherwise the right value |
| `or` | any, any | if the left value is truthy, it is the result and the right side is not evaluated; otherwise the right value |
| `not` | any | `true` if the operand is falsy, else `false` |

Any other combination of operand types is `type error`. `/` or `%` by zero is
`division by zero`. Note that booleans are not integers: `true + 1` is `type error`.

**Equality.** Values of different types are never equal. Integers, strings, booleans and
nil compare by value. Lists are equal when they have the same length and equal elements in
order. Maps are equal when they have the same set of keys and equal values for each key
(order does not matter). Functions are equal only to themselves.

**Indexing** `t[i]`: for a list or string, `i` must be an integer (`type error` otherwise) and
`0 <= i < len(t)` (`index out of range` otherwise); a string yields a one-character string.
For a map, a missing key is `key not found`. Indexing anything else is `type error`.

**Calls**: calling a non-function is `not callable`. Calling with the wrong number of
arguments is `arity mismatch`. Implementations must support at least 1000 nested active
calls; what happens beyond your own limit is unspecified.

## 8. Builtins

| Builtin | Behaviour |
|---|---|
| `print(a, b, ...)` | any number of arguments (including none): writes their display forms separated by one space, then a newline. Returns nil. |
| `len(x)` | length of a string (code points), list or map |
| `push(list, v)` | appends `v`, returns nil |
| `pop(list)` | removes and returns the last element; `pop from empty list` if empty |
| `keys(map)` | a new list of the keys in insertion order |
| `has(map, k)` | whether the key is present |
| `str(x)` | the display form of `x` as a string |
| `int(x)` | an int is returned unchanged; a string must be an optional `-` followed by one or more ASCII digits, nothing else (`invalid int` otherwise) |
| `type(x)` | the type name from section 3 |
| `range(n)` / `range(a, b)` | the list of integers `a <= i < b` (`a` defaults to 0); empty if `b <= a` |
| `slice(x, a, b)` | elements / characters `a <= i < b` of a list or string as a new value; requires `0 <= a <= b <= len(x)`, otherwise `index out of range` |
| `join(list, sep)` | concatenates a list of strings with `sep` between them |
| `split(s, sep)` | splits `s` on every occurrence of `sep`; `split("a,,b", ",")` is `["a", "", "b"]`; an empty `sep` splits into single characters |
| `ord(s)` | code point of a one-character string |
| `chr(n)` | one-character string for code point `0 <= n <= 1114111` |
| `error(msg)` | raises a runtime error whose message is the string `msg` |

A builtin given an argument of the wrong type (including `ord` of a string whose length is not
1, and `chr` out of range) is `type error`. Wrong argument count is `arity mismatch`.
Builtins are values: they can be stored, passed and compared.

## 9. Display form and runtime error messages

The display form is what `print` writes and what `str` returns:

* integers in decimal with a leading `-` if negative; `true`, `false`, `nil`
* a string by itself is its raw characters
* lists: `[` elements separated by `, ` `]`, for example `[1, "a", [true, nil]]`
* maps: `{` `key: value` pairs separated by `, ` in insertion order `}`, for example
  `{"a": 1, 2: [3]}`; an empty map is `{}`
* inside lists and maps, strings are shown in double quotes with `\`, `"`, newline and tab
  written as `\\`, `\"`, `\n` and `\t`
* user functions: `<fn NAME>` when declared with `fn NAME`, otherwise `<fn>`; builtins:
  `<builtin NAME>`
* printing a list or map that contains itself is unspecified

Runtime error messages, exactly:

```
undefined variable: NAME
type error
division by zero
index out of range
key not found
unhashable key
not callable
arity mismatch
pop from empty list
invalid int
```
