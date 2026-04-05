export function OverviewDashboardSection({
  dashboardWarnings,
  refreshDashboardState,
  openProvider,
  status,
  bootstrap,
  setupFlow,
  formatValue,
  healthSeverityClass,
  formatTelemetryTimestamp,
  mqttConnected,
  mqttHealth,
  mqttSeverityClass,
  mqttIndicatorClass,
  maskOnboardingRef,
  onboarding,
  telemetryFreshnessIndicatorClass,
  formatAge,
  serviceControlError,
  serviceControlNotice,
  restartRuntimeService,
  serviceControlPending,
  openSetup,
  declareCapabilities,
  declaringCapabilities,
  form,
}) {
  return (
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

      <article className="card">
        <div className="card-header">
          <h2>Core Connection</h2>
          <p className="muted">Trusted Core endpoint metadata and current onboarding linkage.</p>
        </div>
        <div className="state-grid">
          <span>Core ID</span><code>{formatValue(status?.paired_core_id)}</code>
          <span>Core API</span><code>{formatValue(bootstrap?.config?.core_base_url)}</code>
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
            <span className={`health-indicator ${telemetryFreshnessIndicatorClass(mqttHealth?.status_freshness_state)}`}>
              <span className="health-dot" />
              {formatValue(mqttHealth?.status_freshness_state)}
            </span>
          </span>
          <span>Telemetry Age</span><code>{formatAge(mqttHealth?.status_age_s)}</code>
        </div>
      </article>

      <article className="card">
        <div className="card-header">
          <h2>Actions</h2>
          <p className="muted">Operational controls are grouped by purpose so routine actions stay separate from diagnostics and admin tools.</p>
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
              <button className="btn" type="button" onClick={declareCapabilities} disabled={declaringCapabilities || !form.selected_task_capabilities.length}>
                {declaringCapabilities ? "Redeclaring..." : "Redeclare Capabilities"}
              </button>
            </div>
          </section>

          <section className="action-group">
            <div className="action-group-header">
              <h3>Runtime Controls</h3>
              <p className="muted tiny">Service restarts and runtime recovery actions.</p>
            </div>
            {serviceControlError ? <div className="callout callout-danger">{serviceControlError}</div> : null}
            {serviceControlNotice ? <div className="callout callout-success">{serviceControlNotice}</div> : null}
            <div className="row action-group-buttons">
              <button className="btn" type="button" onClick={() => restartRuntimeService("backend")} disabled={serviceControlPending !== ""}>
                {serviceControlPending === "backend" ? "Restarting Backend..." : "Restart Backend"}
              </button>
              <button className="btn" type="button" onClick={() => restartRuntimeService("frontend")} disabled={serviceControlPending !== ""}>
                {serviceControlPending === "frontend" ? "Restarting Frontend..." : "Restart Frontend"}
              </button>
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
  );
}
