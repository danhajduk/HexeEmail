export function GmailSetupActionCard({ canConnect, providerReadyReasons, onConnect, providerConnecting, connectUrl }) {
  return (
    <article className="card stack">
      <div className="section-heading">
        <h2>Gmail Action</h2>
        <span className="pill">{canConnect ? "ready" : "waiting"}</span>
      </div>
      <div className="callout">Create the Gmail authorization link here, then open it to approve access in Google.</div>
      {!canConnect ? (
        <div className="callout callout-warning">Auth link is not ready yet: {providerReadyReasons.join(", ")}.</div>
      ) : null}
      <div className="actions">
        <button className="btn btn-primary" type="button" onClick={onConnect} disabled={!canConnect}>
          {providerConnecting ? "Creating..." : "Create Auth Link"}
        </button>
      </div>
      {connectUrl ? (
        <div className="stack compact-stack">
          <div className="callout callout-success">Auth link created. Open it to continue Gmail authorization.</div>
          <a className="approval-link" href={connectUrl} target="_blank" rel="noreferrer">Open Gmail Auth Link</a>
        </div>
      ) : null}
    </article>
  );
}
