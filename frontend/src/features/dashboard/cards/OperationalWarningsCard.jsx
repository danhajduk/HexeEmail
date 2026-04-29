export function OperationalWarningsCard({ dashboardWarnings, refreshDashboardState, openProvider }) {
  if (!dashboardWarnings.length) {
    return null;
  }

  return (
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
  );
}
