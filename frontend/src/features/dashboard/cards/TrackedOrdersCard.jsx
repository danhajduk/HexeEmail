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
                <th>Added</th>
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
                  <td>{formatScheduleTimestamp(record.last_seen_at || record.updated_at)}</td>
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
  const status = normalizedTrackingStatus(record);
  const detail = trackingDetail(record, track123Ready);
  const tone = liveTrackingTone(status, record);
  const latestEvent = Array.isArray(record.live_tracking_events) ? record.live_tracking_events[0] : null;
  return (
    <div className="tracking-cell">
      {status ? (
        <div className="row compact-row">
          <span className={`status-pill tone-${tone}`}>
            {status}
          </span>
        </div>
      ) : null}
      {latestEvent ? (
        <div className="tracking-latest-event">
          <span className="tracking-event-detail">{latestEvent.detail || latestEvent.status_code || "Tracking update"}</span>
          <span className="muted tiny">
            {[latestEvent.location, formatTrackingEventTime(latestEvent.time, formatScheduleTimestamp)].filter(Boolean).join(" · ")}
          </span>
        </div>
      ) : detail ? (
        <div className="muted tiny">{detail}</div>
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

function trackingDetail(record, track123Ready) {
  if (!track123Ready) {
    return record.tracking_number ? "Track123 off" : "";
  }
  if (record.live_tracking_error) {
    return record.live_tracking_error;
  }
  if (!record.tracking_number) {
    return "";
  }
  const normalized = normalizedTrackingStatus(record);
  const rawStatus = String(record.live_tracking_status || record.last_known_status || "").trim();
  if (rawStatus && rawStatus.toLowerCase() !== normalized) {
    return rawStatus;
  }
  return record.live_tracking_enabled ? "" : "pending registration";
}

function normalizedTrackingStatus(record) {
  const candidates = [record.live_tracking_status, record.last_known_status];
  for (const candidate of candidates) {
    const status = normalizeStatusText(candidate);
    if (status) {
      return status;
    }
  }
  return "";
}

function normalizeStatusText(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized || ["no number", "no record", "pending registration", "track123 off", "enabled"].includes(normalized)) {
    return "";
  }
  if (normalized.includes("delivery failed") || normalized.includes("failed delivery")) {
    return "delivery failed";
  }
  if (normalized.includes("attention") || normalized.includes("abnormal")) {
    return "attention needed";
  }
  if (normalized.includes("out for delivery")) {
    return "out for delivery";
  }
  if (normalized.includes("delivered")) {
    return "delivered";
  }
  if (normalized.includes("in transit") || normalized.includes("on the way")) {
    return "in transit";
  }
  if (normalized.includes("shipped")) {
    return "shipped";
  }
  if (normalized.includes("label created")) {
    return "label created";
  }
  if (normalized.includes("info received")) {
    return "info received";
  }
  if (normalized.includes("expired")) {
    return "expired";
  }
  return "";
}

function liveTrackingTone(status, record) {
  if (record.live_tracking_error) {
    return "danger";
  }
  if (["delivery failed", "attention needed"].includes(status)) {
    return "danger";
  }
  if (["expired"].includes(status)) {
    return "warning";
  }
  if (["delivered", "in transit", "out for delivery", "shipped", "label created", "info received"].includes(status)) {
    return "success";
  }
  return record.live_tracking_enabled ? "neutral" : "neutral";
}
