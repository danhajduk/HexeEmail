export function DashboardActionsCard({
  openSetup,
  openProvider,
  refreshDashboardState,
  declareCapabilities,
  declaringCapabilities,
  form,
  serviceControlError,
  serviceControlNotice,
  restartRuntimeService,
  serviceControlPending,
}) {
  return (
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
  );
}
