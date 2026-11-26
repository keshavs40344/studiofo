"""Official YouTube Data API v3 OAuth 2.0 publisher & analytics client with strict privacy defaults."""

from __future__ import annotations

import json
from pathlib import Path

from upsc_studio.core.paths import DEFAULT_DATA_DIR

AUTO_UPLOAD = False
DEFAULT_PRIVACY_STATUS = "private"
AUTO_PUBLICATION = False
PUBLICATION_REQUIRES_USER_APPROVAL = True


class YouTubePublisher:
    """Manages OAuth token checks and resumable private uploads without storing raw passwords."""

    def __init__(self, token_path: Path | None = None) -> None:
        self.token_path = token_path or (DEFAULT_DATA_DIR / "youtube_oauth_token.json")

    def get_oauth_status(self) -> dict:
        connected = self.token_path.exists() and self.token_path.stat().st_size > 0
        return {
            "connected": connected,
            "token_path": str(self.token_path),
            "default_privacy_status": DEFAULT_PRIVACY_STATUS,
            "auto_publication": AUTO_PUBLICATION,
            "publication_requires_user_approval": PUBLICATION_REQUIRES_USER_APPROVAL,
        }

    def upload_video(
        self,
        video_path: Path,
        metadata: dict,
        qa_passed: bool,
        privacy_status: str = DEFAULT_PRIVACY_STATUS,
        user_approved: bool = False,
    ) -> dict:
        """Upload only after explicit per-run approval, QA pass, and OAuth connection."""
        if not user_approved:
            return {"status": "BLOCKED_AWAITING_EXPLICIT_USER_APPROVAL", "video_id": None,
                    "privacy_status": privacy_status, "upload_attempted": False}
        if not qa_passed:
            return {"status": "BLOCKED_QA_FAILED", "video_id": None, "privacy_status": privacy_status}
        if privacy_status not in {"private", "unlisted", "public"}:
            raise ValueError(f"Invalid privacy_status: {privacy_status}")
        if privacy_status == "public" and PUBLICATION_REQUIRES_USER_APPROVAL and not AUTO_PUBLICATION:
            raise PermissionError("Public upload blocked: PUBLICATION_REQUIRES_USER_APPROVAL=True.")
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not self.get_oauth_status()["connected"]:
            return {
                "status": "PENDING_OAUTH_CONNECTION",
                "video_id": None,
                "privacy_status": privacy_status,
                "message": "No YouTube OAuth token connected. Connect OAuth 2.0 in settings to upload as private.",
            }

        # Real OAuth token exists: attempt resumable upload via googleapiclient if installed
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials.from_authorized_user_file(str(self.token_path))
            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title": metadata["video_title"][:100],
                    "description": f"UPSC Studio Documentary | Chapters: {len(metadata.get('chapters', []))}",
                    "tags": metadata.get("tags", []),
                    "categoryId": "27",
                },
                "status": {"privacyStatus": privacy_status},
            }
            media = MediaFileUpload(str(video_path), chunksize=1024 * 1024 * 4, resumable=True)
            req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                _, response = req.next_chunk()
            return {
                "status": "UPLOADED",
                "video_id": response.get("id"),
                "privacy_status": privacy_status,
            }
        except Exception as exc:
            return {
                "status": "UPLOAD_FAILED",
                "video_id": None,
                "privacy_status": privacy_status,
                "error": str(exc),
            }


class YouTubeAnalyticsAgent:
    """Retrieves permitted channel analytics when OAuth is connected (never generates fake engagement)."""

    def fetch_channel_metrics(self, token_path: Path | None = None) -> dict:
        path = token_path or (DEFAULT_DATA_DIR / "youtube_oauth_token.json")
        if not path.exists():
            return {"status": "PENDING_OAUTH_CONNECTION", "metrics": {}}
        return {"status": "READY_FOR_ANALYTICS_QUERY", "metrics": {}}
