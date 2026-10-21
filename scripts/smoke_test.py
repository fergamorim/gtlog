"""End-to-end smoke test against a running stack (docker compose up).

Uploads a log file, waits for the import to finish and checks that the API and the web app
serve consistent data. Exits non-zero on the first failure. Standard library only.

Usage:
    python scripts/generate_logs.py --lines 5000 --seed 42 --out samples/ci.log
    docker compose up -d --build
    python scripts/smoke_test.py --log samples/ci.log
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

WEB_ORIGIN = "http://localhost:5173"


def fail(message: str) -> None:
    print(f"FALHOU: {message}", file=sys.stderr)
    sys.exit(1)


def check(condition: bool, message: str) -> None:
    if not condition:
        fail(message)
    print(f"ok - {message}")


def request(url: str, data: bytes = None, headers: dict = None, method: str = None):
    """Return (status, headers, body) without raising on HTTP errors."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def get_json(url: str):
    status, _, body = request(url)
    if status != 200:
        fail(f"GET {url} respondeu {status}: {body[:300]!r}")
    return json.loads(body)


def wait_until_healthy(api: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _, body = request(f"{api}/health")
            if status == 200 and json.loads(body).get("status") == "ok":
                print("ok - API saudável e conectada ao banco")
                return
        except (urllib.error.URLError, ConnectionError, ValueError):
            pass
        time.sleep(2)
    fail(f"API não respondeu /health em {timeout:.0f}s")


def upload(api: str, path: str) -> dict:
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    status, _, resp = request(
        f"{api}/imports", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    check(status == 202, f"POST /imports aceito (status {status})")
    return json.loads(resp)


def wait_for_import(api: str, job_id: int, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = get_json(f"{api}/imports/{job_id}")
        if job["status"] == "DONE":
            return job
        if job["status"] == "FAILED":
            fail(f"importação {job_id} falhou: {job.get('error')}")
        time.sleep(1)
    fail(f"importação {job_id} não terminou em {timeout:.0f}s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default=WEB_ORIGIN)
    parser.add_argument("--log", required=True, help="arquivo de log a importar")
    parser.add_argument("--timeout", type=float, default=120, help="segundos de espera por etapa")
    args = parser.parse_args()

    with open(args.log, "rb") as f:
        expected_lines = sum(1 for line in f if line.strip())

    wait_until_healthy(args.api, args.timeout)
    fail("falha proposital: PR de teste da proteção de branch, não mergear")

    job = upload(args.api, args.log)
    job = wait_for_import(args.api, job["id"], args.timeout)
    total = job["total_lines"]
    check(total == expected_lines, f"total_lines = {total} (esperado {expected_lines})")
    check(job["parsed_lines"] > 0, f"parsed_lines = {job['parsed_lines']}")
    check(
        job["parsed_lines"] + job["invalid_lines"] == job["total_lines"],
        "parsed_lines + invalid_lines = total_lines",
    )

    imports = get_json(f"{args.api}/imports")
    check(any(i["id"] == job["id"] for i in imports), "importação aparece em GET /imports")

    scope = f"import_id={job['id']}"
    count = get_json(f"{args.api}/logs/count?{scope}")["total"]
    check(count == job["parsed_lines"], f"GET /logs/count = {count}")

    page = get_json(f"{args.api}/logs?{scope}&limit=50")
    check(len(page["items"]) == min(50, count), f"GET /logs trouxe {len(page['items'])} registros")
    if count > 50:
        check(page["next_cursor"] is not None, "GET /logs devolve next_cursor")
        nxt = get_json(f"{args.api}/logs?{scope}&limit=50&cursor={page['next_cursor']}")
        first_ids = {item["id"] for item in page["items"]}
        check(
            nxt["items"] and not first_ids & {item["id"] for item in nxt["items"]},
            "segunda página por cursor sem repetir registros",
        )

    errors = get_json(f"{args.api}/logs/count?{scope}&level=ERROR&level=CRITICAL")["total"]
    stats = get_json(f"{args.api}/stats?{scope}")
    check(stats["total"] == count, f"GET /stats total = {stats['total']}")
    check(sum(stats["by_level"].values()) == count, "soma de by_level = total")
    level_errors = stats["by_level"].get("ERROR", 0) + stats["by_level"].get("CRITICAL", 0)
    check(level_errors == errors, f"erros em /stats ({level_errors}) = filtro de nível em /logs ({errors})")

    status, headers, _ = request(f"{args.api}/logs?limit=1", headers={"Origin": args.web})
    check(
        status == 200 and headers.get("access-control-allow-origin") == args.web,
        "CORS libera o frontend",
    )

    status, _, body = request(f"{args.api}/logs?level=NOPE")
    detail = json.loads(body).get("detail", "")
    check(status == 422 and "'level'" in detail, "filtro inválido responde 422 em português")

    for path in ("/dashboard", "/logs"):
        status, _, body = request(f"{args.web}{path}")
        check(status == 200 and b'id="root"' in body, f"web serve o app em {path}")

    print("Smoke test concluído.")


if __name__ == "__main__":
    main()
