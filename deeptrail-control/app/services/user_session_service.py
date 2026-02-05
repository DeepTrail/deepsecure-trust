"""
Service for managing user session lifecycle in the DeepTrail Control Plane.

This service handles creating, reading, validating, and expiring user sessions
after a user authenticates via their enterprise IdP (Identity Provider).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.user_session import UserSession

logger = logging.getLogger(__name__)

# Default session duration in hours
DEFAULT_SESSION_DURATION_HOURS = 8


class UserSessionService:
    """Service for managing user session lifecycle.
    
    Provides methods for creating, retrieving, validating, and managing
    user sessions. Sessions are created after IdP authentication and
    represent an authenticated user's context in the DeepTrail Control Plane.
    
    Usage:
        service = UserSessionService(db)
        session = service.create_session("sarah@acme.com", "https://acme.okta.com")
    """
    
    def __init__(self, db: Session):
        """Initialize the service with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_session(
        self,
        user_id: str,
        idp_issuer: str,
        organization_id: Optional[str] = None,
        expires_in_hours: int = DEFAULT_SESSION_DURATION_HOURS,
        idp_metadata: Optional[str] = None,
    ) -> UserSession:
        """Create a new user session after IdP authentication.
        
        Args:
            user_id: User identifier (typically email, e.g., "sarah@acme.com")
            idp_issuer: Identity provider issuer URL (e.g., "https://acme.okta.com")
            organization_id: Optional organization ID for multi-tenant deployments
            expires_in_hours: Session duration in hours (default: 8)
            idp_metadata: Optional JSON string with additional IdP claims
            
        Returns:
            Created UserSession instance
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            session = UserSession(
                user_id=user_id,
                idp_issuer=idp_issuer,
                organization_id=organization_id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
                idp_metadata=idp_metadata,
            )
            
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(
                f"Created user session: session_id={session.session_id}, "
                f"user_id={user_id}, expires_at={session.expires_at}"
            )
            
            return session
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create user session for {user_id}: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID.
        
        Returns None if the session is not found, expired, or revoked.
        This ensures that callers only receive valid, active sessions.
        
        Args:
            session_id: The session ID to look up
            
        Returns:
            UserSession if found and active, None otherwise
        """
        try:
            result = self.db.execute(
                select(UserSession).where(UserSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if session is None:
                logger.debug(f"Session not found: {session_id}")
                return None
            
            # Check if session is still active
            if not session.is_active:
                logger.debug(
                    f"Session {session_id} is not active: "
                    f"expired={session.is_expired}, revoked={session.is_revoked}"
                )
                return None
            
            return session
            
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            raise
    
    def get_session_including_inactive(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID, including expired/revoked sessions.
        
        Unlike get_session(), this returns the session regardless of its
        active status. Useful for audit purposes or session history.
        
        Args:
            session_id: The session ID to look up
            
        Returns:
            UserSession if found, None otherwise
        """
        try:
            result = self.db.execute(
                select(UserSession).where(UserSession.session_id == session_id)
            )
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            raise
    
    def get_sessions_by_user(
        self, 
        user_id: str, 
        include_inactive: bool = False
    ) -> List[UserSession]:
        """Get all sessions for a user.
        
        Args:
            user_id: The user ID to look up sessions for
            include_inactive: If True, include expired/revoked sessions
            
        Returns:
            List of UserSession objects (may be empty)
        """
        try:
            query = select(UserSession).where(UserSession.user_id == user_id)
            
            if not include_inactive:
                now = datetime.now(timezone.utc)
                query = query.where(
                    UserSession.expires_at > now,
                    UserSession.revoked_at.is_(None)
                )
            
            result = self.db.execute(query)
            sessions = list(result.scalars().all())
            
            logger.debug(f"Found {len(sessions)} sessions for user {user_id}")
            return sessions
            
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving sessions for user {user_id}: {e}")
            raise
    
    def get_sessions_by_organization(
        self, 
        organization_id: str,
        include_inactive: bool = False
    ) -> List[UserSession]:
        """Get all sessions for an organization.
        
        Args:
            organization_id: The organization ID to look up sessions for
            include_inactive: If True, include expired/revoked sessions
            
        Returns:
            List of UserSession objects (may be empty)
        """
        try:
            query = select(UserSession).where(
                UserSession.organization_id == organization_id
            )
            
            if not include_inactive:
                now = datetime.now(timezone.utc)
                query = query.where(
                    UserSession.expires_at > now,
                    UserSession.revoked_at.is_(None)
                )
            
            result = self.db.execute(query)
            return list(result.scalars().all())
            
        except SQLAlchemyError as e:
            logger.error(
                f"Error retrieving sessions for organization {organization_id}: {e}"
            )
            raise
    
    def expire_session(self, session_id: str) -> bool:
        """Immediately expire a session by setting its expiry to now.
        
        This is a soft expire - the session still exists but is no longer
        valid. Use revoke_session() for explicit revocation.
        
        Args:
            session_id: The session ID to expire
            
        Returns:
            True if session was found and expired, False if not found
        """
        try:
            session = self.get_session_including_inactive(session_id)
            
            if session is None:
                logger.warning(f"Cannot expire non-existent session: {session_id}")
                return False
            
            session.expires_at = datetime.now(timezone.utc)
            self.db.commit()
            
            logger.info(f"Expired session: {session_id}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to expire session {session_id}: {e}")
            raise
    
    def revoke_session(self, session_id: str) -> bool:
        """Explicitly revoke a session.
        
        Unlike expire_session(), this sets the revoked_at timestamp,
        indicating an explicit revocation (e.g., user logout, security event).
        
        Args:
            session_id: The session ID to revoke
            
        Returns:
            True if session was found and revoked, False if not found
        """
        try:
            session = self.get_session_including_inactive(session_id)
            
            if session is None:
                logger.warning(f"Cannot revoke non-existent session: {session_id}")
                return False
            
            if session.revoked_at is not None:
                logger.warning(f"Session already revoked: {session_id}")
                return True  # Idempotent - already revoked
            
            session.revoked_at = datetime.now(timezone.utc)
            self.db.commit()
            
            logger.info(f"Revoked session: {session_id}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to revoke session {session_id}: {e}")
            raise
    
    def is_valid(self, session_id: str) -> bool:
        """Check if a session exists and is active.
        
        A session is valid if it:
        - Exists in the database
        - Has not expired (expires_at > now)
        - Has not been revoked (revoked_at is None)
        
        Args:
            session_id: The session ID to check
            
        Returns:
            True if session is valid, False otherwise
        """
        session = self.get_session(session_id)
        return session is not None
    
    def refresh_session(
        self, 
        session_id: str, 
        additional_hours: int = DEFAULT_SESSION_DURATION_HOURS
    ) -> Optional[UserSession]:
        """Extend a session's expiry time.
        
        This resets the expiry to `additional_hours` from now, effectively
        extending the session. Only active sessions can be refreshed.
        
        Args:
            session_id: The session ID to refresh
            additional_hours: Number of hours to extend (from now)
            
        Returns:
            Updated UserSession if found and refreshed, None if not found/inactive
        """
        try:
            session = self.get_session(session_id)
            
            if session is None:
                logger.warning(f"Cannot refresh non-existent or inactive session: {session_id}")
                return None
            
            new_expiry = datetime.now(timezone.utc) + timedelta(hours=additional_hours)
            session.expires_at = new_expiry
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Refreshed session {session_id}: new expiry={new_expiry}")
            return session
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to refresh session {session_id}: {e}")
            raise
    
    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all active sessions for a user.
        
        Useful for security events like password change or suspicious activity.
        
        Args:
            user_id: The user ID whose sessions to revoke
            
        Returns:
            Number of sessions revoked
        """
        try:
            sessions = self.get_sessions_by_user(user_id, include_inactive=False)
            revoked_count = 0
            
            now = datetime.now(timezone.utc)
            for session in sessions:
                if session.revoked_at is None:
                    session.revoked_at = now
                    revoked_count += 1
            
            self.db.commit()
            
            logger.info(f"Revoked {revoked_count} sessions for user {user_id}")
            return revoked_count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to revoke sessions for user {user_id}: {e}")
            raise
