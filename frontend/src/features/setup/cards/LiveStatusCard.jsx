export function LiveStatusCard({ bootstrap, status }) {
  return (
    <article className="card stack">
      <div className="section-heading">
        <h2>Live Status</h2>
        <span className="pill">{bootstrap?.config.node_type || "email-node"}</span>
      </div>
      <dl className="facts">
        <div>
          <dt>Node name</dt>
          <dd>{bootstrap?.config.node_name || "Not set"}</dd>
        </div>
        <div>
          <dt>Version</dt>
          <dd>{bootstrap?.config.node_software_version || "0.1.0"}</dd>
        </div>
        <div>
          <dt>Trust state</dt>
          <dd>{status?.trust_state || "untrusted"}</dd>
        </div>
        <div>
          <dt>Node ID</dt>
          <dd>{status?.node_id || "Pending"}</dd>
        </div>
        <div>
          <dt>MQTT</dt>
          <dd>{status?.mqtt_connection_status || "disconnected"}</dd>
        </div>
        <div>
          <dt>Providers</dt>
          <dd>{status?.providers?.join(", ") || "gmail, smtp, imap, graph"}</dd>
        </div>
      </dl>
    </article>
  );
}
