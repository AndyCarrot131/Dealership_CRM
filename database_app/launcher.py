"""
database.exe launcher: manages the lifecycle of a portable PostgreSQL instance.

Responsibilities:
  1. On first run: initdb to create the cluster in pgdata/
  2. Every run: pg_ctl start → wait for ready → enter system tray loop
  3. On exit: pg_ctl stop

Phase 4 will wire the system tray icon and full config here.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

_BASE = Path(__file__).parent
_PGDATA = _BASE / "pgdata"
_PG_BIN = _BASE / "pgsql" / "bin"
_PG_CTL = _PG_BIN / "pg_ctl"
_INITDB = _PG_BIN / "initdb"
_PGPORT = 5432
_PGUSER = "crm_app"
_PGDB = "dealer_crm"
_LOG = _BASE / "postgres.log"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), check=True, capture_output=True, text=True)


def initdb() -> None:
    if not (_PGDATA / "PG_VERSION").exists():
        _run(str(_INITDB), "-D", str(_PGDATA), "-U", _PGUSER, "--encoding=UTF8", "--auth=scram-sha-256")


def start() -> None:
    _run(str(_PG_CTL), "-D", str(_PGDATA), "-l", str(_LOG), "-o", f"-p {_PGPORT}", "start")
    time.sleep(2)


def create_db() -> None:
    try:
        _run(str(_PG_BIN / "createdb"), "-U", _PGUSER, "-p", str(_PGPORT), _PGDB)
    except subprocess.CalledProcessError:
        pass  # database already exists


def stop() -> None:
    try:
        _run(str(_PG_CTL), "-D", str(_PGDATA), "stop")
    except subprocess.CalledProcessError:
        pass


if __name__ == "__main__":
    try:
        initdb()
        start()
        create_db()
        print(f"PostgreSQL ready on port {_PGPORT}. Press Ctrl+C to stop.")
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        stop()
        sys.exit(0)
