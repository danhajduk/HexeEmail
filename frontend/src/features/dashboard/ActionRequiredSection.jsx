import { useEffect, useMemo, useState } from "react";

const ACTIVE_STATES = new Set(["new", "ready", "review_needed", "waiting"]);
const FINAL_STATES = new Set(["done", "ignored"]);

const STATE_TONES = {
  new: "tone-warning",
  ready: "tone-success",
  review_needed: "tone-danger",
  waiting: "tone-warning",
  snoozed: "tone-warning",
  done: "tone-success",
  ignored: "tone-muted",
};

const FILTERS = [
  { key: "active", label: "Active" },
  { key: "review", label: "Review Needed" },
  { key: "snoozed", label: "Snoozed" },
  { key: "done", label: "Done" },
  { key: "ignored", label: "Ignored" },
  { key: "high_priority", label: "High Priority" },
];

const CLASSIFICATION_LABELS = [
  "action_required",
  "direct_human",
  "financial",
  "order",
  "invoice",
  "shipment",
  "security",
  "system",
  "newsletter",
  "marketing",
  "unknown",
];

export function ActionRequiredSection({
  actionItems,
  actionItemsLoading,
  actionItemsError,
  selectedActionItem,
  selectedActionItemId,
  selectedActionItemLoading,
  selectedActionItemError,
  actionItemActionPending,
  actionItemActionNotice,
  actionItemActionError,
  onSelectActionItem,
  onRefreshActionItems,
  onSetActionItemState,
  onSnoozeActionItem,
  onSaveActionItemNote,
  onReclassifyActionItem,
  onRegenerateActionItemAiDecision,
  onNotifyActionItem,
  formatScheduleTimestamp,
}) {
  const [filter, setFilter] = useState("active");
  const [profileFilter, setProfileFilter] = useState("all");
  const items = Array.isArray(actionItems) ? actionItems : [];
  const profileOptions = useMemo(() => {
    const profiles = new Set();
    for (const item of items) {
      const profile = item.profile_type || item.profile_id;
      if (profile) {
        profiles.add(String(profile));
      }
    }
    return [...profiles].sort((left, right) => left.localeCompare(right));
  }, [items]);
  const visibleItems = useMemo(
    () =>
      items.filter((item) => {
        if (!matchesFilter(item, filter)) {
          return false;
        }
        if (profileFilter === "all") {
          return true;
        }
        return profileFilter === String(item.profile_type || item.profile_id || "");
      }),
    [filter, items, profileFilter],
  );
  const selectedDetail = selectedActionItem || null;

  return (
    <section className="grid action-required-grid">
      <article className="card scheduled-tasks-card action-required-list-card">
        <div className="card-header action-required-header">
          <div>
            <h2>Action Required</h2>
            <p className="muted">Items that need operator attention from Gmail classification and family extraction.</p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onRefreshActionItems} disabled={actionItemsLoading}>
            {actionItemsLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <div className="action-required-filter-row">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`btn action-required-filter ${filter === item.key ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
          <label className="action-required-profile-filter">
            <span className="sr-only">Profile</span>
            <select className="form-input" value={profileFilter} onChange={(event) => setProfileFilter(event.target.value)}>
              <option value="all">All profiles</option>
              {profileOptions.map((profile) => (
                <option key={profile} value={profile}>
                  {profile}
                </option>
              ))}
            </select>
          </label>
        </div>

        {actionItemsError ? <div className="callout callout-danger">{actionItemsError}</div> : null}
        {!actionItemsError && !items.length && actionItemsLoading ? <div className="callout">Loading action items...</div> : null}
        {!actionItemsError && !actionItemsLoading && !visibleItems.length ? (
          <div className="callout">No Action Required items match this view.</div>
        ) : null}

        {visibleItems.length ? (
          <div className="scheduled-tasks-table-wrap">
            <table className="scheduled-tasks-table action-required-table">
              <thead>
                <tr>
                  <th>State</th>
                  <th>Priority</th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Profile</th>
                  <th>Due / Reminder</th>
                  <th>Confidence</th>
                  <th>Review</th>
                  <th>AI Summary</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => {
                  const selected = item.item_id === selectedActionItemId;
                  return (
                    <tr
                      key={item.item_id}
                      className={selected ? "action-required-row-selected" : ""}
                      onClick={() => onSelectActionItem(item.item_id)}
                    >
                      <td>
                        <button type="button" className="action-required-row-button" onClick={() => onSelectActionItem(item.item_id)}>
                          <span className={`status-pill ${stateTone(item.state)}`}>{formatToken(item.state || "new")}</span>
                        </button>
                      </td>
                      <td>
                        <span className={`status-pill ${priorityTone(item.priority_score)}`}>{formatPriority(item.priority_score)}</span>
                      </td>
                      <td>{item.sender || "-"}</td>
                      <td>
                        <span className="action-required-subject">{item.subject || "-"}</span>
                        {Number(item.grouped_message_count || 0) > 1 ? (
                          <span className="muted">Thread x{item.grouped_message_count}</span>
                        ) : null}
                      </td>
                      <td>{item.profile_type || item.profile_id || "-"}</td>
                      <td>{formatDueReminder(item, formatScheduleTimestamp)}</td>
                      <td>
                        <span className={`status-pill ${confidenceTone(item.confidence)}`}>{formatConfidence(item.confidence)}</span>
                      </td>
                      <td>{formatReviewReasons(item.review_reasons)}</td>
                      <td>{item.ai_decision_summary || "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>

      <article className="card scheduled-tasks-card action-required-detail-card">
        <div className="card-header">
          <h2>Review Detail</h2>
          <p className="muted">{selectedDetail?.subject || "Select an item to inspect the mail, extracted data, and AI decision."}</p>
        </div>
        {selectedActionItemError ? <div className="callout callout-danger">{selectedActionItemError}</div> : null}
        {actionItemActionError ? <div className="callout callout-danger">{actionItemActionError}</div> : null}
        {actionItemActionNotice ? <div className="callout callout-success">{actionItemActionNotice}</div> : null}
        {selectedActionItemLoading ? <div className="callout">Loading selected item...</div> : null}
        {!selectedActionItemLoading && !selectedDetail ? <div className="callout">No Action Required item is selected.</div> : null}
        {selectedDetail ? (
          <div className="action-required-detail-panels">
            <OperatorActionsPanel
              item={selectedDetail}
              pendingAction={actionItemActionPending}
              onSetActionItemState={onSetActionItemState}
              onSnoozeActionItem={onSnoozeActionItem}
              onSaveActionItemNote={onSaveActionItemNote}
              onReclassifyActionItem={onReclassifyActionItem}
              onRegenerateActionItemAiDecision={onRegenerateActionItemAiDecision}
              onNotifyActionItem={onNotifyActionItem}
            />
            <MailReviewPanel item={selectedDetail} formatScheduleTimestamp={formatScheduleTimestamp} />
            <ExtractedDataPanel item={selectedDetail} formatScheduleTimestamp={formatScheduleTimestamp} />
            <AiDecisionPanel item={selectedDetail} formatScheduleTimestamp={formatScheduleTimestamp} />
          </div>
        ) : null}
      </article>
    </section>
  );
}

function OperatorActionsPanel({
  item,
  pendingAction,
  onSetActionItemState,
  onSnoozeActionItem,
  onSaveActionItemNote,
  onReclassifyActionItem,
  onRegenerateActionItemAiDecision,
  onNotifyActionItem,
}) {
  const [operatorNote, setOperatorNote] = useState(item.operator_note || "");
  const [snoozedUntil, setSnoozedUntil] = useState(toDateTimeLocal(item.snoozed_until));
  const [reminderAt, setReminderAt] = useState(toDateTimeLocal(item.reminder_at));
  const [classificationLabel, setClassificationLabel] = useState("action_required");
  const [classificationConfidence, setClassificationConfidence] = useState("1");
  const disabled = Boolean(pendingAction);

  useEffect(() => {
    setOperatorNote(item.operator_note || "");
    setSnoozedUntil(toDateTimeLocal(item.snoozed_until));
    setReminderAt(toDateTimeLocal(item.reminder_at));
    setClassificationLabel("action_required");
    setClassificationConfidence("1");
  }, [item.item_id, item.operator_note, item.reminder_at, item.snoozed_until]);

  return (
    <section className="action-required-panel">
      <div className="action-required-panel-heading">
        <h3>Operator Actions</h3>
        {pendingAction ? <span className="status-pill tone-warning">Working...</span> : null}
      </div>
      <div className="action-required-action-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={disabled}
          onClick={() => onSetActionItemState(item.item_id, "done")}
        >
          Mark Done
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={disabled}
          onClick={() => onSetActionItemState(item.item_id, "review_needed")}
        >
          Needs Review
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={disabled}
          onClick={() => onSetActionItemState(item.item_id, "ready")}
        >
          Accept
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={disabled}
          onClick={() => onSetActionItemState(item.item_id, "ignored")}
        >
          Ignore
        </button>
        {item.action_url ? (
          <a className="btn btn-ghost" href={item.action_url} target="_blank" rel="noreferrer">
            Open Action URL
          </a>
        ) : null}
        <button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => onNotifyActionItem(item.item_id)}>
          Send Notification
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={disabled}
          onClick={() => onRegenerateActionItemAiDecision(item.item_id)}
        >
          Regenerate AI
        </button>
      </div>

      <div className="action-required-operator-grid">
        <label className="field">
          <span className="field-label">Snooze Until</span>
          <input
            className="form-input"
            type="datetime-local"
            value={snoozedUntil}
            onChange={(event) => setSnoozedUntil(event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">Reminder At</span>
          <input
            className="form-input"
            type="datetime-local"
            value={reminderAt}
            onChange={(event) => setReminderAt(event.target.value)}
          />
        </label>
        <div className="actions action-required-inline-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={disabled}
            onClick={() =>
              onSnoozeActionItem(item.item_id, {
                snoozed_until: fromDateTimeLocal(snoozedUntil),
                reminder_at: fromDateTimeLocal(reminderAt),
              })
            }
          >
            Save Reminder
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={disabled}
            onClick={() => onSnoozeActionItem(item.item_id, { snoozed_until: null, reminder_at: null })}
          >
            Clear Snooze
          </button>
        </div>
      </div>

      <div className="action-required-operator-grid">
        <label className="field">
          <span className="field-label">Reclassify Label</span>
          <select className="form-input" value={classificationLabel} onChange={(event) => setClassificationLabel(event.target.value)}>
            {CLASSIFICATION_LABELS.map((label) => (
              <option key={label} value={label}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Confidence</span>
          <input
            className="form-input"
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={classificationConfidence}
            onChange={(event) => setClassificationConfidence(event.target.value)}
          />
        </label>
        <div className="actions action-required-inline-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={disabled}
            onClick={() => onReclassifyActionItem(item.item_id, classificationLabel, Number(classificationConfidence || 1))}
          >
            Reclassify
          </button>
        </div>
      </div>

      <label className="field">
        <span className="field-label">Note</span>
        <textarea
          className="form-input form-textarea action-required-note-input"
          value={operatorNote}
          onChange={(event) => setOperatorNote(event.target.value)}
          rows={3}
        />
      </label>
      <div className="actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={disabled}
          onClick={() => onSaveActionItemNote(item.item_id, operatorNote)}
        >
          Save Note
        </button>
      </div>
    </section>
  );
}

function MailReviewPanel({ item, formatScheduleTimestamp }) {
  const source = item.source_message || {};
  const plainText = extractTextBody(source);
  const htmlText = extractHtmlBody(source);
  return (
    <section className="action-required-panel">
      <div className="action-required-panel-heading">
        <h3>Mail</h3>
        {source.message_id ? (
          <a href={gmailMessageUrl(source.message_id)} target="_blank" rel="noreferrer">
            Open Gmail
          </a>
        ) : null}
      </div>
      <dl className="state-grid action-required-meta-grid">
        <dt>Subject</dt>
        <dd>{source.subject || item.subject || "-"}</dd>
        <dt>From</dt>
        <dd>{source.sender || item.sender || "-"}</dd>
        <dt>To</dt>
        <dd>{formatList(source.recipients)}</dd>
        <dt>Received</dt>
        <dd>{formatScheduleTimestamp(source.received_at || item.received_at)}</dd>
        <dt>Gmail Labels</dt>
        <dd>{formatList(source.label_ids)}</dd>
      </dl>
      <h4>Plain Text</h4>
      <pre className="action-required-mail-text">{plainText || source.snippet || "No plain text body is stored for this message."}</pre>
      <h4>HTML Preview</h4>
      {htmlText ? (
        <iframe
          className="action-required-mail-frame"
          sandbox=""
          title="Sanitized email preview"
          srcDoc={sanitizeHtmlDocument(htmlText)}
        />
      ) : (
        <pre className="action-required-mail-text">No HTML body is stored for this message.</pre>
      )}
    </section>
  );
}

function ExtractedDataPanel({ item, formatScheduleTimestamp }) {
  const extractedFields = item.extracted_fields && typeof item.extracted_fields === "object" ? item.extracted_fields : {};
  const flowOutput = item.flow_output && typeof item.flow_output === "object" ? item.flow_output : {};
  const diagnostics = collectDiagnostics(flowOutput);
  return (
    <section className="action-required-panel">
      <div className="action-required-panel-heading">
        <h3>Extracted Data</h3>
        <span className={`status-pill ${confidenceTone(item.confidence)}`}>{formatConfidence(item.confidence)}</span>
      </div>
      <dl className="state-grid action-required-meta-grid">
        <dt>Profile</dt>
        <dd>{item.profile_type || item.profile_id || "-"}</dd>
        <dt>Template</dt>
        <dd>{flowOutput.template_id || flowOutput.template || flowOutput.profile_id || "-"}</dd>
        <dt>Action URL</dt>
        <dd>{item.action_url ? <a href={item.action_url} target="_blank" rel="noreferrer">{item.action_url}</a> : "-"}</dd>
        <dt>Due</dt>
        <dd>{formatScheduleTimestamp(item.due_at)}</dd>
        <dt>Review Reasons</dt>
        <dd>{formatReviewReasons(item.review_reasons)}</dd>
      </dl>
      <div className="action-required-field-list">
        {Object.entries(extractedFields).length ? (
          Object.entries(extractedFields).map(([key, value]) => (
            <div key={key} className="action-required-field-row">
              <span>{formatToken(key)}</span>
              <code>{formatFieldValue(value)}</code>
            </div>
          ))
        ) : (
          <div className="callout">No extracted fields are stored for this item.</div>
        )}
      </div>
      {diagnostics.length ? (
        <>
          <h4>Diagnostics</h4>
          <ul className="action-required-diagnostics">
            {diagnostics.map((item, index) => (
              <li key={`${item}:${index}`}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      <details>
        <summary>Flow Output JSON</summary>
        <pre className="action-required-json">{formatJson(flowOutput)}</pre>
      </details>
    </section>
  );
}

function AiDecisionPanel({ item, formatScheduleTimestamp }) {
  const payload = item.ai_decision_payload && typeof item.ai_decision_payload === "object" ? item.ai_decision_payload : {};
  const recommendedActions = Array.isArray(payload.recommended_actions) ? payload.recommended_actions : [];
  const calendarSignals = payload.calendar_signals || payload.deadline || payload.deadline_signals || null;
  return (
    <section className="action-required-panel">
      <div className="action-required-panel-heading">
        <h3>AI Decision</h3>
        <span className={`status-pill ${payload.human_review_required ? "tone-danger" : "tone-success"}`}>
          {payload.human_review_required ? "Human Review" : "Ready"}
        </span>
      </div>
      <dl className="state-grid action-required-meta-grid">
        <dt>Primary Label</dt>
        <dd>{payload.primary_label || item.profile_type || item.profile_id || "-"}</dd>
        <dt>Recommended Action</dt>
        <dd>{payload.recommended_action || item.ai_decision_summary || formatRecommendedActions(recommendedActions) || "-"}</dd>
        <dt>Risk Notes</dt>
        <dd>{formatRiskNotes(payload)}</dd>
        <dt>Deadline</dt>
        <dd>{formatScheduleTimestamp(payload.deadline_at || payload.due_at || item.due_at)}</dd>
        <dt>Calendar Signals</dt>
        <dd>{formatFieldValue(calendarSignals)}</dd>
      </dl>
      {recommendedActions.length ? (
        <>
          <h4>Recommended Actions</h4>
          <ul className="action-required-diagnostics">
            {recommendedActions.map((action, index) => (
              <li key={index}>{formatRecommendedAction(action)}</li>
            ))}
          </ul>
        </>
      ) : null}
      <details>
        <summary>Raw AI Decision JSON</summary>
        <pre className="action-required-json">{formatJson(payload)}</pre>
      </details>
    </section>
  );
}

function matchesFilter(item, filter) {
  const state = String(item.state || "");
  if (filter === "review") {
    return state === "review_needed" || Boolean(item.review_reasons?.length);
  }
  if (filter === "snoozed") {
    return state === "snoozed";
  }
  if (filter === "done") {
    return state === "done";
  }
  if (filter === "ignored") {
    return state === "ignored";
  }
  if (filter === "high_priority") {
    return Number(item.priority_score || 0) >= 70 && !FINAL_STATES.has(state);
  }
  return ACTIVE_STATES.has(state);
}

function stateTone(state) {
  return STATE_TONES[String(state || "").toLowerCase()] || "";
}

function priorityTone(value) {
  const score = Number(value || 0);
  if (score >= 80) {
    return "tone-danger";
  }
  if (score >= 55) {
    return "tone-warning";
  }
  return "tone-success";
}

function confidenceTone(value) {
  const confidence = Number(value);
  if (!Number.isFinite(confidence)) {
    return "tone-warning";
  }
  if (confidence >= 0.85) {
    return "tone-success";
  }
  if (confidence >= 0.65) {
    return "tone-warning";
  }
  return "tone-danger";
}

function formatPriority(value) {
  const score = Number(value || 0);
  return Number.isFinite(score) ? `${Math.round(score)}` : "-";
}

function formatConfidence(value) {
  const confidence = Number(value);
  return Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : "-";
}

function formatDueReminder(item, formatScheduleTimestamp) {
  const due = formatScheduleTimestamp(item.due_at);
  const reminder = formatScheduleTimestamp(item.reminder_at);
  const snoozed = formatScheduleTimestamp(item.snoozed_until);
  const parts = [];
  if (due && due !== "-") {
    parts.push(`Due ${due}`);
  }
  if (reminder && reminder !== "-") {
    parts.push(`Reminder ${reminder}`);
  }
  if (snoozed && snoozed !== "-") {
    parts.push(`Snoozed ${snoozed}`);
  }
  return parts.length ? parts.join(" | ") : "-";
}

function formatReviewReasons(reasons) {
  if (!Array.isArray(reasons) || !reasons.length) {
    return "-";
  }
  return reasons.map((reason) => formatToken(reason)).join(", ");
}

function formatList(values) {
  if (!Array.isArray(values) || !values.length) {
    return "-";
  }
  return values.filter(Boolean).join(", ") || "-";
}

function formatToken(value) {
  return String(value || "-").replace(/_/g, " ");
}

function formatFieldValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatFieldValue(item)).join(", ");
  }
  if (typeof value === "object" && "value" in value) {
    return formatFieldValue(value.value);
  }
  return formatJson(value);
}

function formatJson(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
}

function collectDiagnostics(flowOutput) {
  const diagnostics = [];
  for (const key of ["diagnostics", "errors", "warnings", "review_reasons", "needs_review_reasons"]) {
    const value = flowOutput[key];
    if (Array.isArray(value)) {
      diagnostics.push(...value.map((item) => formatFieldValue(item)));
    } else if (value) {
      diagnostics.push(formatFieldValue(value));
    }
  }
  return diagnostics.slice(0, 12);
}

function formatRiskNotes(payload) {
  const notes = payload.risk_notes || payload.risks || payload.risk_summary;
  return formatFieldValue(notes);
}

function formatRecommendedActions(actions) {
  if (!actions.length) {
    return "";
  }
  return actions.map((action) => formatRecommendedAction(action)).join("; ");
}

function formatRecommendedAction(action) {
  if (!action || typeof action !== "object") {
    return formatFieldValue(action);
  }
  const label = action.action || action.type || action.label || action.recommendation || "action";
  const reason = action.reason || action.rationale || action.summary || "";
  const confidence = Number(action.confidence);
  const confidenceText = Number.isFinite(confidence) ? ` (${Math.round(confidence * 100)}%)` : "";
  return `${formatToken(label)}${confidenceText}${reason ? `: ${reason}` : ""}`;
}

function toDateTimeLocal(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function fromDateTimeLocal(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function extractTextBody(source) {
  const payload = normalizeRawPayload(source.raw_payload);
  if (typeof payload === "string") {
    return payload;
  }
  return firstString(payload, ["plain_text", "text", "body_text", "body", "message_text"]) || "";
}

function extractHtmlBody(source) {
  const payload = normalizeRawPayload(source.raw_payload);
  if (!payload || typeof payload !== "object") {
    return "";
  }
  return firstString(payload, ["html", "body_html", "html_body", "message_html"]) || "";
}

function normalizeRawPayload(rawPayload) {
  if (!rawPayload) {
    return null;
  }
  if (typeof rawPayload === "string") {
    const trimmed = rawPayload.trim();
    if (!trimmed) {
      return "";
    }
    try {
      return JSON.parse(trimmed);
    } catch {
      return rawPayload;
    }
  }
  return rawPayload;
}

function firstString(payload, keys) {
  if (!payload || typeof payload !== "object") {
    return "";
  }
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return "";
}

function sanitizeHtmlDocument(html) {
  const sanitized = String(html || "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
    .replace(/<object[\s\S]*?<\/object>/gi, "")
    .replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "")
    .replace(/javascript:/gi, "");
  return `<!doctype html><html><head><base target="_blank"><style>body{font-family:Arial,sans-serif;margin:12px;color:#111;line-height:1.4}img{max-width:100%;height:auto}table{max-width:100%}</style></head><body>${sanitized}</body></html>`;
}

function gmailMessageUrl(messageId) {
  return `https://mail.google.com/mail/u/0/#all/${encodeURIComponent(messageId)}`;
}
