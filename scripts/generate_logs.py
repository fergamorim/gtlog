"""Generate synthetic log files for demos and load tests.

Usage:
    python scripts/generate_logs.py --lines 200000 --format text --out samples/app.log
    python scripts/generate_logs.py --lines 50000 --format json --out samples/app.jsonl
    python scripts/generate_logs.py --lines 50000 --format csv --out samples/app.csv

A small share of lines is deliberately malformed so the importer's
validation and error reporting can be exercised.
"""

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVICES = ["auth", "payments", "catalog", "player", "search", "notifications"]
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LEVEL_WEIGHTS = [15, 60, 15, 8, 2]

MESSAGES = {
    "DEBUG": ["cache lookup key={key}", "request payload size={n}B"],
    "INFO": ["user {user} logged in", "request GET /api/{svc} completed in {ms}ms", "job {key} finished"],
    "WARNING": ["slow query took {ms}ms", "retrying call to {svc} (attempt {n})", "token near expiration for {user}"],
    "ERROR": ["timeout calling {svc} after {ms}ms", "database connection refused", "payment {key} declined"],
    "CRITICAL": ["out of memory in worker {n}", "disk usage above 95% on node-{n}"],
}


def render(level: str, svc: str) -> str:
    template = random.choice(MESSAGES[level])
    return template.format(
        key=f"{random.randrange(16**6):06x}",
        n=random.randint(1, 9999),
        user=f"user{random.randint(1, 500)}",
        ms=random.randint(5, 30000),
        svc=random.choice(SERVICES),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lines", type=int, default=100_000)
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text")
    parser.add_argument("--days", type=int, default=14, help="time span covered by the logs")
    parser.add_argument("--invalid-ratio", type=float, default=0.005)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc) - timedelta(days=args.days)
    step = timedelta(days=args.days) / max(args.lines, 1)

    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        if args.format == "csv":
            writer.writerow(["timestamp", "level", "service", "message"])
        for i in range(args.lines):
            if random.random() < args.invalid_ratio:
                f.write("@@ corrupted line without structure @@\n")
                continue
            ts = start + step * i
            level = random.choices(LEVELS, LEVEL_WEIGHTS)[0]
            svc = random.choice(SERVICES)
            msg = render(level, svc)
            if args.format == "csv":
                writer.writerow([ts.isoformat(), level, svc, msg])
            elif args.format == "json":
                f.write(json.dumps({"timestamp": ts.isoformat(), "level": level, "service": svc, "message": msg}) + "\n")
            else:
                f.write(f"{ts.isoformat()} {level} [{svc}] {msg}\n")

    print(f"wrote {args.lines} lines to {args.out}")


if __name__ == "__main__":
    main()
