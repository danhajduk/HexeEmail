import { SenderReputationHeroCard } from "./cards/SenderReputationHeroCard";
import { SenderReputationRecordsCard } from "./cards/SenderReputationRecordsCard";
import { SenderReputationSidebarCard } from "./cards/SenderReputationSidebarCard";

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
      <SenderReputationHeroCard />

      <section className="app-shell">
        <SenderReputationSidebarCard
          summary={summary}
          onBack={onBack}
          loading={loading}
          error={error}
          notice={notice}
          senderReputationFilters={senderReputationFilters}
          filterValue={filterValue}
          onFilterChange={onFilterChange}
        />

        <div className="main-column">
          <SenderReputationRecordsCard
            groups={groups}
            collapsedGroups={collapsedGroups}
            onToggleGroup={onToggleGroup}
            senderReputationTone={senderReputationTone}
            senderReputationEntityLabel={senderReputationEntityLabel}
            formatSenderReputationInputs={formatSenderReputationInputs}
            onInspect={onInspect}
            detailLoading={detailLoading}
            detailError={detailError}
            selectedRecord={selectedRecord}
            formatTelemetryTimestamp={formatTelemetryTimestamp}
            manualNote={manualNote}
            onManualNoteChange={onManualNoteChange}
            senderReputationManualActions={senderReputationManualActions}
            onApplyManualRating={onApplyManualRating}
            manualSavePending={manualSavePending}
            onClearManualRating={onClearManualRating}
            onClear={onClear}
            detailLoadingMessage={detailLoading ? "Loading selected record..." : ""}
            detail={detail}
          />
        </div>
      </section>
    </main>
  );
}
