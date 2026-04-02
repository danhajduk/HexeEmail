# Hexe Node UI Replication Guide

This document explains the current Hexe Email Node UI in enough detail to reproduce it in other node repositories.

The goal is not to describe a generic dashboard pattern. The goal is to document the exact structure, layout rules, CSS contract, and implementation decisions used by this node so the same UI can be recreated consistently across other Hexe nodes.

## Source Of Truth

The current UI is implemented in these files:

- `frontend/src/App.jsx`
- `frontend/src/styles.css`
- `frontend/src/main.jsx`
- `frontend/src/theme/index.css`
- `frontend/src/theme/tokens.css`
- `frontend/src/theme/base.css`
- `frontend/src/theme/components.css`
- `frontend/src/theme/dark.css`

If another node wants full visual parity, these files are the canonical reference.

## Design Intent

The current UI has two major modes:

1. Setup flow
2. Operational dashboard

The setup flow is used before the node is fully operational.

The dashboard becomes the default when `operational_readiness` is true.

The visual language is intentionally:

- card-based
- compact but not dense
- status-forward
- horizontally structured
- built around reusable theme tokens

The design avoids a consumer-app feel. It should read like an operations console for a trusted infrastructure node.

## Global Layout Contract

The entire UI sits inside two outer wrappers:

```jsx
<div className="shell">
  <main className="app-frame">...</main>
</div>
```

### `.shell`

Purpose:

- full-page visual background
- minimum viewport height
- subtle ambient gradients

Current CSS:

```css
.shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, hsl(var(--sx-accent) / 0.16), transparent 28%),
    radial-gradient(circle at 85% 15%, hsl(var(--sx-success) / 0.16), transparent 22%),
    hsl(var(--sx-bg));
}
```

Notes:

- the gradients are decorative only
- they should stay soft and low contrast
- they help keep the UI from looking flat without introducing visual noise

### `.app-frame`

Purpose:

- constrain the app to a fixed viewport-relative width
- create the shared page padding

Current CSS:

```css
.app-frame {
  box-sizing: border-box;
  width: 90vw;
  max-width: 90vw;
  margin: 0 auto;
  padding: 24px;
}
```

Important:

- this is intentionally not a centered narrow app shell
- the UI is meant to breathe horizontally
- other nodes should keep this same container rule if they want parity

## Theme Contract

The UI uses Hexe theme tokens based on `--sx-*` variables.

The current token source is `frontend/src/theme/tokens.css`.

Important tokens:

```css
:root {
  --sx-bg: 222 84% 5%;
  --sx-panel: 222 50% 10%;
  --sx-border: 217 20% 20%;
  --sx-text: 210 40% 98%;
  --sx-text-muted: 215 20% 65%;
  --sx-accent: 262 83% 58%;
  --sx-success: 142 71% 45%;
  --sx-warning: 38 92% 50%;
  --sx-danger: 0 84% 60%;
  --sx-space-1: 4px;
  --sx-space-2: 8px;
  --sx-space-3: 12px;
  --sx-space-4: 16px;
  --sx-space-5: 24px;
  --sx-space-6: 32px;
  --sx-radius-sm: 6px;
  --sx-radius-md: 10px;
  --sx-radius-lg: 14px;
  --sx-radius-pill: 999px;
  --sx-shadow-1: 0 1px 2px rgba(0, 0, 0, 0.3);
  --sx-shadow-2: 0 4px 10px rgba(0, 0, 0, 0.35);
}
```

### Base Theme

The current node UI loads theme files from:

- `frontend/src/theme/index.css`
- `frontend/src/theme/base.css`
- `frontend/src/theme/components.css`
- `frontend/src/theme/dark.css`

Current behavior:

- dark theme is the implemented theme
- there is no separate `light.css` in this repo right now
- the dashboard header currently shows a theme label, but it is not yet wired to a persisted runtime theme switcher

If another node wants exact parity, keep the current behavior.

If another node wants to go beyond parity, it can add a real theme runtime later, but that is not part of the current UI contract.

## Shared Component Primitives

The UI relies on a few theme-level primitives from `frontend/src/theme/components.css`.

These are foundational:

```css
.card {
  background: hsl(var(--sx-panel));
  border: 1px solid hsl(var(--sx-border));
  border-radius: var(--sx-radius-md);
  padding: var(--sx-space-4);
  box-shadow: var(--sx-shadow-1);
}

.btn {
  border-radius: var(--sx-radius-sm);
  border: 1px solid transparent;
  padding: var(--sx-space-2) var(--sx-space-3);
  cursor: pointer;
  font: inherit;
}

.btn-primary {
  background: hsl(var(--sx-accent));
  color: #fff;
}

.form-input {
  width: 100%;
  border: 1px solid hsl(var(--sx-border));
  border-radius: var(--sx-radius-sm);
  padding: var(--sx-space-2) var(--sx-space-3);
  background: color-mix(in oklab, hsl(var(--sx-panel)) 85%, black);
  color: hsl(var(--sx-text));
}
```

Important design rule:

- node-specific styling should build on top of these primitives
- do not restyle from scratch if you want cross-node consistency

## UI Modes

The UI currently has three top-level views:

- `setup`
- `dashboard`
- `provider`

The logic lives in `frontend/src/App.jsx`.

Rules:

- `provider` is a dedicated provider setup page
- `dashboard` is shown when the node is operationally ready
- `setup` remains available through the `Open Setup` action even when the dashboard is available

## Setup Flow Layout

The setup flow uses:

```jsx
<section className="app-shell">
  <SetupSidebar flow={setupFlow} />
  <div className="main-column">
    <section className="content-stack">...</section>
  </div>
</section>
```

### `.app-shell`

Purpose:

- two-column setup layout
- left column for step navigation
- right column for forms and stage cards

Current CSS:

```css
.app-shell {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
```

### `.main-column` and `.content-stack`

Current CSS:

```css
.main-column {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.content-stack {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
```

These are simple vertical stack wrappers used throughout the UI.

## Setup Sidebar Contract

The setup sidebar is a card containing a step list.

Structure:

```jsx
<aside className="card stack flow-sidebar">
  <div className="section-heading">
    <h2>Setup Flow</h2>
    <span className="pill">{flow.current?.label || "Idle"}</span>
  </div>
  <div className="flow-steps">
    ...
  </div>
</aside>
```

Current step rules:

- completed steps show a green check in the top right
- step descriptions were intentionally removed
- the step cards are compact

Key CSS:

```css
.flow-sidebar {
  position: sticky;
  top: 24px;
}

.flow-steps {
  display: grid;
  gap: 10px;
}

.flow-step {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--sx-radius-md);
  border: 1px solid hsl(var(--sx-border));
  background: hsl(var(--sx-text) / 0.03);
  position: relative;
}

.flow-step-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  color: hsl(var(--sx-panel));
  background: hsl(var(--sx-success));
}
```

Replication guidance:

- keep the step height compact
- keep the sidebar sticky on desktop
- collapse it naturally on mobile

## Dashboard Architecture

The dashboard is made of three major layers:

1. top app header
2. operational shell with left nav and right content
3. content header plus dashboard cards

High-level JSX:

```jsx
<main className="app-frame">
  <section className="card app-header">...</section>

  <section className="operational-shell">
    <aside className="card operational-shell-nav-card">...</aside>

    <div className="operational-shell-content">
      <article className="card node-health-strip operational-content-header">...</article>
      <section className="grid operational-dashboard-grid">...</section>
    </div>
  </section>
</main>
```

This structure is important. Other nodes should follow it closely.

## Dashboard App Header

This is the upper header above the main shell. It is not the same thing as the health strip.

It contains:

- node title
- top-level status pills
- action row
- metadata row

Structure:

```jsx
<section className="card app-header">
  <div className="app-header-top">
    <div>
      <h1>Hexe Email Node</h1>
    </div>
    <div className="app-header-status-pills">...</div>
  </div>

  <div className="app-header-bottom">
    <button className="btn btn-ghost app-header-theme-btn" type="button">
      Theme: {currentThemeLabel()}
    </button>
    <div className="app-header-actions">...</div>
  </div>

  <div className="app-header-meta">
    <span className="muted tiny">Updated: <code>...</code></span>
    <span className="muted tiny">Node: <code>...</code></span>
  </div>
</section>
```

Current CSS:

```css
.app-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
  padding-top: 14px;
  padding-bottom: 14px;
}

.app-header-top,
.app-header-bottom,
.app-header-meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.app-header h1 {
  margin: 0;
  font-size: clamp(26px, 3vw, 36px);
  line-height: 1;
}

.app-header-status-pills,
.app-header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}
```

Design notes:

- this header was intentionally shortened compared to the original larger hero
- it should feel like a control-plane header, not a landing-page hero
- actions sit on the right, title stays visually dominant on the left

## Operational Shell

This is the main dashboard body below the app header.

Structure:

```jsx
<section className="operational-shell">
  <aside className="card operational-shell-nav-card">...</aside>
  <div className="operational-shell-content">...</div>
</section>
```

Current CSS:

```css
.operational-shell {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.operational-shell-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.operational-shell-nav-card {
  position: sticky;
  top: 24px;
}
```

Important:

- the shell itself is not the 7-column area
- the 7-column rule belongs to the health strip inside the content area

## Operational Nav

The left nav is currently non-functional placeholder navigation for future operational sections.

Structure:

```jsx
<aside className="card operational-shell-nav-card">
  <nav className="operational-shell-nav" aria-label="Operational sections">
    <button type="button" className="btn operational-nav-btn btn-primary">Overview</button>
    <button type="button" className="btn operational-nav-btn">Capabilities</button>
    <button type="button" className="btn operational-nav-btn">Runtime</button>
    <button type="button" className="btn operational-nav-btn">Activity</button>
    <button type="button" className="btn operational-nav-btn">Diagnostics</button>
  </nav>
</aside>
```

CSS:

```css
.operational-shell-nav {
  display: grid;
  gap: 10px;
}

.operational-nav-btn {
  width: 100%;
  justify-content: center;
}
```

Replication guidance:

- keep this nav as a vertical stack
- keep the first button highlighted as the active section until real routing exists

## Health Strip

The health strip is the header of the main content area.

It is not a side card and it is not a dashboard footer.

It lives directly above the main dashboard grid.

Structure:

```jsx
<article className="card node-health-strip operational-content-header">
  <div className="node-health-strip-grid">
    <div className="node-health-strip-item">...</div>
    <div className="node-health-strip-item">...</div>
    <div className="node-health-strip-item">...</div>
    <div className="node-health-strip-item">...</div>
    <div className="node-health-strip-item">...</div>
    <div className="node-health-strip-item">...</div>
    <div className="node-health-strip-item">...</div>
  </div>
</article>
```

Current metrics:

1. Lifecycle
2. Trust
3. Core API
4. MQTT
5. Governance
6. Providers
7. Last Telemetry

Current CSS:

```css
.node-health-strip {
  padding: 18px 20px;
}

.node-health-strip-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 14px;
}

.node-health-strip-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border-radius: var(--sx-radius-md);
  border: 1px solid hsl(var(--sx-border));
  background: hsl(var(--sx-text) / 0.03);
}
```

Important replication rule:

- if another node adds or removes health strip items, it should revisit the grid column count
- for exact parity with this node, keep it at `7`

### Health Strip Status Styling

The strip uses these reusable utility classes:

```css
.muted {
  color: hsl(var(--sx-text-muted));
}

.tiny {
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.severity-indicator {
  display: inline-flex;
  align-items: center;
}

.severity-success {
  color: hsl(var(--sx-success));
}

.severity-warning {
  color: hsl(var(--sx-warning));
}

.severity-meta {
  color: hsl(var(--sx-accent));
}

.status-badge,
.health-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  padding: 7px 10px;
  border-radius: var(--sx-radius-pill);
  border: 1px solid currentColor;
  text-transform: capitalize;
  font-size: 13px;
  line-height: 1;
  background: hsl(var(--sx-panel));
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
}
```

The visual model is:

- green for success
- yellow/orange for pending or degraded
- accent color for metadata-like healthy-but-not-binary states

## Main Dashboard Content Grid

Below the health strip, the main content uses a `3`-column grid.

Current CSS:

```css
.operational-dashboard-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: start;
}
```

This grid currently contains three cards:

1. Node Overview
2. Core Connection
3. Actions

Because the base `.grid` class already provides `display: grid` and `gap: 24px`, `operational-dashboard-grid` only overrides the column count and alignment.

## Dashboard Cards

### 1. Node Overview Card

Purpose:

- identity summary
- lifecycle summary
- trusted pairing summary

Structure:

```jsx
<article className="card">
  <div className="card-header">
    <h2>Node Overview</h2>
    <p className="muted">Primary home for identity, lifecycle, and trusted pairing summary.</p>
  </div>
  <div className="state-grid">...</div>
</article>
```

Fields currently shown:

- Node ID
- Node Name
- Lifecycle
- Trust
- Paired Hexe Core
- Software
- Pairing Timestamp

### 2. Core Connection Card

Purpose:

- Core metadata
- onboarding linkage
- operational MQTT endpoint

Fields currently shown:

- Core ID
- Core API
- Operational MQTT
- Connection
- Onboarding Ref

### 3. Actions Card

Purpose:

- cluster actions by intent
- avoid mixing operational refreshes with dangerous or diagnostic actions

Action groups:

- Configuration
- Runtime Controls
- Admin & Diagnostics

This grouping is important and should stay the same in other nodes unless there is a strong product reason to change it.

## Card Header Pattern

Used by all operational cards.

CSS:

```css
.card-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 18px;
}
```

Design guidance:

- heading first
- one muted sentence below
- keep headers compact and consistent

## State Grid Pattern

Used for the detail cards.

CSS:

```css
.state-grid {
  display: grid;
  grid-template-columns: minmax(120px, 180px) minmax(0, 1fr);
  gap: 12px 16px;
  align-items: center;
}

.state-grid > span {
  color: hsl(var(--sx-text-muted));
  font-size: 14px;
}

.state-grid > code {
  width: fit-content;
}
```

This creates a label-value grid.

Design rules:

- labels are muted
- values are code or badges
- status values should use the same severity badge system as the health strip

## Action Group Pattern

CSS:

```css
.action-groups {
  display: grid;
  gap: 16px;
}

.action-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: var(--sx-radius-md);
  border: 1px solid hsl(var(--sx-border));
  background: hsl(var(--sx-text) / 0.03);
}

.action-group-admin {
  background: hsl(var(--sx-accent) / 0.05);
}

.row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
```

Important:

- action groups are intentionally visual sub-panels inside the main card
- the admin/diagnostics group uses a slightly different background to mark it as advanced

## Form And Setup Card Patterns

The setup and provider pages use a consistent set of supporting patterns:

- `.field`
- `.field-label`
- `.toggle-field`
- `.toggle`
- `.actions`
- `.callout`
- `.status-pill`
- `.facts`

These should be copied as a unit if another node needs the same setup flow behavior.

Examples:

```css
.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.callout {
  padding: 12px 14px;
  border-radius: var(--sx-radius-md);
  border: 1px solid hsl(var(--sx-border));
}
```

## Responsive Behavior

The current responsive breakpoint is `900px`.

At that breakpoint:

- `app-shell` becomes a single column
- `hero` becomes a single column
- `operational-shell` becomes a single column
- `dashboard-stack` becomes a single column
- generic `.grid` becomes a single column
- sticky sidebars lose `position: sticky`
- `.facts` collapses to one column
- `.node-health-strip-grid` collapses from `7` columns to `2`
- `.state-grid` collapses to one column

Current CSS:

```css
@media (max-width: 900px) {
  .app-shell,
  .hero,
  .operational-shell,
  .dashboard-stack,
  .grid {
    grid-template-columns: 1fr;
  }

  .flow-sidebar {
    position: static;
  }

  .operational-shell-nav-card {
    position: static;
  }

  .facts {
    grid-template-columns: 1fr;
  }

  .node-health-strip-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .state-grid {
    grid-template-columns: 1fr;
  }
}
```

Replication guidance:

- do not keep the 7-column strip on mobile
- the current `2`-column fallback is the intended mobile behavior

## Data Contract Required By The Dashboard

The dashboard UI assumes `bootstrap.status` includes at least:

- `node_name`
- `node_software_version`
- `trust_state`
- `node_id`
- `paired_core_id`
- `mqtt_connection_status`
- `mqtt_health.health_status`
- `mqtt_health.status_freshness_state`
- `mqtt_health.status_stale`
- `mqtt_health.status_inactive`
- `mqtt_health.status_age_s`
- `mqtt_health.status_stale_after_s`
- `mqtt_health.status_inactive_after_s`
- `mqtt_health.last_status_report_at`
- `operational_mqtt_host`
- `operational_mqtt_port`
- `enabled_providers`
- `provider_account_summaries`
- `governance_sync_status`
- `capability_declaration_status`
- `active_governance_version`
- `last_heartbeat_at`
- `trusted_at`
- `operational_readiness`

These are currently shaped in the backend response model from:

- `src/models.py`
- `src/service.py`

If another node wants to reuse this UI, it must expose equivalent data.

### MQTT Telemetry Health Model

The node now computes a local MQTT telemetry health snapshot that intentionally mirrors the Core operational-status freshness model.

Current local rules:

- `fresh` when the last heartbeat telemetry is within the stale threshold
- `stale` when heartbeat telemetry age exceeds the stale threshold
- `inactive` when heartbeat telemetry age exceeds the inactive threshold

Current defaults:

- stale after `300` seconds
- inactive after `1800` seconds

Current effective local health mapping:

- `connected` when MQTT is connected and telemetry is fresh
- `degraded` when MQTT is reconnecting, stale, or otherwise not fresh
- `offline` when MQTT telemetry is inactive or the connection is effectively down
- `unknown` when MQTT is connected but no heartbeat telemetry has been recorded yet

This is a node-local projection for operator UX. It is designed to align with Core’s broader operational-status model without requiring the dashboard to poll Core directly for these values.

## Behavior Contract

### Dashboard Defaulting

The dashboard is the default when `operational_readiness` is true.

However:

- the user can explicitly open setup
- when they do, the setup view should remain open and not auto-bounce back immediately

This manual override behavior is already implemented in the node app and should be copied if the same UX is desired elsewhere.

### Provider Page

Provider setup lives on a separate view rather than inside the dashboard cards.

This is intentional:

- operational dashboard remains clean
- provider configuration stays task-focused

## Replication Checklist

If another node wants to reproduce this UI, it should do the following:

1. Copy the theme token and component primitives from `frontend/src/theme/*`.
2. Copy the node-specific dashboard and setup rules from `frontend/src/styles.css`.
3. Use the same top-level JSX structure:
   - `shell`
   - `app-frame`
   - `app-header`
   - `operational-shell`
   - `operational-shell-nav-card`
   - `operational-shell-content`
   - `node-health-strip`
   - `operational-dashboard-grid`
4. Preserve the health strip as the header of the main content area.
5. Preserve the `7`-column health strip and `3`-column dashboard content grid on desktop.
6. Preserve the current responsive collapse behavior at `900px`.
7. Expose the required status fields from the backend.
8. Keep the setup flow and operational dashboard as separate but connected modes.

## Recommended Cross-Node Consistency Rules

To keep other nodes visually aligned with Hexe Email Node:

- reuse the same spacing scale
- reuse the same badge and health indicator styles
- keep app headers compact, not hero-sized
- keep operational nav on the left
- keep the health strip above the main dashboard grid
- keep detail cards built on the same `card-header` and `state-grid` patterns
- keep admin/diagnostic actions visually separated from routine actions

## What Is Intentionally Not Standardized Yet

The following are not fully standardized across nodes yet:

- active theme switching
- nav section routing behind the operational nav
- runtime restart buttons
- diagnostics page wiring

Other nodes can still replicate the current UI shell without those behaviors being complete.

## Recommended File To Copy First

If another node only copies one file to begin replication, it should start with:

- `frontend/src/styles.css`

Then it should replicate the dashboard structure from:

- `frontend/src/App.jsx`

That combination captures almost all of the visible layout contract.

## Summary

The current Hexe Email Node UI is built around:

- a 90vw framed app surface
- a compact app header
- a left-nav operational shell
- a 7-item health strip as the main content header
- a 3-column operational dashboard grid
- setup and provider views that reuse the same card and token system

That is the design that should be replicated across other nodes if the goal is consistent Hexe node UX.
