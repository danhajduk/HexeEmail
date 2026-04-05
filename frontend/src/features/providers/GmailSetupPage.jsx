export function GmailSetupPage({
  bootstrap,
  providerConfig,
  providerStatus,
  gmailStatus,
  providerForm,
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
  ToggleField,
  Field,
  TextareaField,
  statusTone,
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
            <div><dt>Provider State</dt><dd>{providerSummary?.provider_state || "pending"}</dd></div>
            <div><dt>Configured</dt><dd>{providerSummary?.configured ? "yes" : "no"}</dd></div>
            <div><dt>Enabled</dt><dd>{providerConfig?.config?.enabled ? "yes" : "no"}</dd></div>
            <div><dt>Primary Account</dt><dd>{primaryAccount?.email_address || primaryAccount?.account_id || "not connected"}</dd></div>
            <div><dt>Health</dt><dd>{providerHealth?.status || "unknown"}</dd></div>
            <div><dt>Redirect URI</dt><dd>{providerConfig?.config?.redirect_uri || "not set"}</dd></div>
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
          <ToggleField label="Provider Enabled" name="enabled" checked={providerForm.enabled} onChange={onProviderChange} />
          <Field label="Client ID" name="client_id" value={providerForm.client_id} onChange={onProviderChange} placeholder="Google OAuth client id" required />
          <Field label="Client Secret Ref" name="client_secret_ref" value={providerForm.client_secret_ref} onChange={onProviderChange} placeholder="env:GMAIL_CLIENT_SECRET" required />
          <Field label="Redirect URI" name="redirect_uri" value={providerForm.redirect_uri} onChange={onProviderChange} placeholder="https://your-domain/google/callback" required />
          <TextareaField label="Requested Scopes" name="requested_scopes" value={providerForm.requested_scopes} onChange={onProviderChange} placeholder="One scope per line" />
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
              {validation.ok ? "Configuration looks valid." : `Missing required fields: ${(validation.missing_fields || []).join(", ") || "unknown"}.`}
            </div>
          ) : null}
        </article>

        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Action</h2>
            <span className="pill">{canConnect ? "ready" : "waiting"}</span>
          </div>
          <div className="callout">Create the Gmail authorization link here, then open it to approve access in Google.</div>
          {!canConnect ? (
            <div className="callout callout-warning">Auth link is not ready yet: {providerReadyReasons.join(", ")}.</div>
          ) : null}
          <div className="actions">
            <button className="btn btn-primary" type="button" onClick={onConnect} disabled={!canConnect}>
              {providerConnecting ? "Creating..." : "Create Auth Link"}
            </button>
          </div>
          {connectUrl ? (
            <div className="stack compact-stack">
              <div className="callout callout-success">Auth link created. Open it to continue Gmail authorization.</div>
              <a className="approval-link" href={connectUrl} target="_blank" rel="noreferrer">Open Gmail Auth Link</a>
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}
