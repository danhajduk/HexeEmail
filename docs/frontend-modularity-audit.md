# Frontend Modularity Audit

This audit documents the current frontend drift against the Hexe Node modular frontend standard.

Primary evidence source:

- [App.jsx](/home/dan/Projects/HexeEmail/frontend/src/App.jsx)

## Current State

- `App.jsx` started this standards pass at `4699` lines and is now `2928`
- the routing helper moved to [router.js](/home/dan/Projects/HexeEmail/frontend/src/app/router.js)
- the shared API client moved to [client.js](/home/dan/Projects/HexeEmail/frontend/src/api/client.js)
- extracted feature modules now exist under [frontend/src/features](/home/dan/Projects/HexeEmail/frontend/src/features)
- `App.jsx` still owns:
  - hash routing
  - global polling and shared state
  - setup/onboarding orchestration
  - cross-feature action wiring

This is now closer to a composition-shell role, but not yet a minimal shell.

## Main Drift Areas

### 1. App owns routing directly

Evidence:

- [App.jsx:69](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L69)
- [App.jsx:92](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L92)
- [App.jsx:2012](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2012)
- [App.jsx:2248](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2248)

Problems:

- route parsing, route building, and route-driven view state all live in `App.jsx`
- dashboard section navigation is hard-wired into the main component
- setup, provider, training, sender-reputation, and dashboard view switching all share one state owner

Recommended extraction:

- `frontend/src/app/router.js`
- `frontend/src/app/routes.js`
- `frontend/src/app/navigation.js`

### 2. App owns the shared API client

Evidence:

- [App.jsx:111](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L111)
- many direct `fetchJson(...)` calls across the file, including:
  - [App.jsx:1962](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L1962)
  - [App.jsx:2281](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2281)
  - [App.jsx:2395](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2395)
  - [App.jsx:2760](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2760)
  - [App.jsx:2825](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2825)
  - [App.jsx:3113](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3113)

Problems:

- request normalization, JSON error handling, and endpoint selection are all embedded in the UI shell
- feature code depends on raw endpoint strings instead of feature-scoped API helpers
- provider views still call compatibility routes like `/providers/*`, while the repo has canonical `/api/providers/*`

Recommended extraction:

- `frontend/src/api/client.js`
- `frontend/src/api/node.js`
- `frontend/src/api/providers.js`
- `frontend/src/api/gmail.js`
- `frontend/src/api/runtime.js`
- `frontend/src/api/training.js`

### 3. App owns setup and onboarding orchestration

Evidence:

- setup flow helpers:
  - [App.jsx:999](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L999)
  - [App.jsx:1042](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L1042)
  - [App.jsx:1173](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L1173)
- onboarding actions:
  - [App.jsx:3133](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3133)
  - [App.jsx:3155](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3155)
  - [App.jsx:3180](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3180)
  - [App.jsx:3206](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3206)

Problems:

- setup status derivation, setup sidebar rendering, operator prompts, config saving, onboarding start, and onboarding restart all live in one file
- this couples setup UI tightly to global app state

Recommended extraction:

- `frontend/src/features/setup/`
- `frontend/src/features/setup/hooks/useSetupFlow.js`
- `frontend/src/features/setup/components/SetupPage.jsx`
- `frontend/src/features/setup/components/SetupSidebar.jsx`
- `frontend/src/features/setup/components/StageCard.jsx`

### 4. App owns provider and Gmail operational workflows

Evidence:

- provider page:
  - [App.jsx:1685](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L1685)
- provider actions:
  - [App.jsx:3110](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3110)
  - [App.jsx:3226](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3226)
  - [App.jsx:3247](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3247)
  - [App.jsx:3271](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3271)
- Gmail operational actions:
  - [App.jsx:2755](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2755)
  - [App.jsx:2784](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2784)
  - [App.jsx:2802](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2802)

Problems:

- provider config form state, provider validation, Gmail connect flow, Gmail status polling, manual fetch actions, Spamhaus refresh, and sender-reputation refresh are all coupled into the main app shell

Recommended extraction:

- `frontend/src/features/providers/gmail/`
- `frontend/src/features/providers/gmail/GmailSetupPage.jsx`
- `frontend/src/features/providers/gmail/hooks/useGmailProviderState.js`
- `frontend/src/features/providers/gmail/hooks/useGmailActions.js`

### 5. App owns runtime AI tooling

Evidence:

- runtime status helpers:
  - [App.jsx:177](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L177)
  - [App.jsx:197](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L197)
  - [App.jsx:222](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L222)
- runtime action builders and flows:
  - [App.jsx:2281](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2281)
  - [App.jsx:2336](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2336)
  - [App.jsx:2381](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2381)
  - [App.jsx:2424](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2424)
  - [App.jsx:2467](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2467)
  - [App.jsx:2536](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2536)
  - [App.jsx:2599](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2599)
  - [App.jsx:2646](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2646)
  - [App.jsx:2705](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2705)

Problems:

- runtime settings, payload construction, preview/resolve/authorize flows, prompt sync, single-message execution, batch execution, and action-decision execution all share one state owner

Recommended extraction:

- `frontend/src/features/runtime/`
- `frontend/src/features/runtime/hooks/useRuntimeTaskState.js`
- `frontend/src/features/runtime/runtimePayloads.js`
- `frontend/src/features/runtime/RuntimeDashboard.jsx`

### 6. App owns training and sender-reputation workflows

Evidence:

- sender reputation components:
  - [App.jsx:465](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L465)
  - [App.jsx:566](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L566)
- training page:
  - [App.jsx:1440](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L1440)
- training and reputation actions:
  - [App.jsx:2820](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2820)
  - [App.jsx:2853](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2853)
  - [App.jsx:2910](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2910)
  - [App.jsx:2949](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2949)
  - [App.jsx:2984](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L2984)
  - [App.jsx:3041](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3041)

Problems:

- training batch loading, selection state, pagination, save flows, model training, sender-reputation inspection, manual rating, and sender-group collapse state all live in `App.jsx`

Recommended extraction:

- `frontend/src/features/training/`
- `frontend/src/features/training/TrainingPage.jsx`
- `frontend/src/features/training/hooks/useTrainingState.js`
- `frontend/src/features/training/reputation/`

### 7. App owns scheduled-task and tracked-order presentation

Evidence:

- scheduled-task helper utilities:
  - [App.jsx:808](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L808)
  - [App.jsx:847](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L847)
- tracked order helpers:
  - [App.jsx:264](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L264)
- dashboard section rendering around:
  - [App.jsx:3600](/home/dan/Projects/HexeEmail/frontend/src/App.jsx#L3600)

Problems:

- scheduled-task formatting, legend derivation, status tones, and tracked-order rendering are tangled into the same dashboard shell that also renders runtime and Gmail controls

Recommended extraction:

- `frontend/src/features/scheduled/`
- `frontend/src/features/orders/`

### 8. App mixes utilities, pages, hooks, and rendering in one file

Evidence:

- utility functions at the top of the file
- page components in the middle
- all hooks and side effects inside `App`
- all top-level rendering branches at the bottom

Problems:

- there is no clear separation between:
  - formatting utilities
  - data loading hooks
  - feature state machines
  - page components
  - shell composition

## Recommended Extraction Order

### Phase A: low-risk shared modules

- move `fetchJson` into `frontend/src/api/client.js`
- move formatting and derivation helpers into `frontend/src/lib/`
- move route parsing/building into `frontend/src/app/router.js`

### Phase B: feature hooks

- extract setup hook
- extract provider/Gmail hook
- extract runtime hook
- extract training/reputation hook

### Phase C: page modules

- setup page
- provider page
- training page
- sender reputation page
- dashboard sections split into overview, Gmail, runtime, scheduled, and orders

### Phase D: App as composition shell

Target end state:

- `App.jsx` owns shell-level route choice and shared bootstrap coordination only
- feature modules own their own API helpers, local state, and rendering

## Proposed Module Map

- `frontend/src/app/AppShell.jsx`
- `frontend/src/app/router.js`
- `frontend/src/api/client.js`
- `frontend/src/api/node.js`
- `frontend/src/api/providers.js`
- `frontend/src/api/gmail.js`
- `frontend/src/api/runtime.js`
- `frontend/src/api/training.js`
- `frontend/src/features/setup/`
- `frontend/src/features/dashboard/`
- `frontend/src/features/providers/gmail/`
- `frontend/src/features/runtime/`
- `frontend/src/features/scheduled/`
- `frontend/src/features/orders/`
- `frontend/src/features/training/`
- `frontend/src/lib/formatters.js`
- `frontend/src/lib/status.js`

## Audit Conclusion

The frontend already has usable feature boundaries in the product itself, but those boundaries are not reflected in the code structure. The main modularity problem is not missing components; it is that `App.jsx` is simultaneously the router, data layer, workflow coordinator, and view registry.

Task 209 should reduce `App.jsx` to a composition shell and move feature ownership into extracted modules that match the visible product areas already present in the UI.
