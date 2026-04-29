export function NodeHealthStripCard({
  status,
  setupFlow,
  healthSeverityClass,
  bootstrap,
  mqttSeverityClass,
  mqttConnected,
  mqttIndicatorClass,
  mqttHealth,
  providerConnected,
  formatRelativeTime,
  lastHeartbeatAt,
}) {
  return (
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
  );
}
