# Architecture Overview

> Extracted from CLAUDE.md. This is the reference for system architecture.

## Core Module Structure

- **`deepsecure/_core/`**: Internal implementation modules
  - `client.py`: High-level client services wrapping core functionalities
  - `base_client.py`: Base HTTP client with authentication
  - `vault_client.py`: Secret management operations
  - `agent_client.py`: Agent identity management
  - `identity_manager.py`: Agent identity and key management
  - `crypto/key_manager.py`: Cryptographic key operations
  - `config.py`: Configuration management

- **`deepsecure/`**: Public API layer
  - `client.py`: Main SDK client (uses _core modules)
  - `commands/`: CLI command implementations
  - `integrations/`: Framework integrations (LangChain, CrewAI)
  - `resources/`: Resource objects (Agent, Secret)

## Backend Services

- **`deeptrail-control/`**: Control plane (agent management, authentication, policies)
- **`deeptrail-gateway/`**: Data plane (API proxy with secret injection)

## Key Patterns

### 1. Dual Client Architecture
- `deepsecure.Client` (public SDK) wraps `deepsecure._core.client` (internal)
- Core modules handle low-level operations, public client provides clean API

### 2. Identity Provider Pattern
- Multiple identity providers (Keyring, Kubernetes, AWS)
- Agents bootstrap identity from platform-native mechanisms

### 3. Gateway Architecture
- External API calls routed through gateway with automatic secret injection
- JWT-based authentication between services

## Backend Service File Path Conventions

| Design Doc Pattern | Actual Pattern | Convention |
|--------------------|----------------|------------|
| `[service]/models/` | `[service]/app/models/` | FastAPI `app/` prefix |
| `[service]/services/` | `[service]/app/services/` | FastAPI `app/` prefix |
| `[service]/api/[domain]/` | `[service]/app/api/v1/endpoints/` | Versioned, flat |

### Naming Conventions
- Services: Always use `*_service.py` suffix
- Validation: Use descriptive names (e.g., `[x]_validation.py`)
- Constraints: Use active verbs (e.g., `[x]_checker.py`)

### Directory Structure
```
[service-name]/
├── app/
│   ├── api/v1/endpoints/    ← Flat, versioned API endpoints
│   ├── models/              ← SQLAlchemy/Pydantic models
│   ├── services/            ← Business logic (*_service.py)
│   ├── middleware/          ← Request/response handling
│   ├── security/            ← Security concerns
│   └── [domain]/            ← Domain modules
├── tests/
└── migrations/
```

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tool configurations |
| `docker-compose.yml` | Backend services orchestration |
| `pytest.ini` | Test configuration and markers |
| `Makefile` | Development workflow automation |
