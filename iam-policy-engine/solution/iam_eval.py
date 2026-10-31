#!/usr/bin/env python3
"""Reference Stratus IAM evaluator (spec: /workspace/iam/SPEC.md).

usage: iam-eval SNAPSHOT.json QUERIES.jsonl  ->  one {"id", "decision"} JSON object per line
"""
import ipaddress
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

VAR = re.compile(r"\$\{([^}]*)\}")
NUM = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NEGATED = {"StringNotEquals": "StringEquals", "StringNotEqualsIgnoreCase": "StringEqualsIgnoreCase",
           "StringNotLike": "StringLike", "NumericNotEquals": "NumericEquals", "NotIpAddress": "IpAddress"}


def as_list(x):
    return x if isinstance(x, list) else [x]


def scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    return v


def wild(s):
    return "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in s)


def pattern(pat, ctx):
    """Regex source for a wildcard pattern with ${var} substitution; None if a variable is unresolvable."""
    out, pos = [], 0
    for m in VAR.finditer(pat):
        out.append(wild(pat[pos:m.start()]))
        key = m.group(1)
        if key in ("*", "?", "$"):
            out.append(re.escape(key))
        else:
            v = ctx.get(key.lower())
            if not isinstance(v, str):
                return None
            out.append(re.escape(v))
        pos = m.end()
    out.append(wild(pat[pos:]))
    return "".join(out)


def substitute(s, ctx):
    out, pos = [], 0
    for m in VAR.finditer(s):
        out.append(s[pos:m.start()])
        key = m.group(1)
        v = key if key in ("*", "?", "$") else ctx.get(key.lower())
        if not isinstance(v, str):
            return None
        out.append(v)
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)


def like(pat, value, ctx):
    src = pattern(pat, ctx)
    return src is not None and re.fullmatch(src, value, re.S) is not None


def action_match(pat, action):
    return re.fullmatch(wild(pat), action, re.S | re.I) is not None


def number(s):
    if not isinstance(s, str) or not NUM.match(s):
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def date(s):
    if not isinstance(s, str):
        return None
    if DATE.match(s):
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return None
    if re.fullmatch(r"[0-9]+", s):
        return int(s)
    return None


def compare(base, v, cv, ctx):
    if base.startswith("String"):
        if base == "StringLike":
            return like(cv, v, ctx)
        s = substitute(cv, ctx)
        if s is None:
            return False
        return v.lower() == s.lower() if base == "StringEqualsIgnoreCase" else v == s
    if base.startswith("Numeric"):
        a, b = number(v), number(cv)
        if a is None or b is None:
            return False
        return {"NumericEquals": a == b, "NumericLessThan": a < b, "NumericLessThanEquals": a <= b,
                "NumericGreaterThan": a > b, "NumericGreaterThanEquals": a >= b}[base]
    if base.startswith("Date"):
        a, b = date(v), date(cv)
        if a is None or b is None:
            return False
        return {"DateEquals": a == b, "DateLessThan": a < b, "DateLessThanEquals": a <= b,
                "DateGreaterThan": a > b, "DateGreaterThanEquals": a >= b}[base]
    if base == "Bool":
        return v.lower() == cv.lower()
    if base == "IpAddress":
        try:
            return ipaddress.IPv4Address(v) in ipaddress.IPv4Network(cv, strict=False)
        except ValueError:
            return False
    raise KeyError(base)


KNOWN = {"StringEquals", "StringEqualsIgnoreCase", "StringLike", "NumericEquals", "NumericLessThan",
         "NumericLessThanEquals", "NumericGreaterThan", "NumericGreaterThanEquals", "DateEquals",
         "DateLessThan", "DateLessThanEquals", "DateGreaterThan", "DateGreaterThanEquals", "Bool",
         "IpAddress", "Null"} | set(NEGATED)


def single(op, v, cvals, ctx):
    base = NEGATED.get(op, op)
    hit = isinstance(v, str) and any(compare(base, v, cv, ctx) for cv in cvals)
    return not hit if op in NEGATED else hit


def cond_holds(opfull, key, cvals, ctx):
    prefix, op = None, opfull
    for p in ("ForAnyValue:", "ForAllValues:"):
        if op.startswith(p):
            prefix, op = p, op[len(p):]
    ifexists = op.endswith("IfExists")
    if ifexists:
        op = op[:-len("IfExists")]
    if op not in KNOWN:
        return False
    cvals = [scalar(c) for c in as_list(cvals)]
    val = ctx.get(key.lower())
    absent = val is None or val == []
    if op == "Null":
        return any((c.lower() == "true") == absent for c in cvals)
    if prefix == "ForAllValues:":
        return absent or all(single(op, v, cvals, ctx) for v in as_list(val))
    if prefix == "ForAnyValue:":
        return not absent and any(single(op, v, cvals, ctx) for v in as_list(val))
    if absent:
        return ifexists or op in NEGATED
    return any(single(op, v, cvals, ctx) for v in as_list(val))


def principal_match(spec, arn, acct):
    if spec == "*":
        return True
    if not isinstance(spec, dict):
        return False
    return any(v in ("*", arn, acct, f"srn:stratus:iam::{acct}:root") for v in as_list(spec.get("Stratus", [])))


def stmt_matches(st, action, resource, ctx, who=None):
    if "Action" in st:
        if not any(action_match(p, action) for p in as_list(st["Action"])):
            return False
    elif any(action_match(p, action) for p in as_list(st.get("NotAction", []))):
        return False
    if "Resource" in st:
        if not any(like(p, resource, ctx) for p in as_list(st["Resource"])):
            return False
    elif any(like(p, resource, ctx) for p in as_list(st.get("NotResource", []))):
        return False
    if who is not None and not principal_match(st.get("Principal"), *who):
        return False
    return all(cond_holds(op, key, vals, ctx)
               for op, block in (st.get("Condition") or {}).items() for key, vals in block.items())


def statements(doc, effect):
    return [s for s in as_list(doc.get("Statement", [])) if s.get("Effect") == effect]


def evaluate(snap, q):
    arn, action, resource = q["principal"], q["action"], q["resource"]
    parts = arn.split(":")
    acct = parts[4]
    kind, name = parts[5].split("/", 1)
    ent = snap["users" if kind == "user" else "roles"][name]
    managed = snap.get("managed_policies", {})
    res = snap.get("resources", {}).get(resource, {})

    ctx = {k.lower(): v for k, v in (q.get("context") or {}).items()}
    rparts = resource.split(":")
    r_acct = rparts[4] if len(rparts) > 5 and rparts[4] else acct
    derived = {"stratus:PrincipalArn": arn, "stratus:PrincipalAccount": acct,
               "stratus:PrincipalType": "User" if kind == "user" else "Role", "stratus:ResourceAccount": r_acct}
    if kind == "user":
        derived["stratus:username"] = name
    for k, v in (ent.get("tags") or {}).items():
        derived[f"stratus:PrincipalTag/{k}"] = v
    for k, v in (res.get("tags") or {}).items():
        derived[f"stratus:ResourceTag/{k}"] = v
    ctx.update({k.lower(): v for k, v in derived.items()})

    identity = list(ent.get("inline", [])) + [managed[p] for p in ent.get("policies", [])]
    for g in ent.get("groups", []):
        grp = snap["groups"][g]
        identity += list(grp.get("inline", [])) + [managed[p] for p in grp.get("policies", [])]
    boundary = [managed[ent["boundary"]]] if ent.get("boundary") else None
    org = snap.get("org_policies") or []
    rpol = [res["policy"]] if res.get("policy") else []
    who = (arn, acct)

    def hit(docs, effect, principal=None):
        return any(stmt_matches(s, action, resource, ctx, principal) for d in docs for s in statements(d, effect))

    if (hit(identity, "Deny") or hit(boundary or [], "Deny") or any(hit(level, "Deny") for level in org)
            or hit(rpol, "Deny", who)):
        return "explicit_deny"
    if not all(hit(level, "Allow") for level in org):
        return "implicit_deny"
    boundary_ok = boundary is None or hit(boundary, "Allow")
    identity_allow = hit(identity, "Allow")
    resource_allow = hit(rpol, "Allow", who)
    if r_acct == acct:
        allowed = boundary_ok and (identity_allow or resource_allow)
    else:
        allowed = boundary_ok and identity_allow and resource_allow
    return "allow" if allowed else "implicit_deny"


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: iam-eval SNAPSHOT.json QUERIES.jsonl")
    with open(sys.argv[1], encoding="utf-8") as fh:
        snap = json.load(fh)
    out = []
    with open(sys.argv[2], encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                q = json.loads(line)
                out.append(json.dumps({"id": q["id"], "decision": evaluate(snap, q)}))
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
