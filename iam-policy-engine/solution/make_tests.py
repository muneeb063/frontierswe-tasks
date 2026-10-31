#!/usr/bin/env python3
"""Builds the hidden IAM test data (tests/data, tests/expected.json) and the public example.

Not used by the oracle; kept so the test set can be audited and regenerated:
    python3 solution/make_tests.py <task-dir>
Decisions come from solution/iam_eval.py, the reference implementation of SPEC.md.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iam_eval import evaluate  # noqa: E402

ACCT = "111122223333"
PARTNER = "444455556666"
CLASSES = ("allow", "explicit_deny", "implicit_deny")


def doc(*stmts):
    return {"Version": "2024-01-01", "Statement": list(stmts)}


def st(effect, action=None, resource=None, not_action=None, not_resource=None, condition=None, principal=None):
    s = {"Effect": effect}
    s["Action" if action is not None else "NotAction"] = action if action is not None else not_action
    s["Resource" if resource is not None else "NotResource"] = resource if resource is not None else not_resource
    if condition:
        s["Condition"] = condition
    if principal is not None:
        s["Principal"] = principal
    return s


def pol(name, acct=ACCT):
    return f"srn:stratus:iam::{acct}:policy/{name}"


def user(name, acct=ACCT):
    return f"srn:stratus:iam::{acct}:user/{name}"


def role(name, acct=ACCT):
    return f"srn:stratus:iam::{acct}:role/{name}"


S3 = "srn:stratus:storage:::"
EC2 = f"srn:stratus:compute:eu-west-1:{ACCT}:instance/"
DB = f"srn:stratus:db:eu-west-1:{ACCT}:table/"
KMS = f"srn:stratus:kms:eu-west-1:{ACCT}:key/"
LOGS = f"srn:stratus:logs:eu-west-1:{ACCT}:log-group/"


# ------------------------------------------------------------------ realistic hidden account

def acme_prod():
    managed = {
        pol("AdminAccess"): doc(st("Allow", "*", "*")),
        pol("ReadOnly"): doc(st("Allow", ["storage:Get*", "storage:List*", "compute:Describe*", "db:Query", "db:Scan",
                                          "logs:Get*", "iam:Get*", "iam:List*"], "*")),
        pol("DevBoundary"): doc(
            st("Allow", ["storage:*", "compute:*", "db:*", "logs:*", "kms:Decrypt", "kms:GenerateDataKey"], "*"),
            st("Allow", ["iam:GetUser", "iam:CreateAccessKey"], user("${stratus:username}"))),
        pol("HomeFolder"): doc(
            st("Allow", ["storage:GetObject", "storage:PutObject", "storage:DeleteObject"],
               S3 + "home/${stratus:username}/*"),
            st("Allow", "storage:ListBucket", S3 + "home",
               condition={"StringLike": {"stratus:prefix": ["${stratus:username}/*", "${stratus:username}"]}})),
        pol("TeamABAC"): doc(
            st("Allow", ["compute:StartInstance", "compute:StopInstance", "compute:CreateSnapshot"], EC2 + "*",
               condition={"StringEquals": {"stratus:ResourceTag/team": "${stratus:PrincipalTag/team}"}}),
            st("Allow", "compute:DescribeInstances", "*")),
        pol("RequireMFA"): doc(st("Deny", ["compute:TerminateInstance", "storage:DeleteObject", "db:DeleteTable",
                                           "logs:DeleteLogGroup", "iam:DeleteUser"], "*",
                                  condition={"BoolIfExists": {"stratus:MultiFactorAuthPresent": False}})),
        pol("OfficeOnly"): doc(st("Deny", "*", "*",
                                  condition={"NotIpAddress": {"stratus:SourceIp": ["203.0.113.0/24", "198.51.100.7"]}})),
        pol("DataAnalyst"): doc(
            st("Allow", ["db:Query", "db:Scan"], DB + "analytics_*"),
            st("Allow", "kms:Decrypt", KMS + "*",
               condition={"ForAllValues:StringEquals": {"stratus:EncryptionContextKeys": ["dataset", "purpose"]}})),
        pol("Contractor"): doc(st("Allow", ["storage:GetObject", "storage:ListBucket"], [S3 + "vendor-drop", S3 + "vendor-drop/*"],
                                  condition={"DateGreaterThanEquals": {"stratus:CurrentTime": "2026-06-01T00:00:00Z"},
                                             "DateLessThan": {"stratus:CurrentTime": "2026-12-31T23:59:59Z"}})),
        pol("CIDeploy"): doc(
            st("Allow", "storage:PutObject", S3 + "artifacts/*"),
            st("Allow", "compute:*", f"srn:stratus:compute:*:{ACCT}:instance/*",
               condition={"StringEquals": {"stratus:RequestTag/env": "staging"}}),
            st("Allow", "iam:PassRole", role("app-*"),
               condition={"StringEquals": {"stratus:PassedToService": "compute"},
                          "NumericLessThanEquals": {"stratus:TokenAgeSeconds": 3600}})),
    }
    groups = {
        "developers": {"policies": [pol("ReadOnly"), pol("HomeFolder"), pol("TeamABAC")],
                       "inline": [doc(st("Allow", "logs:PutLogEvents", f"srn:stratus:logs:*:{ACCT}:log-group/dev-*"))]},
        "admins": {"policies": [pol("AdminAccess"), pol("RequireMFA")]},
        "analysts": {"policies": [pol("DataAnalyst"), pol("HomeFolder")]},
        "contractors": {"policies": [pol("Contractor"), pol("OfficeOnly")]},
    }
    users = {
        "alice": {"groups": ["admins"], "tags": {"role": "security", "team": "platform"}},
        "bob": {"groups": ["developers"], "boundary": pol("DevBoundary"), "tags": {"team": "payments"}},
        "carol": {"groups": ["developers", "analysts"], "boundary": pol("DevBoundary"), "tags": {"team": "data"},
                  "inline": [doc(st("Deny", "storage:*", S3 + "finance-ledger/*"))]},
        "dave": {"groups": ["contractors"]},
        "erin": {"groups": ["analysts"], "tags": {"team": "ml*"},
                 "inline": [doc(st("Allow", "db:PutItem", DB + "${stratus:PrincipalTag/team}_*"))]},
        "frank": {},
        "gus": {"groups": ["admins"], "boundary": pol("ReadOnly"), "tags": {"team": "payments"}},
    }
    roles = {
        "ci-deployer": {"policies": [pol("CIDeploy")], "tags": {"team": "platform"}},
        "app-backend": {"inline": [doc(
            st("Allow", ["db:Query", "db:PutItem"], DB + "orders"),
            st("Allow", "storage:GetObject", S3 + "assets/*"),
            st("Allow", "kms:Decrypt", f"srn:stratus:kms:*:{PARTNER}:key/*"),
            st("Allow", ["db:Query", "db:Scan"], f"srn:stratus:db:*:{PARTNER}:table/*"))]},
    }
    resources = {
        S3 + "finance-ledger/2026/ledger.csv": {
            "policy": doc(st("Allow", "storage:GetObject", "*", principal={"Stratus": user("frank")})),
            "tags": {"classification": "restricted"}},
        S3 + "reports/q3.pdf": {"policy": doc(
            st("Allow", "storage:GetObject", "*", principal="*",
               condition={"StringEquals": {"stratus:PrincipalAccount": ACCT}}),
            st("Deny", "storage:DeleteObject", "*", principal="*"))},
        EC2 + "i-pay1": {"tags": {"team": "payments"}},
        EC2 + "i-data1": {"tags": {"team": "data"}},
        EC2 + "i-plat1": {"tags": {"team": "platform"}},
        KMS + "main": {"policy": doc(st("Allow", ["kms:Encrypt", "kms:Decrypt"], "*", principal={"Stratus": ACCT},
                                        condition={"StringEquals": {"stratus:ViaService": "storage"}}))},
        f"srn:stratus:db:eu-west-1:{PARTNER}:table/shared_metrics": {"policy": doc(
            st("Allow", ["db:Query", "db:Scan"], "*", principal={"Stratus": f"srn:stratus:iam::{ACCT}:root"}))},
        f"srn:stratus:kms:eu-west-1:{PARTNER}:key/partner": {"policy": doc(
            st("Allow", "kms:Decrypt", "*", principal={"Stratus": [role("app-backend")]}))},
    }
    org = [
        [doc(st("Allow", "*", "*")),
         doc(st("Deny", not_action=["iam:*", "billing:*"], resource="*",
                condition={"StringNotEqualsIfExists": {"stratus:RequestedRegion": ["eu-west-1", "eu-central-1"]}})),
         doc(st("Deny", "kms:ScheduleKeyDeletion", "*",
                condition={"StringNotEquals": {"stratus:PrincipalTag/role": "security"}}))],
        [doc(st("Allow", ["storage:*", "compute:*", "iam:*", "kms:*", "db:*", "logs:*"], "*"))],
    ]
    snap = {"account_id": ACCT, "managed_policies": managed, "groups": groups, "users": users, "roles": roles,
            "resources": resources, "org_policies": org}
    pairs = [
        ("storage:GetObject", S3 + "home/bob/notes.txt"), ("storage:PutObject", S3 + "home/carol/x.csv"),
        ("storage:DeleteObject", S3 + "home/bob/old.txt"), ("storage:ListBucket", S3 + "home"),
        ("storage:GetObject", S3 + "finance-ledger/2026/ledger.csv"), ("storage:GetObject", S3 + "reports/q3.pdf"),
        ("storage:DeleteObject", S3 + "reports/q3.pdf"), ("storage:GetObject", S3 + "vendor-drop/spec.pdf"),
        ("storage:ListBucket", S3 + "vendor-drop"), ("storage:PutObject", S3 + "artifacts/build-77.tar"),
        ("storage:GetObject", S3 + "assets/logo.png"), ("STORAGE:getobject", S3 + "home/erin/a"),
        ("compute:StartInstance", EC2 + "i-pay1"), ("compute:StopInstance", EC2 + "i-data1"),
        ("compute:CreateSnapshot", EC2 + "i-plat1"), ("compute:StartInstance", EC2 + "i-untagged"),
        ("compute:TerminateInstance", EC2 + "i-pay1"), ("compute:DescribeInstances", "*"),
        ("db:Query", DB + "analytics_events"), ("db:Scan", DB + "orders"), ("db:PutItem", DB + "orders"),
        ("db:PutItem", DB + "ml*_features"), ("db:PutItem", DB + "mlops_features"), ("db:DeleteTable", DB + "orders"),
        ("db:Query", f"srn:stratus:db:eu-west-1:{PARTNER}:table/shared_metrics"),
        ("db:Scan", f"srn:stratus:db:eu-west-1:{PARTNER}:table/private"),
        ("kms:Decrypt", KMS + "main"), ("kms:Encrypt", KMS + "main"), ("kms:ScheduleKeyDeletion", KMS + "main"),
        ("kms:Decrypt", f"srn:stratus:kms:eu-west-1:{PARTNER}:key/partner"),
        ("kms:GenerateDataKey", KMS + "main"),
        ("iam:CreateAccessKey", user("bob")), ("iam:CreateAccessKey", user("alice")), ("iam:GetUser", user("carol")),
        ("iam:DeleteUser", user("dave")), ("iam:PassRole", role("app-backend")), ("iam:PassRole", role("admin")),
        ("logs:PutLogEvents", LOGS + "dev-payments"), ("logs:PutLogEvents", LOGS + "prod-payments"),
        ("logs:DeleteLogGroup", LOGS + "dev-old"), ("billing:ViewInvoice", "*"),
    ]
    principals = [user(u) for u in users] + [role(r) for r in roles]
    return snap, principals, pairs


def realistic_context(rng, principal):
    name = principal.rsplit("/", 1)[1]
    choices = {
        "stratus:RequestedRegion": ["eu-west-1", "eu-west-1", "eu-central-1", "us-east-1", None],
        "stratus:SourceIp": ["203.0.113.10", "198.51.100.7", "198.51.100.8", "10.0.0.5", None],
        "stratus:MultiFactorAuthPresent": ["true", "false", "TRUE", None],
        "stratus:CurrentTime": ["2026-10-29T12:00:00Z", "2027-01-01T00:00:00Z", "2026-05-31T23:59:59Z",
                                "1782864000", "yesterday", None],
        "stratus:TokenAgeSeconds": ["1200", "3600", "3600.5", "abc", None],
        "stratus:ViaService": ["storage", "compute", None],
        "stratus:PassedToService": ["compute", "db", None],
        "stratus:EncryptionContextKeys": [["dataset"], ["dataset", "purpose"], ["dataset", "owner"], [], None],
        "stratus:prefix": [f"{name}/docs", name, "someone/docs", None],
        "stratus:RequestTag/env": ["staging", "prod", None],
        "stratus:PrincipalTag/team": ["payments", None, None, None],  # spoofing attempts; derived keys win
        "stratus:username": ["alice", None, None, None],
    }
    ctx = {}
    for k, vals in choices.items():
        v = rng.choice(vals)
        if v is not None:
            ctx[k] = v
    return ctx


# ------------------------------------------------------------------ random accounts

SERVICES = {
    "storage": ["GetObject", "PutObject", "DeleteObject", "ListBucket", "GetObjectTagging", "PutBucketPolicy"],
    "compute": ["StartInstance", "StopInstance", "TerminateInstance", "DescribeInstances", "CreateSnapshot"],
    "iam": ["CreateUser", "DeleteUser", "PassRole", "CreateAccessKey", "GetUser", "ListUsers"],
    "kms": ["Decrypt", "Encrypt", "GenerateDataKey", "ScheduleKeyDeletion"],
    "db": ["Query", "Scan", "PutItem", "DeleteTable"],
}
ACTIONS = [f"{s}:{a}" for s, acts in SERVICES.items() for a in acts]
NAMES = ["ana", "ben", "cy", "dee", "eli", "fay", "gil"]
TEAMS = ["red", "blue", "green", "x*y"]


def resource_universe():
    out = []
    for n in NAMES[:4] + ["shared"]:
        out += [S3 + f"home/{n}/a.txt", S3 + f"home/{n}/deep/b.txt"]
    out += [S3 + "public/index.html", S3 + "secret/keys.txt", S3 + "home", S3 + "home/x*y/q"]
    for t in TEAMS:
        out += [EC2 + f"i-{t}", DB + f"{t}_table"]
    out += [KMS + "k1", KMS + "k2", f"srn:stratus:db:eu-west-1:{PARTNER}:table/t1",
            f"srn:stratus:storage:eu-west-1:{PARTNER}:bucket/b1", user("ana"), user("ben"), role("svc-a"), role("svc-b")]
    return out


def rand_action_pattern(rng):
    s = rng.choice(list(SERVICES))
    a = rng.choice(SERVICES[s])
    return rng.choice([f"{s}:{a}", f"{s}:{a}", f"{s}:*", f"{s}:{a[:3]}*", "*", f"{s}:?{a[1:]}",
                       f"{s.upper()}:{a.lower()}", f"*:{a}"])


def rand_resource_pattern(rng, universe):
    r = rng.choice(universe)
    return rng.choice([r, r, r[: max(1, len(r) - rng.randint(1, 8))] + "*", "*", S3 + "home/${stratus:username}/*",
                       EC2 + "i-${stratus:PrincipalTag/team}", DB + "${stratus:PrincipalTag/team}_*",
                       r.replace("a", "?", 1), S3 + "home/*/a.txt", f"srn:stratus:*:*:{PARTNER}:*",
                       user("${stratus:username}"), S3 + "home/${stratus:username}${*}"])


def rand_condition(rng):
    pool = [
        ("StringEquals", "stratus:RequestedRegion", ["eu-west-1"]),
        ("StringNotEquals", "stratus:RequestedRegion", ["eu-west-1", "eu-central-1"]),
        ("StringNotEqualsIfExists", "stratus:RequestedRegion", ["eu-west-1"]),
        ("StringEqualsIgnoreCase", "stratus:Department", ["ENGINEERING"]),
        ("StringNotEqualsIgnoreCase", "stratus:Department", ["finance"]),
        ("StringLike", "stratus:UserAgent", ["cli/*", "sdk-?/*"]),
        ("StringNotLike", "stratus:UserAgent", ["*bot*"]),
        ("StringEquals", "stratus:ResourceTag/team", ["${stratus:PrincipalTag/team}"]),
        ("StringEquals", "stratus:Department", ["${stratus:PrincipalTag/dept}"]),
        ("StringLike", "stratus:prefix", ["${stratus:username}/*"]),
        ("StringEqualsIfExists", "stratus:ResourceTag/env", ["dev"]),
        ("NumericLessThan", "stratus:TokenAge", [3600]),
        ("NumericGreaterThanEquals", "stratus:TokenAge", ["100.5"]),
        ("NumericNotEquals", "stratus:TokenAge", [0]),
        ("NumericLessThanEqualsIfExists", "stratus:TokenAge", [600]),
        ("DateLessThan", "stratus:CurrentTime", ["2026-11-01T00:00:00Z"]),
        ("DateGreaterThan", "stratus:CurrentTime", ["1767225600"]),
        ("Bool", "stratus:MultiFactorAuthPresent", [True]),
        ("BoolIfExists", "stratus:MultiFactorAuthPresent", ["false"]),
        ("IpAddress", "stratus:SourceIp", ["10.0.0.0/8", "192.0.2.1"]),
        ("NotIpAddress", "stratus:SourceIp", ["10.0.0.0/8"]),
        ("NotIpAddressIfExists", "stratus:SourceIp", ["172.16.0.0/12"]),
        ("Null", "stratus:SourceIp", [True]),
        ("Null", "stratus:Department", ["false"]),
        ("ForAnyValue:StringEquals", "stratus:Tags", ["pii", "hipaa"]),
        ("ForAllValues:StringLike", "stratus:Tags", ["public*", "internal"]),
        ("ForAllValues:StringEquals", "stratus:Tags", ["internal"]),
        ("ForAnyValue:StringNotEquals", "stratus:Tags", ["internal"]),
        ("StringEquals", "stratus:Tags", ["pii"]),
        ("StringEqualsAnyCase", "stratus:Department", ["x"]),  # unknown operator: never holds
        ("StringEquals", "stratus:PrincipalType", ["Role"]),
        ("StringEquals", "STRATUS:principalaccount", [ACCT]),
    ]
    cond = {}
    for _ in range(rng.choice([1, 1, 1, 2])):
        op, key, vals = rng.choice(pool)
        cond.setdefault(op, {})[key] = vals if len(vals) > 1 or rng.random() < 0.5 else vals[0]
    return cond


def rand_statement(rng, universe, effect=None, principal=False):
    effect = effect or ("Deny" if rng.random() < 0.25 else "Allow")
    acts = [rand_action_pattern(rng) for _ in range(rng.randint(1, 3))]
    ress = [rand_resource_pattern(rng, universe) for _ in range(rng.randint(1, 2))]
    s = {"Effect": effect}
    s["NotAction" if rng.random() < 0.12 else "Action"] = acts if len(acts) > 1 else acts[0]
    s["NotResource" if rng.random() < 0.1 else "Resource"] = ress if len(ress) > 1 else ress[0]
    if rng.random() < 0.45:
        s["Condition"] = rand_condition(rng)
    if principal:
        s["Principal"] = rng.choice(["*", {"Stratus": ACCT}, {"Stratus": f"srn:stratus:iam::{ACCT}:root"},
                                     {"Stratus": user(rng.choice(NAMES))}, {"Stratus": [role("svc-a"), user("ana")]},
                                     {"Stratus": "*"}, {"Stratus": user("ana", PARTNER)}])
        if rng.random() < 0.05:
            del s["Principal"]
    return s


def rand_doc(rng, universe, n=None, **kw):
    stmts = [rand_statement(rng, universe, **kw) for _ in range(n or rng.randint(1, 3))]
    return {"Version": "2024-01-01", "Statement": stmts if len(stmts) > 1 or rng.random() < 0.5 else stmts[0]}


def random_account(seed):
    rng = random.Random(seed)
    universe = resource_universe()
    managed = {pol(f"P{i}"): rand_doc(rng, universe) for i in range(8)}
    managed[pol("Wide")] = doc(st("Allow", "*", "*"))
    groups = {f"g{i}": {"policies": rng.sample(list(managed), rng.randint(0, 2)),
                        "inline": [rand_doc(rng, universe) for _ in range(rng.randint(0, 1))]} for i in range(3)}
    users = {}
    for n in NAMES:
        users[n] = {"groups": rng.sample(list(groups), rng.randint(0, 2)),
                    "policies": rng.sample(list(managed), rng.randint(0, 2)),
                    "inline": [rand_doc(rng, universe) for _ in range(rng.randint(0, 2))],
                    "boundary": rng.choice([None, None, None, pol("Wide")] + list(managed)),
                    "tags": {k: rng.choice(TEAMS if k == "team" else ["eng", "ENGINEERING", "finance"])
                             for k in rng.sample(["team", "dept"], rng.randint(0, 2))}}
    roles = {r: {"policies": rng.sample(list(managed), rng.randint(0, 2)),
                 "inline": [rand_doc(rng, universe) for _ in range(rng.randint(0, 2))],
                 "boundary": rng.choice([None, None] + list(managed)),
                 "tags": {"team": rng.choice(TEAMS)} if rng.random() < 0.6 else {}} for r in ["svc-a", "svc-b"]}
    resources = {}
    for r in rng.sample(universe, 12):
        resources[r] = {"policy": rand_doc(rng, universe, principal=True) if rng.random() < 0.7 else None,
                        "tags": {"team": rng.choice(TEAMS)} if rng.random() < 0.5 else {}}
    org = []
    if seed % 2 == 0:
        org = [[doc(st("Allow", "*", "*")), rand_doc(rng, universe, n=1, effect="Deny")],
               [doc(st("Allow", ["storage:*", "compute:*", "db:*", "iam:*"], "*"))]]
    snap = {"account_id": ACCT, "managed_policies": managed, "groups": groups, "users": users, "roles": roles,
            "resources": resources, "org_policies": org}
    principals = [user(n) for n in NAMES] + [role("svc-a"), role("svc-b")]
    pairs = [(a, r) for a in ACTIONS for r in universe]
    return snap, principals, pairs


def random_context(rng, principal):
    choices = {
        "stratus:RequestedRegion": ["eu-west-1", "eu-central-1", "us-east-1", None],
        "stratus:Department": ["engineering", "Engineering", "finance", "eng", None],
        "stratus:UserAgent": ["cli/2.1", "sdk-j/1.0", "sdk-js/1.0", "crawler-bot/1", None],
        "stratus:prefix": [principal.rsplit("/", 1)[1] + "/x", "other/x", None],
        "stratus:TokenAge": ["50", "100.5", "599", "3600", "0", "1e3", None],
        "stratus:CurrentTime": ["2026-10-29T12:00:00Z", "2026-11-01T00:00:00Z", "1767225601", "2025-01-01T00:00:00Z", None],
        "stratus:MultiFactorAuthPresent": ["true", "false", "True", None],
        "stratus:SourceIp": ["10.1.2.3", "192.0.2.1", "192.0.2.2", "172.16.5.5", "not-an-ip", None],
        "stratus:Tags": [["pii"], ["internal"], ["public-read", "internal"], ["pii", "internal"], [], None],
        "stratus:PrincipalTag/team": ["red", None, None],
    }
    return {k: v for k, vals in choices.items() if (v := rng.choice(vals)) is not None}


# ------------------------------------------------------------------ public example

def example():
    acct, other = "222233334444", "555566667777"
    obj = "srn:stratus:storage:::team-share/plan.txt"
    table = f"srn:stratus:db:eu-west-1:{other}:table/catalog"
    snap = {
        "account_id": acct,
        "managed_policies": {
            pol("Viewer", acct): doc(st("Allow", ["storage:Get*", "storage:List*", "db:Query"], "*")),
            pol("NoDeleteWithoutMfa", acct): doc(st("Deny", "storage:DeleteObject", "*",
                                                    condition={"Bool": {"stratus:MultiFactorAuthPresent": "false"}})),
            pol("StorageOnly", acct): doc(st("Allow", "storage:*", "*")),
        },
        "groups": {"staff": {"policies": [pol("Viewer", acct)],
                             "inline": [doc(st("Allow", ["storage:PutObject", "storage:DeleteObject"],
                                               "srn:stratus:storage:::team-share/*"))]}},
        "users": {
            "pat": {"groups": ["staff"], "policies": [pol("NoDeleteWithoutMfa", acct)], "tags": {"team": "core"}},
            "sam": {"groups": ["staff"], "boundary": pol("StorageOnly", acct)},
            "lee": {},
        },
        "roles": {"batch": {"inline": [doc(st("Allow", "db:*", f"srn:stratus:db:*:{other}:table/*",
                                              condition={"IpAddress": {"stratus:SourceIp": "10.0.0.0/8"}}))]}},
        "resources": {
            obj: {"policy": doc(st("Allow", "storage:GetObject", "*", principal={"Stratus": user("lee", acct)})),
                  "tags": {"team": "core"}},
            table: {"policy": doc(st("Allow", ["db:Query", "db:Scan"], "*", principal={"Stratus": acct}))},
        },
        "org_policies": [[doc(st("Allow", "*", "*"), st("Deny", "billing:*", "*"))]],
    }
    rows = [
        (user("pat", acct), "storage:GetObject", obj, {}),
        (user("pat", acct), "storage:DeleteObject", obj, {"stratus:MultiFactorAuthPresent": "true"}),
        (user("pat", acct), "storage:DeleteObject", obj, {"stratus:MultiFactorAuthPresent": "false"}),
        (user("pat", acct), "storage:DeleteObject", obj, {}),
        (user("pat", acct), "Storage:putobject", obj, {}),
        (user("pat", acct), "storage:PutObject", "srn:stratus:storage:::other/x", {}),
        (user("pat", acct), "billing:ViewInvoice", "*", {}),
        (user("sam", acct), "storage:PutObject", obj, {}),
        (user("sam", acct), "db:Query", f"srn:stratus:db:eu-west-1:{acct}:table/local", {}),
        (user("lee", acct), "storage:GetObject", obj, {}),
        (user("lee", acct), "storage:PutObject", obj, {}),
        (user("pat", acct), "db:Query", table, {}),
        (user("pat", acct), "db:Scan", table, {}),
        (role("batch", acct), "db:Scan", table, {"stratus:SourceIp": "10.20.30.40"}),
        (role("batch", acct), "db:Scan", table, {"stratus:SourceIp": "192.0.2.10"}),
        (role("batch", acct), "db:PutItem", table, {"stratus:SourceIp": "10.20.30.40"}),
    ]
    queries = [{"id": f"ex-{i:02d}", "principal": p, "action": a, "resource": r, "context": c}
               for i, (p, a, r, c) in enumerate(rows)]
    return snap, queries


# ------------------------------------------------------------------ assembly

def sample_queries(snap, principals, pairs, ctx_fn, seed, per_class, prefix):
    rng = random.Random(seed)
    buckets = {c: [] for c in CLASSES}
    seen = set()
    for _ in range(200000):
        if all(len(b) >= per_class for b in buckets.values()):
            break
        p = rng.choice(principals)
        a, r = rng.choice(pairs)
        ctx = ctx_fn(rng, p)
        key = json.dumps([p, a, r, ctx], sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        q = {"principal": p, "action": a, "resource": r, "context": ctx}
        d = evaluate(snap, q)
        if len(buckets[d]) < per_class:
            buckets[d].append(q)
    assert all(len(b) == per_class for b in buckets.values()), {c: len(b) for c, b in buckets.items()}
    qs = [q for b in buckets.values() for q in b]
    rng.shuffle(qs)
    expected = {}
    for i, q in enumerate(qs):
        q["id"] = f"{prefix}-{i:04d}"
        expected[q["id"]] = evaluate(snap, q)
    ordered = [{"id": q["id"], **{k: q[k] for k in ("principal", "action", "resource", "context")}} for q in qs]
    return ordered, expected


def write(path, snap, queries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".json", "w", newline="\n") as fh:
        json.dump(snap, fh, indent=1)
    with open(path + ".jsonl", "w", newline="\n") as fh:
        fh.writelines(json.dumps(q) + "\n" for q in queries)


def main():
    task = sys.argv[1]
    data = os.path.join(task, "tests", "data")
    expected = {}
    snap, principals, pairs = acme_prod()
    qs, exp = sample_queries(snap, principals, pairs, realistic_context, 7, 60, "acme")
    write(os.path.join(data, "acme-prod"), snap, qs)
    expected["acme-prod"] = exp
    for seed in (101, 202, 303, 404):
        snap, principals, pairs = random_account(seed)
        name = f"random-{seed}"
        qs, exp = sample_queries(snap, principals, pairs, random_context, seed, 40, f"r{seed}")
        write(os.path.join(data, name), snap, qs)
        expected[name] = exp
    with open(os.path.join(task, "tests", "expected.json"), "w", newline="\n") as fh:
        json.dump(expected, fh, indent=1, sort_keys=True)
    print({k: len(v) for k, v in expected.items()})

    snap, queries = example()
    ex = os.path.join(task, "environment", "workspace", "iam", "examples", "example")
    write(ex, snap, queries)
    with open(ex + ".expected.jsonl", "w", newline="\n") as fh:
        for q in queries:
            d = evaluate(snap, q)
            fh.write(json.dumps({"id": q["id"], "decision": d}) + "\n")
            print(q["id"], d, q["principal"].rsplit("/", 1)[1], q["action"], q["resource"].split(":")[-1], q["context"])


if __name__ == "__main__":
    main()
