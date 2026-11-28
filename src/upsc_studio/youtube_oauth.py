"""Interactive local OAuth bootstrap for YouTube Data API uploads.

Requires a Google OAuth Desktop App client_secrets.json created by the account owner.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from upsc_studio.core.paths import DEFAULT_DATA_DIR


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def create_oauth_token(client_secrets: Path, token_path: Path | None = None) -> Path:
    secrets_path = Path(client_secrets).expanduser().resolve()
    if not secrets_path.is_file():
        raise FileNotFoundError(f"Google OAuth client file not found: {secrets_path}")
    target = token_path or (DEFAULT_DATA_DIR / "youtube_oauth_token.json")
    target = Path(target).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            'Install YouTube support with: pip install -e ".[youtube]"'
        ) from exc

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(credentials.to_json(), encoding="utf-8")
    temporary.replace(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Connect a YouTube account to UPSC Studio.")
    parser.add_argument("--client-secrets", required=True, type=Path)
    parser.add_argument("--token-path", type=Path, default=None)
    args = parser.parse_args()
    token = create_oauth_token(args.client_secrets, args.token_path)
    print(json.dumps({"status": "OAUTH_TOKEN_CREATED", "token_path": str(token)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
