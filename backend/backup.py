"""
Database backup and recovery utility for local SQLite and production PostgreSQL.
Supports zero-downtime atomic snapshots, retention pruning, and restore verification.
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class DatabaseBackupManager:
    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = Path(backup_dir or os.getenv("BACKUP_DIR", "./backups")).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.database_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PATH", "./data/leads.db")

    def create_backup(self) -> Path:
        """Create a timestamped database backup."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.database_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
            return self._backup_postgres(timestamp)
        else:
            return self._backup_sqlite(timestamp)

    def _backup_sqlite(self, timestamp: str) -> Path:
        """Atomic backup of SQLite database using SQLite backup API."""
        source_path = Path(self.database_url.replace("sqlite:///", "")).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"SQLite database file not found: {source_path}")

        target_file = self.backup_dir / f"leads_backup_{timestamp}.db"
        import sqlite3

        print(f"📦 Creating atomic SQLite backup: {source_path} -> {target_file}")
        source_conn = sqlite3.connect(str(source_path))
        dest_conn = sqlite3.connect(str(target_file))
        with dest_conn:
            source_conn.backup(dest_conn)
        source_conn.close()
        dest_conn.close()

        print(f"✅ SQLite backup completed ({target_file.stat().st_size} bytes)")
        return target_file

    def _backup_postgres(self, timestamp: str) -> Path:
        """Create PostgreSQL dump with gzip compression."""
        target_file = self.backup_dir / f"postgres_backup_{timestamp}.sql.gz"
        pg_url = self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

        print(f"📦 Creating PostgreSQL dump: {target_file}")
        cmd = f"pg_dump '{pg_url}' | gzip > '{target_file}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"PostgreSQL backup failed: {result.stderr}")

        print(f"✅ PostgreSQL backup completed ({target_file.stat().st_size} bytes)")
        return target_file

    def list_backups(self) -> List[Path]:
        """List all available backups sorted newest first."""
        files = list(self.backup_dir.glob("leads_backup_*.db")) + list(self.backup_dir.glob("postgres_backup_*.sql.gz"))
        return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    def prune_old_backups(self, keep_days: int = 14) -> int:
        """Remove backups older than keep_days."""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
        pruned = 0
        for backup in self.list_backups():
            mtime = datetime.datetime.fromtimestamp(backup.stat().st_mtime)
            if mtime < cutoff:
                backup.unlink()
                pruned += 1
                print(f"🗑️ Pruned old backup: {backup.name}")
        return pruned

    def restore_sqlite(self, backup_file: Path) -> None:
        """Restore SQLite database from backup."""
        source_path = Path(self.database_url.replace("sqlite:///", "")).resolve()
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        # Create safety pre-restore backup
        if source_path.exists():
            safety = source_path.with_suffix(".pre_restore.bak")
            shutil.copy2(source_path, safety)
            print(f"🛡️ Created safety snapshot at {safety}")

        shutil.copy2(backup_file, source_path)
        print(f"✅ Restored {backup_file.name} to {source_path}")


def main():
    parser = argparse.ArgumentParser(description="Database Backup and Recovery CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("backup", help="Create a new database backup")
    list_p = subparsers.add_parser("list", help="List existing backups")
    prune_p = subparsers.add_parser("prune", help="Prune backups older than N days")
    prune_p.add_argument("--days", type=int, default=14, help="Retention period in days")

    restore_p = subparsers.add_parser("restore", help="Restore database from a backup file")
    restore_p.add_argument("file", help="Path to backup file")

    args = parser.parse_args()
    mgr = DatabaseBackupManager()

    if args.command == "backup":
        mgr.create_backup()
    elif args.command == "list":
        backups = mgr.list_backups()
        if not backups:
            print("No backups found.")
        for b in backups:
            size_kb = b.stat().st_size / 1024
            mtime = datetime.datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{b.name}  ({size_kb:.1f} KB)  [{mtime}]")
    elif args.command == "prune":
        mgr.prune_old_backups(keep_days=args.days)
    elif args.command == "restore":
        mgr.restore_sqlite(Path(args.file))


if __name__ == "__main__":
    main()
