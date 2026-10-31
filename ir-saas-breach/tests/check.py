#!/usr/bin/env python3
"""IR-2026-114 verifier: scores /workspace/output/findings.json field by field (equal weights)."""
import argparse
import json
import os
import pwd
import signal
from datetime import datetime, timezone

TIMES = ("recon_start_utc", "initial_access_utc")
SETS = ("spray_source_ips", "exfiltrated_objects")
INTS = ("sprayed_account_count", "exfil_total_bytes")
STRINGS = ("enumeration_endpoint", "compromised_user", "persistence_api_key_id", "persistence_iam_user", "exfil_ip")


def kill_agent_processes():
    """Stop anything the agent user left running so it cannot touch the verifier's output."""
    if os.geteuid() != 0:
        return
    try:
        uid = str(pwd.getpwnam("agent").pw_uid)
    except KeyError:
        return
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/status") as fh:
                uids = next(l for l in fh if l.startswith("Uid:")).split()[1:]
            if uid in uids:
                os.kill(int(pid), signal.SIGKILL)
        except (OSError, StopIteration):
            pass


def as_time(v):
    if not isinstance(v, str):
        return None
    try:
        t = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(timezone.utc) if t.tzinfo else None  # a time without a zone is ambiguous


def as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def field_ok(name, got, want):
    if name in TIMES:
        return as_time(got) is not None and as_time(got) == as_time(want)
    if name in SETS:
        return isinstance(got, list) and all(isinstance(x, str) for x in got) and \
            {x.strip() for x in got} == set(want)
    if name in INTS:
        return as_int(got) == want
    return isinstance(got, str) and got.strip() == want


def write_reward(out, score):
    with open(os.path.join(out, "reward.json"), "w") as fh:
        json.dump({"reward": score}, fh)
    with open(os.path.join(out, "reward.txt"), "w") as fh:
        fh.write(str(score))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--expected", default="/tests/expected.json")
    ap.add_argument("--out", default="/logs/verifier")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    kill_agent_processes()

    with open(args.expected) as fh:
        expected = json.load(fh)
    path = os.path.join(args.workspace, "output", "findings.json")
    try:
        with open(path) as fh:
            actual = json.load(fh)
        if not isinstance(actual, dict):
            raise ValueError("findings.json is not a JSON object")
    except (OSError, ValueError) as e:
        print(f"no usable findings at {path}: {e}")
        write_reward(args.out, 0.0)
        return

    fields = TIMES + SETS + INTS + STRINGS
    passed = 0
    for name in fields:
        ok = field_ok(name, actual.get(name), expected[name])
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    score = round(passed / len(fields), 4)
    write_reward(args.out, score)
    print(f"Score: {score} ({passed}/{len(fields)})")


if __name__ == "__main__":
    main()
