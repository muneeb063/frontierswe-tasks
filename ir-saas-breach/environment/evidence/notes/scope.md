# Ledgerly incident IR-2026-114: case notes from the on-call engineer

**Trigger.** On 2026-10-28 a customer reported that their customer list was being offered for sale.
The records match the format of our nightly customer exports. Leadership has asked for a full
reconstruction of what happened, what was taken, and what access the intruder may still hold.

## Environment

* Ledgerly is a B2B invoicing SaaS. Customers log in with their email address. Staff log in with
  `<first initial>.<last name>` (for example `p.nguyen`). Staff can open the support console, which
  lists customer records and lets them create integration API keys.
* Staff SSO sessions are also used for the Stratus cloud console (IAM and storage administration).
* Production VPC: `10.20.0.0/16`. Office and VPN egress: `198.51.100.0/24`.
* Service identities you will see doing routine work: role `app-server` (uploads), role
  `backup-runner` (nightly copy of the newest exports at 02:00 UTC), user `ci-deploy` (release
  artifacts), API keys `key-0a11f3e2` (billing-sync) and `key-7c3d9b10` (crm-bridge).

## Evidence collected (read-only copies)

| Path | What it is | Clock |
|---|---|---|
| `web/access.log.2.gz`, `web/access.log.1`, `web/access.log` | Web tier access logs, rotated at local midnight (oldest first) | Local time, offset in every line |
| `app/auth-events.jsonl` | Application authentication, session and API-key events | UTC |
| `cloud/audit.jsonl` | Stratus control-plane and storage data-plane audit trail | UTC |

The web tier sits behind a pair of internal load balancers (`10.0.1.10`, `10.0.1.11`), so the
first field of every access-log line is a load balancer, not the client. The load balancer appends
the address of the peer that connected to it to the `X-Forwarded-For` header, which is logged as
`xff="..."`. Clients can send their own `X-Forwarded-For` header, and the load balancer keeps
whatever they sent in front of what it appends.

## Authorized activity in the window

* **External assessment.** Bulwark Security ran an authorized unauthenticated scan of the web tier
  on 2026-10-26 from 13:00 to 17:00 UTC, from `192.0.2.10` only. It is in scope for nothing else.
* A customer was locked out and reset their password on 2026-10-27; support confirmed it by phone.
* `p.nguyen` (platform admin) created a reporting integration key on 2026-10-27 and a QA contractor
  account in the cloud console on 2026-10-28, both under change tickets.
