export function GmailSetupStatusCard({
  bootstrap,
  providerSummary,
  providerConfig,
  primaryAccount,
  providerHealth,
  primaryStatus,
  providerNotice,
  providerError,
}) {
  return (
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
  );
}
