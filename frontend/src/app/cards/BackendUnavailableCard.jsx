export function BackendUnavailableCard({
  apiBase,
  error,
  lastUpdatedAt,
  retrying = false,
  onRetry,
  backendUnavailableMessage,
}) {
  return (
    <article className="card backend-unavailable-card">
      <div className="card-header">
        <h2>Backend Unavailable</h2>
        <p>The Hexe Email Node UI loaded, but the node backend could not be reached.</p>
      </div>
      <div className="backend-unavailable-meta">
        <div className="status-pill tone-danger">offline</div>
        <p className="muted">
          Retry after the node backend is back online, or verify the service address and process status.
        </p>
      </div>
      <div className="state-grid">
        <span>API Base</span>
        <code>{apiBase || "unavailable"}</code>
        <span>Last Attempt</span>
        <code>{lastUpdatedAt || "never"}</code>
        <span>Error</span>
        <code>{backendUnavailableMessage(error)}</code>
      </div>
      <div className="row backend-unavailable-actions">
        <button className="btn btn-primary" type="button" onClick={onRetry} disabled={retrying}>
          {retrying ? "Retrying..." : "Retry Connection"}
        </button>
      </div>
    </article>
  );
}
