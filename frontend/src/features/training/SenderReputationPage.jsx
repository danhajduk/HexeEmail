export function SenderReputationPanel({
  summary,
  detail,
  loading,
  error,
  onInspect,
  onClear,
  showRecords = true,
  showDetail = true,
  emptyMessage = "No sender reputation records yet.",
  senderReputationTone,
  formatSenderReputationInputs,
  formatTelemetryTimestamp,
}) {
  const records = summary?.records || [];

  return (
    <div className="sender-reputation-panel stack compact-stack">
      <div className="sender-reputation-summary-grid">
        <div className="callout">Records: {summary?.total_count ?? 0}</div>
        <div className="callout">Trusted: {summary?.by_state?.trusted ?? 0}</div>
        <div className="callout">Risky: {summary?.by_state?.risky ?? 0}</div>
        <div className="callout">Blocked: {summary?.by_state?.blocked ?? 0}</div>
      </div>
      {showRecords && records.length ? (
        <div className="sender-reputation-list">
          {records.map((record) => (
            <div key={`${record.entity_type}:${record.sender_value}`} className="sender-reputation-item">
              <div>
                <div className="sender-reputation-item-top">
                  <strong>{record.sender_value}</strong>
                  <span className={`status-pill tone-${senderReputationTone(record.reputation_state)}`}>
                    {record.reputation_state}
                  </span>
                </div>
                <div className="muted tiny">
                  Rating {Number(record.rating ?? 0).toFixed(2)} · {formatSenderReputationInputs(record.inputs)}
                </div>
              </div>
              <button className="btn btn-ghost" type="button" onClick={() => onInspect(record.entity_type, record.sender_value)} disabled={loading}>
                Inspect
              </button>
            </div>
          ))}
        </div>
      ) : showRecords ? (
        <div className="callout">{emptyMessage}</div>
      ) : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
      {showDetail && detail ? (
        <div className="sender-reputation-detail">
          <div className="sender-reputation-detail-header">
            <div>
              <strong>{detail.record?.sender_value}</strong>
              <div className="muted tiny">
                {detail.record?.entity_type} · rating {Number(detail.record?.rating ?? 0).toFixed(2)}
              </div>
            </div>
            <div className="actions">
              <span className={`status-pill tone-${senderReputationTone(detail.record?.reputation_state)}`}>
                {detail.record?.reputation_state || "neutral"}
              </span>
              <button className="btn btn-ghost" type="button" onClick={onClear}>Clear</button>
            </div>
          </div>
          <dl className="facts single-column-facts">
            <div>
              <dt>Last Seen</dt>
              <dd>{formatTelemetryTimestamp(detail.record?.last_seen_at)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatTelemetryTimestamp(detail.record?.updated_at)}</dd>
            </div>
            <div>
              <dt>Inputs</dt>
              <dd>{formatSenderReputationInputs(detail.record?.inputs)}</dd>
            </div>
          </dl>
          {(detail.recent_messages || []).length ? (
            <div className="sender-reputation-recent-list">
              {detail.recent_messages.map((message) => (
                <div key={message.message_id} className="sender-reputation-recent-item">
                  <strong>{message.subject || "(no subject)"}</strong>
                  <div className="muted tiny">
                    {message.message_id} · {message.local_label || "unclassified"} · {formatTelemetryTimestamp(message.received_at)}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function SenderReputationPage({
  summary,
  loading,
  error,
  detail,
  detailLoading,
  detailError,
  notice,
  onBack,
  onInspect,
  onClear,
  filterValue,
  onFilterChange,
  collapsedGroups,
  onToggleGroup,
  manualNote,
  onManualNoteChange,
  manualSavePending,
  onApplyManualRating,
  onClearManualRating,
  groupSenderReputationRecords,
  senderReputationTone,
  senderReputationEntityLabel,
  formatSenderReputationInputs,
  formatTelemetryTimestamp,
  senderReputationFilters,
  senderReputationManualActions,
}) {
  const groups = groupSenderReputationRecords(summary?.records || [], filterValue);
  const selectedRecord = detail?.record || null;

  return (
    <main className="app-frame">
      <section className="hero card">
        <div>
          <div className="hero-topline">
            <div className="eyebrow">Hexe Email Node</div>
            <div className="status-pill tone-warning">gmail: sender reputation</div>
          </div>
          <h1>Sender Reputation</h1>
          <p className="hero-copy">Inspect sender and domain reputation derived from local classifications and Spamhaus results.</p>
        </div>
      </section>

      <section className="app-shell">
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

        <div className="main-column">
          <article className="card stack">
            <div className="card-header">
              <h2>Reputation Records</h2>
              <p className="muted">Grouped by domain so sender, sender-domain, and business-domain reputation stay together.</p>
            </div>
            {!groups.length ? (
              <div className="callout">No sender reputation records are available yet.</div>
            ) : (
              <div className="sender-reputation-group-list">
                {groups.map((group) => {
                  const summaryRecord = group.summaryRecord;
                  const collapsed = Boolean(collapsedGroups[group.key]);
                  return (
                    <section key={group.key} className="sender-reputation-group">
                      <button className="sender-reputation-group-toggle" type="button" onClick={() => onToggleGroup(group.key)}>
                        <div>
                          <div className="sender-reputation-item-top">
                            <strong>{group.domain}</strong>
                            <span className={`status-pill tone-${senderReputationTone(summaryRecord?.reputation_state)}`}>
                              {summaryRecord?.reputation_state || "neutral"}
                            </span>
                          </div>
                          <div className="muted tiny">
                            {senderReputationEntityLabel(summaryRecord?.entity_type)} · rating {Number(summaryRecord?.rating ?? 0).toFixed(2)}
                            {" · "}
                            {formatSenderReputationInputs(summaryRecord?.inputs)}
                          </div>
                        </div>
                        <span className="pill">{collapsed ? "Expand" : "Collapse"}</span>
                      </button>
                      {!collapsed ? (
                        <div className="sender-reputation-list">
                          {group.records.map((record) => (
                            <div key={`${record.entity_type}:${record.sender_value}`} className="sender-reputation-item">
                              <div>
                                <div className="sender-reputation-item-top">
                                  <strong>{record.sender_value}</strong>
                                  <span className="pill">{senderReputationEntityLabel(record.entity_type)}</span>
                                  <span className={`status-pill tone-${senderReputationTone(record.reputation_state)}`}>
                                    {record.reputation_state}
                                  </span>
                                </div>
                                <div className="muted tiny">
                                  Rating {Number(record.rating ?? 0).toFixed(2)}
                                  {record.manual_rating !== null && record.manual_rating !== undefined ? ` · manual ${Number(record.manual_rating).toFixed(2)}` : ""}
                                  {" · "}
                                  {formatSenderReputationInputs(record.inputs)}
                                </div>
                              </div>
                              <button className="btn btn-ghost" type="button" onClick={() => onInspect(record.entity_type, record.sender_value)} disabled={detailLoading}>
                                Inspect
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </section>
                  );
                })}
              </div>
            )}
            {detailError ? <div className="callout callout-danger">{detailError}</div> : null}
            {selectedRecord ? (
              <div className="sender-reputation-detail">
                <div className="sender-reputation-detail-header">
                  <div>
                    <strong>{selectedRecord.sender_value}</strong>
                    <div className="muted tiny">
                      {senderReputationEntityLabel(selectedRecord.entity_type)} · effective {Number(selectedRecord.rating ?? 0).toFixed(2)}
                      {" · "}
                      derived {Number(selectedRecord.derived_rating ?? 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="actions">
                    <span className={`status-pill tone-${senderReputationTone(selectedRecord.reputation_state)}`}>
                      {selectedRecord.reputation_state || "neutral"}
                    </span>
                    <button className="btn btn-ghost" type="button" onClick={onClear}>Clear</button>
                  </div>
                </div>
                <dl className="facts single-column-facts">
                  <div><dt>Group Domain</dt><dd>{selectedRecord.group_domain || "n/a"}</dd></div>
                  <div><dt>Last Seen</dt><dd>{formatTelemetryTimestamp(selectedRecord.last_seen_at)}</dd></div>
                  <div><dt>Updated</dt><dd>{formatTelemetryTimestamp(selectedRecord.updated_at)}</dd></div>
                  <div><dt>Inputs</dt><dd>{formatSenderReputationInputs(selectedRecord.inputs)}</dd></div>
                  <div>
                    <dt>Manual Rating</dt>
                    <dd>
                      {selectedRecord.manual_rating !== null && selectedRecord.manual_rating !== undefined
                        ? `${Number(selectedRecord.manual_rating).toFixed(2)}${selectedRecord.manual_rating_note ? ` · ${selectedRecord.manual_rating_note}` : ""}`
                        : "none"}
                    </dd>
                  </div>
                </dl>
                <div className="sender-reputation-manual-rating">
                  <div className="card-header">
                    <h3>Manual Rating</h3>
                    <p className="muted">Operator override applied on top of the derived sender reputation score.</p>
                  </div>
                  <label className="field">
                    <span>Note</span>
                    <input value={manualNote} onChange={(event) => onManualNoteChange(event.target.value)} placeholder="Optional note for this sender or domain" />
                  </label>
                  <div className="chip-row">
                    {senderReputationManualActions.map((action) => (
                      <button key={action.label} className="btn btn-ghost" type="button" onClick={() => onApplyManualRating(action.value)} disabled={manualSavePending}>
                        {action.label}
                      </button>
                    ))}
                    <button className="btn btn-ghost" type="button" onClick={onClearManualRating} disabled={manualSavePending}>Clear Manual Rating</button>
                  </div>
                </div>
                {detailLoading ? <div className="callout">Loading selected record...</div> : null}
                {(detail?.recent_messages || []).length ? (
                  <div className="sender-reputation-recent-list">
                    {detail.recent_messages.map((message) => (
                      <div key={message.message_id} className="sender-reputation-recent-item">
                        <strong>{message.subject || "(no subject)"}</strong>
                        <div className="muted tiny">
                          {message.message_id} · {message.local_label || "unclassified"} · {formatTelemetryTimestamp(message.received_at)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </article>
        </div>
      </section>
    </main>
  );
}
