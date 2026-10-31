#!/usr/bin/env python3
"""Reference investigation: derives every finding from the evidence (no hard-coded answers)."""
import gzip
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

EV = "/workspace/evidence"
OUT = "/workspace/output/findings.json"
LINE = re.compile(r'^\S+ - - \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "[^"]*" xff="([^"]*)"')


def utc(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jsonl(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def web_requests():
    for name in ("access.log.2.gz", "access.log.1", "access.log"):
        path = os.path.join(EV, "web", name)
        with (gzip.open(path, "rt") if name.endswith(".gz") else open(path)) as fh:
            for line in fh:
                m = LINE.match(line)
                if m:
                    t = datetime.strptime(m[1], "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
                    client = m[5].split(",")[-1].strip()  # the load balancer appends the real peer last
                    yield t, m[2], m[3], client


def main():
    auth = jsonl(os.path.join(EV, "app", "auth-events.jsonl"))
    audit = jsonl(os.path.join(EV, "cloud", "audit.jsonl"))

    # Password spraying: one source failing against many different existing accounts.
    failed = defaultdict(set)
    for e in auth:
        if e["event"] == "login_failure" and e.get("reason") == "bad_password":
            failed[e["src_ip"]].add(e["user"])
    spray_ips = {ip for ip, users in failed.items() if len(users) >= 10}
    sprayed = {e["user"] for e in auth if e["event"] in ("login_failure", "login_success") and e["src_ip"] in spray_ips}

    first = min((e for e in auth if e["event"] == "login_success" and e["src_ip"] in spray_ips), key=lambda e: e["ts"])
    victim, initial = first["user"], utc(first["ts"])

    keys = [e["key_id"] for e in auth
            if e["event"] == "api_key_created" and e["user"] == victim and utc(e["ts"]) >= initial]
    created = [e["requestParameters"]["userName"] for e in audit
               if e["eventName"] == "CreateUser" and e["userIdentity"].get("userName") == victim
               and utc(e["eventTime"]) >= initial]
    backdoor = created[0]

    exfil_ips = {e["sourceIPAddress"] for e in audit if e["userIdentity"].get("userName") == backdoor} - spray_ips
    gets = [e for e in audit if e["eventName"] == "GetObject" and e["userIdentity"].get("userName") == backdoor
            and not e["errorCode"]]

    attacker = spray_ips | exfil_ips
    reqs = [r for r in web_requests() if r[3] in attacker]
    recon_start = min(r[0] for r in reqs)
    probes = Counter(r[2].split("?")[0] for r in reqs if r[0] < initial and r[1] == "GET")

    findings = {
        "recon_start_utc": iso(recon_start),
        "enumeration_endpoint": probes.most_common(1)[0][0],
        "spray_source_ips": sorted(spray_ips),
        "sprayed_account_count": len(sprayed),
        "compromised_user": victim,
        "initial_access_utc": iso(initial),
        "persistence_api_key_id": keys[0],
        "persistence_iam_user": backdoor,
        "exfil_ip": sorted(exfil_ips)[0],
        "exfiltrated_objects": sorted({e["requestParameters"]["key"] for e in gets}),
        "exfil_total_bytes": sum(e["responseElements"]["bytesTransferred"] for e in gets),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(findings, fh, indent=1)
    print(json.dumps(findings, indent=1))


if __name__ == "__main__":
    main()
