export function NodeOverviewCard({
  status,
  bootstrap,
  setupFlow,
  formatValue,
  healthSeverityClass,
  formatTelemetryTimestamp,
}) {
  return (
    <article className="card dashboard-primary-card">
      <div className="card-header">
        <h2>Node Overview</h2>
        <p className="muted">Primary home for identity, lifecycle, and trusted pairing summary.</p>
      </div>
      <div className="state-grid">
        <span>Node ID</span><code>{formatValue(status?.node_id)}</code>
        <span>Node Name</span><code>{formatValue(bootstrap?.config?.node_name)}</code>
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
        <span>Paired Hexe Core</span><code>{formatValue(status?.paired_core_id)}</code>
        <span>Software</span><code>{formatValue(bootstrap?.config?.node_software_version || status?.node_software_version, "0.1.0")}</code>
        <span>Pairing Timestamp</span><code>{formatTelemetryTimestamp(status?.trusted_at)}</code>
      </div>
    </article>
  );
}
