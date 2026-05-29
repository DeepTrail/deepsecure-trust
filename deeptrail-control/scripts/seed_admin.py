"""Seed script to set initial admin users.

Reads ADMIN_EMAILS env var (comma-separated) and sets role='admin'
on matching user_sessions rows.

Usage:
    ADMIN_EMAILS=admin@acme.com,it-admin@acme.com python -m scripts.seed_admin

Can also be imported and called during application startup:
    from scripts.seed_admin import seed_admin_user
"""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session as SASession

from app.db.session import SessionLocal
from app.models.user_session import UserSession


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


def main() -> None:
    admin_emails_raw = os.getenv("ADMIN_EMAILS", "")
    if not admin_emails_raw:
        logger.error("ADMIN_EMAILS env var not set. Provide comma-separated emails.")
        sys.exit(1)

    admin_emails = [e.strip() for e in admin_emails_raw.split(",") if e.strip()]
    logger.info("Seeding admin role for: %s", admin_emails)

    db = SessionLocal()
    try:
        result = seed_admin_user(db, admin_emails)
        logger.info("Done. Updated: %s, Not found: %s", result["updated"], result["not_found"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
