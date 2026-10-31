# Build the Stratus IAM authorization engine

Stratus is a cloud platform whose access control is modelled on the policy languages of the big
public clouds. Its security team wants an offline evaluator they can run against exported account
snapshots to answer "can this principal do this action on this resource, in this context, and if
not, why not?" before they ship policy changes. Nothing like it exists yet on this machine.

The authorization model is defined completely in `/workspace/iam/SPEC.md`: the snapshot and query
formats, identity policies from users, groups and roles, permission boundaries, multi-level
organization policies, resource policies with principals, action and resource wildcards, policy
variables, every condition operator with its `IfExists`, `ForAnyValue:` / `ForAllValues:` and
`Null` semantics, derived context keys, same-account versus cross-account rules, and the order in
which a decision is reached. Read it closely: several rules deliberately differ from what you may
remember about other clouds, and the spec is the only authority.

## What to deliver

An executable at `/workspace/iam/iam-eval`:

```
/workspace/iam/iam-eval SNAPSHOT.json QUERIES.jsonl
```

It prints one JSON line per query, in input order: `{"id": "...", "decision": "..."}`, where the
decision is `allow`, `explicit_deny` or `implicit_deny`. Use any language available in the
container (Python 3.12, C and C++ with gcc/g++ and make; no network). If you compile, leave the
built binary in place: it is run as-is, from another working directory, as an unprivileged user.

## How it is graded

Your evaluator is run on several hidden account snapshots, each with a large batch of queries (each
batch must finish within 120 seconds). One account is a realistic production setup with groups,
boundaries, tag-based access control, MFA and network guards, time-boxed access, organization
guardrails and cross-account sharing; the others are generated accounts that exercise the corner
cases of every rule in the spec. The three decisions are equally common in the hidden set.

The score is chance-corrected balanced accuracy: the mean of the per-decision recall, rescaled so
that answering every query the same way scores 0 and getting every query right scores 1.

## Getting started

`/workspace/iam/examples/` contains a small example account (`example.json`), queries
(`example.jsonl`) and the correct decisions (`example.expected.jsonl`);
`/workspace/iam/check_example.sh` diffs your output against them. The example covers only the
basics. Write your own snapshots and queries for every rule and corner case in the spec.
