"""Shared fixtures for deepsecure-proxy tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import pytest


@dataclass
class FakeBootstrapResult:
    jwt: str = "fake-discovery-jwt"
    gateway_url: str = "http://localhost:8002"
    expires_in: int = 3600
    delegations: Optional[list] = None
    platform: str = "local"


@pytest.fixture
def mock_bootstrap_client():
    client = MagicMock()
    client.control_url = "http://localhost:8000"
    client.gateway_url = "http://localhost:8002"
    client.bootstrap.return_value = FakeBootstrapResult()
    return client
