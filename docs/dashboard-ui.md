# Dashboard UI

This document explains the dashboard UI, the sections shown in the operational console, and the cards or form-style controls used inside each section.

## Dashboard sections

The dashboard is mounted from:

- `frontend/src/App.jsx`

The active dashboard view is selected by `dashboardSection`. The current sections are:

- `overview`
- `gmail`
- `runtime`
- `scheduled`
- `orders`
- `shipments`
- `review`

These section wrappers now compose card components from:

- `frontend/src/features/dashboard/cards/`

## Shared dashboard shell

Before the section-specific content renders, the dashboard shell shows:

- the operational header via `DashboardHeaderCard`
- the navigation rail via `DashboardSidebarCard`
- the node health strip via `NodeHealthStripCard`

The section-specific card layouts begin after that shell.

Dashboard sidebar card:

- `frontend/src/features/dashboard/cards/DashboardSidebarCard.jsx`

Dashboard header card:

- `frontend/src/features/dashboard/cards/DashboardHeaderCard.jsx`

Header content:

- node title
- lifecycle and provider status pills
- model status pill
- theme button
- restart, setup, provider, and copy actions
- updated time
- quota
- node id
- model detail

Sidebar items:

- `Overview`
- `Gmail`
- `Runtime`
- `Scheduled Tasks`
- `Tracked Orders`
- `Activity`
- `Diagnostics`

Dashboard health strip card:

- `frontend/src/features/dashboard/cards/NodeHealthStripCard.jsx`

Health strip items:

- `Lifecycle`
- `Trust`
- `Core API`
- `MQTT`
- `Governance`
- `Providers`
- `Last Heartbeat`

## Overview section

Section wrapper:

- `frontend/src/features/dashboard/OverviewDashboardSection.jsx`

Cards used:

- `OperationalWarningsCard`
  File: `frontend/src/features/dashboard/cards/OperationalWarningsCard.jsx`
- `NodeOverviewCard`
  File: `frontend/src/features/dashboard/cards/NodeOverviewCard.jsx`
- `CoreConnectionCard`
  File: `frontend/src/features/dashboard/cards/CoreConnectionCard.jsx`
- `DashboardActionsCard`
  File: `frontend/src/features/dashboard/cards/DashboardActionsCard.jsx`

### OperationalWarningsCard

When shown:

- only when `dashboardWarnings.length > 0`

Purpose:

- highlights operational warning conditions

Actions:

- `Refresh Governance`
- `Setup Provider`

### NodeOverviewCard

Purpose:

- shows trusted node identity and lifecycle state

Data shown:

- node id
- node name
- lifecycle
- trust state
- paired Core id
- software version
- pairing timestamp

### CoreConnectionCard

Purpose:

- shows Core pairing and MQTT linkage state

Data shown:

- Core id
- Core API URL
- operational MQTT endpoint
- MQTT connection state
- onboarding reference
- telemetry freshness
- telemetry age

### DashboardActionsCard

Purpose:

- groups operator actions by category

Action groups:

- `Configuration`
- `Runtime Controls`
- `Admin & Diagnostics`

Actions:

- `Open Setup`
- `Setup Gmail Provider`
- `Refresh Governance`
- `Refresh Provider Status`
- `Redeclare Capabilities`
- `Restart Backend`
- `Restart Frontend`

Form-like inputs:

- none

## Gmail section

Section wrapper:

- `frontend/src/features/dashboard/GmailDashboardSection.jsx`

Cards used:

- `GmailStatusCard`
  File: `frontend/src/features/dashboard/cards/GmailStatusCard.jsx`
- `SenderReputationDashboardCard`
  File: `frontend/src/features/dashboard/cards/SenderReputationDashboardCard.jsx`
- `GmailActionCard`
  File: `frontend/src/features/dashboard/cards/GmailActionCard.jsx`
- `GmailSettingsCard`
  File: `frontend/src/features/dashboard/cards/GmailSettingsCard.jsx`

### GmailStatusCard

Purpose:

- shows Gmail provider state and mailbox summary

Data shown:

- provider state
- account
- unread counts
- stored email count
- classified email count
- Spamhaus counts
- quota usage

Form-like inputs:

- none

### SenderReputationDashboardCard

Purpose:

- embeds the sender reputation summary panel inside the dashboard

Data shown:

- sender reputation summary
- aggregate reputation state counts

Form-like inputs:

- none

### GmailActionCard

Purpose:

- groups the manual Gmail operations used for learning, refresh, and AI batch work

Actions:

- `Fetch Initial Learning`
- `Check With Spamhaus`
- `Calculate Sender Reputation`
- `Open Training`
- `Poll Today`
- `Poll Yesterday`
- `Poll Last Hour`
- `Local Classify 100, Send Unknown To AI`

Additional UI:

- batch progress bar
- pipeline stage pills; the active fetch or classification stage turns green while work is running
- status and error callouts

Form-like inputs:

- none

### GmailSettingsCard

Purpose:

- shows Gmail scheduler state and fetch window configuration

Data shown:

- scheduler status
- last check
- last success
- last error
- configured fetch windows

Form-like inputs:

- none in the dashboard

Note:

- the editable Gmail provider form lives on the provider setup page, not inside the dashboard:
  `frontend/src/features/providers/GmailSetupPage.jsx`

## Runtime section

Section wrapper:

- `frontend/src/features/dashboard/RuntimeDashboardSection.jsx`

Cards used:

- `RuntimeStatusCard`
  File: `frontend/src/features/dashboard/cards/RuntimeStatusCard.jsx`
- `RuntimeSettingsCard`
  File: `frontend/src/features/dashboard/cards/RuntimeSettingsCard.jsx`
- `RuntimeActionsCard`
  File: `frontend/src/features/dashboard/cards/RuntimeActionsCard.jsx`

### RuntimeStatusCard

Purpose:

- shows the latest runtime task request state and execution outputs

Data shown:

- AI, provider, and notification enablement states
- task flow enablement states
- request status
- last step
- requested node type
- task family
- resolved service, provider, and model
- authorization status
- execution output and metrics
- started, updated, and completed timestamps

Form-like inputs:

- none

### RuntimeSettingsCard

Purpose:

- holds the runtime dashboard’s interactive form-style controls

Form-style controls:

- `AI`
- `Provider`
- `Notify`
- `Clasify`
- `Action`
- `Order`
- `Financial`
- `Invoice`
- `Shipment`
- `Security`

Implementation note:

- these are toggle buttons rather than text inputs
- they are disabled while a runtime request is pending

This is the main dashboard form component after the refactor.

### RuntimeActionsCard

Purpose:

- runs the runtime workflow and debug operations

Actions:

- `Start Task Resolve`
- `Start Task Authorize`
- `Sync Prompts On AI Node`
- `Send Newest Unknown Mail To Classifier`
- `Send Latest Action Needed / Order To AI`
- `Debug Preview`
- `Debug Resolve`
- `Debug Authorize`

Additional UI:

- summary callout for preview, resolve, authorize, and execute results

Form-like inputs:

- none

## Scheduled section

Section wrapper:

- `frontend/src/features/dashboard/ScheduledTasksSection.jsx`

Card used:

- `ScheduledTasksCard`
  File: `frontend/src/features/dashboard/cards/ScheduledTasksCard.jsx`

Purpose:

- shows background scheduled task execution status

Data shown:

- task title
- task kind
- owner
- schedule
- status
- last success
- last failure
- next run
- last error
- schedule legend

Form-like inputs:

- none

## Orders section

Section wrapper:

- `frontend/src/features/dashboard/TrackedOrdersSection.jsx`

Card used:

- `TrackedOrdersCard`
  File: `frontend/src/features/dashboard/cards/TrackedOrdersCard.jsx`

Purpose:

- `#/dashboard/orders` shows order-linked records from the last four months, including shipments that are tied to an order
- `#/dashboard/shipments` shows standalone shipment records that are not tied to an order

Orders data shown:

- seller
- carrier
- order number
- tracking number
- tracking status, expected delivery time, and latest tracking event
- account
- added

Shipments data shown:

- carrier
- order number
- tracking number
- tracking status, expected delivery time, and latest tracking event
- account
- added

Live tracking:

- set `TRACK123_ENABLED=true` and `TRACK123_API_SECRET` in the local environment to enable Track123 live tracking
- `GET /api/tracking/track123/couriers` proxies the Track123 courier list from `/gateway/open-api/tk/v2.1/courier/list`
- `Shipment Live Tracking Refresh` validates mapped courier codes against Track123's courier list, then automatically registers untracked shipment numbers through `POST /gateway/open-api/tk/v2/track/import`
- order-linked shipments include `orderNo` in the Track123 registration payload
- the same task runs every 5 minutes and queries Track123 through `POST /gateway/open-api/tk/v2.1/track/query` for all enabled live-tracking shipment records
- delivered shipments older than 30 days are removed from Track123 through `POST /gateway/open-api/tk/v2.1/track/delete` while the local shipment record stays in the database
- Track123 requests are throttled per endpoint and briefly retried when Track123 returns `A0706` or HTTP `429`

## Review-needed outputs dashboard section

Section wrapper:

- `frontend/src/features/dashboard/ReviewOutputsSection.jsx`

Purpose:

- `#/dashboard/review` shows persisted family-flow outputs under `runtime/flow_families/*/outputs/review_needed`
- the bootstrap payload exposes these records as `review_needed_outputs`

Data shown:

- flow family
- message id
- subject
- review reason
- profile
- confidence
- extracted field keys
- sender
- persisted timestamp
- output file path

Form-like inputs:

- none

## Refactor summary

Dashboard sections still exist as orchestration wrappers:

- `OverviewDashboardSection.jsx`
- `GmailDashboardSection.jsx`
- `RuntimeDashboardSection.jsx`
- `ScheduledTasksSection.jsx`
- `TrackedOrdersSection.jsx`

But the actual card UI now lives in:

- `frontend/src/features/dashboard/cards/`

This mirrors the setup flow approach:

- section files decide composition
- card files own the card markup
- the one current dashboard form surface is `RuntimeSettingsCard`
