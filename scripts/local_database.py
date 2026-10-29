"""Create an isolated PostgreSQL development cluster for this project."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", default=r"C:\Program Files\PostgreSQL\18\bin")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    binaries = Path(args.bin)
    cluster = ROOT / "data" / "postgres"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def run(name: str, *arguments: str, env: dict[str, str] | None = None) -> None:
        subprocess.run(
            [str(binaries / name), *arguments], check=True, env=env,
            creationflags=flags,
        )

    if args.stop:
        run("pg_ctl", "-D", str(cluster), "stop", "-m", "fast")
        return

    if not (cluster / "PG_VERSION").exists():
        if (ROOT / ".env").exists():
            raise SystemExit("An .env already exists. Configure its DATABASE_URL instead of replacing it.")
        cluster.parent.mkdir(exist_ok=True)
        password = secrets.token_urlsafe(32)
        temporary = cluster.parent / ".postgres-password"
        temporary.write_text(password, encoding="utf-8")
        try:
            run("initdb", "-D", str(cluster), "-U", "lucky_lounge", "-E", "UTF8", "--locale=C",
                "--auth-host=scram-sha-256", "--auth-local=scram-sha-256", "--pwfile", str(temporary))
        finally:
            temporary.unlink(missing_ok=True)
        (ROOT / ".env").write_text(
            f"DATABASE_URL=postgresql+asyncpg://lucky_lounge:{password}@127.0.0.1:5434/lucky_lounge\n"
            "API_PROXY_TARGET=http://127.0.0.1:8000\nVITE_API_BASE=/api\n"
            "ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000\nCOOKIE_SECURE=false\n",
            encoding="utf-8",
        )
    from dotenv import dotenv_values

    config = dotenv_values(ROOT / ".env")
    from urllib.parse import urlparse

    url = urlparse(config["DATABASE_URL"].replace("postgresql+asyncpg", "postgresql"))
    status = subprocess.run([str(binaries / "pg_ctl"), "-D", str(cluster), "status"],
                            capture_output=True, creationflags=flags)
    if status.returncode:
        run("pg_ctl", "-D", str(cluster), "-l", str(ROOT / "data" / "postgres.log"),
            "-o", "-h 127.0.0.1 -p 5434", "start")
    environment = {**os.environ, "PGPASSWORD": url.password or ""}
    exists = subprocess.run(
        [str(binaries / "psql"), "-h", "127.0.0.1", "-p", "5434", "-U", "lucky_lounge",
         "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname='lucky_lounge'"],
        env=environment, capture_output=True, text=True, check=True, creationflags=flags,
    )
    if exists.stdout.strip() != "1":
        run("createdb", "-h", "127.0.0.1", "-p", "5434", "-U", "lucky_lounge", "lucky_lounge", env=environment)
    print("Project PostgreSQL is ready on 127.0.0.1:5434. Configuration is saved in .env.")


if __name__ == "__main__":
    main()
