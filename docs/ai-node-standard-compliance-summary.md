# Email Node Standard Compliance Summary

This document is the email-node equivalent of the standard compliance summary used in other Hexe nodes.

Standards reference:

- Main standard entrypoint: `/home/dan/Projects/Hexe/docs/standards/Node/README.md`
- Standards folder: `/home/dan/Projects/Hexe/docs/standards/Node/`

## Compliance Snapshot

The repository now aligns with the Hexe Node standard in the main structural areas that the standard treats as mandatory:

- modular backend route ownership is present under [src/api/routes](/home/dan/Projects/HexeEmail/src/api/routes)
- modular backend service ownership is present under [src/node_backend](/home/dan/Projects/HexeEmail/src/node_backend)
- provider-specific logic remains under [src/providers](/home/dan/Projects/HexeEmail/src/providers)
- repo-level operational docs exist under [docs/](/home/dan/Projects/HexeEmail/docs)
- canonical local operational control exists through [stack-control.sh](/home/dan/Projects/HexeEmail/scripts/stack-control.sh)
- frontend feature modules now exist under [frontend/src/features](/home/dan/Projects/HexeEmail/frontend/src/features)
- the frontend shell now uses shared routing and API helpers under [frontend/src/app](/home/dan/Projects/HexeEmail/frontend/src/app) and [frontend/src/api](/home/dan/Projects/HexeEmail/frontend/src/api)

## Areas Now Compliant

### Backend structure

Compliant evidence:

- [main.py](/home/dan/Projects/HexeEmail/src/main.py)
- [node.py](/home/dan/Projects/HexeEmail/src/api/routes/node.py)
- [runtime.py](/home/dan/Projects/HexeEmail/src/api/routes/runtime.py)
- [providers_gmail.py](/home/dan/Projects/HexeEmail/src/api/routes/providers_gmail.py)
- [service.py](/home/dan/Projects/HexeEmail/src/service.py)
- [src/node_backend](/home/dan/Projects/HexeEmail/src/node_backend)

Summary:

- startup wiring is thin
- route ownership is split by domain
- recurring work, onboarding, governance, notifications, providers, and runtime state have explicit backend owners

### API structure

Compliant evidence:

- [api-map.md](/home/dan/Projects/HexeEmail/docs/api-map.md)
- [src/api/routes](/home/dan/Projects/HexeEmail/src/api/routes)

Summary:

- canonical route groups are documented
- compatibility paths still exist where needed, but canonical ownership is explicit

### Frontend structure

Compliant evidence:

- [App.jsx](/home/dan/Projects/HexeEmail/frontend/src/App.jsx)
- [frontend/src/app/router.js](/home/dan/Projects/HexeEmail/frontend/src/app/router.js)
- [frontend/src/api/client.js](/home/dan/Projects/HexeEmail/frontend/src/api/client.js)
- [frontend/src/features](/home/dan/Projects/HexeEmail/frontend/src/features)

Summary:

- `App.jsx` now acts as a composition shell plus shared state owner
- setup, provider, training, reputation, runtime, scheduled-task, tracked-order, Gmail dashboard, and overview dashboard rendering are extracted into feature modules

### Scripts and operations

Compliant evidence:

- [operations.md](/home/dan/Projects/HexeEmail/docs/operations.md)
- [stack-control.sh](/home/dan/Projects/HexeEmail/scripts/stack-control.sh)
- [start.sh](/home/dan/Projects/HexeEmail/scripts/start.sh)
- [status.sh](/home/dan/Projects/HexeEmail/scripts/status.sh)

Summary:

- `stack-control.sh status` is the canonical status path
- start and status compatibility wrappers remain allowed repo variants

### Scheduler, runtime paths, and provider boundaries

Compliant evidence:

- [scheduler-and-background-tasks.md](/home/dan/Projects/HexeEmail/docs/scheduler-and-background-tasks.md)
- [runtime-path-ownership.md](/home/dan/Projects/HexeEmail/docs/runtime-path-ownership.md)
- [provider-boundary.md](/home/dan/Projects/HexeEmail/docs/provider-boundary.md)
- [security-and-sensitive-state.md](/home/dan/Projects/HexeEmail/docs/security-and-sensitive-state.md)

Summary:

- recurring work ownership is documented and reflected in code
- runtime storage boundaries are explicit
- provider-specific behavior remains inside the provider subtree

## Allowed Repo Variants

The following are intentional repo-specific variants that still fit the standard:

- the node remains Gmail-focused and email-domain specific
- compatibility routes remain alongside canonical routes where operator or integration continuity still matters
- `App.jsx` still owns global polling, route-driven state, and cross-feature orchestration instead of pushing everything into custom hooks
- the repo keeps provider-specific ORDER flow logic under the Gmail provider subtree rather than forcing generic node abstractions for seller-specific processing

## Intentionally Provider Or Domain Specific

The standard does not attempt to flatten domain-specific behavior, and this repo intentionally keeps the following specialized:

- Gmail mailbox fetch, OAuth, status, and training behavior
- ORDER flow phases and extraction templates
- sender reputation logic derived from local email-classification and Spamhaus inputs
- local email-classification review workflows

## Remaining Drift That Is Acceptable For Now

The repo still has some compact areas, but they are acceptable under the standard’s compact-implementation rules:

- [App.jsx](/home/dan/Projects/HexeEmail/frontend/src/App.jsx) still owns much of the shared polling and cross-feature state
- some frontend API calls are still direct `fetchJson(...)` usages from the shell rather than feature-specific API modules
- some backend model ownership still flows through broader shared model surfaces where domain splits are already underway

These areas no longer blur lifecycle, provider, scheduler, or security ownership, so they are acceptable variants rather than compliance failures.
