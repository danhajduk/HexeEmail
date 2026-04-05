export function TrackedOrdersSection({ trackedOrdersSorted, formatScheduleTimestamp }) {
  return (
    <section className="grid scheduled-tasks-grid">
      <article className="card scheduled-tasks-card">
        <div className="card-header">
          <h2>Tracked Orders</h2>
          <p className="muted">Existing shipment and order records tracked by the local Gmail shipment reconciler.</p>
        </div>
        {trackedOrdersSorted.length ? (
          <div className="scheduled-tasks-table-wrap">
            <table className="scheduled-tasks-table">
              <thead>
                <tr>
                  <th>Seller</th>
                  <th>Carrier</th>
                  <th>Order Number</th>
                  <th>Tracking Number</th>
                  <th>Status</th>
                  <th>Domain</th>
                  <th>Account</th>
                  <th>Last Seen</th>
                  <th>Status Updated</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {trackedOrdersSorted.map((record) => (
                  <tr key={`${record.account_id || "account"}:${record.record_id || record.order_number || record.tracking_number || "record"}`}>
                    <td>{record.seller || "-"}</td>
                    <td>{record.carrier || "-"}</td>
                    <td><code>{record.order_number || "-"}</code></td>
                    <td><code>{record.tracking_number || "-"}</code></td>
                    <td>
                      <span className={`status-pill tone-${record.last_known_status ? "success" : "neutral"}`}>
                        {record.last_known_status || "unknown"}
                      </span>
                    </td>
                    <td>{record.domain || "-"}</td>
                    <td>{record.account_id || "-"}</td>
                    <td>{formatScheduleTimestamp(record.last_seen_at)}</td>
                    <td>{formatScheduleTimestamp(record.status_updated_at)}</td>
                    <td>{formatScheduleTimestamp(record.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="callout">No tracked order records are available yet.</div>
        )}
      </article>
    </section>
  );
}
