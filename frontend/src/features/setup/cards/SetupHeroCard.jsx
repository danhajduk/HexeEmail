export function SetupHeroCard({
  nodeState,
  onboarding,
  status,
  statusTone,
  restartOnboarding,
  restarting,
  dashboardEnabled,
  openDashboard,
  openProvider,
}) {
  return (
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
          <button className="btn btn-ghost" type="button" onClick={openDashboard}>
            Dashboard
          </button>
        ) : null}
        <button className="btn btn-ghost" type="button" onClick={openProvider}>
          Setup Provider
        </button>
      </div>
    </section>
  );
}
