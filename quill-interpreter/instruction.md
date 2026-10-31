# Build an interpreter for Quill

Quill is a small dynamically typed scripting language. Its complete definition is in
`/workspace/quill/SPEC.md`: lexical rules, grammar, scoping, closures, arbitrary-precision
integers, lists and insertion-ordered maps, sixteen builtins, the exact display format, and the
exact output and exit status for syntax errors and runtime errors. No implementation of Quill
exists anywhere on this machine; you are writing the first one.

## What to deliver

An executable at `/workspace/quill/quill` that runs a program:

```
/workspace/quill/quill path/to/program.ql
```

It must reproduce, byte for byte, the standard output and the exit status that the spec
defines for that program. Write it in any language available in the container (Python 3.12,
C and C++ with gcc/g++ and make are installed; there is no network access). If you use a
compiled language, leave the built binary in place: nothing is compiled for you when your work
is graded, and the executable is run as-is, from a different working directory, as an
unprivileged user, with no network.

## How it is graded

Your interpreter is run on a hidden suite of Quill programs. They exercise every section of the
spec: operator semantics and precedence, floor division on huge integers, Unicode strings,
nested display forms with escaping, truthiness, short-circuit evaluation and evaluation order,
lexical scoping and shadowing, closures that capture by reference (including per-iteration loop
bindings), recursion at least 1000 calls deep, snapshot semantics of `for`, every builtin, every
runtime error message, and a range of syntax errors that must be detected before any output is
produced. Some programs are larger workloads (recursive algorithms, sieves, sorting, big-integer
arithmetic); every program has a 10 second limit, which a straightforward tree-walking
interpreter meets comfortably, but an interpreter with accidental quadratic behaviour may not.

A program passes only if both standard output and exit status are exactly right (for a syntax
error, a single line starting with `syntax error` and exit status 2). Your score is the
fraction of hidden programs that pass. Standard error is ignored.

## Getting started

`/workspace/quill/examples/` has a few programs with their expected output (`.out`) and exit
status (`.code`), and `/workspace/quill/run_examples.sh` runs your interpreter against them.
They cover only a small part of the language: passing them is a smoke test, not evidence of
correctness. Read the spec closely, write your own test programs for each rule, and treat the
spec as the only authority when the examples are silent.
