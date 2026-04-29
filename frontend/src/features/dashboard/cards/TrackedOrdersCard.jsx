export function TrackedOrdersCard({
  trackedOrdersSorted,
  formatScheduleTimestamp,
  title = "Tracked Orders",
  description = "Existing shipment and order records tracked by the local Gmail shipment reconciler.",
  emptyMessage = "No tracked order records are available yet.",
  trackingIntegrations,
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
                <th>Tracking</th>
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
                    <LiveTrackingCell
                      record={record}
                      track123Ready={track123Ready}
                      formatScheduleTimestamp={formatScheduleTimestamp}
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
  formatScheduleTimestamp,
}) {
  const status = liveTrackingLabel(record, track123Ready);
  const tone = liveTrackingTone(record);
  const latestEvent = Array.isArray(record.live_tracking_events) ? record.live_tracking_events[0] : null;
  return (
    <div className="tracking-cell">
      <div className="row compact-row">
        <span className={`status-pill tone-${tone}`}>
          {status}
        </span>
      </div>
      {latestEvent ? (
        <div className="tracking-latest-event">
          <span className="tracking-event-detail">{latestEvent.detail || latestEvent.status_code || "Tracking update"}</span>
          <span className="muted tiny">
            {[latestEvent.location, formatTrackingEventTime(latestEvent.time, formatScheduleTimestamp)].filter(Boolean).join(" · ")}
          </span>
        </div>
      ) : record.last_known_status ? (
        <div className="muted tiny">{record.last_known_status}</div>
      ) : null}
      {record.live_tracking_expected_delivery ? (
        <div className="muted tiny">Expected delivery: {formatTrackingEventTime(record.live_tracking_expected_delivery, formatScheduleTimestamp)}</div>
      ) : null}
    </div>
  );
}

function formatTrackingEventTime(value, formatScheduleTimestamp) {
  if (!value) {
    return "";
  }
  return formatScheduleTimestamp?.(value) || value;
}

function liveTrackingLabel(record, track123Ready) {
  if (!record.tracking_number) {
    return "no number";
  }
  if (!track123Ready) {
    return record.last_known_status || "Track123 off";
  }
  if (record.live_tracking_error) {
    return "error";
  }
  if (record.live_tracking_enabled) {
    return record.live_tracking_status || record.last_known_status || "enabled";
  }
  return record.last_known_status || "pending registration";
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
