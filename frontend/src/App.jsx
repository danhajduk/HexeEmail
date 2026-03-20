import { startTransition, useEffect, useState } from "react";

const EMPTY_FORM = {
  core_base_url: "",
  node_name: "",
};

async function fetchJson(url, options) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

function statusTone(value) {
  if (value === "trusted" || value === "approved" || value === "connected") {
    return "success";
  }
  if (value === "rejected" || value === "expired" || value === "invalid") {
    return "danger";
  }
  if (value === "pending" || value === "connecting" || value === "reconnecting") {
    return "warning";
  }
  return "neutral";
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

export function App() {
  const [bootstrap, setBootstrap] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

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

  function handleChange(event) {
    const { name, value } = event.target;
    setTouched(true);
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
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

  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];

  return (
    <div className="shell">
      <main className="app-frame">
        <section className="hero card">
          <div>
            <div className="eyebrow">Synthia Email Node</div>
            <h1>Operator Onboarding Console</h1>
            <p className="hero-copy">
              Configure the target Core, start onboarding, and watch the node move from local setup to trusted
              operational status.
            </p>
          </div>
          <div className="hero-status">
            <div className={`status-pill tone-${statusTone(onboarding?.onboarding_status)}`}>
              onboarding: {onboarding?.onboarding_status || "loading"}
            </div>
            <div className={`status-pill tone-${statusTone(status?.mqtt_connection_status)}`}>
              mqtt: {status?.mqtt_connection_status || "loading"}
            </div>
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
              <span className="pill">API {bootstrap?.config.api_port || 8080}</span>
            </div>
            <ul className="prompt-list">
              {requiredInputs.length > 0 ? (
                <li>Enter the Core base URL and node name, then start onboarding.</li>
              ) : null}
              {onboarding?.approval_url ? <li>Open the approval URL in Core and approve the node.</li> : null}
              {onboarding?.onboarding_status === "pending" ? <li>Keep this page open while finalize polling continues.</li> : null}
              {status?.trust_state === "trusted" ? <li>The node is trusted. Restarts should skip onboarding.</li> : null}
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
