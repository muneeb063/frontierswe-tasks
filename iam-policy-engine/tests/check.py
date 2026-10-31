#!/usr/bin/env python3
"""Stratus IAM verifier.

Runs /workspace/iam/iam-eval on each hidden snapshot and compares its decisions with the ground
truth. The three decisions are balanced in the hidden set; the reward is chance-corrected balanced
accuracy, max(0, (mean per-class recall - 1/3) / (2/3)), so a constant answer scores 0.
"""
import argparse
import json
import os
import pwd
import shutil
import signal
import subprocess
import tempfile

TIMEOUT_SEC = 120
CLASSES = ("allow", "explicit_deny", "implicit_deny")


def agent_ids():
    """When the verifier runs as root, the code under test runs as the unprivileged agent user."""
    if os.geteuid() != 0:
        return None
    try:
        pw = pwd.getpwnam("agent")
    except KeyError:
        return None
    return pw.pw_uid, pw.pw_gid


def kill_user(uid):
    """Stop anything the agent user left running so it cannot touch the verifier's output."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/status") as fh:
                uids = next(l for l in fh if l.startswith("Uid:")).split()[1:]
            if str(uid) in uids:
                os.kill(int(pid), signal.SIGKILL)
        except (OSError, StopIteration):
            pass


def run_dataset(exe, data_dir, name, ids):
    with tempfile.TemporaryDirectory() as tmp:
        snap, queries = os.path.join(tmp, "snapshot.json"), os.path.join(tmp, "queries.jsonl")
        shutil.copyfile(os.path.join(data_dir, name + ".json"), snap)
        shutil.copyfile(os.path.join(data_dir, name + ".jsonl"), queries)
        out_path = os.path.join(tmp, "stdout")
        if ids:
            for p in (tmp, snap, queries):
                os.chown(p, *ids)

        def demote():
            if ids:
                os.setgroups([])
                os.setgid(ids[1])
                os.setuid(ids[0])

        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": tmp, "LANG": "C.UTF-8"}
        with open(out_path, "wb") as out:
            p = subprocess.Popen([exe, snap, queries], cwd=tmp, stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=subprocess.DEVNULL, env=env, preexec_fn=demote, start_new_session=True)
            try:
                p.wait(timeout=TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                print(f"  {name}: timed out after {TIMEOUT_SEC}s")
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            p.wait()
        with open(out_path, "rb") as fh:
            raw = fh.read(16 << 20).decode("utf-8", "replace")
    got = {}
    for line in raw.splitlines():
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and isinstance(obj.get("id"), str):
                got.setdefault(obj["id"], obj.get("decision"))
        except ValueError:
            pass
    return got


def write_reward(out, score):
    with open(os.path.join(out, "reward.json"), "w") as fh:
        json.dump({"reward": score}, fh)
    with open(os.path.join(out, "reward.txt"), "w") as fh:
        fh.write(str(score))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--data", default="/tests/data")
    ap.add_argument("--expected", default="/tests/expected.json")
    ap.add_argument("--out", default="/logs/verifier")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    with open(args.expected) as fh:
        expected = json.load(fh)
    ids = agent_ids()
    if ids:
        kill_user(ids[0])
    exe = os.path.join(args.workspace, "iam", "iam-eval")
    if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
        print(f"no executable evaluator at {exe}")
        write_reward(args.out, 0.0)
        return

    total = {c: 0 for c in CLASSES}
    right = {c: 0 for c in CLASSES}
    for name in sorted(expected):
        got = run_dataset(exe, args.data, name, ids)
        ok = 0
        for qid, want in expected[name].items():
            total[want] += 1
            if got.get(qid) == want:
                right[want] += 1
                ok += 1
        print(f"[{name}] {ok}/{len(expected[name])} decisions correct")
    if ids:
        kill_user(ids[0])
    recall = {c: right[c] / total[c] for c in CLASSES}
    balanced = sum(recall.values()) / len(CLASSES)
    score = round(max(0.0, (balanced - 1 / 3) / (2 / 3)), 4)
    print("per-class recall: " + ", ".join(f"{c}={recall[c]:.3f}" for c in CLASSES))
    write_reward(args.out, score)
    print(f"Score: {score} (balanced accuracy {balanced:.4f})")


if __name__ == "__main__":
    main()
