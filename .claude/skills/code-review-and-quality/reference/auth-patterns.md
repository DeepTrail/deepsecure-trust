# DeepSecure Authentication Patterns

Reference material loaded on-demand when reviewing auth-related code.

## Token Types

| Token Type | How to Obtain | Used For | Header Format |
|------------|---------------|----------|---------------|
| **User Token** | `POST /api/v1/auth/login` → `.token` | User-facing endpoints, service connection | `Authorization: Bearer $USER_TOKEN` |
| **Agent JWT** | Ed25519 challenge-response → `.access_token` | Agent-to-Control APIs, vault token retrieval | `Authorization: Bearer $AGENT_JWT` |
| **Internal API Token** | From `docker-compose.yml` env var | Gateway-to-Control internal APIs | `Authorization: Bearer gateway-internal-secret-token` |

## Common Token Mistakes (Check During Review)

| Mistake | Error | Fix |
|---------|-------|-----|
| Using User Token for vault | `401 "missing user identity"` | Use Agent JWT (has `owner` claim) |
| Using User Token for vault refresh | `401 "Invalid internal token"` | Use Internal Token + `X-User-ID` |
| Using `.access_token` for login | Returns `null` | Login returns `.token` not `.access_token` |
| Calling `tools/call` without `initialize` | `Session not found` | MCP requires `initialize` first |

## Agent JWT Creation Flow

```
1. Generate Ed25519 keypair
2. Register agent with public key: POST /api/v1/agents/
3. Create delegation: POST /api/v1/auth/delegate
4. Request challenge: POST /api/v1/auth/agent/challenge
5. Sign challenge with private key (base64url encoded)
6. Verify and get JWT: POST /api/v1/auth/agent/verify → .access_token
```

## MCP Gateway Protocol

```
1. POST /mcp { "method": "initialize", ... }    → Establishes session
2. POST /mcp { "method": "tools/list", ... }     → Lists available tools (optional)
3. POST /mcp { "method": "tools/call", ... }     → Executes a tool (requires session)
```

Calling `tools/call` without `initialize` returns:
```json
{"error": {"code": -32002, "message": "Session not found. Call initialize first."}}
```

## Endpoint Auth Verification Commands

```bash
# Check all endpoints have auth dependencies
grep -A5 "@router\." [file] | grep -E "Depends|current_user|verify_token"

# Find endpoints missing auth
grep -B2 "@router\." [file] | grep -v "Depends"

# Verify token types match
grep -rn "Authorization\|Bearer\|token\|jwt" [changed_files]
```

## Cryptographic Requirements

- **Algorithm:** Ed25519 only (not RSA, not ECDSA)
- **Challenge entropy:** Minimum 32 bytes
- **Challenge expiry:** 60 seconds maximum
- **Signature encoding:** base64url
- **Libraries:** `nacl` or `cryptography` only (no custom crypto)
- **Banned:** ECB mode, MD5, SHA1 for security purposes
