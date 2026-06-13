#!/usr/bin/env python
"""
Postgres backup tool. Dumps the configured database, gzips it, and uploads to R2
under backups/postgres/<host>-<db>-<UTC-iso>.sql.gz.

Subcommands:
    backup   Create a new backup and upload to R2.
    list     List backups in R2 newest-first.
    restore  Download a backup and restore it (use latest or pass --key).
    prune    Delete backups older than --days (default 30) from R2.

Reads DATABASE_NAME/USER/PASSWORD/HOST/PORT and R2_* from .env (or environment).
Requires pg_dump and psql on PATH for backup/restore.
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.client import Config
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

R2_PREFIX = "backups/postgres/"


def _require(*names: str) -> dict:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)} (set them in .env)")
    return {n: os.environ[n] for n in names}


def _db_config() -> dict:
    cfg = _require("DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD")
    return {
        "name": cfg["DATABASE_NAME"],
        "user": cfg["DATABASE_USER"],
        "password": cfg["DATABASE_PASSWORD"],
        "host": os.environ.get("DATABASE_HOST", "localhost"),
        "port": os.environ.get("DATABASE_PORT", "5432"),
    }


def r2_client_and_bucket():
    cfg = _require("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    return client, cfg["R2_BUCKET_NAME"]


def _pg_env(db: dict) -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"]
    return env


def cmd_backup(args: argparse.Namespace) -> int:
    if not shutil.which("pg_dump"):
        sys.exit("pg_dump not on PATH — install PostgreSQL client tools first.")

    db = _db_config()
    client, bucket = r2_client_and_bucket()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{R2_PREFIX}{db['host']}-{db['name']}-{ts}.sql.gz"

    print(f"Dumping {db['name']} from {db['host']}:{db['port']}…")
    proc = subprocess.Popen(
        [
            "pg_dump",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["name"],
            "--no-owner",
            "--no-privileges",
            "--clean",
            "--if-exists",
        ],
        stdout=subprocess.PIPE,
        env=_pg_env(db),
    )

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        shutil.copyfileobj(proc.stdout, gz)
    proc.wait()
    if proc.returncode != 0:
        sys.exit(f"pg_dump exited {proc.returncode}")

    size_mb = buf.tell() / (1024 * 1024)
    buf.seek(0)
    print(f"Uploading {key} ({size_mb:.1f} MB) to R2…")
    client.upload_fileobj(buf, bucket, key)
    print("Done.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    client, bucket = r2_client_and_bucket()
    paginator = client.get_paginator("list_objects_v2")
    items = []
    for page in paginator.paginate(Bucket=bucket, Prefix=R2_PREFIX):
        items.extend(page.get("Contents", []))
    items.sort(key=lambda o: o["LastModified"], reverse=True)
    for o in items[: args.limit]:
        print(f"{o['LastModified'].isoformat()}  {o['Size']/(1024*1024):>8.1f} MB  {o['Key']}")
    if not items:
        print("(no backups found)")
    return 0


def _latest_key(client, bucket: str) -> str:
    items = client.list_objects_v2(Bucket=bucket, Prefix=R2_PREFIX).get("Contents", [])
    if not items:
        sys.exit("No backups found in R2.")
    return max(items, key=lambda o: o["LastModified"])["Key"]


def cmd_restore(args: argparse.Namespace) -> int:
    if not shutil.which("psql"):
        sys.exit("psql not on PATH — install PostgreSQL client tools first.")

    db = _db_config()
    client, bucket = r2_client_and_bucket()
    key = args.key or _latest_key(client, bucket)

    if not args.yes:
        print(f"About to restore {key} into {db['name']}@{db['host']} — existing data will be dropped.")
        if input("Type 'yes' to continue: ").strip() != "yes":
            return 1

    print(f"Downloading {key}…")
    buf = io.BytesIO()
    client.download_fileobj(bucket, key, buf)
    buf.seek(0)

    print("Restoring…")
    proc = subprocess.Popen(
        [
            "psql",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["name"],
            "-v", "ON_ERROR_STOP=1",
        ],
        stdin=subprocess.PIPE,
        env=_pg_env(db),
    )
    with gzip.GzipFile(fileobj=buf, mode="rb") as gz:
        shutil.copyfileobj(gz, proc.stdin)
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        sys.exit(f"psql exited {proc.returncode}")
    print("Restored.")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    client, bucket = r2_client_and_bucket()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=R2_PREFIX):
        for obj in page.get("Contents", []):
            if obj["LastModified"] < cutoff:
                if args.dry_run:
                    print(f"would delete {obj['Key']}")
                else:
                    client.delete_object(Bucket=bucket, Key=obj["Key"])
                    print(f"deleted {obj['Key']}")
                deleted += 1
    print(f"{'Would delete' if args.dry_run else 'Deleted'} {deleted} backups older than {args.days} days.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("backup", help="Create a backup").set_defaults(func=cmd_backup)

    ls = sub.add_parser("list", help="List recent backups")
    ls.add_argument("--limit", type=int, default=20)
    ls.set_defaults(func=cmd_list)

    rs = sub.add_parser("restore", help="Restore from R2")
    rs.add_argument("--key", help="R2 key to restore (default: latest)")
    rs.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    rs.set_defaults(func=cmd_restore)

    pr = sub.add_parser("prune", help="Delete backups older than N days")
    pr.add_argument("--days", type=int, default=30)
    pr.add_argument("--dry-run", action="store_true")
    pr.set_defaults(func=cmd_prune)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
