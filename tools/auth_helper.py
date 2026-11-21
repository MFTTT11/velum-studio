"""Local-Only YouTube OAuth Token Generator for GitHub Secrets.

Run this script LOCALLY once to generate ready-to-paste Base64 strings for:
  - YOUTUBE_CLIENT_SECRETS
  - YOUTUBE_TOKEN

SECURITY:
- Never executed in GitHub Actions CI.
- Never commits or logs secrets to any tracked file.
- Immediately offers to securely shred local client_secrets.json & token.json
  once you have copied the Base64 strings into GitHub Repository Secrets.

Usage:
  1. Download OAuth Desktop credentials JSON from Google Cloud Console and place
     it temporarily as `client_secrets.json` in the repository root (gitignored).
  2. Run: `python tools/auth_helper.py`
  3. Complete Google OAuth consent in your browser.
  4. Paste the printed Base64 strings into GitHub -> Settings -> Secrets -> Actions.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import secure_delete_file
from publisher.youtube_uploader import YOUTUBE_SCOPES


def main() -> int:
    secrets_path = ROOT_DIR / "client_secrets.json"
    token_path = ROOT_DIR / "token.json"

    if not secrets_path.exists():
        print("ERROR: Place your Google Cloud OAuth Desktop JSON at ./client_secrets.json first.")
        print("       (client_secrets.json is strictly blocked by .gitignore.)")
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    print("Opening browser for Google YouTube Data API v3 + Analytics OAuth consent...")
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), YOUTUBE_SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_json = creds.to_json()
    token_path.write_text(token_json, encoding="utf-8")

    b64_secrets = base64.b64encode(secrets_path.read_bytes()).decode("ascii")
    b64_token = base64.b64encode(token_json.encode("utf-8")).decode("ascii")

    print("\n" + "=" * 72)
    print("COPY THESE TWO VALUES INTO GITHUB -> SETTINGS -> SECRETS -> ACTIONS")
    print("=" * 72)
    print("\n1) Secret Name: YOUTUBE_CLIENT_SECRETS")
    print(b64_secrets)
    print("\n2) Secret Name: YOUTUBE_TOKEN")
    print(b64_token)
    print("\n" + "=" * 72)

    answer = input("\nWipe local client_secrets.json and token.json from disk now? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        secure_delete_file(secrets_path)
        secure_delete_file(token_path)
        print("Securely zeroed and deleted local credential files.")
    else:
        print("Kept locally (protected by .gitignore — never commit them).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
