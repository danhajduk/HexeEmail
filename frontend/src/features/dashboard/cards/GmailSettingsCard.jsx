export function GmailSettingsCard({
  gmailFetchScheduler,
  healthSeverityClass,
  formatScheduleTimestamp,
  gmailWindowSettings,
}) {
  return (
    <article className="card">
      <div className="card-header">
        <h2>Gmail Settings</h2>
        <p className="muted">Scheduled Gmail fetch windows for operational refresh.</p>
      </div>
      <dl className="facts">
        <div>
          <dt>Scheduler</dt>
          <dd>
            <span className={healthSeverityClass(gmailFetchScheduler?.status, ["completed"], ["running"])}>
              <span className="status-badge">
                {gmailFetchScheduler?.loop_active ? "active" : "inactive"}
              </span>
            </span>
          </dd>
        </div>
        <div><dt>Last Check</dt><dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_checked_at)}</dd></div>
        <div><dt>Last Success</dt><dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_success_at)}</dd></div>
        <div><dt>Last Error</dt><dd>{gmailFetchScheduler?.last_error || "-"}</dd></div>
      </dl>
      <p className="muted tiny">{gmailFetchScheduler?.detail || "Scheduler status unavailable."}</p>
      <div className="gmail-settings-grid">
        {gmailWindowSettings.map((windowSetting) => (
          <section key={windowSetting.key} className="gmail-settings-window">
            <div className="gmail-settings-window-header">
              <h3>{windowSetting.label}</h3>
              <span className="status-pill">{windowSetting.runReason || "pending"}</span>
            </div>
            <dl className="facts single-column-facts gmail-settings-facts">
              <div><dt>Fetched</dt><dd>{formatScheduleTimestamp(windowSetting.fetchedAt)}</dd></div>
              <div><dt>Schedule</dt><dd>{windowSetting.schedule}</dd></div>
            </dl>
          </section>
        ))}
      </div>
    </article>
  );
}
