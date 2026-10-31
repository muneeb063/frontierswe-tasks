# Stratus IAM authorization, specification v1

Stratus is a cloud platform whose access control is modelled on the policy languages of the
large public clouds, with its own precise rules. This document is the complete definition of
how Stratus decides whether a request is allowed. Where it differs from any other cloud you
know, this document wins.

## 1. The evaluator you are building

```
iam-eval SNAPSHOT.json QUERIES.jsonl
```

* `SNAPSHOT.json` describes one account: its principals, groups, policies, resource policies and
  organization policies (section 2).
* `QUERIES.jsonl` has one request per line (section 3). Blank lines are ignored.
* Standard output: exactly one line per query, in input order, each a JSON object
  `{"id": <the query's id>, "decision": <decision>}` where decision is one of
  `"allow"`, `"explicit_deny"`, `"implicit_deny"`. Nothing else on standard output.
* Exit status 0. Inputs are always valid as described here.

## 2. Snapshot

```json
{
  "account_id": "111122223333",
  "managed_policies": { "<policy srn>": <policy document>, ... },
  "groups": { "<name>": { "policies": ["<policy srn>", ...], "inline": [<document>, ...] } },
  "users":  { "<name>": { "groups": ["<group name>", ...], "policies": [...], "inline": [...],
                          "boundary": "<policy srn>" | null, "tags": { "<key>": "<value>" } } },
  "roles":  { "<name>": { "policies": [...], "inline": [...], "boundary": ..., "tags": { ... } } },
  "resources": { "<resource srn>": { "policy": <document> | null, "tags": { "<key>": "<value>" } } },
  "org_policies": [ [<document>, ...], [<document>, ...], ... ]
}
```

Every field except `account_id` may be missing; a missing map or list is empty, a missing or null
boundary means no boundary. Every policy srn referenced from a principal or group exists in
`managed_policies`.

**Names (srn).** `srn:stratus:<service>:<region>:<account>:<resource-path>`. The account is
the fifth colon-separated field; region and account may be empty. Principals are
`srn:stratus:iam::<account>:user/<name>` and `srn:stratus:iam::<account>:role/<name>`. A
resource whose account field is empty belongs to the account of the principal making the request.

**Organization policies.** `org_policies` is a list of levels, from the organization root down to
the account. Each level is a list of documents. An empty or missing list means the account has no
organization restrictions.

## 3. Queries

```json
{"id": "q17", "principal": "srn:stratus:iam::111122223333:user/alice",
 "action": "storage:GetObject", "resource": "srn:stratus:storage:::reports/2026/q3.csv",
 "context": {"stratus:SourceIp": "10.1.2.3", "stratus:RequestedRegions": ["eu-west-1", "us-east-1"]}}
```

`principal` always names a user or role present in the snapshot. `context` (possibly missing)
maps context keys to a string or a list of strings (a multi-valued key).

### Request context

The request context is the query's `context` plus these derived keys, which replace any
query-supplied key of the same name:

| Key | Value |
|---|---|
| `stratus:PrincipalArn` | the principal srn |
| `stratus:PrincipalAccount` | the principal's account |
| `stratus:PrincipalType` | `"User"` or `"Role"` |
| `stratus:username` | the user name; **absent** for roles |
| `stratus:PrincipalTag/<k>` | each tag of the principal (its own `tags` only) |
| `stratus:ResourceTag/<k>` | each tag of the requested resource, if it is in `resources` |
| `stratus:ResourceAccount` | the resource's account (the principal's account if the field is empty) |

Context key names are case-insensitive everywhere (in conditions and in `${...}` variables).
Values are case-sensitive unless an operator says otherwise.

## 4. Policy documents

```json
{"Version": "2024-01-01", "Statement": [ <statement>, ... ]}
```

`Statement` may be a single statement object instead of a list. A statement has:

* `Effect`: `"Allow"` or `"Deny"`.
* Exactly one of `Action` / `NotAction`: a string or list of action patterns.
* Exactly one of `Resource` / `NotResource`: a string or list of resource patterns.
* `Principal`: only in resource policies (section 6).
* `Condition` (optional): section 5.
* `Sid` (optional): ignored.

A statement **applies** to a request when its action part, resource part, principal part (resource
policies only) and condition all match.

**Action part.** `Action` matches when at least one pattern matches the request action;
`NotAction` matches when none does. Action patterns compare case-insensitively.

**Resource part.** `Resource` matches when at least one pattern matches the request resource;
`NotResource` matches when none does. Resource patterns compare case-sensitively.

**Wildcards.** In action patterns, resource patterns and `StringLike`/`StringNotLike` values,
`*` matches any sequence of characters (including none, and including `/` and `:`) and `?`
matches exactly one character. The pattern must match the whole string.

**Variables.** Resource patterns and string condition values (every `String*` operator) may
contain `${key}`, replaced by the value of that context key before matching. Text that comes from
a variable is always literal: a `*` or `?` inside a substituted value is not a wildcard. `${*}`,
`${?}` and `${$}` stand for a literal `*`, `?` and `$`. If the key is absent from the context, or
is multi-valued, the pattern or value containing it matches nothing. Action patterns and
non-string condition values are never substituted.

## 5. Conditions

```json
"Condition": { "<operator>": { "<context key>": <value or list of values>, ... }, ... }
```

The condition matches when every operator block holds, and a block holds when every key in it
holds. Condition values may be JSON strings, numbers or booleans; numbers and booleans are first
converted to their JSON text (`3600`, `true`).

### Operators

| Operator | A context value `v` matches a condition value `c` when |
|---|---|
| `StringEquals` | `v == c` |
| `StringEqualsIgnoreCase` | `v` and `c` are equal ignoring case |
| `StringLike` | `v` matches the wildcard pattern `c` (case-sensitive) |
| `NumericEquals`, `NumericLessThan`, `NumericLessThanEquals`, `NumericGreaterThan`, `NumericGreaterThanEquals` | both parse as numbers and `v` (operator) `c` |
| `DateEquals`, `DateLessThan`, `DateLessThanEquals`, `DateGreaterThan`, `DateGreaterThanEquals` | both parse as dates and `v` (operator) `c` |
| `Bool` | `v` and `c` are equal ignoring case |
| `IpAddress` | `v` is an IPv4 address inside CIDR block `c` (a bare address means /32) |

* Numbers: optional `-`, one or more digits, optionally `.` and one or more digits; compared
  exactly as decimals. Anything else does not parse.
* Dates: `YYYY-MM-DDTHH:MM:SSZ` (UTC), or a string of digits meaning seconds since
  1970-01-01T00:00:00Z. Anything else does not parse.
* A value that does not parse never matches.

A context value matches a **positive** operator when it matches at least one of the condition
values. The **negated** operators `StringNotEquals`, `StringNotEqualsIgnoreCase`,
`StringNotLike`, `NumericNotEquals` and `NotIpAddress` hold for a context value when it matches
**none** of the condition values under the corresponding positive operator.

### Keys that are absent or multi-valued

A key is *absent* when it is not in the request context or its value is an empty list.

Without a set prefix:

* absent key: positive operators do not hold; negated operators hold;
* otherwise the block key holds when at least one of the context values satisfies the operator
  (a single string is a one-element list).

`...IfExists` (for example `StringEqualsIfExists`, `NotIpAddressIfExists`): exactly like the
operator without the suffix, except that an absent key holds.

Set prefixes, written before the operator (`ForAnyValue:StringLike`, `ForAllValues:StringEquals`):

* `ForAnyValue:` holds when at least one context value satisfies the operator; never holds for an
  absent key.
* `ForAllValues:` holds when every context value satisfies the operator; **always holds for an
  absent key**.
* `IfExists` has no effect when combined with a set prefix.

`Null`: the value is `true` or `false`. `Null: {k: true}` holds when `k` is absent; `Null: {k:
false}` holds when `k` is present. With several values it holds if any of them does. Prefixes and
`IfExists` have no effect on `Null`.

An operator not named in this section never holds (so a statement that uses one never applies).

## 6. Resource policies and principals

A resource listed in `resources` may have a `policy`. Its statements additionally need a
`Principal` that matches the requesting principal; a statement without `Principal` never applies.

* `"Principal": "*"` matches everyone.
* `"Principal": {"Stratus": <string or list>}` matches when any listed value is `"*"`, the exact
  principal srn, the principal's account id, or `srn:stratus:iam::<principal account>:root`.

## 7. Policies that apply to a request

* **Identity policies** of the principal: its `inline` documents and the managed documents named
  in its `policies`, plus, for a user, the inline and managed documents of every group in its
  `groups`. Roles have no groups.
* **Boundary**: the principal's `boundary` managed document, if set.
* **Organization levels**: `org_policies`.
* **Resource policy**: the `policy` of the requested resource, when the resource srn is a key of
  `resources` (exact string match) and the policy is not null.

## 8. Decision

Evaluate in this order:

1. **Explicit deny.** If any `Deny` statement applies in any identity policy, the boundary, any
   organization level, or the resource policy, the decision is `explicit_deny`.
2. **Organization.** For every organization level, at least one `Allow` statement in that level
   must apply. If some level has none, the decision is `implicit_deny`.
3. **Allow.** Let
   * *identity_allow*: some `Allow` statement applies in the identity policies;
   * *resource_allow*: some `Allow` statement applies in the resource policy;
   * *boundary_ok*: the principal has no boundary, or some `Allow` statement in the boundary applies.

   If the resource's account equals the principal's account, the decision is `allow` when
   *boundary_ok* and (*identity_allow* or *resource_allow*). Otherwise (cross-account) it is
   `allow` when *boundary_ok* and *identity_allow* and *resource_allow*.
4. Anything else is `implicit_deny`.
