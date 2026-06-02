from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.engine import make_url

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackupFile:
    name: str
    path: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class BackupResult:
    file: BackupFile
    deleted_files: list[str]


def backup_directory() -> Path:
    path = Path(settings.backup_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_timezone() -> timezone | ZoneInfo:
    try:
        return ZoneInfo(settings.backup_timezone)
    except ZoneInfoNotFoundError:
        if settings.backup_timezone == "Asia/Shanghai":
            return timezone(timedelta(hours=8), name="Asia/Shanghai")
        logger.warning("Unknown backup timezone %s, falling back to UTC", settings.backup_timezone)
        return timezone.utc


def schedule_times() -> list[time]:
    parsed: list[time] = []
    for raw_value in settings.backup_schedule_times.split(","):
        value = raw_value.strip()
        if not value:
            continue
        hour_text, minute_text = value.split(":", 1)
        parsed.append(time(hour=int(hour_text), minute=int(minute_text), tzinfo=backup_timezone()))
    return sorted(parsed) or [
        time(hour=9, tzinfo=backup_timezone()),
        time(hour=12, tzinfo=backup_timezone()),
        time(hour=18, tzinfo=backup_timezone()),
    ]


def next_backup_at(now: datetime | None = None) -> datetime:
    tz = backup_timezone()
    current = now.astimezone(tz) if now else datetime.now(tz)
    for scheduled_time in schedule_times():
        candidate = datetime.combine(current.date(), scheduled_time).astimezone(tz)
        if candidate > current:
            return candidate
    tomorrow = current.date() + timedelta(days=1)
    return datetime.combine(tomorrow, schedule_times()[0]).astimezone(tz)


def list_backup_files() -> list[BackupFile]:
    files: list[BackupFile] = []
    for path in backup_directory().glob("backup_*.backup"):
        stat = path.stat()
        files.append(
            BackupFile(
                name=path.name,
                path=str(path),
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=backup_timezone()).isoformat(),
            )
        )
    return sorted(files, key=lambda item: item.modified_at, reverse=True)


def cleanup_old_backups(now: datetime | None = None) -> list[str]:
    retention_days = max(settings.backup_retention_days, 1)
    cutoff = (now.astimezone(backup_timezone()) if now else datetime.now(backup_timezone())) - timedelta(days=retention_days)
    deleted: list[str] = []
    for path in backup_directory().glob("backup_*.backup"):
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=backup_timezone())
        if modified_at < cutoff:
            path.unlink()
            deleted.append(path.name)
    return deleted


def _pg_dump_command(output_path: Path) -> tuple[list[str], dict[str, str]]:
    if shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump is not installed in the backend container. Rebuild the backend image after the Dockerfile update.")

    url = make_url(settings.database_url)
    if url.database is None:
        raise RuntimeError("DATABASE_URL does not include a database name.")
    if url.username is None:
        raise RuntimeError("DATABASE_URL does not include a database user.")

    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password

    command = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(output_path),
        "-h",
        url.host or "localhost",
        "-p",
        str(url.port or 5432),
        "-U",
        url.username,
        "-d",
        url.database,
    ]
    return command, env


def run_database_backup() -> BackupResult:
    directory = backup_directory()
    started_at = datetime.now(backup_timezone())
    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    final_path = directory / f"backup_{stamp}.backup"
    temp_path = directory / f"backup_{stamp}.backup.tmp"

    command, env = _pg_dump_command(temp_path)
    try:
        completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False, timeout=60 * 20)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "pg_dump failed.")
        temp_path.replace(final_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    deleted = cleanup_old_backups(started_at)
    stat = final_path.stat()
    result = BackupResult(
        file=BackupFile(
            name=final_path.name,
            path=str(final_path),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=backup_timezone()).isoformat(),
        ),
        deleted_files=deleted,
    )
    logger.info("Database backup created: %s", result.file.path)
    return result


class BackupScheduler:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if not settings.backup_scheduler_enabled:
            logger.info("Backup scheduler is disabled.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="database-backup-scheduler", daemon=True)
        self._thread.start()
        logger.info("Backup scheduler started. Next backup at %s", next_backup_at().isoformat())

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def status(self) -> dict[str, object]:
        return {
            "enabled": settings.backup_scheduler_enabled,
            "timezone": settings.backup_timezone,
            "schedule_times": [item.strftime("%H:%M") for item in schedule_times()],
            "retention_days": settings.backup_retention_days,
            "backup_directory": str(backup_directory()),
            "next_backup_at": next_backup_at().isoformat(),
            "running": bool(self._thread and self._thread.is_alive()),
        }

    def _run(self) -> None:
        cleanup_old_backups()
        while not self._stop_event.is_set():
            wait_seconds = max((next_backup_at() - datetime.now(backup_timezone())).total_seconds(), 1)
            if self._stop_event.wait(wait_seconds):
                break
            try:
                run_database_backup()
            except Exception:
                logger.exception("Scheduled database backup failed.")


backup_scheduler = BackupScheduler()


def backup_result_to_dict(result: BackupResult) -> dict[str, object]:
    return {"file": asdict(result.file), "deleted_files": result.deleted_files}
