import { startTransition, useEffect, useState } from "react";

const EMPTY_FORM = {
  core_base_url: "",
  node_name: "",
};

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
  const [view, setView] = useState("console");
  const [bootstrap, setBootstrap] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
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

  function handleChange(event) {
    const { name, value } = event.target;
    setTouched(true);
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
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
      setNotice(`Saved onboarding configuration for ${payload.node_name || "this node"}.`);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
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

  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];
  const nodeState = deriveNodeState(bootstrap);
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
          onBack={() => setView("console")}
        />
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
            <h1>Operator Onboarding Console</h1>
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
            <button className="btn btn-ghost" type="button" onClick={() => setView("provider")}>
              Setup Provider
            </button>
          </div>
        </section>

        <section className="grid">
          <article className="card stack">
            <div className="section-heading">
              <h2>Setup</h2>
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
              <button className="btn btn-ghost" type="button" onClick={restartOnboarding} disabled={restarting}>
                {restarting ? "Restarting..." : "Restart Setup"}
              </button>
            </div>
            {requiredInputs.length > 0 ? (
              <div className="callout callout-warning">Required before onboarding: {requiredInputs.join(", ")}</div>
            ) : null}
            {notice ? <div className="callout callout-success">{notice}</div> : null}
            {error ? <div className="callout callout-danger">{error}</div> : null}
          </article>

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
        </section>

        <section className="grid">
          <article className="card stack">
            <div className="section-heading">
              <h2>Onboarding Timeline</h2>
              <span className={`status-pill tone-${statusTone(onboarding?.trust_state)}`}>
                trust: {onboarding?.trust_state || "untrusted"}
              </span>
            </div>
            <div className="timeline">
              <div className={`timeline-item ${onboarding?.session_id ? "is-active" : ""}`}>
                <strong>Session</strong>
                <span>{onboarding?.session_id || "No session yet"}</span>
              </div>
              <div className={`timeline-item ${onboarding?.approval_url ? "is-active" : ""}`}>
                <strong>Approval URL</strong>
                <span>{onboarding?.approval_url || "Will appear after session creation"}</span>
              </div>
              <div className={`timeline-item ${onboarding?.node_id ? "is-active" : ""}`}>
                <strong>Trust activation</strong>
                <span>{onboarding?.node_id ? `Trusted as ${onboarding.node_id}` : "Waiting for approval"}</span>
              </div>
            </div>
            {onboarding?.approval_url ? (
              <a className="approval-link" href={onboarding.approval_url} target="_blank" rel="noreferrer">
                Open approval URL
              </a>
            ) : null}
            {onboarding?.last_error ? <div className="callout callout-danger">{onboarding.last_error}</div> : null}
          </article>

          <article className="card stack">
            <div className="section-heading">
              <h2>Operator Prompts</h2>
              <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
            </div>
            <ul className="prompt-list">
              {requiredInputs.length > 0 ? <li>Enter the Core base URL and node name, then start onboarding.</li> : null}
              {onboarding?.approval_url ? <li>Open the approval URL in Core and approve the node.</li> : null}
              {onboarding?.onboarding_status === "pending" ? <li>Keep this page open while finalize polling continues.</li> : null}
              <li>Use Restart Setup if you need a fresh onboarding session.</li>
              {status?.trust_state === "trusted" ? <li>The node is trusted. Use Setup Provider to configure Gmail.</li> : null}
              {!requiredInputs.length && !onboarding?.approval_url && status?.trust_state !== "trusted" ? (
                <li>Start onboarding when you are ready.</li>
              ) : null}
            </ul>
          </article>
        </section>
      </main>
    </div>
  );
}
