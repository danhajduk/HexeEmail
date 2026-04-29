export function ReviewOutputsSection({ reviewOutputsSorted, formatScheduleTimestamp }) {
  return (
    <section className="grid scheduled-tasks-grid">
      <article className="card scheduled-tasks-card">
        <div className="card-header">
          <h2>Review Needed Outputs</h2>
          <p className="muted">Family flow outputs that were persisted for operator review.</p>
        </div>
        {reviewOutputsSorted.length ? (
          <div className="scheduled-tasks-table-wrap">
            <table className="scheduled-tasks-table">
              <thead>
                <tr>
                  <th>Family</th>
                  <th>Message</th>
                  <th>Subject</th>
                  <th>Reason</th>
                  <th>Profile</th>
                  <th>Confidence</th>
                  <th>Fields</th>
                  <th>Sender</th>
                  <th>Persisted</th>
                  <th>File</th>
                </tr>
              </thead>
              <tbody>
                {reviewOutputsSorted.map((record) => (
                  <tr key={`${record.flow_family || "family"}:${record.record_path || record.message_id || "review-output"}`}>
                    <td>
                      <span className="status-pill tone-warning">{record.flow_family || "unknown"}</span>
                    </td>
                    <td><code>{record.message_id || "-"}</code></td>
                    <td>{record.subject || "-"}</td>
                    <td>
                      <span className="status-pill tone-warning">{record.decision_reason || "review_needed"}</span>
                    </td>
                    <td>{record.profile_id || "-"}</td>
                    <td>{formatConfidence(record)}</td>
                    <td>{formatExtractedFields(record)}</td>
                    <td>{record.sender_email || record.sender_domain || record.sender_name || "-"}</td>
                    <td>{formatScheduleTimestamp(record.persisted_at)}</td>
                    <td><code>{record.record_path || "-"}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="callout">No review-needed outputs are available right now.</div>
        )}
      </article>
    </section>
  );
}

function formatConfidence(record) {
  const confidence = Number(record.confidence);
  if (!Number.isFinite(confidence)) {
    return record.confidence_level || "-";
  }
  return `${Math.round(confidence * 100)}% ${record.confidence_level || ""}`.trim();
}

function formatExtractedFields(record) {
  const keys = Array.isArray(record.extracted_field_keys) ? record.extracted_field_keys : [];
  if (keys.length) {
    return keys.join(", ");
  }
  const count = Number(record.extracted_field_count || 0);
  return count ? `${count} fields` : "-";
}
