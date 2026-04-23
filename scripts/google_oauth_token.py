#!/usr/bin/env python3
"""
Google OAuth Token Helper — Obtain real access tokens for DeepSecure demo.

Reads client credentials from .env.google (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
and runs a local OAuth consent flow to get access tokens for Google Drive,
Calendar, and Gmail.

Usage:
  # Get tokens for all 3 services (one consent screen)
  python3 scripts/google_oauth_token.py

  # Drive only
  python3 scripts/google_oauth_token.py --services gdrive

  # Source directly into shell
  eval "$(python3 scripts/google_oauth_token.py)"

  # Then run the demo
  ./scripts/demo_sarah_journey_v2.sh --services google
"""

import json
import os
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

SCOPES_BY_SERVICE = {
    "gdrive": [
        "https://www.googleapis.com/auth/drive.readonly",
    ],
    "gcalendar": [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events.readonly",
    ],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
    ],
}

ENV_NAMES = {
    "gdrive": "GDRIVE_ACCESS_TOKEN",
    "gcalendar": "GCALENDAR_ACCESS_TOKEN",
    "gmail": "GMAIL_ACCESS_TOKEN",
}

REDIRECT_PORT = 8484
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


def load_env_google() -> tuple[str, str]:
    """Load GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from .env.google or env."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if client_id and client_secret:
        return client_id, client_secret

    repo_root = Path(__file__).resolve().parent.parent
    env_file = repo_root / ".env.google"

    if not env_file.exists():
        print(
            "ERROR: .env.google not found and GOOGLE_CLIENT_ID not in environment.\n"
            "       Run: cp .env.google.example .env.google  and fill in your values.",
            file=sys.stderr,
        )
        sys.exit(1)

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Handle both `export VAR=val` and `VAR=val`
        if line.startswith("export "):
            line = line[7:]
        key, _, val = line.partition("=")
        val = val.strip().strip('"').strip("'")
        if key.strip() == "GOOGLE_CLIENT_ID":
            client_id = val
        elif key.strip() == "GOOGLE_CLIENT_SECRET":
            client_secret = val

    if not client_id or not client_secret:
        print("ERROR: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET missing from .env.google", file=sys.stderr)
        sys.exit(1)

    return client_id, client_secret


def run_oauth_flow(client_id: str, client_secret: str, scopes: list[str], label: str) -> dict:
    """Run OAuth 2.0 flow and return the full token response."""
    state = secrets.token_urlsafe(16)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"

    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("state", [None])[0] != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch")
                return

            captured["code"] = qs.get("code", [None])[0]
            captured["error"] = qs.get("error", [None])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body style='font-family:system-ui;text-align:center;padding:60px'>"
                f"<h2>✅ {label} authorized</h2>"
                f"<p style='color:#666'>You can close this tab and return to the terminal.</p>"
                f"</body></html>".encode()
            )

        def log_message(self, *args):
            pass

    print(f"\n  Opening browser for {label} authorization...", file=sys.stderr)
    webbrowser.open(auth_url)

    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    server.handle_request()

    if captured.get("error"):
        print(f"  ERROR: OAuth denied — {captured['error']}", file=sys.stderr)
        sys.exit(1)

    code = captured.get("code")
    if not code:
        print(f"  ERROR: No authorization code received", file=sys.stderr)
        sys.exit(1)

    # Exchange code for tokens
    import urllib.request
    token_data = urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    print(f"  Exchanging code for {label} tokens...", file=sys.stderr)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ERROR: Token exchange failed — {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Get Google OAuth tokens for DeepSecure demo")
    parser.add_argument("--services", default="gdrive,gcalendar,gmail")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of export commands")
    args = parser.parse_args()

    services = [s.strip() for s in args.services.split(",")]
    for s in services:
        if s not in SCOPES_BY_SERVICE:
            print(f"Unknown service: {s}. Valid: {list(SCOPES_BY_SERVICE)}", file=sys.stderr)
            sys.exit(1)

    client_id, client_secret = load_env_google()
    print(f"  Client ID: {client_id[:20]}...", file=sys.stderr)

    # Combine all scopes into one consent screen
    all_scopes = []
    for s in services:
        all_scopes.extend(SCOPES_BY_SERVICE[s])

    token_response = run_oauth_flow(client_id, client_secret, all_scopes, "Google Workspace")
    access_token = token_response["access_token"]
    expires_in = token_response.get("expires_in", "?")

    print(f"\n  ✅ Token obtained (expires in {expires_in}s)", file=sys.stderr)

    if args.json:
        print(json.dumps({
            ENV_NAMES[s]: access_token for s in services
        }, indent=2))
    else:
        for s in services:
            print(f'export {ENV_NAMES[s]}="{access_token}"')
        print("", file=sys.stderr)
        print(f"  # Token works for: {', '.join(services)}", file=sys.stderr)
        print(f"  # Run the demo:", file=sys.stderr)
        print(f"  #   ./scripts/demo_sarah_journey_v2.sh --services {','.join(services)}", file=sys.stderr)


if __name__ == "__main__":
    main()
