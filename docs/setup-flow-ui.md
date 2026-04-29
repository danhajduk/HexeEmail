# Setup Flow UI

This document explains the frontend setup flow in the Hexe Email UI, which cards are visible during setup, and which forms or actions are available at each step.

## Main layout

The setup screen is composed of these persistent areas:

- `SetupHeroCard`
  File: `frontend/src/features/setup/cards/SetupHeroCard.jsx`
  Always visible at the top of the setup screen.
- `SetupSidebar`
  File: `frontend/src/features/setup/SetupComponents.jsx`
  Always visible on the left and shows the flow steps.
- Main setup card area
  Shows either `NodeIdentityFormCard` or `NodeSetupCard` depending on setup state.
- `LiveStatusCard`
  File: `frontend/src/features/setup/cards/LiveStatusCard.jsx`
  Always visible in the lower secondary grid.
- `OperatorPromptsCard`
  File: `frontend/src/features/setup/cards/OperatorPromptsCard.jsx`
  Always visible in the lower secondary grid.

The main setup layout is assembled in:

- `frontend/src/App.jsx`

## Visibility rules

The setup screen switches between two main center cards:

- `NodeIdentityFormCard`
  Shown when `nodeSetupVisible` is `false`.
- `NodeSetupCard`
  Shown when `nodeSetupVisible` is `true`.

`nodeSetupVisible` becomes true when any of these are present:

- an onboarding session id
- an approval URL
- onboarding status is not `not_started`
- trust state is not `untrusted`

That logic lives in:

- `frontend/src/App.jsx`
  Function: `isNodeSetupVisible(bootstrap)`

## Persistent cards

### SetupHeroCard

File:

- `frontend/src/features/setup/cards/SetupHeroCard.jsx`

Purpose:

- shows overall node setup status
- shows top-level actions

Actions:

- `Restart Setup`
- `Dashboard`
- `Setup Provider`

Status shown:

- node state
- onboarding status
- MQTT status

### SetupSidebar

File:

- `frontend/src/features/setup/SetupComponents.jsx`

Purpose:

- shows the ordered flow:
  `Node Identity` -> `Core Connection` -> `Bootstrap Discovery` -> `Registration` -> `Approval` -> `Trust Activation` -> `Provider Setup` -> `Capability Declaration` -> `Governance Sync` -> `Ready`

### LiveStatusCard

File:

- `frontend/src/features/setup/cards/LiveStatusCard.jsx`

Purpose:

- shows current runtime facts for the node

Data shown:

- node name
- version
- trust state
- node id
- MQTT state
- providers

### OperatorPromptsCard

File:

- `frontend/src/features/setup/cards/OperatorPromptsCard.jsx`

Purpose:

- gives the operator next-step guidance based on current setup state

Examples:

- enter Core URL and node name
- open approval URL
- keep page open while finalize polling continues
- use Setup Provider after trust is active

## Main center cards

### 1. NodeIdentityFormCard

File:

- `frontend/src/features/setup/cards/NodeIdentityFormCard.jsx`

When shown:

- before setup has started
- when `nodeSetupVisible === false`

Form fields:

- `core_base_url`
  Label: `Core base URL`
- `node_name`
  Label: `Node name`

Actions:

- `Save`
- `Start Onboarding`

Warnings:

- shows `Required before onboarding` when required inputs are still missing

This is the only true text-input form shown on the main setup screen before onboarding begins.

### 2. NodeSetupCard

File:

- `frontend/src/features/setup/cards/NodeSetupCard.jsx`

When shown:

- once setup has started or trust state has changed
- when `nodeSetupVisible === true`

Purpose:

- shows status pills for lifecycle, trust, governance, and Core pairing
- renders the current stage card via `renderCurrentStageCard(...)`

## Stage-by-stage card map

The current stage card is selected in:

- `frontend/src/features/setup/SetupComponents.jsx`
  Function: `renderCurrentStageCard(...)`

### Step: Node Identity

Sidebar step id:

- `node_identity`

Center card shown:

- `NodeIdentityFormCard` before node setup becomes visible
- `NodeIdentityCard` as the fallback stage card inside `NodeSetupCard` if no later step is active

Files:

- `frontend/src/features/setup/cards/NodeIdentityFormCard.jsx`
- `frontend/src/features/setup/cards/NodeIdentityCard.jsx`

Form:

- `Core base URL`
- `Node name`

Actions:

- `Save`
- `Start Onboarding`

### Step: Core Connection

Sidebar step id:

- `core_connection`

Center stage card:

- `CoreConnectionCard`

File:

- `frontend/src/features/setup/cards/CoreConnectionCard.jsx`

Form in this step:

- no inline form in the stage card
- the actual editable Core URL field exists in `NodeIdentityFormCard`

Card content:

- warning telling the operator to enter the Core URL or confirming it is configured

### Step: Bootstrap Discovery

Sidebar step id:

- `bootstrap_discovery`

Center stage card:

- `RegistrationCard`

File:

- `frontend/src/features/setup/cards/RegistrationCard.jsx`

Form in this step:

- no inline form

Card content:

- session id
- approval URL placeholder or value
- success and error callouts

### Step: Registration

Sidebar step id:

- `registration`

Center stage card:

- `RegistrationCard`

File:

- `frontend/src/features/setup/cards/RegistrationCard.jsx`

Form in this step:

- no inline form

Card content:

- same card as bootstrap discovery
- session id
- approval URL
- notice and error states

### Step: Approval

Sidebar step id:

- `approval`

Center stage card:

- `ApprovalCard`

File:

- `frontend/src/features/setup/cards/ApprovalCard.jsx`

Form in this step:

- no inline form

Actions:

- `Open approval URL`

Card content:

- instruction to approve the node in Core
- optional last error callout

### Step: Trust Activation

Sidebar step id:

- `trust_activation`

Center stage card:

- `TrustActivationCard`

File:

- `frontend/src/features/setup/cards/TrustActivationCard.jsx`

Form in this step:

- no inline form

Card content:

- trust state
- node id
- MQTT state

### Step: Provider Setup

Sidebar step id:

- `provider_setup`

Center stage card:

- `ProviderSetupCard`

File:

- `frontend/src/features/setup/cards/ProviderSetupCard.jsx`

Form in this step on the main setup screen:

- no inline form

Action on the main setup screen:

- `Setup Provider`

What happens next:

- this opens the Gmail provider page, which has its own cards and form UI

Provider page file:

- `frontend/src/features/providers/GmailSetupPage.jsx`

Provider page cards:

- `Gmail Status`
- `Gmail Settings`
- `Gmail Action`

Provider page form fields in `Gmail Settings`:

- `Provider Enabled`
- `Client ID`
- `Client Secret Ref`
- `Redirect URI`
- `Requested Scopes`

Provider page actions:

- `Validate`
- `Save Gmail Config`
- `Create Auth Link`

### Step: Capability Declaration

Sidebar step id:

- `capability_declaration`

Center stage card:

- `CapabilityDeclarationCard`

File:

- `frontend/src/features/setup/cards/CapabilityDeclarationCard.jsx`

Form in this step:

- selectable task capability buttons sourced from `taskCapabilityOptions`
- current selection comes from `form.selected_task_capabilities`

Actions:

- `Save Selection`
- `Declare Capabilities`

Card content:

- list of available capability options
- declaration status
- selected count
- blocking reasons
- notice and error callouts

### Step: Governance Sync

Sidebar step id:

- `governance_sync`

Center stage card:

- `GovernanceSyncCard`

File:

- `frontend/src/features/setup/cards/GovernanceSyncCard.jsx`

Form in this step:

- no inline form

Card content:

- governance sync status

### Step: Ready

Sidebar step id:

- `ready`

Center stage card:

- `ReadyCard`

File:

- `frontend/src/features/setup/cards/ReadyCard.jsx`

Form in this step:

- no inline form

Card content:

- success message confirming readiness

## Current implementation summary

If you want to change the setup flow UI, these are the main files:

- Flow selection logic:
  `frontend/src/App.jsx`
- Stage-card dispatch:
  `frontend/src/features/setup/SetupComponents.jsx`
- Main setup cards:
  `frontend/src/features/setup/cards/`
- Provider setup form and provider cards:
  `frontend/src/features/providers/GmailSetupPage.jsx`
