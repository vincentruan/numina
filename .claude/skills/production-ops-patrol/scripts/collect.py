#!/usr/bin/env python3
"""
collect.py — Production patrol data collector.

SSHes into the production server and gathers all patrol dimensions (A-G).
Outputs a single JSON object to stdout.

Usage:
    python collect.py --window-minutes 60

Requires: .claude/deploy.env sourced in the calling shell.
All commands are READ-ONLY on the production server (no mutations).
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def _ssh_cmd() -> str:
    """Build SSH base command string using deploy.env variables."""
    host = os.environ.get("DEPLOY_SSH_HOST", "")
    port = os.environ.get("DEPLOY_SSH_PORT", "22")
    user = os.environ.get("DEPLOY_SSH_USER", "")
    if not all([host, user]):
        print("ERROR: DEPLOY_SSH_HOST and DEPLOY_SSH_USER must be set", file=sys.stderr)
        sys.exit(1)
    return f'ssh -p {port} -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new {user}@{host}'


def _run_ssh(remote_cmd: str, timeout: int = 30) -> dict:
    """Execute a command on the production server via SSH.

    Returns dict with 'stdout', 'stderr', 'returncode'.
    The remote command is sent via stdin to avoid shell quoting issues.
    """
    ssh_base = _ssh_cmd()
    full_cmd = f'{ssh_base} bash -s'
    try:
        result = subprocess.run(
            full_cmd, shell=True, input=remote_cmd,
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "SSH command timed out", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


def collect_docker_status(remote_dir: str) -> dict:
    """Dimension A: Service and Docker status."""
    compose = "sudo docker compose -f docker-compose.production.yml"
    cmd = f'cd {remote_dir} && {compose} ps --format "{{{{.Name}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}" 2>&1'
    result = _run_ssh(cmd)
    return {
        "dimension": "A",
        "name": "docker_status",
        "raw": result["stdout"],
        "success": result["returncode"] == 0,
        "error": result["stderr"] if result["returncode"] != 0 else None,
    }


def collect_anomaly_logs(window_minutes: int) -> dict:
    """Dimension B: Anomaly logs in the patrol window."""
    since = f'{window_minutes}m'
    services = ["backend", "agent", "scheduler_worker", "nginx"]
    results = {}
    for svc in services:
        # Use docker logs (not compose logs) for more control
        container = f'numina-{svc}' if svc != "scheduler_worker" else "numina-scheduler-worker"
        cmd = f'sudo docker logs --since {since} {container} 2>&1 | grep -iE "ERROR|WARN|CRITICAL|FATAL" | tail -100'
        results[svc] = _run_ssh(cmd, timeout=20)
    return {
        "dimension": "B",
        "name": "anomaly_logs",
        "window_minutes": window_minutes,
        "services": {
            svc: {
                "lines": r["stdout"].split("\n") if r["stdout"] else [],
                "count": len(r["stdout"].split("\n")) if r["stdout"] and r["stdout"] != "" else 0,
                "error": r["stderr"] if r["returncode"] != 0 else None,
            }
            for svc, r in results.items()
        },
    }


def collect_tracebacks(window_minutes: int) -> dict:
    """Dimension C: Python traceback / exception analysis."""
    since = f'{window_minutes}m'
    # Collect from backend and agent (the Python services)
    results = {}
    for svc in ["backend", "agent", "scheduler_worker"]:
        container = f'numina-{svc}' if svc != "scheduler_worker" else "numina-scheduler-worker"
        # Get traceback blocks: look for Traceback lines and following context
        cmd = f'''sudo docker logs --since {since} {container} 2>&1 | \
grep -A 10 "Traceback" | tail -200'''
        results[svc] = _run_ssh(cmd, timeout=20)
    return {
        "dimension": "C",
        "name": "tracebacks",
        "window_minutes": window_minutes,
        "services": {
            svc: {
                "raw": r["stdout"],
                "count": r["stdout"].count("Traceback") if r["stdout"] else 0,
                "error": r["stderr"] if r["returncode"] != 0 else None,
            }
            for svc, r in results.items()
        },
    }


def collect_http_health() -> dict:
    """Dimension D: HTTP health / 5xx check."""
    checks = {}

    # Backend health
    checks["backend"] = _run_ssh(
        'curl -sk -o /dev/null -w "%{http_code}" --max-time 5 https://localhost/api/health'
    )

    # Agent health (via nginx proxy, container has no curl)
    checks["agent"] = _run_ssh(
        'curl -sk -o /dev/null -w "%{http_code}" --max-time 5 https://localhost/agent/health'
    )

    # Scheduler worker health (via nginx proxy, container has no curl)
    checks["scheduler_worker"] = _run_ssh(
        'curl -sk -o /dev/null -w "%{http_code}" --max-time 5 https://localhost/worker/health'
    )

    # Frontend
    checks["frontend"] = _run_ssh(
        'curl -sk -o /dev/null -w "%{http_code}" --max-time 5 https://localhost/'
    )

    # 5xx count from nginx access log (last hour)
    checks["nginx_5xx"] = _run_ssh(
        'sudo docker logs --since 60m numina-nginx 2>&1 | grep -cE "HTTP/[0-9.]+" 5[0-9]{2} | tail -1 || echo 0'
    )

    return {
        "dimension": "D",
        "name": "http_health",
        "checks": {
            name: {
                "status_code": r["stdout"],
                "success": r["returncode"] == 0 and r["stdout"] in ("200", "301", "302"),
            }
            for name, r in checks.items()
            if name != "nginx_5xx"
        },
        "nginx_5xx_count": checks["nginx_5xx"]["stdout"] if checks["nginx_5xx"]["returncode"] == 0 else "unknown",
    }


def collect_db_readonly() -> dict:
    """Dimension E: Database read-only business data check.

    ONLY read-only queries. Uses docker exec with the app's venv Python
    (which has sqlalchemy) inside the backend container.
    Base64-encodes the Python script to avoid shell quoting issues.
    """
    import base64

    queries = {
        "connection_test": "SELECT 1",
        "user_count": "SELECT COUNT(*) FROM users",
        "family_count": "SELECT COUNT(*) FROM families",
        "recent_active_users": "SELECT COUNT(*) FROM users WHERE updated_at > NOW() - INTERVAL '1 day'",
        "alembic_version": "SELECT version_num FROM alembic_version LIMIT 1",
        "db_size": "SELECT pg_size_pretty(pg_database_size(current_database()))",
    }

    results = {}
    for name, sql in queries.items():
        py_script = (
            "import os\n"
            "from sqlalchemy import create_engine, text\n"
            "e = create_engine(os.environ['DATABASE_URL'])\n"
            "with e.connect() as c:\n"
            f"    r = c.execute(text({sql!r}))\n"
            "    print(r.scalar())\n"
        )
        b64 = base64.b64encode(py_script.encode()).decode()
        cmd = f"echo {b64} | base64 -d | sudo docker exec -i numina-backend /app/.venv/bin/python"
        results[name] = _run_ssh(cmd, timeout=15)

    return {
        "dimension": "E",
        "name": "db_readonly",
        "queries": {
            name: {
                "value": r["stdout"],
                "success": r["returncode"] == 0,
                "error": r["stderr"] if r["returncode"] != 0 else None,
            }
            for name, r in results.items()
        },
    }


def collect_resource_usage() -> dict:
    """Dimension F: CPU / memory / restart / OOM / GC."""
    # docker stats (one snapshot, no stream)
    stats = _run_ssh(
        'sudo docker stats --no-stream --format "{{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.MemPerc}}" 2>&1'
    )

    # Restart counts + OOMKilled
    containers = [
        "numina-backend", "numina-agent", "numina-scheduler-worker",
        "numina-frontend-main", "numina-frontend-child", "numina-nginx",
    ]
    inspect_results = {}
    for c in containers:
        inspect_results[c] = _run_ssh(
            f'sudo docker inspect {c} --format "{{{{.RestartCount}}}}\\t{{{{.State.OOMKilled}}}}\\t{{{{.State.Status}}}}\\t{{{{.State.ExitCode}}}}" 2>&1'
        )

    return {
        "dimension": "F",
        "name": "resource_usage",
        "stats_raw": stats["stdout"],
        "containers": {
            c: {
                "raw": r["stdout"],
                "success": r["returncode"] == 0,
            }
            for c, r in inspect_results.items()
        },
    }


def collect_revision() -> dict:
    """Dimension G: Current production code revision / Docker image revision."""
    # Image digests
    images_cmd = 'sudo docker inspect --format "{{.Name}}\\t{{.Config.Image}}\\t{{.Image}}" $(sudo docker ps -q) 2>&1'
    images = _run_ssh(images_cmd)

    # Backend image ID
    backend_image = _run_ssh(
        'sudo docker inspect numina-backend --format "{{.Config.Image}}" 2>&1'
    )

    # Agent image ID
    agent_image = _run_ssh(
        'sudo docker inspect numina-agent --format "{{.Config.Image}}" 2>&1'
    )

    return {
        "dimension": "G",
        "name": "revision",
        "backend_image": backend_image["stdout"],
        "agent_image": agent_image["stdout"],
        "all_images_raw": images["stdout"],
    }


def collect(window_minutes: int = 60) -> dict:
    """Run full data collection across all dimensions."""
    remote_dir = os.environ.get("DEPLOY_REMOTE_DIR", "~/data/numina")
    now = datetime.now(timezone.utc).isoformat()

    patrol = {
        "patrol_id": f"patrol-{int(datetime.now(timezone.utc).timestamp())}",
        "timestamp": now,
        "window_minutes": window_minutes,
        "remote_dir": remote_dir,
    }

    # Execute all collectors
    patrol["dimensions"] = {
        "A_docker_status": collect_docker_status(remote_dir),
        "B_anomaly_logs": collect_anomaly_logs(window_minutes),
        "C_tracebacks": collect_tracebacks(window_minutes),
        "D_http_health": collect_http_health(),
        "E_db_readonly": collect_db_readonly(),
        "F_resource_usage": collect_resource_usage(),
        "G_revision": collect_revision(),
    }

    return patrol


def main():
    parser = argparse.ArgumentParser(description="Production patrol data collector")
    parser.add_argument("--window-minutes", type=int, default=60,
                        help="Log lookback window in minutes")
    args = parser.parse_args()

    data = collect(window_minutes=args.window_minutes)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
