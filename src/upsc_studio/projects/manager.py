"""Safe project lifecycle, backup, and restoration helpers."""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from upsc_studio.core.paths import ensure_within_base, sanitize_slug
from upsc_studio.db.schemas import ProjectCreate, ProjectRecord, ProjectStatus, utc_now_iso


class ProjectManager:
    """Owns project records and their on-disk workspace directories.

    Project files are stored below the configured projects root. Backups contain
    a versioned manifest, project-relative files and only the SQLite rows owned
    by that project (plus referenced syllabus catalogue rows), never the full DB.
    """

    BACKUP_FORMAT = "upsc-studio-project"
    BACKUP_VERSION = 2
    SUPPORTED_BACKUP_VERSIONS = {1, 2}
    MAX_BACKUP_UNCOMPRESSED_BYTES = 20 * 1024 * 1024 * 1024
    PROJECT_DATA_TABLES = (
        "source_documents",
        "sources",
        "claims",
        "assets",
        "render_jobs",
        "qa_gates",
        "coverage_ledger",
    )

    PROJECT_DIRECTORIES = (
        "inputs/originals",
        "inputs/uploads_tmp",
        "research",
        "teaching",
        "storyboard",
        "graphics",
        "audio/narration_segments",
        "audio/processed",
        "subtitles",
        "video/segments",
        "video/final",
        "publishing",
        "qa",
        "logs",
        "backups",
    )

    def __init__(self, conn: sqlite3.Connection, projects_root: Path) -> None:
        self.conn = conn
        self.projects_root = Path(projects_root).expanduser().resolve()
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def _row_to_record(self, row: Any, cursor: sqlite3.Cursor | None = None) -> ProjectRecord:
        if row is None:
            raise ValueError("Project record does not exist")
        if isinstance(row, sqlite3.Row):
            data = dict(row)
        elif isinstance(row, dict):
            data = dict(row)
        elif cursor is not None and cursor.description:
            data = dict(zip((col[0] for col in cursor.description), row))
        else:
            raise TypeError("Unsupported SQLite row format")
        data["tts_enabled"] = bool(data.get("tts_enabled", False))
        return ProjectRecord.model_validate(data)

    def _project_dir(self, slug: str, project_id: str) -> Path:
        safe_slug = sanitize_slug(slug)
        safe_id = sanitize_slug(project_id, max_len=80)
        return ensure_within_base(self.projects_root, self.projects_root / f"{safe_slug}-{safe_id}")

    def _initialise_project_tree(self, project_dir: Path) -> None:
        project_dir = ensure_within_base(self.projects_root, project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        for relative in self.PROJECT_DIRECTORIES:
            target = ensure_within_base(project_dir, project_dir / relative)
            target.mkdir(parents=True, exist_ok=True)

    def create_project(self, payload: ProjectCreate) -> ProjectRecord:
        """Create a project row and a complete, empty workspace."""
        project_id = f"prj_{uuid.uuid4().hex}"
        slug = sanitize_slug(payload.name)
        project_dir = self._project_dir(slug, project_id)
        now = utc_now_iso()
        record = ProjectRecord(
            **payload.model_dump(),
            id=project_id,
            slug=slug,
            root_dir=str(project_dir),
            status=ProjectStatus.NOT_STARTED,
            created_at=now,
            updated_at=now,
        )
        try:
            self._initialise_project_tree(project_dir)
            self.conn.execute(
                """
                INSERT INTO projects (
                    id, name, slug, chapter_title, content_category, exam_cycle, cutoff_date,
                    target_duration_min, tts_enabled, root_dir, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.name,
                    record.slug,
                    record.chapter_title,
                    record.content_category,
                    record.exam_cycle,
                    record.cutoff_date,
                    record.target_duration_min,
                    int(record.tts_enabled),
                    record.root_dir,
                    record.status.value,
                    record.created_at,
                    record.updated_at,
                ),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            if project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
            raise
        return record

    def get_project(self, project_id: str) -> ProjectRecord:
        cursor = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"Project not found: {project_id}")
        return self._row_to_record(row, cursor)

    def list_projects(self) -> list[ProjectRecord]:
        cursor = self.conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC, id DESC"
        )
        return [self._row_to_record(row, cursor) for row in cursor.fetchall()]

    def update_status(self, project_id: str, status: ProjectStatus | str) -> ProjectRecord:
        """Update a project status using the declared project-state enum."""
        try:
            normalised_status = ProjectStatus(status)
        except ValueError as exc:
            raise ValueError(f"Unsupported project status: {status}") from exc
        cursor = self.conn.execute(
            "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
            (normalised_status.value, utc_now_iso(), project_id),
        )
        if cursor.rowcount == 0:
            self.conn.rollback()
            raise KeyError(f"Project not found: {project_id}")
        self.conn.commit()
        return self.get_project(project_id)

    def _capture_project_database(self, project_id: str) -> dict[str, list[dict[str, Any]]]:
        """Capture project-scoped evidence and QA rows without copying the entire DB."""
        snapshot: dict[str, list[dict[str, Any]]] = {}
        for table in self.PROJECT_DATA_TABLES:
            cursor = self.conn.execute(
                f"SELECT * FROM {table} WHERE project_id = ?", (project_id,)
            )
            rows = cursor.fetchall()
            snapshot[table] = [
                dict(row) if isinstance(row, sqlite3.Row)
                else dict(zip((column[0] for column in cursor.description), row))
                for row in rows
            ]

        syllabus_ids = sorted({
            row["syllabus_item_id"]
            for row in snapshot["coverage_ledger"]
            if row.get("syllabus_item_id")
        })
        snapshot["syllabus_items"] = []
        if syllabus_ids:
            placeholders = ",".join("?" for _ in syllabus_ids)
            cursor = self.conn.execute(
                f"SELECT * FROM syllabus_items WHERE id IN ({placeholders})",
                tuple(syllabus_ids),
            )
            rows = cursor.fetchall()
            snapshot["syllabus_items"] = [
                dict(row) if isinstance(row, sqlite3.Row)
                else dict(zip((column[0] for column in cursor.description), row))
                for row in rows
            ]
        return snapshot

    def _restore_project_database(
        self,
        project_id: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Restore whitelisted project rows and referenced syllabus records safely."""
        if not snapshot:
            return
        if not isinstance(snapshot, dict):
            raise ValueError("Backup database snapshot must be an object")

        # Syllabus entries are shared reference data. Insert missing referenced
        # versions without overwriting a newer or already installed catalogue.
        syllabus_rows = snapshot.get("syllabus_items", [])
        if not isinstance(syllabus_rows, list):
            raise ValueError("Backup syllabus_items must be a list")
        for row in syllabus_rows:
            if not isinstance(row, dict) or not row.get("id"):
                raise ValueError("Invalid syllabus item in backup snapshot")
            columns = [
                info[1] for info in self.conn.execute("PRAGMA table_info(syllabus_items)")
                if info[1] in row
            ]
            if set(row) - set(columns):
                raise ValueError("Backup syllabus item contains unknown columns")
            names = ", ".join(f'"{name}"' for name in columns)
            placeholders = ", ".join("?" for _ in columns)
            self.conn.execute(
                f"INSERT OR IGNORE INTO syllabus_items ({names}) VALUES ({placeholders})",
                tuple(row[name] for name in columns),
            )

        for table in self.PROJECT_DATA_TABLES:
            rows = snapshot.get(table, [])
            if not isinstance(rows, list):
                raise ValueError(f"Backup table {table} must contain a list")
            table_columns = [
                info[1] for info in self.conn.execute(f"PRAGMA table_info({table})")
            ]
            if not table_columns:
                raise ValueError(f"Required project table is missing: {table}")
            for row in rows:
                if not isinstance(row, dict) or row.get("project_id") != project_id:
                    raise ValueError(f"Invalid project row in backup table {table}")
                unknown = set(row) - set(table_columns)
                if unknown:
                    raise ValueError(
                        f"Backup table {table} contains unknown columns: {sorted(unknown)}"
                    )
                columns = [name for name in table_columns if name in row]
                if "id" not in columns:
                    raise ValueError(f"Backup row in {table} has no primary ID")

                # Never overwrite another project's row if a corrupt or
                # conflicting backup reuses an identifier.
                existing = self.conn.execute(
                    f'SELECT project_id FROM {table} WHERE id = ?', (row["id"],)
                ).fetchone()
                if existing is not None and existing[0] != project_id:
                    raise ValueError(
                        f"Backup row identifier collision in {table}: {row['id']}"
                    )

                names = ", ".join(f'"{name}"' for name in columns)
                placeholders = ", ".join("?" for _ in columns)
                updates = [
                    f'"{name}" = excluded."{name}"'
                    for name in columns if name != "id"
                ]
                sql = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
                if updates:
                    sql += f' ON CONFLICT("id") DO UPDATE SET {", ".join(updates)}'
                self.conn.execute(sql, tuple(row[name] for name in columns))

    @staticmethod
    def _remap_project_artifact_paths(
        snapshot: dict[str, Any],
        old_project_root: Path,
        new_project_root: Path,
    ) -> dict[str, Any]:
        """Rebase stored artifact paths when a project is restored elsewhere."""
        old_root = Path(old_project_root).expanduser().resolve()
        new_root = Path(new_project_root).expanduser().resolve()
        path_columns = {
            "source_documents": ("original_path",),
            "assets": ("file_path",),
            "render_jobs": ("output_path",),
        }
        remapped = dict(snapshot)
        for table, columns in path_columns.items():
            rows = snapshot.get(table, [])
            if not isinstance(rows, list):
                continue
            updated_rows = []
            for original in rows:
                row = dict(original)
                for column in columns:
                    value = row.get(column)
                    if not value:
                        continue
                    try:
                        original_path = Path(value).expanduser().resolve()
                        relative = original_path.relative_to(old_root)
                    except (OSError, ValueError):
                        # Leave externally managed files untouched; only rebase
                        # paths that were actually inside the original workspace.
                        continue
                    row[column] = str(new_root / relative)
                updated_rows.append(row)
            remapped[table] = updated_rows
        return remapped

    def backup_project(
        self,
        project_id: str,
        destination_dir: Path,
        notes: str = "",
    ) -> Path:
        """Create a portable ZIP backup containing the record and project files."""
        record = self.get_project(project_id)
        project_dir = ensure_within_base(self.projects_root, Path(record.root_dir))
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project workspace is missing: {project_dir}")

        destination_dir = Path(destination_dir).expanduser().resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = destination_dir / f"{record.slug}-{record.id}-{stamp}.zip"
        manifest = {
            "format": self.BACKUP_FORMAT,
            "version": self.BACKUP_VERSION,
            "created_at": utc_now_iso(),
            "notes": notes,
            "project": record.model_dump(mode="json"),
            "database": self._capture_project_database(project_id),
        }

        try:
            with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr(
                    "upsc_studio_backup.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                for item in sorted(project_dir.rglob("*")):
                    if item.is_symlink():
                        raise ValueError(f"Symlinks are not permitted in backups: {item}")
                    if item.is_file():
                        resolved = ensure_within_base(project_dir, item)
                        relative = resolved.relative_to(project_dir).as_posix()
                        archive.write(resolved, f"project/{relative}")
            return backup_path
        except Exception:
            backup_path.unlink(missing_ok=True)
            raise

    def restore_project(self, backup_path: Path) -> ProjectRecord:
        """Safely restore a project backup without allowing ZIP path traversal."""
        backup_path = Path(backup_path).expanduser().resolve()
        if not backup_path.is_file():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        staging = ensure_within_base(
            self.projects_root,
            self.projects_root / f".restore-{uuid.uuid4().hex}",
        )
        staging.mkdir(parents=True, exist_ok=False)

        try:
            with zipfile.ZipFile(backup_path, "r") as archive:
                infos = archive.infolist()
                total_size = sum(info.file_size for info in infos)
                if total_size > self.MAX_BACKUP_UNCOMPRESSED_BYTES:
                    raise ValueError("Backup exceeds the configured uncompressed-size limit")

                manifest_info = next(
                    (item for item in infos if item.filename == "upsc_studio_backup.json"),
                    None,
                )
                if manifest_info is None:
                    raise ValueError("Backup manifest is missing")

                manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
                if manifest.get("format") != self.BACKUP_FORMAT:
                    raise ValueError("Unsupported backup format")
                if manifest.get("version") not in self.SUPPORTED_BACKUP_VERSIONS:
                    raise ValueError("Unsupported backup version")

                project_data = manifest.get("project")
                if not isinstance(project_data, dict):
                    raise ValueError("Backup project metadata is invalid")
                restored_record = ProjectRecord.model_validate(project_data)

                current = self.conn.execute(
                    "SELECT * FROM projects WHERE id = ?", (restored_record.id,)
                ).fetchone()
                if current is not None:
                    current_record = self._row_to_record(current)
                    project_dir = ensure_within_base(
                        self.projects_root, Path(current_record.root_dir)
                    )
                else:
                    project_dir = self._project_dir(
                        restored_record.slug, restored_record.id
                    )

                # Validate every entry before extracting any data.
                file_entries: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
                for info in infos:
                    if info.filename == "upsc_studio_backup.json":
                        continue
                    if not info.filename.startswith("project/"):
                        raise ValueError(f"Unexpected backup entry: {info.filename}")
                    relative_text = info.filename[len("project/"):]
                    relative = PurePosixPath(relative_text)
                    if (
                        not relative_text
                        or relative.is_absolute()
                        or any(part in ("", ".", "..") for part in relative.parts)
                        or ":" in relative_text
                    ):
                        raise ValueError(f"Unsafe backup path: {info.filename}")
                    unix_mode = (info.external_attr >> 16) & 0xFFFF
                    if unix_mode and (unix_mode & 0o170000) == 0o120000:
                        raise ValueError(f"Symbolic links are not permitted: {info.filename}")
                    file_entries.append((info, relative))

                for info, relative in file_entries:
                    stage_target = ensure_within_base(staging, staging.joinpath(*relative.parts))
                    stage_target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as source, stage_target.open("wb") as target:
                        shutil.copyfileobj(source, target)

            self._initialise_project_tree(project_dir)
            for item in staging.rglob("*"):
                if item.is_file():
                    relative = item.relative_to(staging)
                    destination = ensure_within_base(
                        project_dir, project_dir.joinpath(*relative.parts)
                    )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, destination)

            restored_record.root_dir = str(project_dir)
            self.conn.execute(
                """
                INSERT INTO projects (
                    id, name, slug, chapter_title, content_category, exam_cycle, cutoff_date,
                    target_duration_min, tts_enabled, root_dir, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    slug = excluded.slug,
                    chapter_title = excluded.chapter_title,
                    content_category = excluded.content_category,
                    exam_cycle = excluded.exam_cycle,
                    cutoff_date = excluded.cutoff_date,
                    target_duration_min = excluded.target_duration_min,
                    tts_enabled = excluded.tts_enabled,
                    root_dir = excluded.root_dir,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    restored_record.id,
                    restored_record.name,
                    restored_record.slug,
                    restored_record.chapter_title,
                    restored_record.content_category,
                    restored_record.exam_cycle,
                    restored_record.cutoff_date,
                    restored_record.target_duration_min,
                    int(restored_record.tts_enabled),
                    restored_record.root_dir,
                    restored_record.status.value,
                    restored_record.created_at,
                    utc_now_iso(),
                ),
            )
            database_snapshot = manifest.get("database", {})
            if database_snapshot:
                old_root = Path(project_data.get("root_dir", project_dir))
                database_snapshot = self._remap_project_artifact_paths(
                    database_snapshot, old_root, project_dir
                )
            self._restore_project_database(
                restored_record.id, database_snapshot
            )
            self.conn.commit()
            return self.get_project(restored_record.id)
        except Exception:
            self.conn.rollback()
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
