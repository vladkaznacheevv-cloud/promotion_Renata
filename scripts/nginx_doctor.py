from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = PROJECT_ROOT / "compose.prod.yml"


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
    if not cmd:
        return None
    if shutil.which(cmd[0]) is None:
        print(f"skipped: command not found: {cmd[0]}")
        return None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        print(f"skipped: command failed to start ({cmd[0]}): {exc.__class__.__name__}")
        return None


def _print_header(title: str) -> None:
    print(f"\n== {title} ==")


def _check_ports_with_docker_ps() -> None:
    _print_header("docker ps ports check")
    res = _run(["docker", "ps", "--format", "table {{.Names}}\t{{.Ports}}"])
    if res is None:
        return
    if res.returncode != 0:
        print("skipped: docker ps failed")
        if res.stderr:
            print(res.stderr.strip())
        return
    output = res.stdout.strip()
    print(output)
    has_web_loopback = "127.0.0.1:8000->8000/tcp" in output
    has_front_loopback = "127.0.0.1:8080->80/tcp" in output
    has_front_public_80 = "0.0.0.0:80->80/tcp" in output or ":::80->80/tcp" in output
    print(
        f"summary: web_loopback_8000={has_web_loopback} "
        f"frontend_loopback_8080={has_front_loopback} frontend_public_80={has_front_public_80}"
    )


def _check_ports_with_ss() -> None:
    _print_header("ss listen sockets check")
    res = _run(["ss", "-lntp"])
    if res is None:
        return
    if res.returncode != 0:
        print("skipped: ss -lntp failed")
        if res.stderr:
            print(res.stderr.strip())
        return
    lines = [ln for ln in (res.stdout or "").splitlines() if any(p in ln for p in (":80", ":443", ":8000", ":8080"))]
    if not lines:
        print("no matching sockets found")
    else:
        for line in lines:
            print(line)
    print("expected: 127.0.0.1:8000 and 127.0.0.1:8080 are listening; :80/:443 reserved for host nginx")


def _print_compose_commands() -> None:
    _print_header("compose checks (copy-paste)")
    print(f"docker compose -f {COMPOSE_FILE.as_posix()} config")
    print(
        f"docker compose -f {COMPOSE_FILE.as_posix()} config | "
        "sed -n '/frontend:/,/healthcheck:/p' | sed -n '/ports:/,/healthcheck:/p'"
    )
    print(
        f"docker compose -f {COMPOSE_FILE.as_posix()} config | "
        "sed -n '/web:/,/healthcheck:/p' | sed -n '/ports:/,/healthcheck:/p'"
    )


def _print_nginx_install_commands() -> None:
    _print_header("host nginx install/update (copy-paste)")
    print("sudo cp deploy/nginx/renatapromotion.conf /etc/nginx/sites-available/renatapromotion.conf")
    print("sudo cp deploy/nginx/limits.conf /etc/nginx/conf.d/limits.conf")
    print(
        "sudo ln -sfn /etc/nginx/sites-available/renatapromotion.conf "
        "/etc/nginx/sites-enabled/renatapromotion.conf"
    )
    print("sudo nginx -t && sudo systemctl reload nginx")
    print("sh scripts/nginx_header_check.sh")


def _print_curl_commands() -> None:
    _print_header("curl checks via host nginx (copy-paste)")
    print("# CRM vhost (frontend + /api proxy)")
    print("curl -i -H 'Host: crm.<domain>' http://127.0.0.1/")
    print("curl -i -H 'Host: crm.<domain>' http://127.0.0.1/api/healthz")
    print("curl -i -H 'Host: crm.<domain>' http://127.0.0.1/api/readyz")
    print("")
    print("# API vhost")
    print("curl -i -H 'Host: api.<domain>' http://127.0.0.1/healthz")
    print("curl -i -H 'Host: api.<domain>' http://127.0.0.1/readyz")
    print("curl -i -H 'Host: api.<domain>' http://127.0.0.1/api/healthz   # alias -> /healthz")
    print("curl -i -H 'Host: api.<domain>' http://127.0.0.1/api/readyz    # alias -> /readyz")


def _print_health_note() -> None:
    _print_header("health endpoint note")
    print("Primary backend health endpoints are /healthz and /readyz on FastAPI.")
    print("If host nginx is configured only with API prefix routing, /api/healthz may return 404 unless alias is added.")
    print("Template deploy/nginx/renatapromotion.conf includes aliases:")
    print("  /api/healthz -> /healthz")
    print("  /api/readyz  -> /readyz")


def main() -> int:
    print("nginx_doctor: checks and copy-paste diagnostics (no systemctl actions)")
    print(f"compose_file={COMPOSE_FILE.as_posix()}")
    _check_ports_with_docker_ps()
    _check_ports_with_ss()
    _print_compose_commands()
    _print_nginx_install_commands()
    _print_curl_commands()
    _print_health_note()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
