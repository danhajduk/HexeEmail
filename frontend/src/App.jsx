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
  requested_scopes: "https://www.googleapis.com/auth/gmail.send\nhttps://www.googleapis.com/auth/gmail.readonly",
};

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

function ProviderSetupPage({
  bootstrap,
  providerConfig,
  providerStatus,
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
  const canConnect =
    bootstrap?.status?.trust_state === "trusted" &&
    providerSummary?.configured &&
    providerForm.enabled &&
    !providerConnecting;
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
          <h1>Provider Setup</h1>
          <p className="hero-copy">
            Configure Gmail OAuth for this node, validate the settings, and launch the connect flow once the node is
            trusted.
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
            <h2>Gmail Configuration</h2>
            <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
          </div>
          <ToggleField label="Provider status" name="enabled" checked={providerForm.enabled} onChange={onProviderChange} />
          <Field
            label="Client ID"
            name="client_id"
            value={providerForm.client_id}
            onChange={onProviderChange}
            placeholder="google-oauth-client-id.apps.googleusercontent.com"
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
            placeholder="https://hexe-ai.com/google/gmail/callback"
            required
          />
          <TextareaField
            label="Requested scopes"
            name="requested_scopes"
            value={providerForm.requested_scopes}
            onChange={onProviderChange}
            placeholder="One Gmail scope per line"
          />
          <div className="actions">
            <button className="btn btn-ghost" type="button" onClick={onValidate} disabled={providerValidating}>
              {providerValidating ? "Validating..." : "Validate Config"}
            </button>
            <button className="btn btn-primary" type="button" onClick={onSave} disabled={providerSaving || !providerDirty}>
              {providerSaving ? "Saving..." : "Save Provider"}
            </button>
          </div>
          {providerNotice ? <div className="callout callout-success">{providerNotice}</div> : null}
          {providerError ? <div className="callout callout-danger">{providerError}</div> : null}
        </article>

        <article className="card stack">
          <div className="section-heading">
            <h2>Provider Status</h2>
            <span className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
              {providerSummary?.provider_state || "unknown"}
            </span>
          </div>
          <dl className="facts">
            <div>
              <dt>Configured</dt>
              <dd>{providerSummary?.configured ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt>Enabled</dt>
              <dd>{providerSummary?.enabled ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt>Accounts</dt>
              <dd>{providerSummary?.account_count ?? 0}</dd>
            </div>
            <div>
              <dt>Trust State</dt>
              <dd>{bootstrap?.status?.trust_state || "untrusted"}</dd>
            </div>
          </dl>

          <div className="stack compact-stack">
            <div className="section-heading">
              <h2>Validation</h2>
              <span className={`status-pill tone-${providerConfig?.validation?.ok ? "success" : "warning"}`}>
                {providerConfig?.validation?.ok ? "valid" : "needs fields"}
              </span>
            </div>
            {(providerConfig?.validation?.messages || []).length > 0 ? (
              <ul className="prompt-list">
                {providerConfig.validation.messages.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            ) : (
              <div className="callout">
                {(providerConfig?.validation?.missing_fields || []).length > 0
                  ? `Missing: ${providerConfig.validation.missing_fields.join(", ")}`
                  : "Gmail configuration currently validates."}
              </div>
            )}
          </div>

          <div className="actions">
            <button className="btn btn-primary" type="button" onClick={onConnect} disabled={!canConnect}>
              {providerConnecting ? "Preparing..." : "Start Gmail Connect"}
            </button>
          </div>
          {!providerForm.enabled ? <div className="callout callout-warning">Enable the provider before connecting.</div> : null}
          {bootstrap?.status?.trust_state !== "trusted" ? (
            <div className="callout callout-warning">The node must be trusted before Gmail OAuth can start.</div>
          ) : null}
          <div className="callout">
            Use the centralized public redirect URI `https://hexe-ai.com/google/gmail/callback`, then start the connect flow.
          </div>
          {connectUrl ? (
            <a className="approval-link" href={connectUrl} target="_blank" rel="noreferrer">
              Open Google connect URL
            </a>
          ) : null}
        </article>
      </section>
    </main>
  );
}

export function App() {
  const [view, setView] = useState("setup");
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
  const [copyNotice, setCopyNotice] = useState("");

  useEffect(() => {
    let active = true;

    async function loadBootstrap() {
      try {
        const payload = await fetchJson("/ui/bootstrap");
        if (!active) {
          return;
        }

        startTransition(() => {
          setBootstrap(payload);
          setProviderStatus(payload.status);
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
    const dashboardReady = Boolean(bootstrap?.status?.operational_readiness);
    if (view === "provider") {
      return;
    }
    if (dashboardReady && view === "setup") {
      setView("dashboard");
      return;
    }
    if (!dashboardReady && view === "dashboard") {
      setView("setup");
    }
  }, [bootstrap?.status?.operational_readiness, view]);

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
      const payload = await fetchJson("/ui/config", {
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
      const payload = await fetchJson("/ui/capabilities/declare", {
        method: "POST",
      });
      setNotice(
        payload.capability_declaration_status === "accepted"
          ? "Capability declaration submitted."
          : `Capability declaration status: ${payload.capability_declaration_status || "pending"}.`,
      );
      const refreshed = await fetchJson("/ui/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
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
      await fetchJson("/ui/config", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      const payload = await fetchJson("/ui/onboarding/start", {
        method: "POST",
      });
      setTouched(false);
      setNotice(`Onboarding started for ${payload.node_name || "this node"}.`);
      const refreshed = await fetchJson("/ui/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
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
      const payload = await fetchJson("/ui/onboarding/restart", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setTouched(false);
      setNotice(`Setup restarted for ${payload.node_name || "this node"}.`);
      const refreshed = await fetchJson("/ui/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
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

  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];
  const nodeState = deriveNodeState(bootstrap);
  const setupFlow = deriveSetupFlow(bootstrap);
  const nodeSetupVisible = isNodeSetupVisible(bootstrap);
  const dashboardEnabled = Boolean(status?.operational_readiness);
  const providerSummary = status?.provider_account_summaries?.gmail || {};
  if (view === "provider") {
    return (
      <div className="shell">
        <ProviderSetupPage
          bootstrap={bootstrap}
          providerConfig={providerConfig}
          providerStatus={providerStatus}
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
          onBack={() => setView(dashboardEnabled ? "dashboard" : "setup")}
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
                <button className="btn btn-ghost" type="button" onClick={() => setView("setup")}>
                  Open Setup
                </button>
                <button className="btn btn-ghost" type="button" onClick={() => setView("provider")}>
                  Setup Provider
                </button>
                <button className="btn btn-ghost" type="button" onClick={copyNodeId} disabled={!status?.node_id}>
                  {copyNotice || "Copy Node ID"}
                </button>
              </div>
            </div>
            <div className="app-header-meta">
              <span className="muted tiny">
                Updated: <code>{formatTelemetryTimestamp(status?.last_heartbeat_at)}</code>
              </span>
              <span className="muted tiny">
                Node: <code>{status?.node_id || "pending"}</code>
              </span>
            </div>
          </section>

          <section className="dashboard-stack">
            <article className="card node-health-strip dashboard-primary-card">
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
                  <span className={healthSeverityClass(status?.mqtt_connection_status, ["connected"])}>
                    <span className={`health-indicator ${status?.mqtt_connection_status === "connected" ? "health-connected" : "health-pending"}`}>
                      <span className="health-dot" />
                      {status?.mqtt_connection_status || "pending"}
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
                      {status?.enabled_providers?.length ? "configured" : "pending"}
                    </span>
                  </span>
                </div>
                <div className="node-health-strip-item">
                  <span className="muted tiny">Last Telemetry</span>
                  <code>{formatTelemetryTimestamp(status?.last_heartbeat_at)}</code>
                </div>
              </div>
            </article>
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
              <button className="btn btn-ghost" type="button" onClick={() => setView("dashboard")}>
                Dashboard
              </button>
            ) : null}
            <button className="btn btn-ghost" type="button" onClick={() => setView("provider")}>
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

              <section className="grid">
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
