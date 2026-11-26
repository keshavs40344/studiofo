"""Asset provenance and copyright/licence verification ledger."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from upsc_studio.core.paths import sha256_file
from upsc_studio.db.schemas import RightsStatus, utc_now_iso


class AssetRightsLedger:
    """Tracks provenance and usage rights for every visual and audio asset."""

    ALLOWED_EXPORT_STATUSES = {
        RightsStatus.ORIGINAL_GENERATED.value,
        RightsStatus.USER_OWNED.value,
        RightsStatus.PUBLIC_DOMAIN.value,
        RightsStatus.LICENSED.value,
    }

    def __init__(self, conn: sqlite3.Connection, project_dir: Path) -> None:
        self.conn = conn
        self.project_dir = project_dir
        self.manifests_dir = project_dir / "assets" / "manifests"
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def register_asset(
        self,
        project_id: str,
        asset_type: str,
        file_path: Path,
        creator: str,
        licence: str,
        rights_status: RightsStatus,
        origin_url: str | None = None,
        attribution: str = "",
    ) -> str:
        """Register an asset with SHA-256 hash and licence status in SQLite."""
        if not file_path.exists():
            raise FileNotFoundError(f"Asset file not found: {file_path}")
        asset_id = f"ast_{uuid.uuid4().hex[:8]}"
        digest = sha256_file(file_path)
        self.conn.execute(
            """
            INSERT INTO assets (
                id, project_id, asset_type, file_path, sha256, creator,
                origin_url, licence, attribution, rights_status, retrieved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                project_id,
                asset_type,
                str(file_path),
                digest,
                creator,
                origin_url,
                licence,
                attribution,
                rights_status.value,
                utc_now_iso(),
            ),
        )
        self.conn.commit()
        self.export_manifest(project_id)
        return asset_id

    def export_manifest(self, project_id: str) -> list[dict]:
        """Write assets/manifests/asset_rights.json."""
        rows = self.conn.execute(
            "SELECT * FROM assets WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        data = [dict(r) for r in rows]
        (self.manifests_dir / "asset_rights.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return data

    def find_unverified_assets(self, project_id: str) -> list[dict]:
        """Return any assets whose rights_status is UNVERIFIED or missing."""
        rows = self.conn.execute(
            "SELECT * FROM assets WHERE project_id = ?", (project_id,)
        ).fetchall()
        return [dict(r) for r in rows if r["rights_status"] not in self.ALLOWED_EXPORT_STATUSES]
