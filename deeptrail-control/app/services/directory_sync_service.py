"""Service for syncing groups and users from Google Workspace Directory API.

Uses service-account delegation (same pattern as google.py provider) to list
all groups and users in the Workspace domain, then upserts them into the
org_directory table for use by the admin service-access UI.
"""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.org_directory import OrgDirectory

logger = logging.getLogger(__name__)

_DIRECTORY_API = "https://admin.googleapis.com/admin/directory/v1"
_GROUP_SCOPE = "https://www.googleapis.com/auth/admin.directory.group.readonly"
_USER_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"


class DirectorySyncService:
    def __init__(self, db: Session):
        self.db = db

    def sync_from_google(self) -> dict:
        """Sync groups and users from Google Workspace Directory API.

        This is a full replacement sync: entries not present in the API
        response are deleted so stale data doesn't accumulate.

        Returns {"groups_synced": N, "users_synced": M}.
        Gracefully returns zeros if the service account is not configured.
        """
        sa_email = os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")
        admin_email = os.environ.get("GOOGLE_ADMIN_EMAIL")

        if not sa_email or not admin_email:
            logger.warning(
                "GOOGLE_SERVICE_ACCOUNT_EMAIL or GOOGLE_ADMIN_EMAIL not set — "
                "skipping directory sync"
            )
            return {"groups_synced": 0, "users_synced": 0}

        access_token = self._get_access_token(sa_email, admin_email)
        if access_token is None:
            return {"groups_synced": 0, "users_synced": 0}

        synced_group_emails = self._sync_groups(access_token)
        synced_user_emails = self._sync_users(access_token)

        stale_deleted = self._delete_stale(synced_group_emails, synced_user_emails)
        self.db.commit()

        if stale_deleted:
            logger.info("Deleted %d stale org_directory entries", stale_deleted)

        return {
            "groups_synced": len(synced_group_emails),
            "users_synced": len(synced_user_emails),
        }

    def get_groups(self) -> list:
        return (
            self.db.query(OrgDirectory)
            .filter(OrgDirectory.entity_type == "group")
            .order_by(OrgDirectory.display_name)
            .all()
        )

    def get_users(self) -> list:
        return (
            self.db.query(OrgDirectory)
            .filter(OrgDirectory.entity_type == "user")
            .order_by(OrgDirectory.display_name)
            .all()
        )

    def get_all(self) -> dict:
        groups = self.get_groups()
        users = self.get_users()
        return {
            "groups": [
                {
                    "email": g.email,
                    "display_name": g.display_name,
                    "member_count": g.member_count,
                    "members": g.members or [],
                }
                for g in groups
            ],
            "users": [
                {
                    "email": u.email,
                    "display_name": u.display_name,
                }
                for u in users
            ],
        }

    # --- internal helpers ---

    def _get_access_token(self, sa_email: str, admin_email: str) -> str | None:
        try:
            import google.auth
            from google.auth import impersonated_credentials
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError:
            logger.error("google-auth library not installed — cannot sync directory")
            return None

        scopes = [_GROUP_SCOPE, _USER_SCOPE]

        try:
            source_credentials, _ = google.auth.default()

            if (
                hasattr(source_credentials, "service_account_email")
                and source_credentials.service_account_email == sa_email
            ):
                delegated = service_account.Credentials(
                    signer=source_credentials.signer,
                    service_account_email=sa_email,
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=scopes,
                    subject=admin_email,
                )
            else:
                delegated = impersonated_credentials.Credentials(
                    source_credentials=source_credentials,
                    target_principal=sa_email,
                    target_scopes=scopes,
                    delegates=[],
                    subject=admin_email,
                )

            delegated.refresh(Request())
            return delegated.token
        except Exception:
            logger.warning("Failed to obtain delegated credentials for directory sync", exc_info=True)
            return None

    def _sync_groups(self, access_token: str) -> set[str]:
        import httpx

        synced_emails: set[str] = set()
        now = datetime.now(timezone.utc)
        page_token = None

        while True:
            params: dict = {"customer": "my_customer", "maxResults": 200}
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = httpx.get(
                    f"{_DIRECTORY_API}/groups",
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0,
                )
            except httpx.HTTPError:
                logger.warning("Failed to fetch groups page from Directory API", exc_info=True)
                break

            if resp.status_code != 200:
                logger.warning("Directory API groups returned %d: %s", resp.status_code, resp.text[:300])
                break

            data = resp.json()
            for g in data.get("groups", []):
                email = g["email"]
                members = self._fetch_group_members(access_token, email)
                self._upsert_entry(
                    entity_type="group",
                    email=email,
                    display_name=g.get("name", email),
                    member_count=g.get("directMembersCount"),
                    members=members,
                    synced_at=now,
                )
                synced_emails.add(email)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return synced_emails

    def _fetch_group_members(self, access_token: str, group_email: str) -> list[str]:
        import httpx

        member_emails: list[str] = []
        page_token = None

        while True:
            params: dict = {"maxResults": 200}
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = httpx.get(
                    f"{_DIRECTORY_API}/groups/{group_email}/members",
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0,
                )
            except httpx.HTTPError:
                logger.warning("Failed to fetch members for group %s", group_email, exc_info=True)
                break

            if resp.status_code != 200:
                logger.warning(
                    "Directory API members for %s returned %d",
                    group_email,
                    resp.status_code,
                )
                break

            data = resp.json()
            for m in data.get("members", []):
                if m.get("type") == "USER" and m.get("email"):
                    member_emails.append(m["email"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return member_emails

    def _sync_users(self, access_token: str) -> set[str]:
        import httpx

        synced_emails: set[str] = set()
        now = datetime.now(timezone.utc)
        page_token = None

        while True:
            params: dict = {"customer": "my_customer", "maxResults": 500}
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = httpx.get(
                    f"{_DIRECTORY_API}/users",
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0,
                )
            except httpx.HTTPError:
                logger.warning("Failed to fetch users page from Directory API", exc_info=True)
                break

            if resp.status_code != 200:
                logger.warning("Directory API users returned %d: %s", resp.status_code, resp.text[:300])
                break

            data = resp.json()
            for u in data.get("users", []):
                email = u["primaryEmail"]
                full_name = u.get("name", {}).get("fullName", email)
                self._upsert_entry(
                    entity_type="user",
                    email=email,
                    display_name=full_name,
                    member_count=None,
                    synced_at=now,
                )
                synced_emails.add(email)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return synced_emails

    def _delete_stale(
        self, synced_groups: set[str], synced_users: set[str]
    ) -> int:
        """Remove org_directory rows not present in the latest sync."""
        all_synced = synced_groups | synced_users
        if not all_synced:
            return 0

        stale = (
            self.db.query(OrgDirectory)
            .filter(OrgDirectory.email.notin_(all_synced))
            .all()
        )
        for entry in stale:
            logger.debug("Removing stale directory entry: %s (%s)", entry.email, entry.entity_type)
            self.db.delete(entry)
        return len(stale)

    def _upsert_entry(
        self,
        entity_type: str,
        email: str,
        display_name: str,
        member_count: int | None,
        synced_at: datetime,
        members: list[str] | None = None,
    ) -> None:
        existing = (
            self.db.query(OrgDirectory)
            .filter(OrgDirectory.email == email)
            .first()
        )
        if existing:
            existing.entity_type = entity_type
            existing.display_name = display_name
            existing.member_count = member_count
            existing.members = members
            existing.synced_at = synced_at
        else:
            self.db.add(
                OrgDirectory(
                    entity_type=entity_type,
                    email=email,
                    display_name=display_name,
                    member_count=member_count,
                    members=members,
                    synced_at=synced_at,
                )
            )
