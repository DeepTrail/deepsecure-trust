"""
.well-known endpoints for the Control Plane.

Provides:
  - ``/.well-known/jwks.json`` — JSON Web Key Set (RFC 7517) for RS256
    token signature verification.  The gateway (D3) fetches this
    endpoint to validate Agent Session JWTs.
"""

import logging

from fastapi import APIRouter

from app.core.jwt_signing import get_jwt_signing_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["well-known"])


@router.get(
    "/.well-known/jwks.json",
    summary="JSON Web Key Set (RFC 7517)",
    response_description="JWKS containing the Control Plane's public signing key(s)",
)
async def jwks_endpoint():
    """Return the JWKS document for verifying JWTs issued by this Control Plane.

    Consumers (e.g. the DeepTrail Gateway) should cache this response
    according to standard HTTP caching headers.
    """
    svc = get_jwt_signing_service()
    jwks = svc.get_jwks()
    logger.debug("JWKS requested, returning %d key(s)", len(jwks.get("keys", [])))
    return jwks
