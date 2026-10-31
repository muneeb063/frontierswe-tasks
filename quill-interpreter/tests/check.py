#!/usr/bin/env python3
"""Quill verifier: runs /workspace/quill/quill on every hidden program; reward = fraction passed."""
import argparse
import json
import os
import pwd
import signal
import subprocess
import tempfile

TIMEOUT_SEC = 10
MAX_OUT = 1 << 20


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


def run_case(exe, source, ids):
    with tempfile.TemporaryDirectory() as tmp:
        prog = os.path.join(tmp, "prog.ql")
        with open(prog, "wb") as fh:
            fh.write(source)
        out_path = os.path.join(tmp, "stdout")
        if ids:
            os.chown(tmp, *ids)
            os.chown(prog, *ids)

        def demote():
            if ids:
                os.setgroups([])
                os.setgid(ids[1])
                os.setuid(ids[0])

        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": tmp, "LANG": "C.UTF-8"}
        with open(out_path, "wb") as out:
            p = subprocess.Popen([exe, prog], cwd=tmp, stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=subprocess.DEVNULL, env=env, preexec_fn=demote, start_new_session=True)
            try:
                code = p.wait(timeout=TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                code = None
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            p.wait()
        with open(out_path, "rb") as fh:
            stdout = fh.read(MAX_OUT).decode("utf-8", "replace")
    return code, stdout


def passes(want, code, stdout):
    if code is None or code != want["exit"]:
        return False
    if want["stdout"] is None:  # syntax error: exactly one line, starting with "syntax error"
        line = stdout[:-1] if stdout.endswith("\n") else stdout
        return line.startswith("syntax error") and "\n" not in line
    return stdout == want["stdout"]


def write_reward(out, score):
    with open(os.path.join(out, "reward.json"), "w") as fh:
        json.dump({"reward": score}, fh)
    with open(os.path.join(out, "reward.txt"), "w") as fh:
        fh.write(str(score))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--cases", default="/tests/cases")
    ap.add_argument("--expected", default="/tests/expected.json")
    ap.add_argument("--out", default="/logs/verifier")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    with open(args.expected, encoding="utf-8") as fh:
        expected = json.load(fh)
    sources = {}
    for name in expected:
        with open(os.path.join(args.cases, name + ".ql"), "rb") as fh:
            sources[name] = fh.read()

    ids = agent_ids()
    if ids:
        kill_user(ids[0])
    exe = os.path.join(args.workspace, "quill", "quill")
    if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
        print(f"no executable interpreter at {exe}")
        write_reward(args.out, 0.0)
        return

    passed = 0
    for name in sorted(expected):
        code, stdout = run_case(exe, sources[name], ids)
        ok = passes(expected[name], code, stdout)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name} (exit {code})")
    if ids:
        kill_user(ids[0])
    score = round(passed / len(expected), 4)
    write_reward(args.out, score)
    print(f"Score: {score} ({passed}/{len(expected)})")


if __name__ == "__main__":
    main()
