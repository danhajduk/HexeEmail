export function GmailSetupHeroCard({ providerSummary, statusTone, onRefresh, providerLoading, onBack }) {
  return (
    <section className="hero card">
      <div>
        <div className="hero-topline">
          <div className="eyebrow">Hexe Email Node</div>
          <div className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
            gmail: {providerSummary?.provider_state || "loading"}
          </div>
        </div>
        <h1>Gmail</h1>
        <p className="hero-copy">
          Gmail management will live here. This view is being staged into dedicated Gmail status, settings, and action cards.
        </p>
      </div>
      <div className="hero-actions">
        <button className="btn btn-ghost" type="button" onClick={onRefresh} disabled={providerLoading}>
          {providerLoading ? "Refreshing..." : "Refresh"}
        </button>
        <button className="btn btn-ghost" type="button" onClick={onBack}>
          Back To Console
        </button>
      </div>
    </section>
  );
}
