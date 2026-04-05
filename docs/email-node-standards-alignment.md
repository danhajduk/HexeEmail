# Email Node Standards Alignment

This document maps the current `HexeEmail` repository to the Hexe Node Standard.

Standards reference:

- Main standard entrypoint: `/home/dan/Projects/Hexe/docs/standards/Node/README.md`
- Standards folder: `/home/dan/Projects/Hexe/docs/standards/Node/`

## Current Repo Map

### Backend composition

- App entrypoint: [src/main.py](/home/dan/Projects/HexeEmail/src/main.py)
- Primary service owner: [src/service.py](/home/dan/Projects/HexeEmail/src/service.py)
- Shared node models: [src/models.py](/home/dan/Projects/HexeEmail/src/models.py)
- Provider-specific implementation: [src/providers/](/home/dan/Projects/HexeEmail/src/providers/)

Current status:

- The repo satisfies the standard’s requirement for a clear backend entrypoint and provider subtree.
- The repo currently drifts from the modular backend standard because route ownership is concentrated in `src/main.py` and most runtime/service ownership is concentrated in `src/service.py`.

### Frontend composition

- Frontend entry shell: [frontend/src/App.jsx](/home/dan/Projects/HexeEmail/frontend/src/App.jsx)

Current status:

- The repo satisfies the standard’s requirement for a local operator UI.
- The repo currently drifts from the frontend modularity standard because one file still owns onboarding, dashboard state, Gmail operations, runtime tooling, scheduled-task views, and training controls.

### Scripts and operations

- Scripts folder: [scripts/](/home/dan/Projects/HexeEmail/scripts/)

Current status:

- The repo already has the required local operational scripts such as `start.sh`, `run-from-env.sh`, `stack-control.sh`, `restart-stack.sh`, and systemd templates.
- The operator docs still need one canonical workflow path so the scripts line up with the standard’s expectations.

### Repo documentation

Existing implementation and phase docs already present include:

- [email-node-architecture.md](/home/dan/Projects/HexeEmail/docs/email-node-architecture.md)
- [phase1-runbook.md](/home/dan/Projects/HexeEmail/docs/phase1-runbook.md)
- [phase2-gmail-provider-runbook.md](/home/dan/Projects/HexeEmail/docs/phase2-gmail-provider-runbook.md)
- ORDER flow notes under [docs/](/home/dan/Projects/HexeEmail/docs)

Current status:

- The repo has substantial implementation notes.
- The repo drift is that operators still have to infer the source-of-truth path from phase-specific notes instead of starting from a small set of canonical repo-level docs.

## Standards Alignment By Area

### Core node model

Aligned:

- onboarding/trust lifecycle exists
- readiness and governance state exist
- node status and bootstrap visibility exist

Primary evidence:

- [src/service.py](/home/dan/Projects/HexeEmail/src/service.py)
- [src/main.py](/home/dan/Projects/HexeEmail/src/main.py)

### Backend standard

Partially aligned:

- provider subtree exists
- runtime and onboarding behavior are implemented
- main service boundaries are not yet modular enough

Primary drift:

- `src/main.py` is still a monolithic route registry
- `src/service.py` still owns too many domains directly
- `src/models.py` is still a broad shared schema file

### API standard

Partially aligned:

- canonical `/api/*` routes already exist for many domains
- compatibility routes still coexist with canonical routes
- provider routes still mix canonical and compatibility ownership

Primary evidence:

- [api-map.md](/home/dan/Projects/HexeEmail/docs/api-map.md)

### Frontend standard

Partially aligned:

- setup and operational UI are present
- operator visibility exists for runtime and Gmail behavior
- frontend feature boundaries are not yet modularized

Primary drift:

- [frontend/src/App.jsx](/home/dan/Projects/HexeEmail/frontend/src/App.jsx) is still the main owner of nearly every feature path

### Scripts and operations standard

Mostly aligned:

- required scripts exist
- systemd templates exist
- stack-oriented operation scripts exist

Primary drift:

- docs need to declare one canonical startup/restart/status workflow

### Background tasks and scheduler standard

Partially aligned:

- recurring tasks exist for onboarding finalize polling, Gmail status, Gmail fetch, and runtime activity
- scheduler ownership is still embedded inside `NodeService`

### Persistence, configuration, and security standard

Mostly aligned:

- typed config exists
- runtime path usage exists
- provider stores and token/state files exist

Primary drift:

- repo docs need explicit operator guidance for runtime path ownership and sensitive-state handling

### Provider boundary standard

Partially aligned:

- Gmail-specific implementation lives under `src/providers/gmail/`
- provider registration and some ownership boundaries are still split between registry and node service

### Testing and documentation standard

Mostly aligned:

- API tests, onboarding tests, provider tests, persistence tests, and runtime-related tests exist
- repo-level source-of-truth docs and standards compliance docs were missing before this standards batch

## Current Standards Work Queue

This standards batch is intended to close the main repo drift in this order:

1. establish repo-level source-of-truth docs
2. document and normalize the API
3. modularize route ownership
4. modularize models and services
5. isolate scheduler/background-task ownership
6. document provider, runtime-path, and security boundaries
7. modularize the frontend
8. finish with compliance summary and verification
