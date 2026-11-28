# YouTube account connection and controlled publishing

The dashboard does not create Google credentials. The channel owner must create OAuth client credentials in their own Google Cloud project and approve access.

## 1. Prepare Google OAuth

1. Create/select a Google Cloud project.
2. Enable the YouTube Data API v3 for that project.
3. Configure the OAuth consent screen and add the channel owner as a test user when the app remains in testing.
4. Create an OAuth client ID of type **Desktop app**.
5. Download the client JSON to a private local path such as `secrets/youtube_client_secrets.json`. Do not commit this file.

## 2. Install and connect locally

From the repository root, install optional upload support:

```powershell
python -m pip install -e ".[youtube]"
```

Run the local interactive OAuth flow:

```powershell
python -m upsc_studio.youtube_oauth --client-secrets .\secrets\youtube_client_secrets.json
```

The token is written to the application's data directory as `youtube_oauth_token.json`. Keep it private; do not upload it to GitHub or share it in chat. To use a different location, pass `--token-path`.

## 3. Publish from a project

1. Complete production and the final ten-gate human approval.
2. Confirm the manual review still matches the exact current artifacts.
3. Select Private, Unlisted or Public in the dashboard.
4. Enter the reviewer name and tick the per-run upload confirmation.
5. For Public, confirm the additional browser prompt.

Private is the default. Every request requires explicit per-run confirmation. The API records a hash-bound upload receipt and blocks a second upload of the same video after a successful upload. An interrupted upload can leave an in-progress marker; reconcile that state before retrying.

## 4. Limits

- OAuth token presence does not guarantee that Google will accept an upload; API permissions, quota, consent status and token validity are checked by the live request.
- CI never uploads to a real channel.
- This workflow uploads the main approved video. It does not automatically publish Shorts or schedule multi-platform releases.
