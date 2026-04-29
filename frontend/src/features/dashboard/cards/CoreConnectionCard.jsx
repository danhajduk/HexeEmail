export function CoreConnectionCard({
  status,
  bootstrap,
  mqttConnected,
  mqttHealth,
  mqttSeverityClass,
  mqttIndicatorClass,
  maskOnboardingRef,
  onboarding,
  telemetryFreshnessIndicatorClass,
  healthSeverityClass,
  formatValue,
  formatAge,
}) {
  return (
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
  );
}
