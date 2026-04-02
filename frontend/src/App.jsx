import { startTransition, useEffect, useState } from "react";

const EMPTY_FORM = {
  core_base_url: "",
  node_name: "",
  selected_task_capabilities: [],
};

const TASK_CAPABILITY_OPTIONS = [
  "task.classification",
  "task.summarization",
  "task.tracking",
];

const EMPTY_PROVIDER_FORM = {
  enabled: false,
  client_id: "",
  client_secret_ref: "",
  redirect_uri: "",
  requested_scopes:
    "https://www.googleapis.com/auth/gmail.send\nhttps://www.googleapis.com/auth/gmail.readonly\nhttps://www.googleapis.com/auth/gmail.modify",
};

const TRAINING_LABEL_OPTIONS = [
  "action_required",
  "direct_human",
  "financial",
  "order",
  "invoice",
  "shipment",
  "security",
  "system",
  "newsletter",
  "marketing",
  "unknown",
];

async function fetchJson(url, options) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const rawText = await response.text();
  let payload;

  if (contentType.includes("application/json")) {
    payload = rawText ? JSON.parse(rawText) : {};
  } else {
    payload = { detail: rawText || `Unexpected ${contentType || "response"} from server` };
  }

  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  if (!contentType.includes("application/json")) {
    throw new Error("Server returned HTML instead of JSON. Check that the API proxy points to the node backend.");
  }
  return payload;
}

function statusTone(value) {
  if (value === "trusted" || value === "approved" || value === "connected" || value === "configured") {
    return "success";
  }
  if (value === "rejected" || value === "expired" || value === "invalid" || value === "revoked") {
    return "danger";
  }
  if (value === "pending" || value === "connecting" || value === "reconnecting" || value === "oauth_pending") {
    return "warning";
  }
  return "neutral";
}

function boolTone(value) {
  return value ? "success" : "neutral";
}

function formatTelemetryTimestamp(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function healthSeverityClass(value, successValues = [], metaValues = []) {
  if (successValues.includes(value)) {
    return "severity-indicator severity-success";
  }
  if (metaValues.includes(value)) {
    return "severity-indicator severity-meta";
  }
  return "severity-indicator severity-warning";
}

function currentThemeLabel() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return "system";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function formatValue(value, fallback = "pending") {
  return value || fallback;
}

function formatAge(value) {
  if (value === null || value === undefined) {
    return "pending";
  }
  if (value < 60) {
    return `${value}s`;
  }
  if (value < 3600) {
    return `${Math.floor(value / 60)}m`;
  }
  return `${Math.floor(value / 3600)}h`;
}

function formatScheduleTimestamp(value) {
  if (!value) {
    return "-";
  }
  return formatTelemetryTimestamp(value);
}

function buildGmailWindowSettings(fetchSchedule) {
  return [
    {
      key: "yesterday",
      label: "Yesterday",
      fetchedAt: fetchSchedule?.yesterday?.last_run_at,
      runReason: fetchSchedule?.yesterday?.last_run_reason,
      schedule: "00:01 daily",
    },
    {
      key: "today",
      label: "Today",
      fetchedAt: fetchSchedule?.today?.last_run_at,
      runReason: fetchSchedule?.today?.last_run_reason,
      schedule: "00:00, 06:00, 12:00, 18:00",
    },
    {
      key: "last_hour",
      label: "Last Hour",
      fetchedAt: fetchSchedule?.last_hour?.last_run_at,
      runReason: fetchSchedule?.last_hour?.last_run_reason,
      schedule: "top of every hour",
    },
  ];
}

function telemetryFreshnessIndicatorClass(value) {
  return value === "fresh" ? "health-fresh" : "health-pending";
}

function deriveDashboardWarnings({ status, providerConnected, mqttConnected, mqttHealth }) {
  const warnings = [];

  if (status?.governance_sync_status && status.governance_sync_status !== "ok") {
    warnings.push(`Governance sync is ${status.governance_sync_status}.`);
  }
  if (!providerConnected) {
    warnings.push("Gmail provider is not connected.");
  }
  if (!mqttConnected) {
    warnings.push("MQTT is not currently connected.");
  }
  if (mqttHealth?.status_freshness_state && mqttHealth.status_freshness_state !== "fresh") {
    warnings.push(`Telemetry freshness is ${mqttHealth.status_freshness_state}.`);
  }

  return warnings;
}

function formatRelativeTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  const diffSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSeconds < 60) {
    return `${diffSeconds} sec ago`;
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} min ago`;
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)} hour ago`;
  }
  return `${Math.floor(diffSeconds / 86400)} day ago`;
}

function maskOnboardingRef(value) {
  if (!value) {
    return "pending";
  }
  if (value === "operational") {
    return value;
  }
  if (value.length <= 7) {
    return `**********${value}`;
  }
  return `**********${value.slice(-7)}`;
}

function deriveNodeState(bootstrap) {
  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];

  if (requiredInputs.length > 0) {
    return { label: "Configuration Required", tone: "warning" };
  }
  if (status?.trust_state === "trusted") {
    return { label: "Trusted", tone: "success" };
  }
  if (onboarding?.onboarding_status === "pending" && onboarding?.approval_url) {
    return { label: "Awaiting Approval", tone: "warning" };
  }
  if (onboarding?.onboarding_status === "pending") {
    return { label: "Registering", tone: "warning" };
  }
  if (onboarding?.onboarding_status === "approved") {
    return { label: "Trust Activating", tone: "warning" };
  }
  if (onboarding?.onboarding_status === "rejected") {
    return { label: "Rejected", tone: "danger" };
  }
  if (onboarding?.onboarding_status === "expired") {
    return { label: "Expired", tone: "danger" };
  }
  if (onboarding?.onboarding_status === "invalid" || onboarding?.onboarding_status === "consumed") {
    return { label: "Needs Recovery", tone: "danger" };
  }
  return { label: "Ready To Start", tone: "neutral" };
}

function isNodeSetupVisible(bootstrap) {
  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  return Boolean(
    onboarding?.session_id ||
      onboarding?.approval_url ||
      onboarding?.onboarding_status !== "not_started" ||
      status?.trust_state !== "untrusted",
  );
}

function deriveSetupFlow(bootstrap) {
  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];
  const coreConfigured = Boolean(bootstrap?.config?.core_base_url) && !requiredInputs.includes("core_base_url");
  const nodeNamed = Boolean(bootstrap?.config?.node_name) && !requiredInputs.includes("node_name");
  const trusted = status?.trust_state === "trusted";
  const providerSummary = status?.provider_account_summaries?.gmail || {};
  const providerConnected = providerSummary?.provider_state === "connected";
  const capabilityCurrent = status?.capability_declaration_status === "accepted";
  const governanceCurrent = status?.governance_sync_status === "ok";
  const ready = Boolean(status?.operational_readiness);
  const sessionCreated = Boolean(onboarding?.session_id);
  const approvalReady = Boolean(onboarding?.approval_url);
  const pendingApproval = onboarding?.onboarding_status === "pending";
  const inTrustActivation = onboarding?.onboarding_status === "approved" && !trusted;

  const steps = [
    {
      id: "node_identity",
      label: "Node Identity",
      complete: nodeNamed,
      current: !nodeNamed,
      description: nodeNamed ? bootstrap?.config?.node_name : "Set a node name to establish local identity.",
    },
    {
      id: "core_connection",
      label: "Core Connection",
      complete: coreConfigured,
      current: nodeNamed && !coreConfigured,
      description: coreConfigured ? bootstrap?.config?.core_base_url : "Set the Core base URL for registration.",
    },
    {
      id: "bootstrap_discovery",
      label: "Bootstrap Discovery",
      complete: sessionCreated || trusted,
      current: nodeNamed && coreConfigured && !sessionCreated && !trusted,
      description: sessionCreated || trusted ? "Bootstrap metadata resolved from the configured Core." : "Start onboarding to discover bootstrap metadata.",
    },
    {
      id: "registration",
      label: "Registration",
      complete: sessionCreated || trusted,
      current: sessionCreated && !approvalReady && !trusted,
      description: sessionCreated ? onboarding?.session_id : "Create a node onboarding session in Core.",
    },
    {
      id: "approval",
      label: "Approval",
      complete: trusted,
      current: pendingApproval,
      description: approvalReady ? "Awaiting operator approval in Core." : "Approval URL will appear here.",
    },
    {
      id: "trust_activation",
      label: "Trust Activation",
      complete: trusted,
      current: inTrustActivation && !ready,
      description: trusted ? `Trusted as ${status?.node_id || "this node"}` : "Finalize trust activation after approval.",
    },
    {
      id: "provider_setup",
      label: "Provider Setup",
      complete: providerConnected,
      current: trusted && !providerConnected,
      description: providerConnected ? "Gmail connected." : "Configure and connect Gmail once trust is active.",
    },
    {
      id: "capability_declaration",
      label: "Capability Declaration",
      complete: capabilityCurrent,
      current: providerConnected && !capabilityCurrent,
      description: capabilityCurrent ? "Capability declaration accepted." : "Waiting for accepted capability declaration.",
    },
    {
      id: "governance_sync",
      label: "Governance Sync",
      complete: governanceCurrent,
      current: capabilityCurrent && !governanceCurrent,
      description: governanceCurrent ? "Governance snapshot synced." : "Waiting for governance snapshot sync.",
    },
    {
      id: "ready",
      label: "Ready",
      complete: ready,
      current: governanceCurrent && !ready,
      description: ready ? "Node is operationally ready." : "Final readiness checks are still running.",
    },
  ];

  const current = steps.find((step) => step.current) || steps.find((step) => !step.complete) || steps[steps.length - 1];
  return { steps, current };
}

function StageCard({ title, tone, children, action }) {
  return (
    <article className={`card stack stage-card tone-${tone}`}>
      <div className="section-heading">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </article>
  );
}

function SetupSidebar({ flow }) {
  return (
    <aside className="card stack flow-sidebar">
      <div className="section-heading">
        <h2>Setup Flow</h2>
        <span className="pill">{flow.current?.label || "Idle"}</span>
      </div>
      <div className="flow-steps">
        {flow.steps.map((step, index) => {
          const state = step.complete ? "success" : step.current ? "warning" : "neutral";
          return (
            <div key={step.id} className={`flow-step is-${state}`}>
              {step.complete ? <span className="flow-step-check" aria-label="Completed">✓</span> : null}
              <div className="flow-step-index">{index + 1}</div>
              <div className="flow-step-body">
                <strong>{step.label}</strong>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

function renderCurrentStageCard({
  flow,
  bootstrap,
  status,
  onboarding,
  requiredInputs,
  notice,
  error,
  setView,
  form,
  saving,
  declaringCapabilities,
  onCapabilityToggle,
  onSaveConfiguration,
  onDeclareCapabilities,
}) {
  const stepId = flow.current?.id;
  const capabilitySetup = status?.capability_setup || {};
  const capabilitySelection = capabilitySetup?.task_capability_selection || {};
  const approvalLink = onboarding?.approval_url ? (
    <a className="approval-link" href={onboarding.approval_url} target="_blank" rel="noreferrer">
      Open approval URL
    </a>
  ) : null;

  if (stepId === "core_connection") {
    return (
      <StageCard title="Core Connection" tone="warning">
        <div className="callout callout-warning">
          {requiredInputs.includes("core_base_url")
            ? "Enter the Core base URL, then save or start onboarding."
            : "Core URL is configured and ready for bootstrap discovery."}
        </div>
      </StageCard>
    );
  }

  if (stepId === "bootstrap_discovery" || stepId === "registration") {
    return (
      <StageCard title="Registration" tone={statusTone(onboarding?.onboarding_status)}>
        <dl className="facts single-column-facts">
          <div>
            <dt>Session</dt>
            <dd>{onboarding?.session_id || "No session yet"}</dd>
          </div>
          <div>
            <dt>Approval URL</dt>
            <dd>{onboarding?.approval_url || "Will appear after session creation"}</dd>
          </div>
        </dl>
        {notice ? <div className="callout callout-success">{notice}</div> : null}
        {error ? <div className="callout callout-danger">{error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "approval") {
    return (
      <StageCard title="Approval" tone="warning" action={approvalLink}>
        <div className="callout">
          Open the Core approval URL and approve the node. Keep this page open while finalize polling continues.
        </div>
        {onboarding?.last_error ? <div className="callout callout-danger">{onboarding.last_error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "trust_activation") {
    return (
      <StageCard title="Trust Activation" tone={statusTone(status?.trust_state)}>
        <dl className="facts single-column-facts">
          <div>
            <dt>Trust state</dt>
            <dd>{status?.trust_state || "untrusted"}</dd>
          </div>
          <div>
            <dt>Node ID</dt>
            <dd>{status?.node_id || "Pending"}</dd>
          </div>
          <div>
            <dt>MQTT</dt>
            <dd>{status?.mqtt_connection_status || "disconnected"}</dd>
          </div>
        </dl>
      </StageCard>
    );
  }

  if (stepId === "provider_setup") {
    return (
      <StageCard
        title="Provider Setup"
        tone={statusTone(status?.provider_account_summaries?.gmail?.provider_state)}
        action={
          <button className="btn btn-primary" type="button" onClick={() => setView("provider")}>
            Setup Provider
          </button>
        }
      >
        <div className="callout">
          Trust is active. Configure Gmail and complete the connect flow to move the node into provider-ready state.
        </div>
      </StageCard>
    );
  }

  if (stepId === "capability_declaration") {
    return (
      <StageCard
        title="Capability Declaration"
        tone={statusTone(status?.capability_declaration_status)}
        action={
          <div className="actions">
            <button className="btn btn-ghost" type="button" onClick={onSaveConfiguration} disabled={saving}>
              {saving ? "Saving..." : "Save Selection"}
            </button>
            <button className="btn btn-primary" type="button" onClick={onDeclareCapabilities} disabled={declaringCapabilities}>
              {declaringCapabilities ? "Declaring..." : "Declare Capabilities"}
            </button>
          </div>
        }
      >
        <div className="callout">
          Select the task families this node should declare to Core once Gmail is connected.
        </div>
        <div className="capability-list">
          {TASK_CAPABILITY_OPTIONS.map((capability) => {
            const selected = form.selected_task_capabilities.includes(capability);
            return (
              <button
                key={capability}
                className={`capability-option ${selected ? "is-selected" : ""}`}
                type="button"
                onClick={() => onCapabilityToggle(capability)}
              >
                <span className="capability-check">{selected ? "✓" : ""}</span>
                <span className="capability-copy">
                  <strong>{capability}</strong>
                </span>
              </button>
            );
          })}
        </div>
        <div className="callout">
          Capability declaration status: {status?.capability_declaration_status || "pending"}.
          {" "}
          Selected: {capabilitySelection.selected_count ?? form.selected_task_capabilities.length}.
        </div>
        {(capabilitySetup?.blocking_reasons || []).length > 0 ? (
          <ul className="prompt-list">
            {capabilitySetup.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
        {notice ? <div className="callout callout-success">{notice}</div> : null}
        {error ? <div className="callout callout-danger">{error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "governance_sync") {
    return (
      <StageCard title="Governance Sync" tone={statusTone(status?.governance_sync_status)}>
        <div className="callout">Governance sync status: {status?.governance_sync_status || "pending"}.</div>
      </StageCard>
    );
  }

  if (stepId === "ready") {
    return (
      <StageCard title="Ready" tone={boolTone(status?.operational_readiness)}>
        <div className="callout callout-success">
          The node is fully ready. Gmail is connected, capability declaration is current, and governance sync is healthy.
        </div>
      </StageCard>
    );
  }

  return (
    <StageCard title="Node Identity" tone={requiredInputs.length > 0 ? "warning" : "success"}>
      <div className="callout">
        Set the local node name and keep this workstation open during the rest of the setup flow.
      </div>
      {notice ? <div className="callout callout-success">{notice}</div> : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
    </StageCard>
  );
}

function normalizeProviderForm(config) {
  return {
    enabled: Boolean(config?.enabled),
    oauth_client_type: config?.oauth_client_type || "web",
    client_id: config?.client_id || "",
    client_secret_ref: config?.client_secret_ref || "",
    redirect_uri: config?.redirect_uri || "",
    requested_scopes: (config?.requested_scopes?.scopes || []).join("\n") || EMPTY_PROVIDER_FORM.requested_scopes,
  };
}

function buildProviderPayload(form) {
  return {
    enabled: form.enabled,
    oauth_client_type: "web",
    client_id: form.client_id.trim() || null,
    client_secret_ref: form.client_secret_ref.trim() || null,
    redirect_uri: form.redirect_uri.trim() || null,
    requested_scopes: {
      scopes: form.requested_scopes
        .split("\n")
        .map((scope) => scope.trim())
        .filter(Boolean),
    },
  };
}

function Field({ label, name, value, onChange, placeholder, required }) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        className="form-input"
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
      />
    </label>
  );
}

function ToggleField({ label, name, checked, onChange }) {
  return (
    <label className="toggle-field">
      <span className="field-label">{label}</span>
      <button
        className={`toggle ${checked ? "is-on" : ""}`}
        type="button"
        onClick={() => onChange({ target: { name, type: "checkbox", checked: !checked } })}
      >
        <span className="toggle-thumb" />
        <span>{checked ? "Enabled" : "Disabled"}</span>
      </button>
    </label>
  );
}

function TextareaField({ label, name, value, onChange, placeholder }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <textarea
        className="form-input form-textarea"
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={5}
      />
    </label>
  );
}

function TrainingPage({
  trainingStatus,
  trainingLoading,
  trainingError,
  trainingBatch,
  trainingBatchLoading,
  trainingBatchError,
  trainingSavePending,
  trainingModelPending,
  trainingNotice,
  trainingSelections,
  onBack,
  onLoadManualBatch,
  onLoadSemiAutoBatch,
  onTrainModel,
  onSelectionChange,
  onSaveBatch,
}) {
  const [trainingPage, setTrainingPage] = useState(0);
  const items = trainingBatch?.items || [];
  const pageSize = 5;
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(trainingPage, pageCount - 1);
  const pageStart = currentPage * pageSize;
  const visibleItems = items.slice(pageStart, pageStart + pageSize);

  useEffect(() => {
    setTrainingPage(0);
  }, [trainingBatch?.count]);

  return (
    <main className="app-frame">
      <section className="hero card">
        <div>
          <div className="hero-topline">
            <div className="eyebrow">Hexe Email Node</div>
            <div className="status-pill tone-warning">gmail: training</div>
          </div>
          <h1>Training</h1>
          <p className="hero-copy">
            Review flattened local mail and apply manual labels for future local classification work.
          </p>
        </div>
      </section>

      <section className="app-shell">
        <aside className="card stack flow-sidebar">
          <div className="section-heading">
            <h2>Training</h2>
            <span className="pill">{trainingBatch?.count ?? 0} mails</span>
          </div>
          <div className="stack compact-stack">
            <button className="btn btn-ghost" type="button" onClick={onBack}>
              Back To Dashboard
            </button>
            <button className="btn btn-primary" type="button" onClick={onLoadManualBatch} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Manual Classify"}
            </button>
            <button className="btn" type="button" onClick={onTrainModel} disabled={trainingModelPending}>
              {trainingModelPending ? "Training..." : "Train Model"}
            </button>
            <button className="btn" type="button" onClick={onLoadSemiAutoBatch} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Semi Auto Classify"}
            </button>
            <div className="callout">
              Threshold: {trainingStatus?.threshold ?? 0.6}
            </div>
            <div className="callout">
              Classified: {trainingStatus?.classification_summary?.classified_count ?? 0}
            </div>
            <div className="callout">
              Model: {trainingStatus?.model_status?.trained
                ? `trained (${trainingStatus?.model_status?.train_count ?? 0} train / ${trainingStatus?.model_status?.test_count ?? 0} test)`
                : "not trained"}
            </div>
            {trainingStatus?.classification_summary?.per_label
              ? (
                <div className="training-sidebar-stats">
                  {Object.entries(trainingStatus.classification_summary.per_label).map(([label, count]) => (
                    <div key={label} className="training-sidebar-stat">
                      <span>{label}</span>
                      <strong>{count}</strong>
                    </div>
                  ))}
                </div>
                )
              : null}
            {trainingLoading ? <div className="callout">Loading training status...</div> : null}
            {trainingError ? <div className="callout callout-danger">{trainingError}</div> : null}
            {trainingBatchError ? <div className="callout callout-danger">{trainingBatchError}</div> : null}
            {trainingNotice ? <div className="callout callout-success">{trainingNotice}</div> : null}
          </div>
        </aside>

        <div className="main-column">
          <article className="card stack">
            <div className="card-header">
              <h2>Manual Classification</h2>
              <p className="muted">
                {trainingModelPending
                  ? "Training in progress..."
                  : trainingBatch?.source === "semi_auto"
                    ? "Oldest unclassified mails are pre-labeled by the local model and shown here for review."
                    : "Random unknown or low-confidence mails are flattened into a consistent training format for local review."}
              </p>
            </div>
            {!trainingBatch?.items?.length ? (
              <div className="callout">
                Use <code>Manual Classify</code> to load up to 40 local emails for review.
              </div>
            ) : (
              <>
                <div className="actions">
                  <button className="btn btn-primary" type="button" onClick={onSaveBatch} disabled={trainingSavePending}>
                    {trainingSavePending ? "Saving..." : "Save Manual Labels"}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.max(page - 1, 0))}
                    disabled={currentPage === 0}
                  >
                    Previous 5
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.min(page + 1, pageCount - 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next 5
                  </button>
                  <span className="muted tiny training-page-meta">
                    Showing {pageStart + 1}-{Math.min(pageStart + visibleItems.length, items.length)} of {items.length}
                  </span>
                </div>
                <div className="training-list">
                  {visibleItems.map((item) => {
                    const selected = trainingSelections[item.message_id] || {
                      label: item.selected_label || item.predicted_label || item.local_label || "unknown",
                      confidence: item.predicted_confidence ?? item.local_label_confidence ?? trainingStatus?.threshold ?? 0.6,
                    };
                    return (
                      <section key={item.message_id} className="training-item">
                        <div className="training-item-top">
                          <div>
                            <strong>{item.subject || "(no subject)"}</strong>
                            <div className="muted tiny">{item.sender_email || "-"}</div>
                            {item.predicted_label ? (
                              <div className="muted tiny">
                                Predicted: {item.predicted_label} ({Number(item.predicted_confidence || 0).toFixed(2)})
                              </div>
                            ) : null}
                          </div>
                          <span className="pill">{item.message_id}</span>
                        </div>
                        <pre className="training-flat-text">{item.raw_text || item.flat_text}</pre>
                        <div className="training-controls">
                          <label className="field">
                            <span className="field-label">Label</span>
                            <select
                              name="label"
                              value={selected.label}
                              onChange={(event) => onSelectionChange(item.message_id, "label", event.target.value)}
                            >
                              {TRAINING_LABEL_OPTIONS.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span className="field-label">Confidence</span>
                            <input
                              type="number"
                              min="0"
                              max="1"
                              step="0.05"
                              value={selected.confidence}
                              onChange={(event) => onSelectionChange(item.message_id, "confidence", event.target.value)}
                            />
                          </label>
                        </div>
                      </section>
                    );
                  })}
                </div>
                <div className="actions">
                  <button className="btn btn-primary" type="button" onClick={onSaveBatch} disabled={trainingSavePending}>
                    {trainingSavePending ? "Saving..." : "Save Manual Labels"}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.max(page - 1, 0))}
                    disabled={currentPage === 0}
                  >
                    Previous 5
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.min(page + 1, pageCount - 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next 5
                  </button>
                  <span className="muted tiny training-page-meta">
                    Showing {pageStart + 1}-{Math.min(pageStart + visibleItems.length, items.length)} of {items.length}
                  </span>
                </div>
              </>
            )}
          </article>
        </div>
      </section>
    </main>
  );
}

function ProviderSetupPage({
  bootstrap,
  providerConfig,
  providerStatus,
  gmailStatus,
  providerForm,
  providerDirty,
  providerLoading,
  providerSaving,
  providerValidating,
  providerConnecting,
  providerNotice,
  providerError,
  connectUrl,
  onProviderChange,
  onRefresh,
  onSave,
  onValidate,
  onConnect,
  onBack,
}) {
  const providerSummary = providerStatus?.provider_account_summaries?.gmail || {};
  const providerHealth = providerSummary?.health || null;
  const providerAccounts = providerSummary?.accounts || [];
  const primaryAccount = providerAccounts[0] || null;
  const primaryStatus = gmailStatus?.accounts?.[0] || null;
  const validation = providerConfig?.validation || null;
  const providerReadyReasons = [];
  if (bootstrap?.status?.trust_state !== "trusted") {
    providerReadyReasons.push("node trust is not active");
  }
  if (!providerSummary?.configured) {
    providerReadyReasons.push("Gmail config is not valid yet");
  }
  if (!providerForm.enabled) {
    providerReadyReasons.push("provider is disabled");
  }
  const canConnect = providerReadyReasons.length === 0 && !providerConnecting;
  return (
    <main className="app-frame">
      <section className="hero card">
        <div>
          <div className="hero-topline">
            <div className="eyebrow">Hexe Email Node</div>
            <div className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
              gmail: {providerSummary?.provider_state || "loading"}
            </div>
          </div>
          <h1>Gmail</h1>
          <p className="hero-copy">
            Gmail management will live here. This view is being staged into dedicated Gmail status, settings, and action cards.
          </p>
        </div>
        <div className="hero-actions">
          <button className="btn btn-ghost" type="button" onClick={onRefresh} disabled={providerLoading}>
            {providerLoading ? "Refreshing..." : "Refresh"}
          </button>
          <button className="btn btn-ghost" type="button" onClick={onBack}>
            Back To Console
          </button>
        </div>
      </section>

      <section className="grid provider-grid">
        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Status</h2>
            <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
          </div>
          <dl className="facts single-column-facts">
            <div>
              <dt>Provider State</dt>
              <dd>{providerSummary?.provider_state || "pending"}</dd>
            </div>
            <div>
              <dt>Configured</dt>
              <dd>{providerSummary?.configured ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Enabled</dt>
              <dd>{providerConfig?.config?.enabled ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Primary Account</dt>
              <dd>{primaryAccount?.email_address || primaryAccount?.account_id || "not connected"}</dd>
            </div>
            <div>
              <dt>Health</dt>
              <dd>{providerHealth?.status || "unknown"}</dd>
            </div>
            <div>
              <dt>Redirect URI</dt>
              <dd>{providerConfig?.config?.redirect_uri || "not set"}</dd>
            </div>
          </dl>
          {primaryStatus?.labels?.labels?.length ? (
            <div className="stack">
              <div className="section-heading">
                <h3>Available Labels</h3>
                <span className="pill">{primaryStatus.labels.labels.length}</span>
              </div>
              <div className="training-sidebar-stats">
                {primaryStatus.labels.labels.map((label) => (
                  <div key={label.id} className="training-sidebar-stat">
                    <span>{label.name}</span>
                    <span className="muted tiny">{label.id}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {providerNotice ? <div className="callout callout-success">{providerNotice}</div> : null}
          {providerError ? <div className="callout callout-danger">{providerError}</div> : null}
        </article>

        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Settings</h2>
            <span className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
              {providerSummary?.provider_state || "unknown"}
            </span>
          </div>
          <ToggleField
            label="Provider Enabled"
            name="enabled"
            checked={providerForm.enabled}
            onChange={onProviderChange}
          />
          <Field
            label="Client ID"
            name="client_id"
            value={providerForm.client_id}
            onChange={onProviderChange}
            placeholder="Google OAuth client id"
            required
          />
          <Field
            label="Client Secret Ref"
            name="client_secret_ref"
            value={providerForm.client_secret_ref}
            onChange={onProviderChange}
            placeholder="env:GMAIL_CLIENT_SECRET"
            required
          />
          <Field
            label="Redirect URI"
            name="redirect_uri"
            value={providerForm.redirect_uri}
            onChange={onProviderChange}
            placeholder="https://your-domain/google/callback"
            required
          />
          <TextareaField
            label="Requested Scopes"
            name="requested_scopes"
            value={providerForm.requested_scopes}
            onChange={onProviderChange}
            placeholder="One scope per line"
          />
          <div className="actions">
            <button className="btn btn-ghost" type="button" onClick={onValidate} disabled={providerValidating}>
              {providerValidating ? "Validating..." : "Validate"}
            </button>
            <button className="btn btn-primary" type="button" onClick={onSave} disabled={providerSaving}>
              {providerSaving ? "Saving..." : "Save Gmail Config"}
            </button>
          </div>
          {validation ? (
            <div className={`callout ${validation.ok ? "callout-success" : "callout-warning"}`}>
              {validation.ok
                ? "Configuration looks valid."
                : `Missing required fields: ${(validation.missing_fields || []).join(", ") || "unknown"}.`}
            </div>
          ) : null}
        </article>

        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Action</h2>
            <span className="pill">{canConnect ? "ready" : "waiting"}</span>
          </div>
          <div className="callout">
            Create the Gmail authorization link here, then open it to approve access in Google.
          </div>
          {!canConnect ? (
            <div className="callout callout-warning">
              Auth link is not ready yet: {providerReadyReasons.join(", ")}.
            </div>
          ) : null}
          <div className="actions">
            <button className="btn btn-primary" type="button" onClick={onConnect} disabled={!canConnect}>
              {providerConnecting ? "Creating..." : "Create Auth Link"}
            </button>
          </div>
          {connectUrl ? (
            <div className="stack compact-stack">
              <div className="callout callout-success">Auth link created. Open it to continue Gmail authorization.</div>
              <a className="approval-link" href={connectUrl} target="_blank" rel="noreferrer">
                Open Gmail Auth Link
              </a>
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}

export function App() {
  const [view, setView] = useState("setup");
  const [dashboardSection, setDashboardSection] = useState("overview");
  const [setupPinned, setSetupPinned] = useState(false);
  const [bootstrap, setBootstrap] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [declaringCapabilities, setDeclaringCapabilities] = useState(false);
  const [starting, setStarting] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const [providerConfig, setProviderConfig] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [providerForm, setProviderForm] = useState(EMPTY_PROVIDER_FORM);
  const [providerDirty, setProviderDirty] = useState(false);
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerSaving, setProviderSaving] = useState(false);
  const [providerValidating, setProviderValidating] = useState(false);
  const [providerConnecting, setProviderConnecting] = useState(false);
  const [providerNotice, setProviderNotice] = useState("");
  const [providerError, setProviderError] = useState("");
  const [connectUrl, setConnectUrl] = useState("");
  const [gmailStatus, setGmailStatus] = useState(null);
  const [gmailStatusLoading, setGmailStatusLoading] = useState(false);
  const [gmailStatusError, setGmailStatusError] = useState("");
  const [gmailActionPending, setGmailActionPending] = useState("");
  const [gmailActionNotice, setGmailActionNotice] = useState("");
  const [gmailActionError, setGmailActionError] = useState("");
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [trainingError, setTrainingError] = useState("");
  const [trainingBatch, setTrainingBatch] = useState(null);
  const [trainingBatchLoading, setTrainingBatchLoading] = useState(false);
  const [trainingBatchError, setTrainingBatchError] = useState("");
  const [trainingSavePending, setTrainingSavePending] = useState(false);
  const [trainingModelPending, setTrainingModelPending] = useState(false);
  const [trainingNotice, setTrainingNotice] = useState("");
  const [trainingSelections, setTrainingSelections] = useState({});
  const [copyNotice, setCopyNotice] = useState("");
  const [uiUpdatedAt, setUiUpdatedAt] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadBootstrap() {
      try {
        const payload = await fetchJson("/api/node/bootstrap");
        if (!active) {
          return;
        }

        startTransition(() => {
          setBootstrap(payload);
          setProviderStatus(payload.status);
          setUiUpdatedAt(new Date().toISOString());
        });

        if (!touched) {
          setForm({
            core_base_url: payload.config.core_base_url || "",
            node_name: payload.config.node_name || "",
            selected_task_capabilities: payload.config.selected_task_capabilities || [],
          });
        }
      } catch (fetchError) {
        if (!active) {
          return;
        }
        setError(fetchError.message);
      }
    }

    loadBootstrap();
    const intervalId = window.setInterval(loadBootstrap, 2000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [touched]);

  useEffect(() => {
    if (view !== "provider") {
      return undefined;
    }

    let active = true;

    async function loadProviderConfig() {
      setProviderLoading(true);
      try {
      const [configPayload, statusPayload] = await Promise.all([
          fetchJson("/providers/gmail/config"),
          fetchJson("/providers"),
        ]);
        if (!active) {
          return;
        }
        startTransition(() => {
          setProviderConfig(configPayload);
          setProviderStatus(statusPayload);
        });
        if (!providerDirty) {
          setProviderForm(normalizeProviderForm(configPayload.config));
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setProviderError(loadError.message);
      } finally {
        if (active) {
          setProviderLoading(false);
        }
      }
    }

    loadProviderConfig();
    const intervalId = window.setInterval(loadProviderConfig, 4000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [view, providerDirty]);

  useEffect(() => {
    if (!((view === "dashboard" && dashboardSection === "gmail") || view === "provider")) {
      return undefined;
    }

    let active = true;

    async function loadGmailStatus() {
      setGmailStatusLoading(true);
      try {
        const payload = await fetchJson("/api/gmail/status");
        if (!active) {
          return;
        }
        setGmailStatus(payload);
        setGmailStatusError("");
      } catch (loadError) {
        if (!active) {
          return;
        }
        setGmailStatusError(loadError.message);
      } finally {
        if (active) {
          setGmailStatusLoading(false);
        }
      }
    }

    loadGmailStatus();
    const intervalId = window.setInterval(loadGmailStatus, 10000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [view, dashboardSection]);

  useEffect(() => {
    if (view !== "training") {
      return undefined;
    }

    let active = true;

    async function loadTrainingStatus() {
      setTrainingLoading(true);
      try {
        const payload = await fetchJson("/api/gmail/training");
        if (!active) {
          return;
        }
        setTrainingStatus(payload);
        setTrainingError("");
      } catch (loadError) {
        if (!active) {
          return;
        }
        setTrainingError(loadError.message);
      } finally {
        if (active) {
          setTrainingLoading(false);
        }
      }
    }

    loadTrainingStatus();
    return () => {
      active = false;
    };
  }, [view]);

  useEffect(() => {
    const dashboardReady = Boolean(bootstrap?.status?.operational_readiness);
    if (view === "provider") {
      return;
    }
    if (dashboardReady && view === "setup" && !setupPinned) {
      setView("dashboard");
      return;
    }
    if (!dashboardReady && view === "dashboard") {
      setView("setup");
    }
  }, [bootstrap?.status?.operational_readiness, setupPinned, view]);

  function openSetup() {
    setSetupPinned(true);
    setView("setup");
  }

  function openDashboard() {
    setSetupPinned(false);
    setDashboardSection("overview");
    setView("dashboard");
  }

  function openProvider() {
    setSetupPinned(false);
    setView("provider");
  }

  function openTraining() {
    setSetupPinned(false);
    setView("training");
  }

  async function runGmailFetch(window, successLabel) {
    setGmailActionPending(window);
    setGmailActionError("");
    setGmailActionNotice("");
    try {
      const payload = await fetchJson(`/api/gmail/fetch/${window}`, { method: "POST" });
      const refreshedStatus = await fetchJson("/api/gmail/status");
      setGmailStatus(refreshedStatus);
      setGmailActionNotice(`${successLabel} completed. Stored ${payload.summary?.total_count ?? payload.stored_count ?? 0} emails.`);
    } catch (actionError) {
      setGmailActionError(actionError.message);
    } finally {
      setGmailActionPending("");
    }
  }

  async function runSpamhausCheck() {
    setGmailActionPending("spamhaus");
    setGmailActionError("");
    setGmailActionNotice("");
    try {
      const payload = await fetchJson("/api/gmail/spamhaus/check", { method: "POST" });
      const refreshedStatus = await fetchJson("/api/gmail/status");
      setGmailStatus(refreshedStatus);
      setGmailActionNotice(
        `Spamhaus check completed. Checked ${payload.checked_count ?? 0} senders, flagged ${payload.listed_count ?? 0}.`,
      );
    } catch (actionError) {
      setGmailActionError(actionError.message);
    } finally {
      setGmailActionPending("");
    }
  }

  async function loadTrainingManualBatch() {
    setTrainingBatchLoading(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson("/api/gmail/training/manual-batch", { method: "POST" });
      setTrainingBatch(payload);
      setTrainingSelections(
        Object.fromEntries(
          (payload.items || []).map((item) => [
            item.message_id,
            {
              label: item.local_label || "unknown",
              confidence: 1.0,
            },
          ]),
        ),
      );
    } catch (loadError) {
      setTrainingBatchError(loadError.message);
    } finally {
      setTrainingBatchLoading(false);
    }
  }

  async function loadTrainingSemiAutoBatch() {
    setTrainingBatchLoading(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson("/api/gmail/training/semi-auto-batch", { method: "POST" });
      setTrainingBatch(payload);
      setTrainingSelections(
        Object.fromEntries(
          (payload.items || []).map((item) => [
            item.message_id,
            {
              label: item.predicted_label || "unknown",
              confidence: item.predicted_confidence ?? payload.threshold ?? 0.6,
            },
          ]),
        ),
      );
    } catch (loadError) {
      setTrainingBatchError(loadError.message);
    } finally {
      setTrainingBatchLoading(false);
    }
  }

  async function trainLocalModel() {
    setTrainingModelPending(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson("/api/gmail/training/train-model", { method: "POST" });
      const refreshedTraining = await fetchJson("/api/gmail/training");
      setTrainingStatus(refreshedTraining);
      setTrainingNotice(
        `Model trained with ${payload.model_status?.sample_count ?? refreshedTraining?.model_status?.sample_count ?? 0} samples.`,
      );
    } catch (trainError) {
      setTrainingBatchError(trainError.message);
    } finally {
      setTrainingModelPending(false);
    }
  }

  function handleTrainingSelectionChange(messageId, field, value) {
    setTrainingSelections((current) => ({
      ...current,
      [messageId]: {
        ...(current[messageId] || {}),
        [field]: field === "confidence" ? value : value,
      },
    }));
  }

  async function saveTrainingBatch() {
    const isSemiAuto = trainingBatch?.source === "semi_auto";
    const items = Object.entries(trainingSelections).map(([message_id, selection]) => {
      const originalItem = (trainingBatch?.items || []).find((item) => item.message_id === message_id) || {};
      if (isSemiAuto) {
        return {
          message_id,
          selected_label: selection.label || "unknown",
          predicted_label: originalItem.predicted_label || "unknown",
          predicted_confidence: Number(originalItem.predicted_confidence ?? trainingStatus?.threshold ?? 0.6),
        };
      }
      return {
        message_id,
        label: selection.label || "unknown",
        confidence: 1.0,
      };
    });
    setTrainingSavePending(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson(isSemiAuto ? "/api/gmail/training/semi-auto-review" : "/api/gmail/training/manual-classify", {
        method: "POST",
        body: JSON.stringify({ items }),
      });
      setTrainingNotice(`Saved ${payload.saved_count ?? 0} manual classifications.`);
      const [refreshedStatus, refreshedTraining] = await Promise.all([
        fetchJson("/api/gmail/status"),
        fetchJson("/api/gmail/training"),
      ]);
      setGmailStatus(refreshedStatus);
      setTrainingStatus(refreshedTraining);
      await loadTrainingManualBatch();
    } catch (saveError) {
      setTrainingBatchError(saveError.message);
    } finally {
      setTrainingSavePending(false);
    }
  }

  function handleChange(event) {
    const { name, value } = event.target;
    setTouched(true);
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function handleCapabilityToggle(capability) {
    setTouched(true);
    setForm((current) => {
      const selected = current.selected_task_capabilities.includes(capability);
      return {
        ...current,
        selected_task_capabilities: selected
          ? current.selected_task_capabilities.filter((item) => item !== capability)
          : [...current.selected_task_capabilities, capability],
      };
    });
  }

  function handleProviderChange(event) {
    const { name, value, type, checked } = event.target;
    setProviderDirty(true);
    setProviderError("");
    setProviderNotice("");
    setConnectUrl("");
    setProviderForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function refreshProviderState() {
    setProviderLoading(true);
    setProviderError("");
    try {
      const [configPayload, statusPayload] = await Promise.all([
        fetchJson("/providers/gmail/config"),
        fetchJson("/providers"),
      ]);
      setProviderConfig(configPayload);
      setProviderStatus(statusPayload);
      if (!providerDirty) {
        setProviderForm(normalizeProviderForm(configPayload.config));
      }
    } catch (refreshError) {
      setProviderError(refreshError.message);
    } finally {
      setProviderLoading(false);
    }
  }

  async function saveConfiguration() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = await fetchJson("/api/node/config", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setTouched(false);
      setNotice(
        bootstrap?.status?.trust_state === "trusted"
          ? "Capability selection saved."
          : `Saved onboarding configuration for ${payload.node_name || "this node"}.`,
      );
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function declareCapabilities() {
    setDeclaringCapabilities(true);
    setError("");
    setNotice("");
    try {
      const payload = await fetchJson("/api/capabilities/declare", {
        method: "POST",
      });
      setNotice(
        payload.capability_declaration_status === "accepted"
          ? "Capability declaration submitted."
          : `Capability declaration status: ${payload.capability_declaration_status || "pending"}.`,
      );
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (declareError) {
      setError(declareError.message);
    } finally {
      setDeclaringCapabilities(false);
    }
  }

  async function startOnboarding() {
    setStarting(true);
    setError("");
    setNotice("");
    try {
      await fetchJson("/api/node/config", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      const payload = await fetchJson("/api/onboarding/start", {
        method: "POST",
      });
      setTouched(false);
      setNotice(`Onboarding started for ${payload.node_name || "this node"}.`);
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (startError) {
      setError(startError.message);
    } finally {
      setStarting(false);
    }
  }

  async function restartOnboarding() {
    setRestarting(true);
    setError("");
    setNotice("");
    try {
      const payload = await fetchJson("/api/onboarding/restart", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setTouched(false);
      setNotice(`Setup restarted for ${payload.node_name || "this node"}.`);
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (restartError) {
      setError(restartError.message);
    } finally {
      setRestarting(false);
    }
  }

  async function saveProviderConfig() {
    setProviderSaving(true);
    setProviderError("");
    setProviderNotice("");
    try {
      const payload = await fetchJson("/providers/gmail/config", {
        method: "PUT",
        body: JSON.stringify(buildProviderPayload(providerForm)),
      });
      setProviderConfig(payload);
      setProviderStatus(await fetchJson("/providers"));
      setProviderForm(normalizeProviderForm(payload.config));
      setProviderDirty(false);
      setProviderNotice("Gmail provider configuration saved.");
    } catch (saveError) {
      setProviderError(saveError.message);
    } finally {
      setProviderSaving(false);
    }
  }

  async function validateProviderConfig() {
    setProviderValidating(true);
    setProviderError("");
    setProviderNotice("");
    try {
      const payload = await fetchJson("/providers/gmail/config", {
        method: "PUT",
        body: JSON.stringify(buildProviderPayload(providerForm)),
      });
      setProviderConfig(payload);
      setProviderForm(normalizeProviderForm(payload.config));
      setProviderDirty(false);
      setProviderNotice(
        payload.validation.ok
          ? "Gmail provider configuration is valid."
          : `Gmail provider configuration is incomplete: ${payload.validation.missing_fields.join(", ")}.`,
      );
    } catch (validateError) {
      setProviderError(validateError.message);
    } finally {
      setProviderValidating(false);
    }
  }

  async function startProviderConnect() {
    setProviderConnecting(true);
    setProviderError("");
    setProviderNotice("");
    try {
      const payload = await fetchJson("/providers/gmail/accounts/primary/connect/start", {
        method: "POST",
      });
      setConnectUrl(payload.connect_url);
      setProviderNotice("Gmail connect URL created for the primary account.");
      setProviderStatus(await fetchJson("/providers"));
    } catch (connectError) {
      setProviderError(connectError.message);
    } finally {
      setProviderConnecting(false);
    }
  }

  async function copyNodeId() {
    const nodeId = bootstrap?.status?.node_id;
    if (!nodeId || typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      return;
    }
    await navigator.clipboard.writeText(nodeId);
    setCopyNotice("Copied");
    window.setTimeout(() => setCopyNotice(""), 1600);
  }

  async function refreshDashboardState(message = "") {
    setError("");
    try {
      if (message) {
        setNotice(message);
      }
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setProviderStatus(refreshed.status);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (refreshError) {
      setError(refreshError.message);
    }
  }

  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];
  const nodeState = deriveNodeState(bootstrap);
  const setupFlow = deriveSetupFlow(bootstrap);
  const nodeSetupVisible = isNodeSetupVisible(bootstrap);
  const dashboardEnabled = Boolean(status?.operational_readiness);
  const providerSummary = status?.provider_account_summaries?.gmail || {};
  const providerConnected = providerSummary?.provider_state === "connected";
  const gmailPrimary = gmailStatus?.accounts?.[0] || null;
  const gmailPrimaryMailboxStatus = gmailPrimary?.mailbox_status || null;
  const gmailPrimaryAccount = gmailPrimary?.account || null;
  const gmailPrimaryStore = gmailPrimary?.message_store || null;
  const gmailPrimarySpamhaus = gmailPrimary?.spamhaus || null;
  const gmailPrimaryQuotaUsage = gmailPrimary?.quota_usage || null;
  const gmailFetchSchedule = gmailStatus?.fetch_schedule || null;
  const gmailWindowSettings = buildGmailWindowSettings(gmailFetchSchedule);
  const mqttHealth = status?.mqtt_health || {};
  const lastHeartbeatAt = mqttHealth?.last_status_report_at || status?.last_heartbeat_at || null;
  const mqttConnected = status?.mqtt_connection_status === "connected" || mqttHealth?.health_status === "connected";
  const mqttTelemetryFresh = mqttHealth?.status_freshness_state === "fresh";
  const dashboardWarnings = deriveDashboardWarnings({
    status,
    providerConnected,
    mqttConnected,
    mqttHealth,
  });
  const mqttIndicatorClass = mqttConnected || mqttTelemetryFresh
    ? "health-connected"
    : mqttHealth?.status_freshness_state === "unknown"
      ? "health-fresh"
      : "health-pending";
  const mqttSeverityClass = mqttConnected || mqttTelemetryFresh
    ? healthSeverityClass("connected", ["connected"])
    : healthSeverityClass(mqttHealth?.status_freshness_state, [], ["unknown"]);
  if (view === "provider") {
    return (
      <div className="shell">
        <ProviderSetupPage
          bootstrap={bootstrap}
          providerConfig={providerConfig}
          providerStatus={providerStatus}
          gmailStatus={gmailStatus}
          providerForm={providerForm}
          providerDirty={providerDirty}
          providerLoading={providerLoading}
          providerSaving={providerSaving}
          providerValidating={providerValidating}
          providerConnecting={providerConnecting}
          providerNotice={providerNotice}
          providerError={providerError}
          connectUrl={connectUrl}
          onProviderChange={handleProviderChange}
          onRefresh={refreshProviderState}
          onSave={saveProviderConfig}
          onValidate={validateProviderConfig}
          onConnect={startProviderConnect}
          onBack={() => (dashboardEnabled ? openDashboard() : openSetup())}
        />
      </div>
    );
  }

  if (view === "training") {
    return (
      <div className="shell">
        <TrainingPage
          trainingStatus={trainingStatus}
          trainingLoading={trainingLoading}
          trainingError={trainingError}
          trainingBatch={trainingBatch}
          trainingBatchLoading={trainingBatchLoading}
          trainingBatchError={trainingBatchError}
          trainingSavePending={trainingSavePending}
          trainingModelPending={trainingModelPending}
          trainingNotice={trainingNotice}
          trainingSelections={trainingSelections}
          onBack={() => (dashboardEnabled ? openDashboard() : openSetup())}
          onLoadManualBatch={loadTrainingManualBatch}
          onLoadSemiAutoBatch={loadTrainingSemiAutoBatch}
          onTrainModel={trainLocalModel}
          onSelectionChange={handleTrainingSelectionChange}
          onSaveBatch={saveTrainingBatch}
        />
      </div>
    );
  }

  if (view === "dashboard" && dashboardEnabled) {
    return (
      <div className="shell">
        <main className="app-frame">
          <section className="card app-header">
            <div className="app-header-top">
              <div>
                <h1>Hexe Email Node</h1>
              </div>
              <div className="app-header-status-pills">
                <span className={healthSeverityClass(status?.operational_readiness ? "operational" : "pending", ["operational"])}>
                  <span className="status-badge status-operational">
                    {status?.operational_readiness ? "operational" : nodeState.label}
                  </span>
                </span>
                <span className={healthSeverityClass(providerSummary?.provider_state, ["connected"], ["configured"])}>
                  <span className="status-badge">
                    {providerSummary?.provider_state === "connected" ? "Gmail connected" : "Gmail pending"}
                  </span>
                </span>
              </div>
            </div>
            <div className="app-header-bottom">
              <button className="btn btn-ghost app-header-theme-btn" type="button">
                Theme: {currentThemeLabel()}
              </button>
              <div className="app-header-actions">
                <button className="btn btn-ghost" type="button" onClick={restartOnboarding} disabled={restarting}>
                  {restarting ? "Restarting..." : "Restart Setup"}
                </button>
                <button className="btn btn-ghost" type="button" onClick={openSetup}>
                  Open Setup
                </button>
                <button className="btn btn-ghost" type="button" onClick={openProvider}>
                  Setup Provider
                </button>
                <button className="btn btn-ghost" type="button" onClick={copyNodeId} disabled={!status?.node_id}>
                  {copyNotice || "Copy Node ID"}
                </button>
              </div>
            </div>
            <div className="app-header-meta">
              <span className="muted tiny">
                Updated: <code>{formatTelemetryTimestamp(uiUpdatedAt)}</code>
              </span>
              <span className="muted tiny">
                Quota: <code>{gmailPrimaryQuotaUsage ? `${gmailPrimaryQuotaUsage.used_last_minute}/${gmailPrimaryQuotaUsage.limit_per_minute}` : "0/15000"}</code>
              </span>
              <span className="muted tiny">
                Node: <code>{status?.node_id || "pending"}</code>
              </span>
            </div>
          </section>

          <section className="operational-shell">
            <aside className="card operational-shell-nav-card">
              <nav className="operational-shell-nav" aria-label="Operational sections">
                <button
                  type="button"
                  className={`btn operational-nav-btn ${dashboardSection === "overview" ? "btn-primary" : ""}`}
                  onClick={() => setDashboardSection("overview")}
                >
                  Overview
                </button>
                <button
                  type="button"
                  className={`btn operational-nav-btn ${dashboardSection === "gmail" ? "btn-primary" : ""}`}
                  onClick={() => setDashboardSection("gmail")}
                >
                  Gmail
                </button>
                <button type="button" className="btn operational-nav-btn">Runtime</button>
                <button type="button" className="btn operational-nav-btn">Activity</button>
                <button type="button" className="btn operational-nav-btn">Diagnostics</button>
              </nav>
            </aside>

            <div className="operational-shell-content">
              <article className="card node-health-strip operational-content-header">
                <div className="node-health-strip-grid">
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Lifecycle</span>
                    <span className={healthSeverityClass(status?.operational_readiness ? "operational" : "pending", ["operational"])}>
                      <span className="status-badge status-operational">
                        {status?.operational_readiness ? "operational" : setupFlow.current?.label || "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Trust</span>
                    <span className={healthSeverityClass(status?.trust_state, ["trusted"])}>
                      <span className="status-badge status-trusted">{status?.trust_state || "untrusted"}</span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Core API</span>
                    <span className={healthSeverityClass(bootstrap?.config?.core_base_url ? "connected" : "pending", ["connected"])}>
                      <span className={`health-indicator ${bootstrap?.config?.core_base_url ? "health-connected" : "health-pending"}`}>
                        <span className="health-dot" />
                        {bootstrap?.config?.core_base_url ? "connected" : "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">MQTT</span>
                    <span className={mqttSeverityClass}>
                      <span className={`health-indicator ${mqttIndicatorClass}`}>
                        <span className="health-dot" />
                        {mqttConnected ? "connected" : mqttHealth?.status_freshness_state || status?.mqtt_connection_status || "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Governance</span>
                    <span className={healthSeverityClass(status?.governance_sync_status, [], ["ok"])}>
                      <span className={`health-indicator ${status?.governance_sync_status === "ok" ? "health-fresh" : "health-pending"}`}>
                        <span className="health-dot" />
                        {status?.governance_sync_status === "ok" ? "fresh" : status?.governance_sync_status || "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Providers</span>
                    <span className={healthSeverityClass(status?.enabled_providers?.length ? "configured" : "pending", [], ["configured"])}>
                      <span className="status-badge status-configured">
                        {providerConnected ? "configured" : "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Last Heartbeat</span>
                    <code>{formatRelativeTime(lastHeartbeatAt)}</code>
                  </div>
                </div>
              </article>

              {dashboardSection === "gmail" ? (
                <section className="grid operational-dashboard-grid">
                  <article className="card dashboard-primary-card">
                    <div className="card-header">
                      <h2>Gmail Status</h2>
                      <p className="muted">Background Gmail inbox status and unread counts.</p>
                    </div>
                    {gmailStatusError ? <div className="callout callout-danger">{gmailStatusError}</div> : null}
                    <dl className="facts">
                      <div>
                        <dt>Provider State</dt>
                        <dd>{gmailStatus?.provider_state || providerSummary?.provider_state || "pending"}</dd>
                      </div>
                      <div>
                        <dt>Account</dt>
                        <dd>{gmailPrimaryAccount?.email_address || gmailPrimaryAccount?.account_id || "Pending"}</dd>
                      </div>
                      <div>
                        <dt>Unread Today</dt>
                        <dd>{gmailPrimaryMailboxStatus?.unread_today_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd>
                      </div>
                      <div>
                        <dt>Unread Yesterday</dt>
                        <dd>{gmailPrimaryMailboxStatus?.unread_yesterday_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd>
                      </div>
                      <div>
                        <dt>Stored Emails</dt>
                        <dd>{gmailPrimaryStore?.total_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Spamhaus Checked</dt>
                        <dd>{gmailPrimarySpamhaus?.checked_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Spamhaus Pending</dt>
                        <dd>{gmailPrimarySpamhaus?.pending_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Spamhaus Listed</dt>
                        <dd>{gmailPrimarySpamhaus?.listed_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Quota Used / Min</dt>
                        <dd>{gmailPrimaryQuotaUsage ? `${gmailPrimaryQuotaUsage.used_last_minute}/${gmailPrimaryQuotaUsage.limit_per_minute}` : 0}</dd>
                      </div>
                      <div>
                        <dt>Quota Remaining</dt>
                        <dd>{gmailPrimaryQuotaUsage?.remaining_last_minute ?? 15000}</dd>
                      </div>
                    </dl>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Gmail Settings</h2>
                      <p className="muted">Scheduled Gmail fetch windows for operational refresh.</p>
                    </div>
                    <div className="gmail-settings-grid">
                      {gmailWindowSettings.map((windowSetting) => (
                        <section key={windowSetting.key} className="gmail-settings-window">
                          <div className="gmail-settings-window-header">
                            <h3>{windowSetting.label}</h3>
                            <span className="status-pill">{windowSetting.runReason || "pending"}</span>
                          </div>
                          <dl className="facts single-column-facts gmail-settings-facts">
                            <div>
                              <dt>Fetched</dt>
                              <dd>{formatScheduleTimestamp(windowSetting.fetchedAt)}</dd>
                            </div>
                            <div>
                              <dt>Schedule</dt>
                              <dd>{windowSetting.schedule}</dd>
                            </div>
                          </dl>
                        </section>
                      ))}
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Gmail Action</h2>
                      <p className="muted">Manual Gmail fetch actions for initial learning and time-window refresh.</p>
                    </div>
                    <div className="stack compact-stack">
                      {gmailActionError ? <div className="callout callout-danger">{gmailActionError}</div> : null}
                      {gmailActionNotice ? <div className="callout callout-success">{gmailActionNotice}</div> : null}
                      <button
                        type="button"
                        className="btn"
                        disabled={gmailActionPending !== ""}
                        onClick={() => runGmailFetch("initial_learning", "Initial learning fetch")}
                      >
                        Fetch Initial Learning
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={gmailActionPending !== "" || (gmailPrimaryStore?.total_count ?? 0) === 0}
                        onClick={runSpamhausCheck}
                      >
                        Check With Spamhaus
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={openTraining}
                      >
                        Open Training
                      </button>
                      <div className="row gmail-fetch-row">
                        <button
                          type="button"
                          className="btn"
                          disabled={gmailActionPending !== ""}
                        onClick={() => runGmailFetch("today", "Today poll")}
                      >
                        Poll Today
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={gmailActionPending !== ""}
                        onClick={() => runGmailFetch("yesterday", "Yesterday poll")}
                      >
                        Poll Yesterday
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={gmailActionPending !== ""}
                        onClick={() => runGmailFetch("last_hour", "Last hour poll")}
                      >
                        Poll Last Hour
                      </button>
                      </div>
                      <p className="muted tiny">
                        {gmailActionPending
                          ? gmailActionPending === "spamhaus"
                            ? "Spamhaus check in progress..."
                            : "Fetch in progress..."
                          : "Scheduled fetches use the node local timezone and store up to six months of mail."}
                      </p>
                    </div>
                  </article>
                </section>
              ) : (
              <section className="grid operational-dashboard-grid">
                  {dashboardWarnings.length ? (
                    <article className="card degraded-state-banner">
                      <div className="card-header">
                        <h2>Operational With Warnings</h2>
                        <p className="muted">The node is operational, but a few runtime signals still need attention.</p>
                      </div>
                      <div className="stack compact-stack">
                        {dashboardWarnings.map((warning) => (
                          <div key={warning} className="callout callout-warning">
                            {warning}
                          </div>
                        ))}
                        <div className="row">
                          <button className="btn" type="button" onClick={() => refreshDashboardState("Governance status refreshed.")}>
                            Refresh Governance
                          </button>
                          <button className="btn" type="button" onClick={openProvider}>
                            Setup Provider
                          </button>
                        </div>
                      </div>
                    </article>
                  ) : null}
                  <article className="card dashboard-primary-card">
                    <div className="card-header">
                      <h2>Node Overview</h2>
                      <p className="muted">Primary home for identity, lifecycle, and trusted pairing summary.</p>
                    </div>
                    <div className="state-grid">
                      <span>Node ID</span>
                      <code>{formatValue(status?.node_id)}</code>
                      <span>Node Name</span>
                      <code>{formatValue(bootstrap?.config?.node_name)}</code>
                      <span>Lifecycle</span>
                      <span className={healthSeverityClass(status?.operational_readiness ? "operational" : "pending", ["operational"])}>
                        <span className="status-badge status-operational">
                          {status?.operational_readiness ? "operational" : setupFlow.current?.label || "pending"}
                        </span>
                      </span>
                      <span>Trust</span>
                      <span className={healthSeverityClass(status?.trust_state, ["trusted"])}>
                        <span className="status-badge status-trusted">{formatValue(status?.trust_state, "untrusted")}</span>
                      </span>
                      <span>Paired Hexe Core</span>
                      <code>{formatValue(status?.paired_core_id)}</code>
                      <span>Software</span>
                      <code>{formatValue(bootstrap?.config?.node_software_version || status?.node_software_version, "0.1.0")}</code>
                      <span>Pairing Timestamp</span>
                      <code>{formatTelemetryTimestamp(status?.trusted_at)}</code>
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Core Connection</h2>
                      <p className="muted">Trusted Core endpoint metadata and current onboarding linkage.</p>
                    </div>
                    <div className="state-grid">
                      <span>Core ID</span>
                      <code>{formatValue(status?.paired_core_id)}</code>
                      <span>Core API</span>
                      <code>{formatValue(bootstrap?.config?.core_base_url)}</code>
                      <span>Operational MQTT</span>
                      <code>
                        {status?.operational_mqtt_host && status?.operational_mqtt_port
                          ? `${status.operational_mqtt_host}:${status.operational_mqtt_port}`
                          : mqttConnected
                            ? "connected"
                            : "pending"}
                      </code>
                      <span>Connection</span>
                      <span className={mqttSeverityClass}>
                        <span className={`health-indicator ${mqttIndicatorClass}`}>
                          <span className="health-dot" />
                          {mqttConnected ? "connected" : formatValue(mqttHealth?.health_status)}
                        </span>
                      </span>
                      <span>Onboarding Ref</span>
                      <code>{maskOnboardingRef(formatValue(onboarding?.session_id, status?.operational_readiness ? "operational" : "pending"))}</code>
                      <span>Telemetry Freshness</span>
                      <span className={healthSeverityClass(mqttHealth?.status_freshness_state, [], ["fresh"])}>
                        <span
                          className={`health-indicator ${telemetryFreshnessIndicatorClass(
                            mqttHealth?.status_freshness_state,
                          )}`}
                        >
                          <span className="health-dot" />
                          {formatValue(mqttHealth?.status_freshness_state)}
                        </span>
                      </span>
                      <span>Telemetry Age</span>
                      <code>{formatAge(mqttHealth?.status_age_s)}</code>
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Actions</h2>
                      <p className="muted">
                        Operational controls are grouped by purpose so routine actions stay separate from diagnostics and admin tools.
                      </p>
                    </div>
                    <div className="action-groups">
                      <section className="action-group">
                        <div className="action-group-header">
                          <h3>Configuration</h3>
                          <p className="muted tiny">Everyday sync and reconfiguration actions.</p>
                        </div>
                        <div className="row action-group-buttons">
                          <button className="btn" type="button" onClick={openSetup}>Open Setup</button>
                          <button className="btn" type="button" onClick={openProvider}>Setup Gmail Provider</button>
                          <button className="btn" type="button" onClick={() => refreshDashboardState("Governance status refreshed.")}>
                            Refresh Governance
                          </button>
                          <button className="btn" type="button" onClick={() => refreshDashboardState("Provider status refreshed.")}>
                            Refresh Provider Status
                          </button>
                          <button
                            className="btn"
                            type="button"
                            onClick={declareCapabilities}
                            disabled={declaringCapabilities || !form.selected_task_capabilities.length}
                          >
                            {declaringCapabilities ? "Redeclaring..." : "Redeclare Capabilities"}
                          </button>
                        </div>
                      </section>

                      <section className="action-group">
                        <div className="action-group-header">
                          <h3>Runtime Controls</h3>
                          <p className="muted tiny">Service restarts and runtime recovery actions.</p>
                        </div>
                        <div className="row action-group-buttons">
                          <button className="btn" type="button" disabled>Restart Backend</button>
                          <button className="btn" type="button" disabled>Restart Frontend</button>
                          <button className="btn btn-primary" type="button" disabled>Restart Node</button>
                        </div>
                      </section>

                      <section className="action-group action-group-admin">
                        <div className="action-group-header">
                          <h3>Admin &amp; Diagnostics</h3>
                          <p className="muted tiny">Advanced rebuild and inspection actions stay on the diagnostics page.</p>
                        </div>
                        <div className="row action-group-buttons">
                          <button className="btn" type="button" disabled>Open Diagnostics</button>
                        </div>
                      </section>
                    </div>
                  </article>
              </section>
              )}
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="shell">
      <main className="app-frame">
        <section className="hero card">
          <div>
            <div className="hero-topline">
              <div className="eyebrow">Hexe Email Node</div>
              <div className={`status-pill tone-${nodeState.tone}`}>state: {nodeState.label}</div>
            </div>
            <h1>Hexe Email Node Setup</h1>
            <p className="hero-copy">
              Configure the target Core, start onboarding, and watch the node move from local setup to trusted
              operational status.
            </p>
          </div>
          <div className="hero-actions">
            <div className="hero-status">
              <div className={`status-pill tone-${statusTone(onboarding?.onboarding_status)}`}>
                onboarding: {onboarding?.onboarding_status || "loading"}
              </div>
              <div className={`status-pill tone-${statusTone(status?.mqtt_connection_status)}`}>
                mqtt: {status?.mqtt_connection_status || "loading"}
              </div>
            </div>
            <button className="btn btn-ghost" type="button" onClick={restartOnboarding} disabled={restarting}>
              {restarting ? "Restarting..." : "Restart Setup"}
            </button>
            {dashboardEnabled ? (
              <button className="btn btn-ghost" type="button" onClick={openDashboard}>
                Dashboard
              </button>
            ) : null}
            <button className="btn btn-ghost" type="button" onClick={openProvider}>
              Setup Provider
            </button>
          </div>
        </section>

        <section className="app-shell">
          <SetupSidebar flow={setupFlow} />
          <div className="main-column">
            <section className="content-stack">
              {!nodeSetupVisible ? (
                <article className="card stack">
                  <div className="section-heading">
                    <h2>Node Identity</h2>
                    <span className="pill">UI {bootstrap?.config.ui_port || 8083}</span>
                  </div>
                  <Field
                    label="Core base URL"
                    name="core_base_url"
                    value={form.core_base_url}
                    onChange={handleChange}
                    placeholder="http://192.168.1.10:8000"
                    required
                  />
                  <Field
                    label="Node name"
                    name="node_name"
                    value={form.node_name}
                    onChange={handleChange}
                    placeholder="front-desk-email-node"
                    required
                  />
                  <div className="actions">
                    <button className="btn btn-ghost" type="button" onClick={saveConfiguration} disabled={saving}>
                      {saving ? "Saving..." : "Save"}
                    </button>
                    <button className="btn btn-primary" type="button" onClick={startOnboarding} disabled={starting}>
                      {starting ? "Starting..." : "Start Onboarding"}
                    </button>
                  </div>
                  {requiredInputs.length > 0 ? <div className="callout callout-warning">Required before onboarding: {requiredInputs.join(", ")}</div> : null}
                </article>
              ) : null}

              {nodeSetupVisible ? (
                <article className="card stack">
                  <div className="section-heading">
                    <h2>Node Setup</h2>
                    <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
                  </div>
                  <div className="status-rail">
                    <div className={`status-pill tone-${statusTone(onboarding?.onboarding_status)}`}>
                      lifecycle: {onboarding?.onboarding_status || "not_started"}
                    </div>
                    <div className={`status-pill tone-${statusTone(status?.trust_state)}`}>trust: {status?.trust_state || "untrusted"}</div>
                    <div className={`status-pill tone-${statusTone(status?.governance_sync_status)}`}>
                      governance: {status?.governance_sync_status || "pending"}
                    </div>
                    <div className={`status-pill tone-${status?.trust_state === "trusted" ? "success" : "neutral"}`}>
                      core: {status?.trust_state === "trusted" ? "paired" : "not paired"}
                    </div>
                  </div>
                  {renderCurrentStageCard({
                    flow: setupFlow,
                    bootstrap,
                    status,
                    onboarding,
                    requiredInputs,
                    notice,
                    error,
                    setView,
                    form,
                    saving,
                    declaringCapabilities,
                    onCapabilityToggle: handleCapabilityToggle,
                    onSaveConfiguration: saveConfiguration,
                    onDeclareCapabilities: declareCapabilities,
                  })}
                </article>
              ) : null}

              <section className="grid setup-secondary-grid">
                <article className="card stack">
                  <div className="section-heading">
                    <h2>Live Status</h2>
                    <span className="pill">{bootstrap?.config.node_type || "email-node"}</span>
                  </div>
                  <dl className="facts">
                    <div>
                      <dt>Node name</dt>
                      <dd>{bootstrap?.config.node_name || "Not set"}</dd>
                    </div>
                    <div>
                      <dt>Version</dt>
                      <dd>{bootstrap?.config.node_software_version || "0.1.0"}</dd>
                    </div>
                    <div>
                      <dt>Trust state</dt>
                      <dd>{status?.trust_state || "untrusted"}</dd>
                    </div>
                    <div>
                      <dt>Node ID</dt>
                      <dd>{status?.node_id || "Pending"}</dd>
                    </div>
                    <div>
                      <dt>MQTT</dt>
                      <dd>{status?.mqtt_connection_status || "disconnected"}</dd>
                    </div>
                    <div>
                      <dt>Providers</dt>
                      <dd>{status?.providers?.join(", ") || "gmail, smtp, imap, graph"}</dd>
                    </div>
                  </dl>
                </article>

                <article className="card stack">
                  <div className="section-heading">
                    <h2>Operator Prompts</h2>
                    <span className="pill">{setupFlow.current?.label || "Idle"}</span>
                  </div>
                  <ul className="prompt-list">
                    {requiredInputs.length > 0 ? <li>Enter the Core base URL and node name, then save or start onboarding.</li> : null}
                    {onboarding?.approval_url ? <li>Open the approval URL in Core and approve the node.</li> : null}
                    {onboarding?.onboarding_status === "pending" ? <li>Keep this page open while finalize polling continues.</li> : null}
                    <li>Use Restart Setup if you need a fresh onboarding session.</li>
                    {status?.trust_state === "trusted" ? <li>The node is trusted. Use Setup Provider to configure Gmail.</li> : null}
                    {!requiredInputs.length && !onboarding?.approval_url && status?.trust_state !== "trusted" ? <li>Start onboarding when you are ready.</li> : null}
                  </ul>
                </article>
              </section>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}
