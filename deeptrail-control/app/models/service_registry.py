"""SQLAlchemy models for the Service Registry and OAuth Config.

The service registry is the single source of truth for all backend services
(REST+OAuth and Remote MCP) available in the organization. The gateway polls
this registry to dynamically load backends.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

from app.db.base import Base


class ServiceRegistry(Base):
    """A registered backend service (REST or MCP) in the organization catalog.

    Backend types:
        - "rest": Traditional REST+OAuth service (Notion, Slack, etc.)
                  Uses DirectClient adapter in the gateway.
        - "mcp":  Remote MCP server (Jira MCP, GitHub MCP, etc.)
                  Uses GenericMCPClient adapter in the gateway.

    Lifecycle: sandbox -> active -> disabled
    """

    __tablename__ = "service_registry"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    service_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Stable identifier (e.g., 'notion', 'jira-mcp')",
    )
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    backend_type = Column(
        String(20),
        nullable=False,
        server_default="rest",
        comment="'rest' (DirectClient) or 'mcp' (GenericMCPClient)",
    )
    endpoint_url = Column(
        String(500),
        nullable=False,
        comment="REST: API base URL. MCP: server endpoint URL",
    )
    transport = Column(String(20), server_default="rest")
    mcp_auth_method = Column(
        String(20),
        server_default="none",
        comment="MCP only: 'none', 'api-key', 'bearer-token', 'oauth'",
    )
    mcp_auth_header = Column(String(100), nullable=True)
    mcp_auth_value_encrypted = Column(
        String(2000),
        nullable=True,
        comment="GCP KMS envelope-encrypted credential",
    )
    mcp_protocol_version = Column(String(20), server_default="2024-11-05")
    discovered_tools = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Cached tool schemas from tools/list",
    )
    tools_last_discovered_at = Column(DateTime(timezone=True), nullable=True)
    permission_map = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Auto-generated: tool_name -> permission_string",
    )
    data_classification = Column(String(20), server_default="internal")
    status = Column(
        String(20),
        server_default="sandbox",
        comment="'active', 'sandbox', 'review', 'disabled'",
    )
    available_to_roles = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        server_default='["all"]',
    )
    available_to_groups = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        server_default="[]",
    )
    available_to_users = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        server_default="[]",
    )
    requires_approval = Column(Boolean, server_default="false")
    health_status = Column(String(20), server_default="unknown")
    health_last_checked_at = Column(DateTime(timezone=True), nullable=True)
    health_latency_ms = Column(Integer, nullable=True)
    health_error_count_24h = Column(Integer, server_default="0")
    organization_id = Column(String(36), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    oauth_config = relationship(
        "ServiceOAuthConfig",
        back_populates="service",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ServiceRegistry(service_id='{self.service_id}', "
            f"backend_type='{self.backend_type}', status='{self.status}')>"
        )


class ServiceOAuthConfig(Base):
    """Organization-level OAuth credentials for a REST service.

    Stores the client_id and encrypted client_secret that the gateway
    uses during OAuth token exchange on behalf of users.
    """

    __tablename__ = "service_oauth_config"
    __table_args__ = (
        UniqueConstraint("service_id", "organization_id", name="uq_oauth_config_service_org"),
    )

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    service_id = Column(
        String(50),
        ForeignKey("service_registry.service_id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id = Column(String(500), nullable=False)
    client_secret_encrypted = Column(
        String(2000),
        nullable=False,
        comment="GCP KMS envelope-encrypted client secret",
    )
    auth_url = Column(String(500), nullable=True)
    token_url = Column(String(500), nullable=True)
    scopes = Column(
        ARRAY(String),
        nullable=True,
        comment="Available OAuth scopes",
    )
    organization_id = Column(String(36), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    service = relationship("ServiceRegistry", back_populates="oauth_config")

    def __repr__(self) -> str:
        return f"<ServiceOAuthConfig(service_id='{self.service_id}')>"
