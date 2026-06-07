"""Seed script to set initial admin users and default service registry.

Reads ADMIN_EMAILS env var (comma-separated) and sets role='admin'
on matching user_sessions rows. Also seeds the 6 default REST services
into the service_registry table if they don't already exist.

Usage:
    ADMIN_EMAILS=admin@acme.com,it-admin@acme.com python -m scripts.seed_admin

Can also be imported and called during application startup:
    from scripts.seed_admin import seed_admin_user, seed_default_services
"""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session as SASession

from app.db.session import SessionLocal
from app.models.service_registry import ServiceRegistry
from app.models.user_session import UserSession

DEFAULT_SERVICES = [
    {
        "service_id": "notion",
        "display_name": "Notion",
        "description": "Access workspace pages, databases, and documents",
        "backend_type": "rest",
        "endpoint_url": "https://api.notion.com/v1",
    },
    {
        "service_id": "slack",
        "display_name": "Slack",
        "description": "Search messages and send notifications",
        "backend_type": "rest",
        "endpoint_url": "https://slack.com/api",
    },
    {
        "service_id": "hubspot",
        "display_name": "HubSpot",
        "description": "Manage contacts, deals, and CRM data",
        "backend_type": "rest",
        "endpoint_url": "https://api.hubapi.com",
    },
    {
        "service_id": "gmail",
        "display_name": "Gmail",
        "description": "Read and send emails on your behalf",
        "backend_type": "rest",
        "endpoint_url": "https://gmail.googleapis.com",
    },
    {
        "service_id": "gcalendar",
        "display_name": "Google Calendar",
        "description": "View and manage calendar events",
        "backend_type": "rest",
        "endpoint_url": "https://www.googleapis.com/calendar/v3",
    },
    {
        "service_id": "gdrive",
        "display_name": "Google Drive",
        "description": "Access files and folders in Drive",
        "backend_type": "rest",
        "endpoint_url": "https://www.googleapis.com/drive/v3",
    },
]


def seed_default_services(db: SASession) -> int:
    """Insert default REST services into service_registry if absent.

    Returns the number of services inserted (skips existing ones).
    """
    inserted = 0
    for svc in DEFAULT_SERVICES:
        exists = (
            db.query(ServiceRegistry)
            .filter(ServiceRegistry.service_id == svc["service_id"])
            .first()
        )
        if exists:
            continue
        entry = ServiceRegistry(
            service_id=svc["service_id"],
            display_name=svc["display_name"],
            description=svc["description"],
            backend_type=svc["backend_type"],
            endpoint_url=svc["endpoint_url"],
            status="active",
            health_status="healthy",
            data_classification="internal",
        )
        db.add(entry)
        inserted += 1
        logger.info("Seeded service: %s", svc["service_id"])

    if inserted:
        db.commit()
    return inserted


def seed_admin_user(db: SASession, admin_emails: list[str]) -> dict:
    """Set role='admin' for the specified email addresses.

    Returns a dict summarizing what happened:
        {"updated": ["admin@acme.com"], "not_found": ["nobody@acme.com"]}
    """
    result = {"updated": [], "not_found": []}

    for email in admin_emails:
        email = email.strip()
        if not email:
            continue

        session = (
            db.query(UserSession)
            .filter(UserSession.user_id == email)
            .order_by(UserSession.created_at.desc())
            .first()
        )
        if session:
            session.role = "admin"
            result["updated"].append(email)
            logger.info("Set role=admin for %s", email)
        else:
            result["not_found"].append(email)
            logger.warning("No user_session found for %s — will be set on next login", email)

    db.commit()
    return result


def sync_org_directory(db: SASession) -> dict:
    """Sync org_directory from Google Workspace (replaces seed-based approach).

    Returns {"groups_synced": N, "users_synced": M}.
    Falls back gracefully if Workspace credentials aren't configured.
    """
    from app.services.directory_sync_service import DirectorySyncService

    sync_svc = DirectorySyncService(db)
    result = sync_svc.sync_from_google()
    return result


def main() -> None:
    db = SessionLocal()
    try:
        count = seed_default_services(db)
        logger.info("Service registry: %d new services seeded", count)

        dir_result = sync_org_directory(db)
        logger.info(
            "Org directory: %d groups, %d users synced from Google Workspace",
            dir_result["groups_synced"],
            dir_result["users_synced"],
        )

        admin_emails_raw = os.getenv("ADMIN_EMAILS", "")
        if admin_emails_raw:
            admin_emails = [e.strip() for e in admin_emails_raw.split(",") if e.strip()]
            logger.info("Seeding admin role for: %s", admin_emails)
            result = seed_admin_user(db, admin_emails)
            logger.info("Done. Updated: %s, Not found: %s", result["updated"], result["not_found"])
        else:
            logger.info("ADMIN_EMAILS not set — skipping admin role seeding")
    finally:
        db.close()


if __name__ == "__main__":
    main()
