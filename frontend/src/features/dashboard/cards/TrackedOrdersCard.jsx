export function TrackedOrdersCard({
  trackedOrdersSorted,
  formatScheduleTimestamp,
  title = "Tracked Orders",
  description = "Existing shipment and order records tracked by the local Gmail shipment reconciler.",
  emptyMessage = "No tracked order records are available yet.",
  trackingIntegrations,
  liveTrackingPending = "",
  enableLiveTracking,
  refreshLiveTracking,
  showSeller = true,
}) {
  const track123 = trackingIntegrations?.track123 || {};
  const track123Ready = Boolean(track123.enabled && track123.configured);
  return (
    <article className="card scheduled-tasks-card">
      <div className="card-header">
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      {trackedOrdersSorted.length ? (
        <div className="scheduled-tasks-table-wrap">
          <table className="scheduled-tasks-table">
            <thead>
              <tr>
                {showSeller ? <th>Seller</th> : null}
                <th>Carrier</th>
                <th>Order Number</th>
                <th>Tracking Number</th>
                <th>Status</th>
                <th>Live Tracking</th>
                <th>Account</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {trackedOrdersSorted.map((record) => (
                <tr key={`${record.account_id || "account"}:${record.record_id || record.order_number || record.tracking_number || "record"}`}>
                  {showSeller ? <td>{record.seller || "-"}</td> : null}
                  <td>{record.carrier || "-"}</td>
                  <td><code>{record.order_number || "-"}</code></td>
                  <td><code>{record.tracking_number || "-"}</code></td>
                  <td>
                    <span className={`status-pill tone-${record.last_known_status ? "success" : "neutral"}`}>
                      {record.last_known_status || "unknown"}
                    </span>
                  </td>
                  <td>
                    <LiveTrackingCell
                      record={record}
                      track123Ready={track123Ready}
                      liveTrackingPending={liveTrackingPending}
                      enableLiveTracking={enableLiveTracking}
                      refreshLiveTracking={refreshLiveTracking}
                    />
                  </td>
                  <td>{record.account_id || "-"}</td>
                  <td>{formatScheduleTimestamp(record.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="callout">{emptyMessage}</div>
      )}
    </article>
  );
}

function LiveTrackingCell({
  record,
  track123Ready,
  liveTrackingPending,
  enableLiveTracking,
  refreshLiveTracking,
}) {
  if (!record.tracking_number) {
    return <span className="status-pill tone-neutral">no number</span>;
  }
  if (!track123Ready) {
    return <span className="status-pill tone-warning">Track123 off</span>;
  }
  const actionKey = `${record.account_id}:${record.record_id}`;
  const pending = liveTrackingPending === actionKey;
  const status = record.live_tracking_error
    ? "error"
    : record.live_tracking_enabled
      ? record.live_tracking_status || "enabled"
      : "off";
  const tone = liveTrackingTone(record);
  return (
    <div className="row compact-row">
      <span className={`status-pill tone-${tone}`}>
        {status}
      </span>
      {record.live_tracking_location ? <span className="muted">{record.live_tracking_location}</span> : null}
      {record.live_tracking_enabled ? (
        <button
          type="button"
          className="btn btn-ghost"
          disabled={pending}
          onClick={() => refreshLiveTracking?.(record)}
        >
          Refresh
        </button>
      ) : (
        <button
          type="button"
          className="btn btn-ghost"
          disabled={pending}
          onClick={() => enableLiveTracking?.(record)}
        >
          Track
        </button>
      )}
    </div>
  );
}

function liveTrackingTone(record) {
  if (record.live_tracking_error) {
    return "danger";
  }
  const status = String(record.live_tracking_status || "").toLowerCase();
  if (["delivery failed", "attention needed"].includes(status)) {
    return "danger";
  }
  if (["no record", "expired"].includes(status)) {
    return "warning";
  }
  if (["delivered", "in transit", "out for delivery"].includes(status)) {
    return "success";
  }
  return record.live_tracking_enabled ? "neutral" : "neutral";
}
