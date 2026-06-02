from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_fleet,
    admin_roles,
    admin_services,
    agent_auth,
    agents,
    attestation_policies,
    audit,
    auth,
    bootstrap,
    delegation,
    internal,
    oauth,
    policies,
    services_catalog,
    sso,
    tasks,
    users,
    vault,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(delegation.router, prefix="/auth", tags=["auth"])
api_router.include_router(
    agent_auth.router,
    prefix="/auth/agent",
    tags=["agent-auth"],
)
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(
    attestation_policies.router,
    prefix="/policies/attestation",
    tags=["policies"],
)
api_router.include_router(policies.router, prefix="/policies", tags=["policies"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"], include_in_schema=False)
api_router.include_router(bootstrap.router, prefix="/bootstrap", tags=["bootstrap"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(sso.router, prefix="/auth/sso", tags=["sso"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(services_catalog.router, prefix="/services", tags=["services"])
api_router.include_router(admin_roles.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_services.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_fleet.router, prefix="/admin", tags=["admin"])