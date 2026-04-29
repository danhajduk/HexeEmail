export function DashboardHeaderCard({
  status,
  nodeState,
  healthSeverityClass,
  providerSummary,
  modelTrainingState,
  currentThemeLabel,
  restartOnboarding,
  restarting,
  openSetup,
  openProvider,
  copyNodeId,
  copyNotice,
  formatTelemetryTimestamp,
  uiUpdatedAt,
  gmailPrimaryQuotaUsage,
}) {
  return (
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
          {modelTrainingState ? (
            <span className={`status-pill tone-${modelTrainingState.tone}`}>
              model: {modelTrainingState.label}
            </span>
          ) : null}
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
        {modelTrainingState ? (
          <span className="muted tiny">
            Model: <code>{modelTrainingState.detail}</code>
          </span>
        ) : null}
      </div>
    </section>
  );
}
