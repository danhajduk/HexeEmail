export function SenderReputationSidebarCard({
  summary,
  onBack,
  loading,
  error,
  notice,
  senderReputationFilters,
  filterValue,
  onFilterChange,
}) {
  return (
    <aside className="card stack flow-sidebar">
      <div className="section-heading">
        <h2>Sender Reputation</h2>
        <span className="pill">{summary?.total_count ?? 0} records</span>
      </div>
      <div className="stack compact-stack">
        <button className="btn btn-ghost" type="button" onClick={onBack}>Back To Training</button>
        {loading ? <div className="callout">Loading reputation...</div> : null}
        {error ? <div className="callout callout-danger">{error}</div> : null}
        {notice ? <div className="callout callout-success">{notice}</div> : null}
        <div className="callout">Trusted: {summary?.by_state?.trusted ?? 0}</div>
        <div className="callout">Neutral: {summary?.by_state?.neutral ?? 0}</div>
        <div className="callout">Risky: {summary?.by_state?.risky ?? 0}</div>
        <div className="callout">Blocked: {summary?.by_state?.blocked ?? 0}</div>
        <div className="stack compact-stack">
          <strong>Risk Filter</strong>
          <div className="chip-row">
            {senderReputationFilters.map((option) => (
              <button key={option.value} className={`btn ${filterValue === option.value ? "" : "btn-ghost"}`} type="button" onClick={() => onFilterChange(option.value)}>
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
