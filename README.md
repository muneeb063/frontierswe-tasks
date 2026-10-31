# FrontierSWE-style sample tasks

Three [Harbor](https://github.com/harbor-framework/harbor) task folders in the FrontierSWE layout
(`instruction.md`, `task.toml`, `environment/`, `tests/`, `solution/solve.sh`). Each gives the agent
20 hours (`timeout_sec = 72000`), runs it as the unprivileged `agent` user with no network, and
scores the agent's work by running or checking it against hidden data that is only uploaded at
verification time.

| Task | Kind | The agent must | Score |
|---|---|---|---|
| [`quill-interpreter`](quill-interpreter) | Long-horizon SWE | Implement a full interpreter for Quill, a new dynamically typed language (closures, bigints, Unicode strings, ordered maps, exact error semantics), from a 9-section spec | Fraction of 75 hidden programs whose stdout and exit status match exactly |
| [`iam-policy-engine`](iam-policy-engine) | Cloud / IAM security | Implement a cloud IAM authorization engine: identity, group, boundary, multi-level organization and resource policies, wildcards, policy variables, 20+ condition operators with `IfExists` / set prefixes, cross-account rules | Chance-corrected balanced accuracy over 660 hidden, class-balanced access decisions in 5 accounts (one realistic, four generated) |
| [`ir-saas-breach`](ir-saas-breach) | Incident response / forensics | Reconstruct an account-takeover and data-theft incident from 3 days of web (rotated, gzipped, local time, spoofable `X-Forwarded-For`), application and cloud audit logs, separating it from an authorized scan and other look-alike activity | 11 findings, equal weight |

Verification details shared by all three:

* Hidden tests live in `tests/` (Harbor uploads them to `/tests` only for the verifier). When the
  verifier runs as root it makes `/tests` root-only, runs any agent-built program as `agent`, and
  kills processes the agent left behind before scoring.
* `solution/` holds the reference solution and, for the two data-driven tasks, the generator
  (`make_tests.py`, `make_evidence.py`) that produced the hidden data, so the ground truth can be
  audited and rebuilt.
* An agent that does nothing produces no program or findings file and scores 0.
