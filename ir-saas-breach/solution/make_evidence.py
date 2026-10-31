#!/usr/bin/env python3
"""Builds the evidence bundle (environment/evidence) and ground truth (tests/expected.json).

Not used by the oracle; kept so the scenario can be audited and regenerated:
    python3 solution/make_evidence.py <task-dir>
All addresses used for the intrusion come from the RFC 5737 documentation ranges.
"""
import gzip
import io
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=-4))  # web tier logs in US Eastern daylight time
rng = random.Random(20261027)

START = datetime(2026, 10, 26, 4, 0, 0, tzinfo=UTC)   # local midnight, Oct 26
END = datetime(2026, 10, 29, 4, 0, 0, tzinfo=UTC)     # local midnight, Oct 29
LB = ["10.0.1.10", "10.0.1.11"]

RECON_IP, SPRAY_IPS, EXFIL_IP = "203.0.113.41", ["203.0.113.41", "203.0.113.87", "203.0.113.152"], "192.0.2.200"
PENTEST_IP = "192.0.2.10"
VICTIM, API_KEY, BACKDOOR_USER, BACKDOOR_KEY = "m.okafor", "key-5d1e0c7a", "svc-backup", "SKX7F3Q9M2LT0B"
BUCKET = "ledgerly-prod-data"

FIRST = ["amara", "ben", "chen", "dana", "eli", "farah", "gabe", "hana", "ivan", "jo", "kofi", "lena", "mateo",
         "nia", "omar", "priya", "quinn", "rosa", "sam", "tariq", "uma", "vik", "wen", "xavi", "yara", "zoe"]
LAST = ["adeyemi", "brandt", "costa", "diaz", "eriksen", "fischer", "garcia", "haddad", "ito", "jensen", "kim",
        "lopez", "moreau", "nakamura", "okafor", "patel", "quint", "rossi", "silva", "tanaka", "ueda", "vance",
        "weber", "xu", "young", "zhou"]
UAS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
       "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
       "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"]
SCANNER_UA = "Mozilla/5.0 (compatible; BulwarkScan/4.2; +authorized-assessment)"


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def staff_names():
    names = set()
    while len(names) < 45:
        names.add(f"{rng.choice(FIRST)[0]}.{rng.choice(LAST)}")
    names.discard(VICTIM)
    return sorted(names)[:44] + [VICTIM]


STAFF = staff_names()
ADMINS = ["p.nguyen"]
CUSTOMERS = [f"{rng.choice(FIRST)}.{rng.choice(LAST)}{rng.randint(1, 99)}@example.{rng.choice(['com', 'net', 'org'])}"
             for _ in range(300)]


def rand_public_ip():
    while True:
        a = rng.randint(11, 223)
        if a not in (100, 127, 169, 172, 192, 198, 203):
            return f"{a}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


CUSTOMER_IPS = [rand_public_ip() for _ in range(400)]
CORP_IPS = [f"198.51.100.{i}" for i in range(20, 60)]


def rand_time(a=START, b=END):
    """Uniform time with a mild daytime bias (US business hours)."""
    while True:
        t = a + timedelta(seconds=rng.uniform(0, (b - a).total_seconds()))
        hour = t.astimezone(LOCAL).hour
        if rng.random() < (1.0 if 8 <= hour <= 20 else 0.35):
            return t.replace(microsecond=0)


web, app, audit = [], [], []


def hit(t, ip, method, path, status, size, ua, xff=None, ref="-"):
    chain = f"{xff}, {ip}" if xff else ip
    web.append((t, f'{rng.choice(LB)} - - [{t.astimezone(LOCAL).strftime("%d/%b/%Y:%H:%M:%S %z")}] '
                   f'"{method} {path} HTTP/1.1" {status} {size} "{ref}" "{ua}" xff="{chain}" '
                   f'rt={rng.uniform(0.002, 0.4):.3f}'))


def ev(t, **kw):
    app.append((t, {"ts": iso(t), **kw}))


def cloud(t, name, identity, ip, params=None, response=None, error=None):
    audit.append((t, {"eventTime": iso(t), "eventSource": "storage.stratus" if name in (
        "GetObject", "PutObject", "ListObjects", "DeleteObject") else "iam.stratus", "eventName": name,
        "userIdentity": identity, "sourceIPAddress": ip, "requestParameters": params or {},
        "responseElements": response, "errorCode": error}))


# ------------------------------------------------------------------ background noise

PAGES = [("/", 200, 5120), ("/pricing", 200, 8840), ("/login", 200, 3301), ("/dashboard", 200, 12001),
         ("/static/app.3f9c1.js", 200, 284113), ("/static/app.3f9c1.css", 200, 40210), ("/favicon.ico", 200, 1150),
         ("/api/v1/invoices?page=1", 200, 2210), ("/api/v1/invoices?page=2", 200, 2190), ("/api/v1/me", 200, 640),
         ("/api/v1/reports/summary", 200, 1830), ("/docs/getting-started", 200, 15020), ("/blog/", 200, 9020)]

for _ in range(26000):
    t = rand_time()
    ip = rng.choice(CUSTOMER_IPS)
    path, status, size = rng.choice(PAGES)
    if rng.random() < 0.02:
        path, status, size = rng.choice(["/wp-login.php", "/.env", "/admin", "/old-site/"]), 404, 153
    hit(t, ip, "GET", path, status, size + rng.randint(-40, 40), rng.choice(UAS))

session_n = 0


def login(t, user, ip, ua, ok=True, mfa="passed", reason="bad_password", exists=True):
    global session_n
    hit(t, ip, "POST", "/api/v1/auth/login", 200 if ok else 401, 412 if ok else 96, ua)
    if ok:
        session_n += 1
        sid = f"s-{rng.getrandbits(48):012x}"
        ev(t, event="login_success", user=user, src_ip=ip, user_agent=ua)
        ev(t + timedelta(seconds=rng.randint(1, 3)), event="session_created", user=user, session_id=sid, mfa=mfa,
           src_ip=ip)
        return sid
    ev(t, event="login_failure", user=user, src_ip=ip, user_agent=ua, reason=reason if exists else "unknown_user")
    return None


for _ in range(900):  # customer logins
    t = rand_time()
    who = rng.choice(CUSTOMERS)
    ip, ua = rng.choice(CUSTOMER_IPS), rng.choice(UAS)
    if rng.random() < 0.08:
        login(t, who, ip, ua, ok=False)
        t += timedelta(seconds=rng.randint(10, 90))
    login(t, who, ip, ua, mfa=rng.choice(["passed", "not_enrolled", "remembered_device"]))

for _ in range(500):  # staff logins from the office ranges
    t = rand_time()
    who = rng.choice(STAFF + ADMINS)
    if who == VICTIM and t > datetime(2026, 10, 26, 20, 0, tzinfo=UTC):
        continue  # the real m.okafor was off shift during the intrusion window
    login(t, who, rng.choice(CORP_IPS), rng.choice(UAS[:3]),
          mfa="not_enrolled" if who == VICTIM else rng.choice(["passed", "passed", "remembered_device"]))

for _ in range(40):  # the signup page legitimately uses the username check
    t = rand_time()
    ip = rng.choice(CUSTOMER_IPS)
    hit(t, ip, "GET", f"/api/v1/auth/check-username?u={rng.choice(CUSTOMERS).split('@')[0]}",
        rng.choice([200, 404, 404]), 41, rng.choice(UAS), ref="https://app.ledgerly.example/signup")

KEYS = {"key-0a11f3e2": ("billing-sync", "10.20.0.40"), "key-7c3d9b10": ("crm-bridge", "10.20.0.41")}
for key, (label, ip) in KEYS.items():
    t = START + timedelta(minutes=rng.randint(0, 20))
    while t < END:
        ev(t, event="api_request", key_id=key, src_ip=ip, method="GET", path="/api/v1/invoices?updated_since=1h",
           status=200)
        t += timedelta(minutes=15, seconds=rng.randint(-30, 30))

APP_ROLE = {"type": "AssumedRole", "roleName": "app-server"}
for _ in range(4200):
    t = rand_time()
    key = f"uploads/{rng.choice(CUSTOMERS).split('@')[0]}/{rng.getrandbits(32):08x}.pdf"
    op = rng.choice(["GetObject", "PutObject", "GetObject"])
    cloud(t, op, APP_ROLE, f"10.20.0.{rng.randint(20, 29)}", {"bucket": BUCKET, "key": key},
          {"bytesTransferred": rng.randint(20000, 900000)})

EXPORTS = [f"exports/customers-2026-10-{d:02d}.csv.gz" for d in range(13, 27)]
EXPORT_SIZE = {k: rng.randint(30_000_000, 60_000_000) for k in EXPORTS}
EXPORT_SIZE.update({f"exports/payments-2026-10-{d:02d}.csv.gz": rng.randint(5_000_000, 9_000_000)
                    for d in range(20, 27)})
BACKUP = {"type": "AssumedRole", "roleName": "backup-runner"}
for day in (26, 27, 28):  # nightly backup copies the newest exports
    t = datetime(2026, 10, day, 2, 0, 5, tzinfo=UTC)
    cloud(t, "ListObjects", BACKUP, "10.20.0.15", {"bucket": BUCKET, "prefix": "exports/"})
    for k in sorted(EXPORT_SIZE)[-6:]:
        t += timedelta(seconds=rng.randint(20, 60))
        cloud(t, "GetObject", BACKUP, "10.20.0.15", {"bucket": BUCKET, "key": k},
              {"bytesTransferred": EXPORT_SIZE[k]})
CI = {"type": "IAMUser", "userName": "ci-deploy", "accessKeyId": "SKC1D2E3F4G5H6"}
for _ in range(30):
    t = rand_time()
    cloud(t, "PutObject", CI, "10.20.5.9", {"bucket": "ledgerly-releases", "key": f"web/{rng.getrandbits(24):06x}.tar.gz"},
          {"bytesTransferred": rng.randint(10_000_000, 30_000_000)})

# ------------------------------------------------------------------ decoys

t = datetime(2026, 10, 26, 13, 5, 0, tzinfo=UTC)  # authorized external scan, see scope.md
while t < datetime(2026, 10, 26, 16, 40, tzinfo=UTC):
    r = rng.random()
    if r < 0.08:
        u = rng.choice(["admin", "test", "root", "support", STAFF[3]])
        login(t, u, PENTEST_IP, SCANNER_UA, ok=False, exists=u == STAFF[3])
    elif r < 0.2:
        hit(t, PENTEST_IP, "GET", f"/api/v1/auth/check-username?u={rng.choice(['admin', 'test', 'root', 'guest'])}",
            404, 41, SCANNER_UA)
    else:
        hit(t, PENTEST_IP, "GET", rng.choice(["/.git/config", "/server-status", "/api/v1/../../etc/passwd", "/backup.zip",
                                              "/api/v1/debug", "/actuator/health", "/console", "/phpinfo.php"]),
            rng.choice([404, 404, 403, 400]), 153, SCANNER_UA)
    t += timedelta(seconds=rng.randint(4, 40))

t = datetime(2026, 10, 27, 14, 2, 0, tzinfo=UTC)  # a locked-out customer, then a reset
jip, jwho = rng.choice(CUSTOMER_IPS), "j.alvarez7@example.com"
for _ in range(6):
    login(t, jwho, jip, UAS[1], ok=False)
    t += timedelta(seconds=rng.randint(8, 30))
ev(t, event="password_reset", user=jwho, src_ip=jip)
login(t + timedelta(minutes=4), jwho, jip, UAS[1])

t = datetime(2026, 10, 27, 15, 10, 44, tzinfo=UTC)  # a real admin creates an integration key
sid = login(t - timedelta(minutes=3), "p.nguyen", "198.51.100.23", UAS[0])
ev(t, event="api_key_created", user="p.nguyen", key_id="key-91b2aa04", label="looker-reporting", session_id=sid,
   src_ip="198.51.100.23")
cloud(datetime(2026, 10, 28, 16, 20, 3, tzinfo=UTC), "CreateUser", {"type": "SSOUser", "userName": "p.nguyen"},
      "198.51.100.23", {"userName": "contractor-qa"})
cloud(datetime(2026, 10, 28, 16, 21, 9, tzinfo=UTC), "AttachUserPolicy", {"type": "SSOUser", "userName": "p.nguyen"},
      "198.51.100.23", {"userName": "contractor-qa", "policyArn": "srn:stratus:iam::stratus:policy/ReadOnly"})

# ------------------------------------------------------------------ the intrusion

candidates = sorted(set(STAFF[:36]) | {VICTIM} | {f"{f[0]}.{l}" for f, l in zip(rng.sample(FIRST, 26), rng.sample(LAST, 26))})
valid = [u for u in candidates if u in STAFF]
probe_order = rng.sample(candidates, len(candidates))
t = datetime(2026, 10, 26, 22, 47, 31, tzinfo=UTC)
recon_start = t
hit(t, RECON_IP, "GET", "/", 200, 5133, UAS[2], xff="127.0.0.1")
for path in ["/robots.txt", "/login", "/static/app.3f9c1.js", "/api/v1/auth/login"]:
    t += timedelta(seconds=rng.randint(2, 9))
    hit(t, RECON_IP, "GET", path, 404 if path == "/robots.txt" else 405 if path.endswith("login") and "api" in path else 200,
        153, UAS[2], xff="127.0.0.1")
for u in probe_order:
    t += timedelta(seconds=rng.randint(3, 11))
    hit(t, RECON_IP, "GET", f"/api/v1/auth/check-username?u={u}", 200 if u in STAFF else 404, 41, UAS[2],
        xff=rng.choice(["127.0.0.1", "10.0.0.5", None]))

sprayed = valid  # every account the probe confirmed
rounds = [datetime(2026, 10, 27, h, m, 0, tzinfo=UTC) for h, m in ((0, 5), (1, 2), (2, 6), (3, 9))]
initial_access = None
for i, start in enumerate(rounds):
    t = start
    for u in rng.sample(sprayed, len(sprayed)):
        t += timedelta(seconds=rng.randint(2, 7))
        ip = rng.choice(SPRAY_IPS)
        if i == 3 and u == VICTIM:
            ip = "203.0.113.87"
            initial_access = t
            victim_sid = login(t, u, ip, UAS[0], mfa="not_enrolled")
        else:
            login(t, u, ip, UAS[0], ok=False)
assert initial_access is not None

t = initial_access + timedelta(minutes=5)
for page in range(1, 9):
    t += timedelta(seconds=rng.randint(20, 70))
    hit(t, "203.0.113.87", "GET", f"/api/v1/support/customers?page={page}&per_page=500", 200, 248000 + page, UAS[0])
t += timedelta(minutes=6)
hit(t, "203.0.113.87", "POST", "/api/v1/integrations/api-keys", 201, 188, UAS[0])
ev(t, event="api_key_created", user=VICTIM, key_id=API_KEY, label="zapier-sync", session_id=victim_sid,
   src_ip="203.0.113.87")
SSO = {"type": "SSOUser", "userName": VICTIM}
t += timedelta(minutes=8, seconds=17)
cloud(t, "CreateUser", SSO, "203.0.113.87", {"userName": BACKDOOR_USER})
t += timedelta(seconds=41)
cloud(t, "AttachUserPolicy", SSO, "203.0.113.87",
      {"userName": BACKDOOR_USER, "policyArn": "srn:stratus:iam::stratus:policy/StorageFullAccess"})
t += timedelta(seconds=29)
cloud(t, "CreateAccessKey", SSO, "203.0.113.87", {"userName": BACKDOOR_USER}, {"accessKeyId": BACKDOOR_KEY})

t = datetime(2026, 10, 27, 3, 58, 12, tzinfo=UTC)
for _ in range(5):
    ev(t, event="api_request", key_id=API_KEY, src_ip=EXFIL_IP, method="GET",
       path="/api/v1/support/customers?per_page=500", status=200)
    t += timedelta(seconds=rng.randint(30, 90))

BD = {"type": "IAMUser", "userName": BACKDOOR_USER, "accessKeyId": BACKDOOR_KEY}
t = datetime(2026, 10, 27, 4, 2, 40, tzinfo=UTC)
cloud(t, "ListObjects", BD, EXFIL_IP, {"bucket": BUCKET, "prefix": ""})
cloud(t + timedelta(seconds=9), "ListObjects", BD, EXFIL_IP, {"bucket": BUCKET, "prefix": "exports/"})
t += timedelta(seconds=30)
plan = sorted(EXPORT_SIZE, reverse=True)[:12] + ["exports/customers-2026-10-26.csv.gz", "finance/ledger-2026.xlsx",
                                                 "finance/payroll-2026-10.csv", "exports/customers-2026-10-27.csv.gz",
                                                 "secrets/backup-codes.txt"]
exfil_bytes, exfil_objects = 0, set()
for k in plan:
    t += timedelta(seconds=rng.randint(40, 400))
    if k in EXPORT_SIZE:
        cloud(t, "GetObject", BD, EXFIL_IP, {"bucket": BUCKET, "key": k}, {"bytesTransferred": EXPORT_SIZE[k]})
        exfil_bytes += EXPORT_SIZE[k]
        exfil_objects.add(k)
    else:
        cloud(t, "GetObject", BD, EXFIL_IP, {"bucket": BUCKET, "key": k}, None,
              "NoSuchKey" if k.endswith("27.csv.gz") else "AccessDenied")

# ------------------------------------------------------------------ write

task = sys.argv[1]
evd = os.path.join(task, "environment", "evidence")
for sub in ("web", "app", "cloud"):
    os.makedirs(os.path.join(evd, sub), exist_ok=True)
web.sort(key=lambda x: x[0])
by_day = {26: [], 27: [], 28: []}
for t, line in web:
    by_day[t.astimezone(LOCAL).day].append(line)
with open(os.path.join(evd, "web", "access.log.2.gz"), "wb") as raw:
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(("\n".join(by_day[26]) + "\n").encode())
for day, name in ((27, "access.log.1"), (28, "access.log")):
    with open(os.path.join(evd, "web", name), "w", newline="\n") as fh:
        fh.write("\n".join(by_day[day]) + "\n")
app.sort(key=lambda x: x[0])
with open(os.path.join(evd, "app", "auth-events.jsonl"), "w", newline="\n") as fh:
    fh.writelines(json.dumps(e) + "\n" for _, e in app)
audit.sort(key=lambda x: x[0])
with open(os.path.join(evd, "cloud", "audit.jsonl"), "w", newline="\n") as fh:
    fh.writelines(json.dumps(e) + "\n" for _, e in audit)

expected = {
    "recon_start_utc": iso(recon_start),
    "enumeration_endpoint": "/api/v1/auth/check-username",
    "spray_source_ips": sorted(SPRAY_IPS),
    "sprayed_account_count": len(set(sprayed)),
    "compromised_user": VICTIM,
    "initial_access_utc": iso(initial_access),
    "persistence_api_key_id": API_KEY,
    "persistence_iam_user": BACKDOOR_USER,
    "exfil_ip": EXFIL_IP,
    "exfiltrated_objects": sorted(exfil_objects),
    "exfil_total_bytes": exfil_bytes,
}
os.makedirs(os.path.join(task, "tests"), exist_ok=True)
with open(os.path.join(task, "tests", "expected.json"), "w", newline="\n") as fh:
    json.dump(expected, fh, indent=1)
print(json.dumps(expected, indent=1))
print({k: len(v) for k, v in by_day.items()}, len(app), len(audit))
