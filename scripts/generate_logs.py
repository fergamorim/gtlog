"""Generate synthetic log files for demos and load tests.

Usage:
    python scripts/generate_logs.py --lines 200000 --format text --out samples/app.log
    python scripts/generate_logs.py --lines 50000 --format json --out samples/app.jsonl
    python scripts/generate_logs.py --lines 50000 --format csv --out samples/app.csv
    python scripts/generate_logs.py --lines 50000 --format http --out samples/access.log
    python scripts/generate_logs.py --lines 20000 --scenario ssh --out samples/ssh.log
    python scripts/generate_logs.py --lines 0 --follow 5 --out samples/live.log

--scenario picks the kind of system the messages come from (default: mixed, all of them):

    app        web application (payments, catalog, player...)
    k8s        Kubernetes workloads: OOMKilled, CrashLoopBackOff, ImagePullBackOff, 502/503, deadlocks
    ssh        sshd authentication, with brute-force bursts from one IP
    wordpress  WordPress site under a pingback (xmlrpc) DDoS: bursts of 503 from WordPress user agents
    events     Flask app with an event SDK: exceptions, DB errors, routing errors, slow endpoints

--format http writes Apache/Nginx combined access lines (normal traffic, vulnerability
scans and the WordPress pingback flood), whatever the scenario.

--follow N keeps appending N lines per second (timestamped now) until Ctrl+C,
to try the live watch of a file.

A small share of lines is deliberately malformed so the importer's
validation and error reporting can be exercised. Attacks come in bursts:
consecutive lines with the same source IP, as in real incidents.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


_STATUS = re.compile(r"\bstatus=(\d{3})\b")


@dataclass(frozen=True)
class Event:
    level: str
    service: str
    message: str

    @property
    def status(self) -> int | None:
        """The HTTP status in the message (status=503), written as its own field in JSON and CSV."""
        match = _STATUS.search(self.message)
        return int(match[1]) if match else None


@dataclass(frozen=True)
class Template:
    level: str
    weight: float
    text: str
    # Services the message can come from; None uses the scenario's services.
    services: tuple[str, ...] | None = None
    # A burst repeats the message (min, max) times with the same values, e.g. an attack from one IP.
    # Its weight is per burst, so a long burst gets a small weight.
    burst: tuple[int, int] = (1, 1)


# ------------------------------ value helpers ------------------------------

WORDPRESS_SITES = [
    "http://www.cakefantasia.com", "http://aifs2.pvdveen.net", "http://sociedia.com", "http://photekusa.com",
    "http://enabledkids.ca", "http://guyana-tourism.com/blog", "http://blog.bakery-lisboa.pt",
    "http://www.trailrunners.org",
]
WORDPRESS_VERSIONS = ["3.0.2", "3.5.1", "3.5.2", "3.6", "3.6.1", "4.9.8", "5.8.3", "6.4.2"]
SSH_USERS = ["kamran", "student", "osamac", "deploy", "ubuntu"]
# Usernames tried by brute-force bots, as seen in real sshd logs.
SSH_GUESSES = [
    "admin", "admins", "phoenix", "piglet", "rainbow", "runner", "sam", "abc123", "passwd", "newpass", "notused",
    "qwerty", "computer", "mustang", "jennifer", "oracle", "test", "guest", "pi", "ftpuser", "git",
]
K8S_SERVICES = ("backend-api", "orders", "auth-service", "nginx-frontend", "payments")
UPSTREAMS = ["payments.internal:9000", "auth.internal:8080", "db.internal:5432", "cache.internal:6379"]
ENDPOINTS = ["/checkout", "/login", "/api/v1/orders", "/api/v1/accounts", "/health", "/api/v1/transfers"]
METHODS = ["GET", "GET", "GET", "POST", "PUT", "DELETE"]
CONFIG_FILES = ["/etc/config/db.yml", "/etc/config/app.yml", "/etc/config/feature-flags.json"]
JOBS = ["report-generator", "ledger-reconcile", "cache-warmup", "email-digest", "fraud-score"]
FLASK_ROUTES = ["/db/constraint", "/db/connection", "/external/timeout", "/crash", "/memory-leak"]
APP_SERVICES = ["auth", "payments", "catalog", "player", "search", "notifications"]


def private_ip() -> str:
    return f"10.0.{random.randint(0, 9)}.{random.randint(1, 254)}"


def public_ip() -> str:
    return ".".join(str(random.randint(1, 223)) for _ in range(4))


def values() -> dict[str, object]:
    """Fresh random values for one message (a burst reuses the same ones)."""
    pod = random.choice(K8S_SERVICES)
    return {
        "key": f"{random.randrange(16**6):06x}",
        "n": random.randint(1, 9999),
        "small": random.randint(2, 12),
        "user": f"user{random.randint(1, 500)}",
        "uid": random.randint(10_000, 99_999),
        "ms": random.randint(5, 30_000),
        "fast_ms": random.randint(20, 900),
        "p95": random.randint(800, 2500),
        "p99": random.randint(2500, 9000),
        "pct": random.randint(85, 99),
        "svc": random.choice(APP_SERVICES),
        "pod": f"{pod}-{random.randint(1, 12):02d}",
        "ns": random.choice(["prod", "prod", "staging"]),
        "image": f"myorg/{pod}:{random.randint(0, 2)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
        "upstream": random.choice(UPSTREAMS),
        "endpoint": random.choice(ENDPOINTS),
        "method": random.choice(METHODS),
        "status_ok": random.choice([200, 200, 200, 201, 204, 304]),
        "config": random.choice(CONFIG_FILES),
        "job": random.choice(JOBS),
        "ip": private_ip(),
        "attacker": public_ip(),
        "port": random.randint(30_000, 65_000),
        "ssh_user": random.choice(SSH_USERS),
        "guess": random.choice(SSH_GUESSES),
        "wp_site": random.choice(WORDPRESS_SITES),
        "wp_version": random.choice(WORDPRESS_VERSIONS),
        "route": random.choice(FLASK_ROUTES),
        "trace": f"{random.randrange(16**8):08x}-{random.randrange(16**4):04x}",
        "table": random.choice(["orders", "customers", "payments", "events"]),
    }


# -------------------------------- scenarios --------------------------------
# "status=NNN" in a message is picked up by the importer as the line's HTTP status code.

APP = [
    Template("DEBUG", 10, "cache lookup key={key}"),
    Template("DEBUG", 5, "request payload size={n}B"),
    Template("INFO", 20, "user {user} logged in"),
    Template("INFO", 25, "request GET /api/{svc} completed in {ms}ms status={status_ok}"),
    Template("INFO", 15, "job {key} finished"),
    Template("WARNING", 6, "slow query took {ms}ms"),
    Template("WARNING", 5, "retrying call to {svc} (attempt {small})"),
    Template("WARNING", 4, "token near expiration for {user}"),
    Template("ERROR", 3, "timeout calling {svc} after {ms}ms"),
    Template("ERROR", 3, "database connection refused"),
    Template("ERROR", 2, "payment {key} declined: card declined by issuer", ("payments",)),
    Template("ERROR", 1, "request POST /api/{svc} failed status=500"),
    Template("CRITICAL", 1, "out of memory in worker {n}"),
    Template("CRITICAL", 1, "disk usage above {pct}% on node-{small}"),
]

# Kubernetes workloads (pod, namespace and the usual failure reasons).
K8S = [
    Template("INFO", 12, "pod={pod} ns={ns} Background job {job} completed in {fast_ms}ms"),
    Template("INFO", 11, "pod={pod} ns={ns} Started request {method} {endpoint} from {ip}"),
    Template("INFO", 10, "pod={pod} ns={ns} Completed {method} {endpoint} in {fast_ms}ms status={status_ok}"),
    Template("DEBUG", 10, "pod={pod} ns={ns} Health check passed: ready=true, status=200"),
    Template("INFO", 10, "pod={pod} ns={ns} Established connection to upstream {upstream}"),
    Template("DEBUG", 10, "pod={pod} ns={ns} Cache hit for key=session:{n}; ttl={n}s"),
    Template("DEBUG", 9, "pod={pod} ns={ns} Opening database transaction; connection_id={n}"),
    Template("INFO", 9, "pod={pod} ns={ns} User {uid} authenticated successfully"),
    Template("INFO", 8, "pod={pod} ns={ns} Loaded config from {config}"),
    Template("INFO", 7, "pod={pod} ns={ns} Graceful shutdown initiated, waiting for connections to drain"),
    Template("WARNING", 3, "pod={pod} ns={ns} latency spike: p95={p95}ms, p99={p99}ms for endpoint {endpoint}"),
    Template("ERROR", 6, "pod={pod} ns={ns} connection refused from {upstream}"),
    Template("ERROR", 6, "pod={pod} ns={ns} request timeout after {ms}ms while calling db"),
    Template("ERROR", 3, "pod={pod} ns={ns} database deadlock detected; rolling back transaction"),
    Template("ERROR", 3, "pod={pod} ns={ns} ImagePullBackOff: failed to pull image {image}"),
    Template("ERROR", 3, "pod={pod} ns={ns} gateway error from upstream {upstream}: 502 Bad Gateway status=502"),
    Template("CRITICAL", 5, "pod={pod} ns={ns} OOMKilled - process terminated due to out-of-memory"),
    Template("CRITICAL", 4, "pod={pod} ns={ns} Segmentation fault (core dumped) in worker thread"),
    Template("CRITICAL", 1.5, "pod={pod} ns={ns} CrashLoopBackOff: container restarted {small} times", burst=(2, 5)),
    Template("CRITICAL", 1, "pod={pod} ns={ns} 503 Service Unavailable - downstream overloaded status=503",
             burst=(3, 10)),
]

# sshd: regular logins plus brute-force bursts (invalid users, root guesses) from one public IP.
SSH = [
    Template("INFO", 20, "Accepted password for {ssh_user} from {ip} port {port} ssh2"),
    Template("INFO", 8, "Accepted publickey for {ssh_user} from {ip} port {port} ssh2: RSA SHA256:{key}"),
    Template("INFO", 15, "pam_unix(sshd:session): session opened for user {ssh_user} by (uid=0)"),
    Template("INFO", 12, "pam_unix(sshd:session): session closed for user {ssh_user}"),
    Template("DEBUG", 6, "Connection from {ip} port {port} on 0.0.0.0 port 22"),
    Template("WARNING", 10, "Failed password for {ssh_user} from {ip} port {port} ssh2"),
    Template("WARNING", 6,
             "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh rhost={attacker} user=root"),
    Template("WARNING", 0.8, "Invalid user {guess} from {attacker} port {port}", burst=(5, 30)),
    Template("ERROR", 0.6, "Failed password for root from {attacker} port {port} ssh2", burst=(5, 40)),
    Template("ERROR", 3, "error: maximum authentication attempts exceeded for root from {attacker} port {port} ssh2"),
    Template("INFO", 4, "Disconnected from authenticating user root {attacker} port {port} [preauth]"),
    Template("CRITICAL", 1, "Accepted password for root from {attacker} port {port} ssh2 after {small} failed attempts"),
]

# WordPress under a pingback DDoS: other WordPress sites, abused via xmlrpc, flood "/" until it answers 503.
WORDPRESS = [
    Template("INFO", 25, "GET / from {ip} status=200 bytes=8955"),
    Template("INFO", 10, "GET /wp-content/uploads/{key}.jpg from {ip} status=200 bytes={n}"),
    Template("INFO", 8, "user {user} logged in to wp-admin"),
    Template("DEBUG", 6, "WP_Query for post_type=post took {fast_ms}ms"),
    Template("WARNING", 8, 'pingback.ping via xmlrpc.php from {attacker} ua="WordPress/{wp_version}; {wp_site}"'),
    Template("WARNING", 5, "rate limit exceeded for {attacker}: {n} req/min status=429"),
    Template("WARNING", 0.6, "failed login for admin from {attacker} (wp-login.php) status=401", burst=(3, 20)),
    Template("CRITICAL", 0.6,
             'GET / from {attacker} ua="WordPress/{wp_version}; {wp_site}" status=503 bytes=913 - pingback flood',
             burst=(10, 60)),
    Template("ERROR", 4, "PHP Fatal error: Allowed memory size of 268435456 bytes exhausted in class-wp-query.php"),
    Template("ERROR", 3, "Error establishing a database connection to mysql:3306"),
]

# A Flask app reporting through an event SDK (event types as the message prefix).
EVENTS = [
    Template("INFO", 25, "INCOMING_REQUEST GET /http/200 status=200 in {fast_ms}ms trace={trace}"),
    Template("DEBUG", 30, "DB_QUERY SELECT * FROM {table} WHERE id = {n} took {fast_ms}ms"),
    Template("WARNING", 4, "INCOMING_REQUEST GET /performance/slow status=200 in {ms}ms"),
    Template("INFO", 3, "HTTP_CALL GET https://api.partner.example/v1/rates status=200 in {fast_ms}ms"),
    Template("WARNING", 6, "ROUTING_ERROR 404 Not Found: /{key} status=404"),
    Template("WARNING", 2, "HTTP_EXCEPTION 405 Method Not Allowed: POST /http/200 status=405"),
    Template("ERROR", 8, "SERVER_ERROR Exception on {route} [GET] status=500 trace={trace}"),
    Template("ERROR", 3, 'DB_ERROR IntegrityError: duplicate key value violates unique constraint "{table}_pkey"'),
    Template("ERROR", 2, "DB_ERROR OperationalError: could not connect to server: Connection refused (db:5432)"),
    Template("ERROR", 1, "HTTP_ERROR GET https://api.partner.example/v1/rates timed out after {ms}ms"),
    Template("WARNING", 1, "WARNING: This is a development server. Do not use it in a production deployment."),
    Template("CRITICAL", 1, "MemoryError in /memory-leak: process RSS above {pct}% of limit"),
]

SCENARIOS: dict[str, tuple[list[Template], tuple[str, ...]]] = {
    "app": (APP, tuple(APP_SERVICES)),
    "k8s": (K8S, K8S_SERVICES),
    "ssh": (SSH, ("sshd",)),
    "wordpress": (WORDPRESS, ("wordpress", "nginx")),
    "events": (EVENTS, ("client-test-app", "flask")),
}
MIXED_WEIGHTS = {"app": 35, "k8s": 30, "ssh": 12, "wordpress": 10, "events": 13}


def events(scenario: str) -> Iterator[Event]:
    """Endless stream of events; a burst comes out as consecutive identical events."""
    names = list(MIXED_WEIGHTS) if scenario == "mixed" else [scenario]
    weights = [MIXED_WEIGHTS[n] for n in names]
    while True:
        templates, services = SCENARIOS[random.choices(names, weights)[0]]
        template = random.choices(templates, [t.weight for t in templates])[0]
        service = random.choice(template.services or services)
        message = template.text.format(**values())
        for _ in range(random.randint(*template.burst)):
            yield Event(template.level, service, message)


# ------------------------------ access log mode ----------------------------

PAGES = ["/", "/blog/", "/contato/", "/wp-content/themes/twenty/style.css", "/feed/", "/?p={n}", "/wp-json/wp/v2/posts"]
SCANS = ["/wp-login.php", "/.env", "/phpmyadmin/", "/xmlrpc.php", "/wp-config.php.bak", "/admin/.git/config"]
BROWSERS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "curl/8.5.0",
]


def access_requests() -> Iterator[tuple[str, str, str, int, int, str]]:
    """Endless (ip, method, path, status, bytes, user agent): visitors, scanners and pingback floods."""
    while True:
        kind = random.choices(["visit", "scan", "flood", "error"], [70, 3, 0.8, 4])[0]
        if kind == "visit":
            path = random.choice(PAGES).format(n=random.randint(1, 900))
            status = random.choice([200, 200, 200, 200, 304, 301])
            yield public_ip(), "GET", path, status, random.randint(300, 40_000), random.choice(BROWSERS)
        elif kind == "scan":
            ip = public_ip()
            for path in random.sample(SCANS, random.randint(2, len(SCANS))):
                status = random.choice([404, 403, 404, 401])
                yield ip, random.choice(["GET", "POST"]), path, status, 0, "python-requests/2.31"
        elif kind == "flood":
            # Many WordPress sites abused as reflectors hit "/" at once; the server soon answers 503.
            for _ in range(random.randint(10, 60)):
                agent = f"WordPress/{random.choice(WORDPRESS_VERSIONS)}; {random.choice(WORDPRESS_SITES)}"
                status = random.choices([503, 200], [92, 8])[0]
                yield public_ip(), "GET", "/", status, 913 if status == 503 else 8955, agent
        else:
            status = random.choice([500, 502, 504])
            yield public_ip(), "POST", "/wp-admin/admin-ajax.php", status, 0, random.choice(BROWSERS)


# --------------------------------- writing ---------------------------------


def make_writer(f, fmt: str, scenario: str, invalid_ratio: float) -> Callable[[datetime], None]:
    """A function that writes one line, stamped with the given time, in the chosen format."""
    writer = csv.writer(f, lineterminator="\n")
    if fmt == "csv":
        writer.writerow(["timestamp", "level", "service", "status", "message"])
    stream = events(scenario)
    requests = access_requests()

    def write(ts: datetime) -> None:
        if random.random() < invalid_ratio:
            f.write("@@ corrupted line without structure @@\n")
            return
        if fmt == "http":
            ip, method, path, status, size, agent = next(requests)
            stamp = ts.strftime("%d/%b/%Y:%H:%M:%S %z")
            f.write(f'{ip} - - [{stamp}] "{method} {path} HTTP/1.1" {status} {size} "-" "{agent}"\n')
            return
        event = next(stream)
        if fmt == "csv":
            writer.writerow([ts.isoformat(), event.level, event.service, event.status or "", event.message])
        elif fmt == "json":
            record = {"timestamp": ts.isoformat(), "level": event.level, "service": event.service,
                      "message": event.message}
            if event.status:
                record["status"] = event.status
            f.write(json.dumps(record) + "\n")
        else:
            f.write(f"{ts.isoformat()} {event.level} [{event.service}] {event.message}\n")

    return write


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lines", type=int, default=100_000)
    parser.add_argument("--format", choices=["text", "json", "csv", "http"], default="text")
    parser.add_argument("--scenario", choices=["mixed", *SCENARIOS], default="mixed")
    parser.add_argument("--days", type=int, default=14, help="time span covered by the logs")
    parser.add_argument("--invalid-ratio", type=float, default=0.005)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--follow", type=int, default=0, metavar="N", help="then append N lines per second")
    args = parser.parse_args()

    random.seed(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc) - timedelta(days=args.days)
    step = timedelta(days=args.days) / max(args.lines, 1)

    with args.out.open("w", encoding="utf-8", newline="") as f:
        write = make_writer(f, args.format, args.scenario, args.invalid_ratio)
        for i in range(args.lines):
            write(start + step * i)

        print(f"wrote {args.lines} lines to {args.out}")
        if args.follow <= 0:
            return
        print(f"appending {args.follow} lines/s, Ctrl+C to stop")
        try:
            while True:
                for _ in range(args.follow):
                    write(datetime.now(timezone.utc))
                f.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
