# Shared Node API Reference

This document compares the currently implemented API surface in:

- Hexe Email node: `/home/dan/Projects/HexeEmail/src`
- Hexe AI node: `/home/dan/Projects/HexeAiNode/src`

This is a code-derived reference. It reflects the routes and Core client paths that exist now, not planned contracts.

## Scope

This file covers:

- local node control APIs exposed by each node
- overlapping operator workflows
- shared Core-facing APIs used by both nodes

This file does not try to normalize provider-specific APIs that only exist in one node type, such as Gmail OAuth on the Email node or OpenAI model catalogs on the AI node.

## Summary

The Email node now exposes a much closer AI-node-style `/api/*` control-plane surface than it did originally.

The strongest local overlap now includes:

- health
- node status
- onboarding restart
- capability config / declare / redeclare / rebuild / diagnostics / resolved
- governance status / refresh
- services status / restart
- node recovery

The strongest exact overlap remains in the Core-facing APIs:

- capability declaration to Core
- governance retrieval from Core
- trust-status checks against Core

The biggest remaining divergence is no longer the control-plane namespace. It is now:

- onboarding start naming and request shape
- provider route families
- service restart semantics
- bootstrap payload shape

## 1. Shared Local Control-Plane APIs

These are local node APIs, not Core APIs.

### 1.1 Health

Hexe Email:

- `GET /api/health`
- `GET /health/live`
- `GET /health/ready`

Hexe AI node:

- `GET /api/health`

Notes:

- `GET /api/health` now overlaps directly.
- Email still keeps separate liveness/readiness endpoints in addition to the AI-style alias.

Reuse value:

- strong shared local API shape

### 1.2 Node Status

Hexe Email:

- `GET /api/node/status`
- `GET /status`
- `GET /api/node/bootstrap`
- `GET /ui/bootstrap` as a compatibility alias

Hexe AI node:

- `GET /api/node/status`

Notes:

- `GET /api/node/status` now overlaps directly.
- Email still exposes a richer bootstrap aggregate endpoint that the AI node does not expose under the same path.

Reuse value:

- strong shared local API shape
- bootstrap remains Email-specific

### 1.3 Node Config

Hexe Email:

- `GET /api/node/config`
- `PUT /api/node/config`
- `GET /ui/config` as a compatibility alias
- `PUT /ui/config` as a compatibility alias

Hexe AI node:

- no direct `GET/PUT /api/node/config` equivalent found in the scanned route set

Notes:

- Email exposes node/operator configuration directly.
- AI node spreads similar setup state across more task-specific routes.

Reuse value:

- Email-specific in current comparison

### 1.4 Onboarding Start

Hexe Email:

- `POST /api/onboarding/start`
- `POST /ui/onboarding/start` as a compatibility alias

Hexe AI node:

- `POST /api/onboarding/initiate`

Notes:

- Same lifecycle intent: begin onboarding with Core.
- Still not path-compatible.
- Email starts from saved operator config.
- AI node accepts a more explicit initiate payload.

Reuse value:

- shared lifecycle operation
- not fully normalized yet

### 1.5 Onboarding Restart

Hexe Email:

- `POST /api/onboarding/restart`
- `POST /ui/onboarding/restart` as a compatibility alias

Hexe AI node:

- `POST /api/onboarding/restart`

Notes:

- This is now directly aligned at the `/api/*` route level.
- The request payload semantics still differ slightly.

Reuse value:

- strong shared local API shape

### 1.6 Capability Config

Hexe Email:

- `GET /api/capabilities/config`
- `POST /api/capabilities/config`

Hexe AI node:

- `GET /api/capabilities/config`
- `POST /api/capabilities/config`

Notes:

- This is now a real local API overlap.
- Email internally stores this in operator config, but exposes it as a dedicated capability config surface.

Reuse value:

- strong shared local API shape

### 1.7 Capability Declaration

Hexe Email:

- `POST /api/capabilities/declare`
- `POST /ui/capabilities/declare` as a compatibility alias

Hexe AI node:

- `POST /api/capabilities/declare`

Notes:

- Route shape now overlaps directly.
- The underlying Core-facing capability declaration contract is also shared.

Reuse value:

- strong shared local API shape

### 1.8 Capability Diagnostics / Redeclare / Rebuild / Resolved

Hexe Email:

- `GET /api/capabilities/diagnostics`
- `POST /api/capabilities/redeclare`
- `POST /api/capabilities/rebuild`
- `GET /api/capabilities/node/resolved`

Hexe AI node:

- `GET /api/capabilities/diagnostics`
- `POST /api/capabilities/redeclare`
- `POST /api/capabilities/rebuild`
- `GET /api/capabilities/node/resolved`

Notes:

- This is now one of the strongest route-family overlaps between the two repos.
- Email implements these in a thinner way, based on a simpler runtime/capability model.
- AI node has deeper capability graph and catalog machinery behind the same route family.

Reuse value:

- strong shared local route family

### 1.9 Governance Status / Refresh

Hexe Email:

- `GET /api/governance/status`
- `POST /api/governance/refresh`

Hexe AI node:

- `GET /api/governance/status`
- `POST /api/governance/refresh`

Notes:

- This now overlaps directly as a local control-plane API.
- Email still also includes governance state inside broader node status/bootstrap responses.

Reuse value:

- strong shared local API shape

### 1.10 Services Status / Restart

Hexe Email:

- `GET /api/services/status`
- `POST /api/services/restart`

Hexe AI node:

- `GET /api/services/status`
- `POST /api/services/restart`

Notes:

- Route shape now overlaps directly.
- Behavior is not identical:
  - Email returns `manual_required` for backend/frontend/node restarts because the API process does not directly own those external processes
  - Email can restart MQTT locally
  - AI node has a richer service-control runtime

Reuse value:

- strong shared local API shape
- partial behavioral alignment

### 1.11 Node Recovery

Hexe Email:

- `POST /api/node/recover`

Hexe AI node:

- `POST /api/node/recover`

Notes:

- Route shape now overlaps directly.
- Email recovery currently performs a local trust/onboarding reset.
- AI node recovery is broader in scope.

Reuse value:

- strong shared local recovery contract family

## 2. Shared Provider Configuration Pattern

Both nodes implement a provider configuration workflow, but the provider family differs.

Hexe Email:

- `GET /providers`
- `GET /providers/gmail/config`
- `PUT /providers/gmail/config`
- `POST /providers/gmail/validate-config`

Hexe AI node:

- `GET /api/providers/config`
- `POST /api/providers/config`
- `GET /api/providers/openai/credentials`
- `POST /api/providers/openai/credentials`
- `POST /api/providers/openai/preferences`

Notes:

- The shared pattern is real even though the paths are different:
  - read provider config
  - write provider config
  - expose provider-specific credential/configuration APIs
- Email is narrower and Gmail-specific.
- AI node is broader and OpenAI-provider oriented.

Reuse value:

- shared design pattern
- not a shared route contract

## 3. Shared Core-Facing APIs

These are the most important overlaps because both nodes already talk to the same Core contracts.

### 3.1 Core Capability Declaration

Hexe Email Core client:

- `POST /api/system/nodes/capabilities/declaration`

Hexe AI node Core client:

- `POST /api/system/nodes/capabilities/declaration`

Where:

- Email: `src/core/capability_client.py`
- AI node: `/home/dan/Projects/HexeAiNode/src/ai_node/core_api/capability_client.py`

Notes:

- This is a genuine shared Core API.
- Both nodes send a manifest payload under `{"manifest": ...}`.
- Both use the node trust token in headers.
- Email currently models the response more minimally.
- AI node has richer response classification and retryability handling.

Reuse value:

- exact shared Core path
- high-value implementation reference

### 3.2 Core Governance Retrieval

Hexe Email Core client:

- `GET /api/system/nodes/governance/current`
- `POST /api/system/nodes/governance/refresh`

Hexe AI node Core client:

- `GET /api/system/nodes/governance/current` via `DEFAULT_GOVERNANCE_SYNC_PATH`

Where:

- Email: `src/core/governance_client.py`
- AI node: `/home/dan/Projects/HexeAiNode/src/ai_node/core_api/governance_client.py`

Notes:

- Both nodes already depend on the same governance-current contract.
- Email additionally uses the refresh endpoint directly in its current client.
- AI node wraps the current path as a single baseline governance fetch operation.

Reuse value:

- exact shared Core path for current governance
- near-shared refresh behavior

### 3.3 Core Trust Status

Hexe Email Core client:

- `GET /api/system/nodes/trust-status/{node_id}`

Hexe AI node Core client:

- `GET /api/system/nodes/trust-status/{node_id}`

Where:

- Email: `src/core_client.py`
- AI node: `/home/dan/Projects/HexeAiNode/src/ai_node/core_api/trust_status_client.py`

Notes:

- This is another exact shared Core contract.
- Both nodes send the node trust token headers.
- AI node has more explicit status classification helpers.

Reuse value:

- exact shared Core path
- strong candidate for shared client logic in the future

### 3.4 Core Platform Identity

Hexe Email Core client:

- `GET /api/system/platform`

Hexe AI node:

- no direct equivalent found in the scanned local API client set

Notes:

- This is currently Email-specific in the compared code.
- It is useful for resolving the real Core UUID.

Reuse value:

- Email-only in this comparison

## 4. APIs Used In Both Repositories

This section lists APIs that are genuinely used in both codebases, either as shared local route families or as shared Core contracts.

### 4.1 Same local route family in both

- `GET /api/health`
- `GET /api/node/status`
- `POST /api/onboarding/restart`
- `GET /api/capabilities/config`
- `POST /api/capabilities/config`
- `POST /api/capabilities/declare`
- `GET /api/capabilities/diagnostics`
- `POST /api/capabilities/redeclare`
- `POST /api/capabilities/rebuild`
- `GET /api/capabilities/node/resolved`
- `GET /api/governance/status`
- `POST /api/governance/refresh`
- `GET /api/services/status`
- `POST /api/services/restart`
- `POST /api/node/recover`

### 4.2 Same capability, different local route or behavior

- onboarding start:
  - Email: `POST /api/onboarding/start`
  - AI node: `POST /api/onboarding/initiate`
- runtime bootstrap:
  - Email: `GET /api/node/bootstrap`
  - AI node: no direct equivalent route found in the scanned local API set
- provider configuration:
  - Email uses Gmail-specific provider routes
  - AI node uses OpenAI-focused provider routes
- service restart behavior:
  - routes align
  - Email intentionally returns `manual_required` for some targets

### 4.3 Same Core route in both

- `POST /api/system/nodes/capabilities/declaration`
- `GET /api/system/nodes/governance/current`
- `GET /api/system/nodes/trust-status/{node_id}`

### 4.4 Closely related Core route family

- `POST /api/system/nodes/governance/refresh`

Email uses it directly.

AI node already implements the same governance sync domain and could align to the same explicit refresh flow if needed.

## 5. Practical Reuse Opportunities

The AI node repo still contains implementation patterns that are useful to the Email node.

### 5.1 Good reuse candidates from HexeAiNode

- clearer capability declaration lifecycle responses
- richer trust-status response classification
- deeper diagnostics payloads behind already-aligned routes
- richer provider debug surfaces if the Email node needs them later

### 5.2 Already-shared contracts worth keeping aligned

- local `/api/*` control-plane route families
- Core capability declaration
- Core governance retrieval
- Core trust-status checks

### 5.3 Not shared enough yet to treat as one contract

- provider configuration routes
- UI bootstrap payload shape
- onboarding start request bodies
- restart execution semantics

## 6. Recommendation

If the goal is gradual cross-node convergence, the safest order is:

1. keep the shared Core APIs aligned first
2. keep the shared local `/api/*` control-plane routes aligned second
3. normalize provider route families last

That order keeps the Core contract stable while allowing each node to evolve its provider-specific behavior without breaking trusted runtime behavior.

## 7. Source Files Used

Hexe Email:

- `src/main.py`
- `src/core/capability_client.py`
- `src/core/governance_client.py`
- `src/core_client.py`
- `src/service.py`
- `frontend/src/App.jsx`

Hexe AI node:

- `/home/dan/Projects/HexeAiNode/src/ai_node/runtime/node_control_api.py`
- `/home/dan/Projects/HexeAiNode/src/ai_node/core_api/capability_client.py`
- `/home/dan/Projects/HexeAiNode/src/ai_node/core_api/governance_client.py`
- `/home/dan/Projects/HexeAiNode/src/ai_node/core_api/trust_status_client.py`
