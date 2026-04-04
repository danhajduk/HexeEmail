import { startTransition, useEffect, useState } from "react";

const EMPTY_FORM = {
  core_base_url: "",
  node_name: "",
  selected_task_capabilities: [],
};

const TASK_CAPABILITY_OPTIONS = [
  "task.classification",
  "task.summarization",
  "task.tracking",
];

const EMPTY_PROVIDER_FORM = {
  enabled: false,
  client_id: "",
  client_secret_ref: "",
  redirect_uri: "",
  requested_scopes:
    "https://www.googleapis.com/auth/gmail.send\nhttps://www.googleapis.com/auth/gmail.readonly\nhttps://www.googleapis.com/auth/gmail.modify",
};

const EMPTY_RUNTIME_TASK_FORM = {
  requested_node_type: "ai",
  task_family: "task.classification",
  content_type: "email",
  preferred_provider: "openai",
  preferred_model: "",
  service_id: "",
  target_api_base_url: "http://127.0.0.1:9002",
  email_subject: "",
  email_body: "",
};

const EMPTY_RUNTIME_TASK_STATUS = {
  request_status: "idle",
  last_step: "none",
  detail: "No runtime task request has been started yet.",
  preview_response: null,
  resolve_response: null,
  authorize_response: null,
  registration_request_payload: null,
  execution_request_payload: null,
  execution_response: null,
  usage_summary_response: null,
  started_at: null,
  updated_at: null,
};

const TRAINING_LABEL_OPTIONS = [
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

const DASHBOARD_SECTIONS = new Set(["overview", "gmail", "runtime", "scheduled"]);

function parseHashRoute(hash) {
  const normalized = String(hash || "").replace(/^#\/?/, "").replace(/^\/+|\/+$/g, "");
  if (!normalized) {
    return { view: "dashboard", dashboardSection: "overview" };
  }

  const [head, tail] = normalized.split("/");
  if (head === "dashboard") {
    const section = DASHBOARD_SECTIONS.has(tail) ? tail : "overview";
    return { view: "dashboard", dashboardSection: section };
  }
  if (head === "provider") {
    return { view: "provider", dashboardSection: "overview" };
  }
  if (head === "training" && tail === "reputation") {
    return { view: "training_reputation", dashboardSection: "overview" };
  }
  if (head === "training") {
    return { view: "training", dashboardSection: "overview" };
  }
  return { view: "setup", dashboardSection: "overview" };
}

function buildHashRoute(view, dashboardSection) {
  if (view === "dashboard") {
    const section = DASHBOARD_SECTIONS.has(dashboardSection) ? dashboardSection : "overview";
    return `#/dashboard/${section}`;
  }
  if (view === "provider") {
    return "#/provider";
  }
  if (view === "training") {
    return "#/training";
  }
  if (view === "training_reputation") {
    return "#/training/reputation";
  }
  return "#/setup";
}

const MODEL_TRAINING_STALE_DAYS = 14;

async function fetchJson(url, options) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const rawText = await response.text();
  let payload;

  if (contentType.includes("application/json")) {
    payload = rawText ? JSON.parse(rawText) : {};
  } else {
    payload = { detail: rawText || `Unexpected ${contentType || "response"} from server` };
  }

  if (!response.ok) {
    const detail = payload?.detail;
    const message = (detail && typeof detail === "object" && detail.message) || payload.detail || "Request failed";
    const error = new Error(message);
    error.serverPayload = payload;
    throw error;
  }
  if (!contentType.includes("application/json")) {
    throw new Error("Server returned HTML instead of JSON. Check that the API proxy points to the node backend.");
  }
  return payload;
}

function statusTone(value) {
  if (value === "trusted" || value === "approved" || value === "connected" || value === "configured") {
    return "success";
  }
  if (value === "rejected" || value === "expired" || value === "invalid" || value === "revoked") {
    return "danger";
  }
  if (value === "pending" || value === "connecting" || value === "reconnecting" || value === "oauth_pending") {
    return "warning";
  }
  return "neutral";
}

function boolTone(value) {
  return value ? "success" : "neutral";
}

function formatTelemetryTimestamp(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function healthSeverityClass(value, successValues = [], metaValues = []) {
  if (successValues.includes(value)) {
    return "severity-indicator severity-success";
  }
  if (metaValues.includes(value)) {
    return "severity-indicator severity-meta";
  }
  return "severity-indicator severity-warning";
}

function runtimeAuthorizationGranted(payload) {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  if (payload.authorized === true) {
    return true;
  }
  return Boolean(payload.token || payload.authorization_id || payload.grant_id);
}

function runtimeTaskStateHasContent(payload) {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  if (payload.last_step && payload.last_step !== "none") {
    return true;
  }
  return Boolean(
    payload.preview_response ||
      payload.resolve_response ||
      payload.authorize_response ||
      payload.registration_request_payload ||
      payload.execution_request_payload ||
      payload.execution_response ||
      payload.usage_summary_response,
  );
}

function currentThemeLabel() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return "system";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function parseRuntimeExecutionOutput(output) {
  if (!output || typeof output !== "object") {
    return null;
  }
  if (output.label || output.confidence !== undefined || output.rationale) {
    return output;
  }
  if (typeof output.text !== "string") {
    return null;
  }
  try {
    const parsed = JSON.parse(output.text);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function formatValue(value, fallback = "pending") {
  return value || fallback;
}

function formatAge(value) {
  if (value === null || value === undefined) {
    return "pending";
  }
  if (value < 60) {
    return `${value}s`;
  }
  if (value < 3600) {
    return `${Math.floor(value / 60)}m`;
  }
  return `${Math.floor(value / 3600)}h`;
}

function formatScheduleTimestamp(value) {
  if (!value) {
    return "-";
  }
  return formatTelemetryTimestamp(value);
}

function deriveModelTrainingState(modelStatus, providerConnected) {
  if (!providerConnected) {
    return null;
  }
  if (!modelStatus?.trained || !modelStatus?.trained_at) {
    return {
      label: "untrained",
      tone: "danger",
      detail: "Local classifier has not been trained yet.",
    };
  }
  const trainedAt = new Date(modelStatus.trained_at);
  if (Number.isNaN(trainedAt.getTime())) {
    return {
      label: "degraded",
      tone: "warning",
      detail: "Local classifier metadata is missing a valid training timestamp.",
    };
  }
  const ageMs = Date.now() - trainedAt.getTime();
  const staleMs = MODEL_TRAINING_STALE_DAYS * 24 * 60 * 60 * 1000;
  if (ageMs < staleMs) {
    return {
      label: "trained",
      tone: "success",
      detail: `Last local model training was ${formatTelemetryTimestamp(modelStatus.trained_at)}.`,
    };
  }
  const ageDays = Math.floor(ageMs / (24 * 60 * 60 * 1000));
  return {
    label: "degraded",
    tone: "warning",
    detail: `Last local model training was ${ageDays} days ago.`,
  };
}

function resolvePrimaryModelStatus(gmailModelStatus, trainingModelStatus) {
  const gmailTrainedAt = gmailModelStatus?.trained_at ? new Date(gmailModelStatus.trained_at) : null;
  const trainingTrainedAt = trainingModelStatus?.trained_at ? new Date(trainingModelStatus.trained_at) : null;
  const gmailHasValidTimestamp = gmailTrainedAt instanceof Date && !Number.isNaN(gmailTrainedAt.getTime());
  const trainingHasValidTimestamp = trainingTrainedAt instanceof Date && !Number.isNaN(trainingTrainedAt.getTime());

  if (trainingHasValidTimestamp && (!gmailHasValidTimestamp || trainingTrainedAt >= gmailTrainedAt)) {
    return trainingModelStatus;
  }
  if (gmailHasValidTimestamp) {
    return gmailModelStatus;
  }
  if (trainingModelStatus?.trained) {
    return trainingModelStatus;
  }
  return gmailModelStatus || trainingModelStatus || null;
}

function backendUnavailableMessage(error) {
  return error || "backend unavailable";
}

function senderReputationTone(value) {
  if (value === "trusted") {
    return "success";
  }
  if (value === "risky") {
    return "warning";
  }
  if (value === "blocked") {
    return "danger";
  }
  return "neutral";
}

function formatSenderReputationInputs(inputs) {
  const value = inputs || {};
  return [
    `${value.message_count ?? 0} msgs`,
    `+${value.classification_positive_count ?? 0}`,
    `-${value.classification_negative_count ?? 0}`,
    `clean ${value.spamhaus_clean_count ?? 0}`,
    `listed ${value.spamhaus_listed_count ?? 0}`,
  ].join(" · ");
}

const SENDER_REPUTATION_FILTERS = [
  { value: "all", label: "All" },
  { value: "trusted", label: "Trusted" },
  { value: "neutral", label: "Neutral" },
  { value: "risky", label: "Risky" },
  { value: "blocked", label: "Blocked" },
];

const SENDER_REPUTATION_MANUAL_ACTIONS = [
  { label: "Mark Trusted", value: 2.0 },
  { label: "Mark Neutral", value: 0.0 },
  { label: "Mark Risky", value: -2.0 },
  { label: "Block", value: -4.0 },
];

function senderReputationEntityLabel(entityType) {
  if (entityType === "business_domain") {
    return "Business Domain";
  }
  if (entityType === "domain") {
    return "Sender Domain";
  }
  return "Sender";
}

function groupSenderReputationRecords(records, riskFilter = "all") {
  const filteredRecords = (records || []).filter((record) => {
    if (riskFilter === "all") {
      return true;
    }
    return record.reputation_state === riskFilter;
  });
  const groupsByDomain = new Map();
  filteredRecords.forEach((record) => {
    const domainKey = record.group_domain || record.sender_domain || record.sender_value || "unknown";
    const currentGroup = groupsByDomain.get(domainKey) || {
      key: domainKey,
      domain: domainKey,
      records: [],
    };
    currentGroup.records.push(record);
    groupsByDomain.set(domainKey, currentGroup);
  });
  return Array.from(groupsByDomain.values())
    .map((group) => {
      const sortedRecords = [...group.records].sort((left, right) => {
        const priority = {
          business_domain: 0,
          domain: 1,
          email: 2,
        };
        const leftPriority = priority[left.entity_type] ?? 99;
        const rightPriority = priority[right.entity_type] ?? 99;
        if (leftPriority !== rightPriority) {
          return leftPriority - rightPriority;
        }
        return String(left.sender_value || "").localeCompare(String(right.sender_value || ""));
      });
      const summaryRecord =
        sortedRecords.find((record) => record.entity_type === "business_domain") ||
        sortedRecords.find((record) => record.entity_type === "domain" && record.sender_value === group.domain) ||
        sortedRecords[0] ||
        null;
      return {
        ...group,
        records: sortedRecords,
        summaryRecord,
      };
    })
    .sort((left, right) => String(left.domain).localeCompare(String(right.domain)));
}

function BackendUnavailableScreen({
  apiBase,
  error,
  lastUpdatedAt,
  retrying = false,
  onRetry,
}) {
  return (
    <section className="backend-unavailable-view">
      <article className="card backend-unavailable-card">
        <div className="card-header">
          <h2>Backend Unavailable</h2>
          <p>The Hexe Email Node UI loaded, but the node backend could not be reached.</p>
        </div>
        <div className="backend-unavailable-meta">
          <div className="status-pill tone-danger">offline</div>
          <p className="muted">
            Retry after the node backend is back online, or verify the service address and process status.
          </p>
        </div>
        <div className="state-grid">
          <span>API Base</span>
          <code>{apiBase || "unavailable"}</code>
          <span>Last Attempt</span>
          <code>{lastUpdatedAt || "never"}</code>
          <span>Error</span>
          <code>{backendUnavailableMessage(error)}</code>
        </div>
        <div className="row backend-unavailable-actions">
          <button className="btn btn-primary" type="button" onClick={onRetry} disabled={retrying}>
            {retrying ? "Retrying..." : "Retry Connection"}
          </button>
        </div>
      </article>
    </section>
  );
}

function SenderReputationPanel({
  summary,
  detail,
  loading,
  error,
  onInspect,
  onClear,
  showRecords = true,
  showDetail = true,
  emptyMessage = "No sender reputation records yet.",
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
              <button
                className="btn btn-ghost"
                type="button"
                onClick={() => onInspect(record.entity_type, record.sender_value)}
                disabled={loading}
              >
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
              <button className="btn btn-ghost" type="button" onClick={onClear}>
                Clear
              </button>
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

function SenderReputationPage({
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
          <p className="hero-copy">
            Inspect sender and domain reputation derived from local classifications and Spamhaus results.
          </p>
        </div>
      </section>

      <section className="app-shell">
        <aside className="card stack flow-sidebar">
          <div className="section-heading">
            <h2>Sender Reputation</h2>
            <span className="pill">{summary?.total_count ?? 0} records</span>
          </div>
          <div className="stack compact-stack">
            <button className="btn btn-ghost" type="button" onClick={onBack}>
              Back To Training
            </button>
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
                {SENDER_REPUTATION_FILTERS.map((option) => (
                  <button
                    key={option.value}
                    className={`btn ${filterValue === option.value ? "" : "btn-ghost"}`}
                    type="button"
                    onClick={() => onFilterChange(option.value)}
                  >
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
                                  {record.manual_rating !== null && record.manual_rating !== undefined
                                    ? ` · manual ${Number(record.manual_rating).toFixed(2)}`
                                    : ""}
                                  {" · "}
                                  {formatSenderReputationInputs(record.inputs)}
                                </div>
                              </div>
                              <button
                                className="btn btn-ghost"
                                type="button"
                                onClick={() => onInspect(record.entity_type, record.sender_value)}
                                disabled={detailLoading}
                              >
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
                    <button className="btn btn-ghost" type="button" onClick={onClear}>
                      Clear
                    </button>
                  </div>
                </div>
                <dl className="facts single-column-facts">
                  <div>
                    <dt>Group Domain</dt>
                    <dd>{selectedRecord.group_domain || "n/a"}</dd>
                  </div>
                  <div>
                    <dt>Last Seen</dt>
                    <dd>{formatTelemetryTimestamp(selectedRecord.last_seen_at)}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatTelemetryTimestamp(selectedRecord.updated_at)}</dd>
                  </div>
                  <div>
                    <dt>Inputs</dt>
                    <dd>{formatSenderReputationInputs(selectedRecord.inputs)}</dd>
                  </div>
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
                    <input
                      value={manualNote}
                      onChange={(event) => onManualNoteChange(event.target.value)}
                      placeholder="Optional note for this sender or domain"
                    />
                  </label>
                  <div className="chip-row">
                    {SENDER_REPUTATION_MANUAL_ACTIONS.map((action) => (
                      <button
                        key={action.label}
                        className="btn btn-ghost"
                        type="button"
                        onClick={() => onApplyManualRating(action.value)}
                        disabled={manualSavePending}
                      >
                        {action.label}
                      </button>
                    ))}
                    <button className="btn btn-ghost" type="button" onClick={onClearManualRating} disabled={manualSavePending}>
                      Clear Manual Rating
                    </button>
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

function buildGmailWindowSettings(fetchSchedule) {
  return [
    {
      key: "yesterday",
      label: "Yesterday",
      fetchedAt: fetchSchedule?.yesterday?.last_run_at,
      runReason: fetchSchedule?.yesterday?.last_run_reason,
      schedule: "00:01 daily",
    },
    {
      key: "today",
      label: "Today",
      fetchedAt: fetchSchedule?.today?.last_run_at,
      runReason: fetchSchedule?.today?.last_run_reason,
      schedule: "00:00, 06:00, 12:00, 18:00",
    },
    {
      key: "last_hour",
      label: "Last Hour",
      fetchedAt: fetchSchedule?.last_hour?.last_run_at,
      runReason: fetchSchedule?.last_hour?.last_run_reason,
      schedule: "00, 05, 10, 15, ...",
    },
  ];
}

function scheduledTaskStatusTone(value) {
  if (value === "active") {
    return "success";
  }
  if (value === "pending") {
    return "warning";
  }
  return "neutral";
}

function schedulerStatusTone(value) {
  if (value === "completed") {
    return "success";
  }
  if (value === "running") {
    return "warning";
  }
  if (value === "error") {
    return "danger";
  }
  return "neutral";
}

function buildGmailLastHourPipelinePills(pipeline) {
  const stages = pipeline?.stages || {};
  const now = Date.now();
  const completedAt = pipeline?.last_completed_at ? new Date(pipeline.last_completed_at).getTime() : null;
  const completionExpired = completedAt !== null && !Number.isNaN(completedAt) && now - completedAt >= 10000;
  const normalizeStageStatus = (value) => {
    if (value === "failed") {
      return "error";
    }
    if (value === "running") {
      return "in_progress";
    }
    if (value === "completed" && completionExpired) {
      return "idle";
    }
    if (value === "completed") {
      return "completed";
    }
    return "idle";
  };
  return [
    { key: "fetch", label: "Fetch", value: normalizeStageStatus(stages.fetch?.status || "idle") },
    { key: "spamhaus", label: "Spamhaus", value: normalizeStageStatus(stages.spamhaus?.status || "idle") },
    { key: "local", label: "Local", value: normalizeStageStatus(stages.local_classification?.status || "idle") },
    { key: "ai", label: "AI", value: normalizeStageStatus(stages.ai_classification?.status || "idle") },
  ];
}

function pipelineStageClass(value) {
  if (value === "completed") {
    return "pipeline-pill pipeline-pill-completed";
  }
  if (value === "in_progress") {
    return "pipeline-pill pipeline-pill-in-progress";
  }
  if (value === "error") {
    return "pipeline-pill pipeline-pill-error";
  }
  return "pipeline-pill pipeline-pill-idle";
}

function telemetryFreshnessIndicatorClass(value) {
  return value === "fresh" ? "health-fresh" : "health-pending";
}

function deriveDashboardWarnings({ status, providerConnected, mqttConnected, mqttHealth }) {
  const warnings = [];

  if (status?.governance_sync_status && status.governance_sync_status !== "ok") {
    warnings.push(`Governance sync is ${status.governance_sync_status}.`);
  }
  if (!providerConnected) {
    warnings.push("Gmail provider is not connected.");
  }
  if (!mqttConnected) {
    warnings.push("MQTT is not currently connected.");
  }
  if (mqttHealth?.status_freshness_state && mqttHealth.status_freshness_state !== "fresh") {
    warnings.push(`Telemetry freshness is ${mqttHealth.status_freshness_state}.`);
  }

  return warnings;
}

function formatRelativeTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  const diffSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSeconds < 60) {
    return `${diffSeconds} sec ago`;
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} min ago`;
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)} hour ago`;
  }
  return `${Math.floor(diffSeconds / 86400)} day ago`;
}

function maskOnboardingRef(value) {
  if (!value) {
    return "pending";
  }
  if (value === "operational") {
    return value;
  }
  if (value.length <= 7) {
    return `**********${value}`;
  }
  return `**********${value.slice(-7)}`;
}

function deriveNodeState(bootstrap) {
  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];

  if (requiredInputs.length > 0) {
    return { label: "Configuration Required", tone: "warning" };
  }
  if (status?.trust_state === "trusted") {
    return { label: "Trusted", tone: "success" };
  }
  if (onboarding?.onboarding_status === "pending" && onboarding?.approval_url) {
    return { label: "Awaiting Approval", tone: "warning" };
  }
  if (onboarding?.onboarding_status === "pending") {
    return { label: "Registering", tone: "warning" };
  }
  if (onboarding?.onboarding_status === "approved") {
    return { label: "Trust Activating", tone: "warning" };
  }
  if (onboarding?.onboarding_status === "rejected") {
    return { label: "Rejected", tone: "danger" };
  }
  if (onboarding?.onboarding_status === "expired") {
    return { label: "Expired", tone: "danger" };
  }
  if (onboarding?.onboarding_status === "invalid" || onboarding?.onboarding_status === "consumed") {
    return { label: "Needs Recovery", tone: "danger" };
  }
  return { label: "Ready To Start", tone: "neutral" };
}

function isNodeSetupVisible(bootstrap) {
  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  return Boolean(
    onboarding?.session_id ||
      onboarding?.approval_url ||
      onboarding?.onboarding_status !== "not_started" ||
      status?.trust_state !== "untrusted",
  );
}

function deriveSetupFlow(bootstrap) {
  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];
  const coreConfigured = Boolean(bootstrap?.config?.core_base_url) && !requiredInputs.includes("core_base_url");
  const nodeNamed = Boolean(bootstrap?.config?.node_name) && !requiredInputs.includes("node_name");
  const trusted = status?.trust_state === "trusted";
  const providerSummary = status?.provider_account_summaries?.gmail || {};
  const providerConnected = providerSummary?.provider_state === "connected";
  const capabilityCurrent = status?.capability_declaration_status === "accepted";
  const governanceCurrent = status?.governance_sync_status === "ok";
  const ready = Boolean(status?.operational_readiness);
  const sessionCreated = Boolean(onboarding?.session_id);
  const approvalReady = Boolean(onboarding?.approval_url);
  const pendingApproval = onboarding?.onboarding_status === "pending";
  const inTrustActivation = onboarding?.onboarding_status === "approved" && !trusted;

  const steps = [
    {
      id: "node_identity",
      label: "Node Identity",
      complete: nodeNamed,
      current: !nodeNamed,
      description: nodeNamed ? bootstrap?.config?.node_name : "Set a node name to establish local identity.",
    },
    {
      id: "core_connection",
      label: "Core Connection",
      complete: coreConfigured,
      current: nodeNamed && !coreConfigured,
      description: coreConfigured ? bootstrap?.config?.core_base_url : "Set the Core base URL for registration.",
    },
    {
      id: "bootstrap_discovery",
      label: "Bootstrap Discovery",
      complete: sessionCreated || trusted,
      current: nodeNamed && coreConfigured && !sessionCreated && !trusted,
      description: sessionCreated || trusted ? "Bootstrap metadata resolved from the configured Core." : "Start onboarding to discover bootstrap metadata.",
    },
    {
      id: "registration",
      label: "Registration",
      complete: sessionCreated || trusted,
      current: sessionCreated && !approvalReady && !trusted,
      description: sessionCreated ? onboarding?.session_id : "Create a node onboarding session in Core.",
    },
    {
      id: "approval",
      label: "Approval",
      complete: trusted,
      current: pendingApproval,
      description: approvalReady ? "Awaiting operator approval in Core." : "Approval URL will appear here.",
    },
    {
      id: "trust_activation",
      label: "Trust Activation",
      complete: trusted,
      current: inTrustActivation && !ready,
      description: trusted ? `Trusted as ${status?.node_id || "this node"}` : "Finalize trust activation after approval.",
    },
    {
      id: "provider_setup",
      label: "Provider Setup",
      complete: providerConnected,
      current: trusted && !providerConnected,
      description: providerConnected ? "Gmail connected." : "Configure and connect Gmail once trust is active.",
    },
    {
      id: "capability_declaration",
      label: "Capability Declaration",
      complete: capabilityCurrent,
      current: providerConnected && !capabilityCurrent,
      description: capabilityCurrent ? "Capability declaration accepted." : "Waiting for accepted capability declaration.",
    },
    {
      id: "governance_sync",
      label: "Governance Sync",
      complete: governanceCurrent,
      current: capabilityCurrent && !governanceCurrent,
      description: governanceCurrent ? "Governance snapshot synced." : "Waiting for governance snapshot sync.",
    },
    {
      id: "ready",
      label: "Ready",
      complete: ready,
      current: governanceCurrent && !ready,
      description: ready ? "Node is operationally ready." : "Final readiness checks are still running.",
    },
  ];

  const current = steps.find((step) => step.current) || steps.find((step) => !step.complete) || steps[steps.length - 1];
  return { steps, current };
}

function StageCard({ title, tone, children, action }) {
  return (
    <article className={`card stack stage-card tone-${tone}`}>
      <div className="section-heading">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </article>
  );
}

function SetupSidebar({ flow }) {
  return (
    <aside className="card stack flow-sidebar">
      <div className="section-heading">
        <h2>Setup Flow</h2>
        <span className="pill">{flow.current?.label || "Idle"}</span>
      </div>
      <div className="flow-steps">
        {flow.steps.map((step, index) => {
          const state = step.complete ? "success" : step.current ? "warning" : "neutral";
          return (
            <div key={step.id} className={`flow-step is-${state}`}>
              {step.complete ? <span className="flow-step-check" aria-label="Completed">✓</span> : null}
              <div className="flow-step-index">{index + 1}</div>
              <div className="flow-step-body">
                <strong>{step.label}</strong>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

function renderCurrentStageCard({
  flow,
  bootstrap,
  status,
  onboarding,
  requiredInputs,
  notice,
  error,
  setView,
  form,
  saving,
  declaringCapabilities,
  onCapabilityToggle,
  onSaveConfiguration,
  onDeclareCapabilities,
}) {
  const stepId = flow.current?.id;
  const capabilitySetup = status?.capability_setup || {};
  const capabilitySelection = capabilitySetup?.task_capability_selection || {};
  const approvalLink = onboarding?.approval_url ? (
    <a className="approval-link" href={onboarding.approval_url} target="_blank" rel="noreferrer">
      Open approval URL
    </a>
  ) : null;

  if (stepId === "core_connection") {
    return (
      <StageCard title="Core Connection" tone="warning">
        <div className="callout callout-warning">
          {requiredInputs.includes("core_base_url")
            ? "Enter the Core base URL, then save or start onboarding."
            : "Core URL is configured and ready for bootstrap discovery."}
        </div>
      </StageCard>
    );
  }

  if (stepId === "bootstrap_discovery" || stepId === "registration") {
    return (
      <StageCard title="Registration" tone={statusTone(onboarding?.onboarding_status)}>
        <dl className="facts single-column-facts">
          <div>
            <dt>Session</dt>
            <dd>{onboarding?.session_id || "No session yet"}</dd>
          </div>
          <div>
            <dt>Approval URL</dt>
            <dd>{onboarding?.approval_url || "Will appear after session creation"}</dd>
          </div>
        </dl>
        {notice ? <div className="callout callout-success">{notice}</div> : null}
        {error ? <div className="callout callout-danger">{error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "approval") {
    return (
      <StageCard title="Approval" tone="warning" action={approvalLink}>
        <div className="callout">
          Open the Core approval URL and approve the node. Keep this page open while finalize polling continues.
        </div>
        {onboarding?.last_error ? <div className="callout callout-danger">{onboarding.last_error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "trust_activation") {
    return (
      <StageCard title="Trust Activation" tone={statusTone(status?.trust_state)}>
        <dl className="facts single-column-facts">
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
        </dl>
      </StageCard>
    );
  }

  if (stepId === "provider_setup") {
    return (
      <StageCard
        title="Provider Setup"
        tone={statusTone(status?.provider_account_summaries?.gmail?.provider_state)}
        action={
          <button className="btn btn-primary" type="button" onClick={() => setView("provider")}>
            Setup Provider
          </button>
        }
      >
        <div className="callout">
          Trust is active. Configure Gmail and complete the connect flow to move the node into provider-ready state.
        </div>
      </StageCard>
    );
  }

  if (stepId === "capability_declaration") {
    return (
      <StageCard
        title="Capability Declaration"
        tone={statusTone(status?.capability_declaration_status)}
        action={
          <div className="actions">
            <button className="btn btn-ghost" type="button" onClick={onSaveConfiguration} disabled={saving}>
              {saving ? "Saving..." : "Save Selection"}
            </button>
            <button className="btn btn-primary" type="button" onClick={onDeclareCapabilities} disabled={declaringCapabilities}>
              {declaringCapabilities ? "Declaring..." : "Declare Capabilities"}
            </button>
          </div>
        }
      >
        <div className="callout">
          Select the task families this node should declare to Core once Gmail is connected.
        </div>
        <div className="capability-list">
          {TASK_CAPABILITY_OPTIONS.map((capability) => {
            const selected = form.selected_task_capabilities.includes(capability);
            return (
              <button
                key={capability}
                className={`capability-option ${selected ? "is-selected" : ""}`}
                type="button"
                onClick={() => onCapabilityToggle(capability)}
              >
                <span className="capability-check">{selected ? "✓" : ""}</span>
                <span className="capability-copy">
                  <strong>{capability}</strong>
                </span>
              </button>
            );
          })}
        </div>
        <div className="callout">
          Capability declaration status: {status?.capability_declaration_status || "pending"}.
          {" "}
          Selected: {capabilitySelection.selected_count ?? form.selected_task_capabilities.length}.
        </div>
        {(capabilitySetup?.blocking_reasons || []).length > 0 ? (
          <ul className="prompt-list">
            {capabilitySetup.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
        {notice ? <div className="callout callout-success">{notice}</div> : null}
        {error ? <div className="callout callout-danger">{error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "governance_sync") {
    return (
      <StageCard title="Governance Sync" tone={statusTone(status?.governance_sync_status)}>
        <div className="callout">Governance sync status: {status?.governance_sync_status || "pending"}.</div>
      </StageCard>
    );
  }

  if (stepId === "ready") {
    return (
      <StageCard title="Ready" tone={boolTone(status?.operational_readiness)}>
        <div className="callout callout-success">
          The node is fully ready. Gmail is connected, capability declaration is current, and governance sync is healthy.
        </div>
      </StageCard>
    );
  }

  return (
    <StageCard title="Node Identity" tone={requiredInputs.length > 0 ? "warning" : "success"}>
      <div className="callout">
        Set the local node name and keep this workstation open during the rest of the setup flow.
      </div>
      {notice ? <div className="callout callout-success">{notice}</div> : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
    </StageCard>
  );
}

function normalizeProviderForm(config) {
  return {
    enabled: Boolean(config?.enabled),
    oauth_client_type: config?.oauth_client_type || "web",
    client_id: config?.client_id || "",
    client_secret_ref: config?.client_secret_ref || "",
    redirect_uri: config?.redirect_uri || "",
    requested_scopes: (config?.requested_scopes?.scopes || []).join("\n") || EMPTY_PROVIDER_FORM.requested_scopes,
  };
}

function buildProviderPayload(form) {
  return {
    enabled: form.enabled,
    oauth_client_type: "web",
    client_id: form.client_id.trim() || null,
    client_secret_ref: form.client_secret_ref.trim() || null,
    redirect_uri: form.redirect_uri.trim() || null,
    requested_scopes: {
      scopes: form.requested_scopes
        .split("\n")
        .map((scope) => scope.trim())
        .filter(Boolean),
    },
  };
}

function Field({ label, name, value, onChange, placeholder, required }) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        className="form-input"
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
      />
    </label>
  );
}

function ToggleField({ label, name, checked, onChange }) {
  return (
    <label className="toggle-field">
      <span className="field-label">{label}</span>
      <button
        className={`toggle ${checked ? "is-on" : ""}`}
        type="button"
        onClick={() => onChange({ target: { name, type: "checkbox", checked: !checked } })}
      >
        <span className="toggle-thumb" />
        <span>{checked ? "Enabled" : "Disabled"}</span>
      </button>
    </label>
  );
}

function TextareaField({ label, name, value, onChange, placeholder }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <textarea
        className="form-input form-textarea"
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={5}
      />
    </label>
  );
}

function TrainingPage({
  trainingStatus,
  trainingLoading,
  trainingError,
  trainingBatch,
  trainingBatchLoading,
  trainingBatchError,
  trainingSavePending,
  trainingModelPending,
  trainingNotice,
  trainingSelections,
  onBack,
  onOpenSenderReputation,
  onLoadClassifiedLabelBatch,
  onLoadManualBatch,
  onLoadSemiAutoBatch,
  onLoadSemiAutoBatch300,
  onTrainModel,
  onTrainHighConfidenceModel,
  onSelectionChange,
  onSaveBatch,
}) {
  const [trainingPage, setTrainingPage] = useState(0);
  const items = trainingBatch?.items || [];
  const pageSize = 5;
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(trainingPage, pageCount - 1);
  const pageStart = currentPage * pageSize;
  const visibleItems = items.slice(pageStart, pageStart + pageSize);

  useEffect(() => {
    setTrainingPage(0);
  }, [trainingBatch?.count]);

  return (
    <main className="app-frame">
      <section className="hero card">
        <div>
          <div className="hero-topline">
            <div className="eyebrow">Hexe Email Node</div>
            <div className="status-pill tone-warning">gmail: training</div>
          </div>
          <h1>Training</h1>
          <p className="hero-copy">
            Review flattened local mail and apply manual labels for future local classification work.
          </p>
        </div>
      </section>

      <section className="app-shell">
        <aside className="card stack flow-sidebar">
          <div className="section-heading">
            <h2>Training</h2>
            <span className="pill">{trainingBatch?.count ?? 0} mails</span>
          </div>
          <div className="stack compact-stack">
            <button className="btn btn-ghost" type="button" onClick={onBack}>
              Back To Dashboard
            </button>
            <button className="btn btn-primary" type="button" onClick={onLoadManualBatch} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Manual Classify"}
            </button>
            <button className="btn" type="button" onClick={onTrainModel} disabled={trainingModelPending}>
              {trainingModelPending ? "Training..." : "Train Model"}
            </button>
            <button className="btn" type="button" onClick={onTrainHighConfidenceModel} disabled={trainingModelPending}>
              {trainingModelPending ? "Training..." : "Train 92%+"}
            </button>
            <button className="btn" type="button" onClick={onLoadSemiAutoBatch} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Semi Auto Classify"}
            </button>
            <button className="btn" type="button" onClick={onLoadSemiAutoBatch300} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Semi Auto 300"}
            </button>
            <button className="btn" type="button" onClick={onOpenSenderReputation}>
              Show Sender Reputation
            </button>
            <div className="callout">
              Threshold: {trainingStatus?.threshold ?? 0.6}
            </div>
            <div className="callout">
              Classified: {trainingStatus?.classification_summary?.classified_count ?? 0}
            </div>
            <div className="callout">
              Manual Labels: {trainingStatus?.classification_summary?.manual_count ?? 0}
            </div>
            <div className="callout">
              High Confidence: {trainingStatus?.classification_summary?.high_confidence_count ?? 0}
            </div>
            <div className="callout">
              Model: {trainingStatus?.model_status?.trained
                ? `trained (${trainingStatus?.model_status?.train_count ?? 0} train / ${trainingStatus?.model_status?.test_count ?? 0} test)`
                : "not trained"}
            </div>
            {trainingStatus?.classification_summary?.per_label
              ? (
                <div className="training-sidebar-stats">
                  {Object.entries(trainingStatus.classification_summary.per_label).map(([label, count]) => (
                    <div key={label} className="training-sidebar-stat">
                      <button className="btn btn-ghost" type="button" onClick={() => onLoadClassifiedLabelBatch(label)}>
                        {label}
                      </button>
                      <strong>{count}</strong>
                    </div>
                  ))}
                </div>
                )
              : null}
            {trainingLoading ? <div className="callout">Loading training status...</div> : null}
            {trainingError ? <div className="callout callout-danger">{trainingError}</div> : null}
            {trainingBatchError ? <div className="callout callout-danger">{trainingBatchError}</div> : null}
            {trainingNotice ? <div className="callout callout-success">{trainingNotice}</div> : null}
          </div>
        </aside>

        <div className="main-column">
          <article className="card stack">
            <div className="card-header">
              <h2>Manual Classification</h2>
              <p className="muted">
                {trainingModelPending
                  ? "Training in progress..."
                  : trainingBatch?.source === "classified_label"
                    ? `Showing stored mails already classified as ${trainingBatch?.selected_label || "selected"}`
                  : trainingBatch?.source === "semi_auto"
                    ? "Oldest unclassified mails are pre-labeled by the local model and shown here for review."
                    : "Random unknown or low-confidence mails are flattened into a consistent training format for local review."}
              </p>
            </div>
            {!trainingBatch?.items?.length ? (
              <div className="callout">
                Use <code>Manual Classify</code> to load up to 40 local emails for review.
              </div>
            ) : (
              <>
                <div className="actions">
                  <button className="btn btn-primary" type="button" onClick={onSaveBatch} disabled={trainingSavePending}>
                    {trainingSavePending ? "Saving..." : "Save Manual Labels"}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.max(page - 1, 0))}
                    disabled={currentPage === 0}
                  >
                    Previous 5
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.min(page + 1, pageCount - 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next 5
                  </button>
                  <span className="muted tiny training-page-meta">
                    Showing {pageStart + 1}-{Math.min(pageStart + visibleItems.length, items.length)} of {items.length}
                  </span>
                </div>
                <div className="training-list">
                  {visibleItems.map((item) => {
                    const selected = trainingSelections[item.message_id] || {
                      label: item.selected_label || item.predicted_label || item.local_label || "unknown",
                      confidence: item.predicted_confidence ?? item.local_label_confidence ?? trainingStatus?.threshold ?? 0.6,
                    };
                    return (
                      <section key={item.message_id} className="training-item">
                        <div className="training-item-top">
                          <div>
                            <strong>{item.subject || "(no subject)"}</strong>
                            <div className="muted tiny">{item.sender_email || "-"}</div>
                          </div>
                          <span className="pill">{item.message_id}</span>
                        </div>
                        {trainingBatch?.source === "semi_auto" && (item.predicted_label || item.raw_predicted_label) ? (
                          <div className="callout">
                            Model Prediction: {item.predicted_label || "unknown"} ({Number(item.predicted_confidence || 0).toFixed(2)})
                            {item.predicted_label === "unknown" && item.raw_predicted_label ? `, top guess was ${item.raw_predicted_label}` : ""}
                          </div>
                        ) : null}
                        <pre className="training-flat-text">{item.raw_text || item.flat_text}</pre>
                        <div className="training-controls">
                          <label className="field">
                            <span className="field-label">Label</span>
                            <select
                              name="label"
                              value={selected.label}
                              onChange={(event) => onSelectionChange(item.message_id, "label", event.target.value)}
                            >
                              {TRAINING_LABEL_OPTIONS.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span className="field-label">Confidence</span>
                            <input
                              type="number"
                              min="0"
                              max="1"
                              step="0.05"
                              value={selected.confidence}
                              onChange={(event) => onSelectionChange(item.message_id, "confidence", event.target.value)}
                            />
                          </label>
                        </div>
                      </section>
                    );
                  })}
                </div>
                <div className="actions">
                  <button className="btn btn-primary" type="button" onClick={onSaveBatch} disabled={trainingSavePending}>
                    {trainingSavePending ? "Saving..." : "Save Manual Labels"}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.max(page - 1, 0))}
                    disabled={currentPage === 0}
                  >
                    Previous 5
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.min(page + 1, pageCount - 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next 5
                  </button>
                  <span className="muted tiny training-page-meta">
                    Showing {pageStart + 1}-{Math.min(pageStart + visibleItems.length, items.length)} of {items.length}
                  </span>
                </div>
              </>
            )}
          </article>
        </div>
      </section>
    </main>
  );
}

function ProviderSetupPage({
  bootstrap,
  providerConfig,
  providerStatus,
  gmailStatus,
  providerForm,
  providerDirty,
  providerLoading,
  providerSaving,
  providerValidating,
  providerConnecting,
  providerNotice,
  providerError,
  connectUrl,
  onProviderChange,
  onRefresh,
  onSave,
  onValidate,
  onConnect,
  onBack,
}) {
  const providerSummary = providerStatus?.provider_account_summaries?.gmail || {};
  const providerHealth = providerSummary?.health || null;
  const providerAccounts = providerSummary?.accounts || [];
  const primaryAccount = providerAccounts[0] || null;
  const primaryStatus = gmailStatus?.accounts?.[0] || null;
  const validation = providerConfig?.validation || null;
  const providerReadyReasons = [];
  if (bootstrap?.status?.trust_state !== "trusted") {
    providerReadyReasons.push("node trust is not active");
  }
  if (!providerSummary?.configured) {
    providerReadyReasons.push("Gmail config is not valid yet");
  }
  if (!providerForm.enabled) {
    providerReadyReasons.push("provider is disabled");
  }
  const canConnect = providerReadyReasons.length === 0 && !providerConnecting;
  return (
    <main className="app-frame">
      <section className="hero card">
        <div>
          <div className="hero-topline">
            <div className="eyebrow">Hexe Email Node</div>
            <div className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
              gmail: {providerSummary?.provider_state || "loading"}
            </div>
          </div>
          <h1>Gmail</h1>
          <p className="hero-copy">
            Gmail management will live here. This view is being staged into dedicated Gmail status, settings, and action cards.
          </p>
        </div>
        <div className="hero-actions">
          <button className="btn btn-ghost" type="button" onClick={onRefresh} disabled={providerLoading}>
            {providerLoading ? "Refreshing..." : "Refresh"}
          </button>
          <button className="btn btn-ghost" type="button" onClick={onBack}>
            Back To Console
          </button>
        </div>
      </section>

      <section className="grid provider-grid">
        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Status</h2>
            <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
          </div>
          <dl className="facts single-column-facts">
            <div>
              <dt>Provider State</dt>
              <dd>{providerSummary?.provider_state || "pending"}</dd>
            </div>
            <div>
              <dt>Configured</dt>
              <dd>{providerSummary?.configured ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Enabled</dt>
              <dd>{providerConfig?.config?.enabled ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Primary Account</dt>
              <dd>{primaryAccount?.email_address || primaryAccount?.account_id || "not connected"}</dd>
            </div>
            <div>
              <dt>Health</dt>
              <dd>{providerHealth?.status || "unknown"}</dd>
            </div>
            <div>
              <dt>Redirect URI</dt>
              <dd>{providerConfig?.config?.redirect_uri || "not set"}</dd>
            </div>
          </dl>
          {primaryStatus?.labels?.labels?.length ? (
            <div className="stack">
              <div className="section-heading">
                <h3>Available Labels</h3>
                <span className="pill">{primaryStatus.labels.labels.length}</span>
              </div>
              <div className="training-sidebar-stats">
                {primaryStatus.labels.labels.map((label) => (
                  <div key={label.id} className="training-sidebar-stat">
                    <span>{label.name}</span>
                    <span className="muted tiny">{label.id}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {providerNotice ? <div className="callout callout-success">{providerNotice}</div> : null}
          {providerError ? <div className="callout callout-danger">{providerError}</div> : null}
        </article>

        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Settings</h2>
            <span className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
              {providerSummary?.provider_state || "unknown"}
            </span>
          </div>
          <ToggleField
            label="Provider Enabled"
            name="enabled"
            checked={providerForm.enabled}
            onChange={onProviderChange}
          />
          <Field
            label="Client ID"
            name="client_id"
            value={providerForm.client_id}
            onChange={onProviderChange}
            placeholder="Google OAuth client id"
            required
          />
          <Field
            label="Client Secret Ref"
            name="client_secret_ref"
            value={providerForm.client_secret_ref}
            onChange={onProviderChange}
            placeholder="env:GMAIL_CLIENT_SECRET"
            required
          />
          <Field
            label="Redirect URI"
            name="redirect_uri"
            value={providerForm.redirect_uri}
            onChange={onProviderChange}
            placeholder="https://your-domain/google/callback"
            required
          />
          <TextareaField
            label="Requested Scopes"
            name="requested_scopes"
            value={providerForm.requested_scopes}
            onChange={onProviderChange}
            placeholder="One scope per line"
          />
          <div className="actions">
            <button className="btn btn-ghost" type="button" onClick={onValidate} disabled={providerValidating}>
              {providerValidating ? "Validating..." : "Validate"}
            </button>
            <button className="btn btn-primary" type="button" onClick={onSave} disabled={providerSaving}>
              {providerSaving ? "Saving..." : "Save Gmail Config"}
            </button>
          </div>
          {validation ? (
            <div className={`callout ${validation.ok ? "callout-success" : "callout-warning"}`}>
              {validation.ok
                ? "Configuration looks valid."
                : `Missing required fields: ${(validation.missing_fields || []).join(", ") || "unknown"}.`}
            </div>
          ) : null}
        </article>

        <article className="card stack">
          <div className="section-heading">
            <h2>Gmail Action</h2>
            <span className="pill">{canConnect ? "ready" : "waiting"}</span>
          </div>
          <div className="callout">
            Create the Gmail authorization link here, then open it to approve access in Google.
          </div>
          {!canConnect ? (
            <div className="callout callout-warning">
              Auth link is not ready yet: {providerReadyReasons.join(", ")}.
            </div>
          ) : null}
          <div className="actions">
            <button className="btn btn-primary" type="button" onClick={onConnect} disabled={!canConnect}>
              {providerConnecting ? "Creating..." : "Create Auth Link"}
            </button>
          </div>
          {connectUrl ? (
            <div className="stack compact-stack">
              <div className="callout callout-success">Auth link created. Open it to continue Gmail authorization.</div>
              <a className="approval-link" href={connectUrl} target="_blank" rel="noreferrer">
                Open Gmail Auth Link
              </a>
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}

export function App() {
  const initialRoute = parseHashRoute(typeof window !== "undefined" ? window.location.hash : "");
  const [view, setView] = useState(initialRoute.view);
  const [dashboardSection, setDashboardSection] = useState(initialRoute.dashboardSection);
  const [setupPinned, setSetupPinned] = useState(false);
  const [bootstrap, setBootstrap] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [declaringCapabilities, setDeclaringCapabilities] = useState(false);
  const [starting, setStarting] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const [providerConfig, setProviderConfig] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [providerForm, setProviderForm] = useState(EMPTY_PROVIDER_FORM);
  const [providerDirty, setProviderDirty] = useState(false);
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerSaving, setProviderSaving] = useState(false);
  const [providerValidating, setProviderValidating] = useState(false);
  const [providerConnecting, setProviderConnecting] = useState(false);
  const [providerNotice, setProviderNotice] = useState("");
  const [providerError, setProviderError] = useState("");
  const [connectUrl, setConnectUrl] = useState("");
  const [runtimeTaskForm, setRuntimeTaskForm] = useState(EMPTY_RUNTIME_TASK_FORM);
  const [runtimeTaskPending, setRuntimeTaskPending] = useState("");
  const [runtimeTaskError, setRuntimeTaskError] = useState("");
  const [runtimeTaskNotice, setRuntimeTaskNotice] = useState("");
  const [runtimeTaskStatus, setRuntimeTaskStatus] = useState(EMPTY_RUNTIME_TASK_STATUS);
  const [gmailStatus, setGmailStatus] = useState(null);
  const [gmailStatusLoading, setGmailStatusLoading] = useState(false);
  const [gmailStatusError, setGmailStatusError] = useState("");
  const [gmailActionPending, setGmailActionPending] = useState("");
  const [gmailActionNotice, setGmailActionNotice] = useState("");
  const [gmailActionError, setGmailActionError] = useState("");
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [trainingError, setTrainingError] = useState("");
  const [senderReputationSummary, setSenderReputationSummary] = useState(null);
  const [senderReputationSummaryLoading, setSenderReputationSummaryLoading] = useState(false);
  const [senderReputationSummaryError, setSenderReputationSummaryError] = useState("");
  const [trainingBatch, setTrainingBatch] = useState(null);
  const [trainingBatchLoading, setTrainingBatchLoading] = useState(false);
  const [trainingBatchError, setTrainingBatchError] = useState("");
  const [trainingSavePending, setTrainingSavePending] = useState(false);
  const [trainingModelPending, setTrainingModelPending] = useState(false);
  const [trainingNotice, setTrainingNotice] = useState("");
  const [trainingSelections, setTrainingSelections] = useState({});
  const [senderReputationDetail, setSenderReputationDetail] = useState(null);
  const [senderReputationLoading, setSenderReputationLoading] = useState(false);
  const [senderReputationError, setSenderReputationError] = useState("");
  const [senderReputationNotice, setSenderReputationNotice] = useState("");
  const [senderReputationFilter, setSenderReputationFilter] = useState("all");
  const [senderReputationCollapsedGroups, setSenderReputationCollapsedGroups] = useState({});
  const [senderReputationManualNote, setSenderReputationManualNote] = useState("");
  const [senderReputationManualSavePending, setSenderReputationManualSavePending] = useState(false);
  const [copyNotice, setCopyNotice] = useState("");
  const [serviceControlPending, setServiceControlPending] = useState("");
  const [serviceControlNotice, setServiceControlNotice] = useState("");
  const [serviceControlError, setServiceControlError] = useState("");
  const [uiUpdatedAt, setUiUpdatedAt] = useState(null);
  const [backendReachable, setBackendReachable] = useState(true);
  const [retryingBackend, setRetryingBackend] = useState(false);

  async function loadBootstrap({ fromRetry = false } = {}) {
    try {
      const payload = await fetchJson("/api/node/bootstrap");

      startTransition(() => {
        setBootstrap(payload);
        setProviderStatus(payload.status);
        setRuntimeTaskStatus((current) =>
          runtimeTaskStateHasContent(payload.runtime_task_state)
            ? { ...EMPTY_RUNTIME_TASK_STATUS, ...(payload.runtime_task_state || {}) }
            : current,
        );
        setUiUpdatedAt(new Date().toISOString());
        setBackendReachable(true);
      });

      if (!touched) {
        setForm({
          core_base_url: payload.config.core_base_url || "",
          node_name: payload.config.node_name || "",
          selected_task_capabilities: payload.config.selected_task_capabilities || [],
        });
      }

      setError("");
    } catch (fetchError) {
      setBackendReachable(false);
      setUiUpdatedAt(new Date().toISOString());
      setError(fetchError.message);
      if (!fromRetry) {
        setBootstrap(null);
      }
      throw fetchError;
    } finally {
      if (fromRetry) {
        setRetryingBackend(false);
      }
    }
  }

  useEffect(() => {
    function applyHashRoute() {
      const route = parseHashRoute(window.location.hash);
      setView(route.view);
      setDashboardSection(route.dashboardSection);
      setSetupPinned(route.view === "setup");
    }

    applyHashRoute();
    window.addEventListener("hashchange", applyHashRoute);
    return () => {
      window.removeEventListener("hashchange", applyHashRoute);
    };
  }, []);

  useEffect(() => {
    const nextHash = buildHashRoute(view, dashboardSection);
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
    }
  }, [view, dashboardSection]);

  useEffect(() => {
    let active = true;

    async function loadBootstrapActive() {
      try {
        await loadBootstrap();
      } catch {
        if (!active) {
          return;
        }
      }
    }

    loadBootstrapActive();
    const intervalId = window.setInterval(loadBootstrapActive, 2000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [touched]);

  async function retryBackendConnection() {
    if (retryingBackend) {
      return;
    }
    setRetryingBackend(true);
    try {
      await loadBootstrap({ fromRetry: true });
    } catch {
      return;
    }
  }

  useEffect(() => {
    if (view !== "provider") {
      return undefined;
    }

    let active = true;

    async function loadProviderConfig() {
      setProviderLoading(true);
      try {
      const [configPayload, statusPayload] = await Promise.all([
          fetchJson("/providers/gmail/config"),
          fetchJson("/providers"),
        ]);
        if (!active) {
          return;
        }
        startTransition(() => {
          setProviderConfig(configPayload);
          setProviderStatus(statusPayload);
        });
        if (!providerDirty) {
          setProviderForm(normalizeProviderForm(configPayload.config));
        }
      } catch (loadError) {
        if (!active) {
          return;
        }
        setProviderError(loadError.message);
      } finally {
        if (active) {
          setProviderLoading(false);
        }
      }
    }

    loadProviderConfig();
    const intervalId = window.setInterval(loadProviderConfig, 4000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [view, providerDirty]);

  useEffect(() => {
    if (!((view === "dashboard" && dashboardSection === "gmail") || view === "provider")) {
      return undefined;
    }

    let active = true;

    async function loadGmailStatus() {
      setGmailStatusLoading(true);
      try {
        const payload = await fetchJson("/api/gmail/status");
        if (!active) {
          return;
        }
        setGmailStatus(payload);
        setGmailStatusError("");
      } catch (loadError) {
        if (!active) {
          return;
        }
        setGmailStatusError(loadError.message);
      } finally {
        if (active) {
          setGmailStatusLoading(false);
        }
      }
    }

    loadGmailStatus();
    const intervalId = window.setInterval(loadGmailStatus, 10000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [view, dashboardSection]);

  useEffect(() => {
    if (view !== "training") {
      return undefined;
    }

    let active = true;

    async function loadTrainingStatus() {
      setTrainingLoading(true);
      try {
        const payload = await fetchJson("/api/gmail/training");
        if (!active) {
          return;
        }
        setTrainingStatus(payload);
        setTrainingError("");
      } catch (loadError) {
        if (!active) {
          return;
        }
        setTrainingError(loadError.message);
      } finally {
        if (active) {
          setTrainingLoading(false);
        }
      }
    }

    loadTrainingStatus();
    return () => {
      active = false;
    };
  }, [view]);

  useEffect(() => {
    if (view !== "training_reputation") {
      return undefined;
    }

    let active = true;

    async function loadSenderReputationSummary() {
      setSenderReputationSummaryLoading(true);
      try {
        const payload = await fetchJson("/api/gmail/reputation?limit=100");
        if (!active) {
          return;
        }
        setSenderReputationSummary(payload);
        setSenderReputationSummaryError("");
        setSenderReputationNotice("");
        setSenderReputationCollapsedGroups((current) => {
          const next = { ...current };
          for (const record of payload.records || []) {
            const key = record.group_domain || record.sender_domain || record.sender_value || "unknown";
            if (!(key in next)) {
              next[key] = false;
            }
          }
          return next;
        });
      } catch (loadError) {
        if (!active) {
          return;
        }
        setSenderReputationSummaryError(loadError.message);
      } finally {
        if (active) {
          setSenderReputationSummaryLoading(false);
        }
      }
    }

    loadSenderReputationSummary();
    return () => {
      active = false;
    };
  }, [view]);

  useEffect(() => {
    const dashboardReady = Boolean(bootstrap?.status?.operational_readiness);
    if (view === "provider") {
      return;
    }
    if (dashboardReady && view === "setup" && !setupPinned) {
      setView("dashboard");
      return;
    }
    if (!dashboardReady && view === "dashboard") {
      setView("setup");
    }
  }, [bootstrap?.status?.operational_readiness, setupPinned, view]);

  function openSetup() {
    setSetupPinned(true);
    setView("setup");
  }

  function openDashboard(section = "overview") {
    setSetupPinned(false);
    setDashboardSection(DASHBOARD_SECTIONS.has(section) ? section : "overview");
    setView("dashboard");
  }

  function openProvider() {
    setSetupPinned(false);
    setView("provider");
  }

  function openTraining() {
    setSetupPinned(false);
    setView("training");
  }

  function handleRuntimeTaskFormChange(event) {
    const { name, value } = event.target;
    setRuntimeTaskForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function buildRuntimePreviewPayload() {
    return {
      task_family: runtimeTaskForm.task_family,
      requested_node_type: runtimeTaskForm.requested_node_type,
      requested_provider: runtimeTaskForm.preferred_provider,
      inputs: {
        content_type: runtimeTaskForm.content_type,
      },
      constraints: {},
    };
  }

  function buildRuntimeResolvePayload() {
    return {
      task_family: runtimeTaskForm.task_family,
      type: runtimeTaskForm.requested_node_type,
      task_context: {
        content_type: runtimeTaskForm.content_type,
      },
      preferred_provider: runtimeTaskForm.preferred_provider,
    };
  }

  function buildRuntimeAuthorizePayload(resolvePayload) {
    const selectedServiceId =
      runtimeTaskForm.service_id ||
      resolvePayload?.selected_service_id ||
      resolvePayload?.service_id ||
      runtimeTaskStatus?.resolve_response?.selected_service_id ||
      runtimeTaskStatus?.resolve_response?.service_id ||
      "";
    const selectedProvider =
      resolvePayload?.provider || runtimeTaskStatus?.resolve_response?.provider || runtimeTaskForm.preferred_provider;
    const selectedModel =
      resolvePayload?.model_id || runtimeTaskStatus?.resolve_response?.model_id || runtimeTaskForm.preferred_model;
    return {
      task_family: runtimeTaskForm.task_family,
      type: runtimeTaskForm.requested_node_type,
      task_context: {
        content_type: runtimeTaskForm.content_type,
      },
      service_id: selectedServiceId,
      provider: selectedProvider,
      ...(selectedModel ? { model_id: selectedModel } : {}),
    };
  }

  function buildRuntimeExecutionPayload() {
    const authorizePayload = runtimeTaskStatus?.authorize_response || {};
    const resolvedPayload = runtimeTaskStatus?.resolve_response || {};
    const resolvedCandidate =
      Array.isArray(resolvedPayload?.candidates) && resolvedPayload.candidates.length > 0 ? resolvedPayload.candidates[0] : null;
    return {
      task_family: runtimeTaskForm.task_family,
      target_api_base_url:
        runtimeTaskForm.target_api_base_url ||
        authorizePayload?.resolution?.provider_api_base_url ||
        resolvedCandidate?.provider_api_base_url ||
        "http://127.0.0.1:9002",
      service_token: authorizePayload.token || "",
      grant_id: authorizePayload.grant_id || "",
      service_id:
        runtimeTaskForm.service_id ||
        authorizePayload.service_id ||
        authorizePayload?.resolution?.service_id ||
        resolvedPayload.selected_service_id ||
        resolvedPayload.service_id ||
        "",
      provider: authorizePayload.provider || resolvedPayload.provider || runtimeTaskForm.preferred_provider,
      ...(authorizePayload.model_id || runtimeTaskForm.preferred_model
        ? { model_id: authorizePayload.model_id || runtimeTaskForm.preferred_model }
        : {}),
      content_type: runtimeTaskForm.content_type,
      subject: runtimeTaskForm.email_subject,
      body: runtimeTaskForm.email_body,
    };
  }

  async function runRuntimePreview() {
    const now = new Date().toISOString();
    setRuntimeTaskPending("preview");
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus((current) => ({
      ...current,
      request_status: "running",
      last_step: "preview",
      started_at: current.started_at || now,
      updated_at: now,
      detail: "Previewing task routing...",
    }));
    try {
      const payload = await fetchJson("/api/tasks/routing/preview", {
        method: "POST",
        body: JSON.stringify(buildRuntimePreviewPayload()),
      });
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "previewed",
        last_step: "preview",
        detail: payload.detail || "Routing preview completed.",
        preview_response: payload,
        updated_at: new Date().toISOString(),
      }));
      setRuntimeTaskNotice("Routing preview completed.");
      return payload;
    } catch (taskError) {
      setRuntimeTaskError(taskError.message);
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "failed",
        last_step: "preview",
        detail: taskError.message,
        updated_at: new Date().toISOString(),
      }));
      throw taskError;
    } finally {
      setRuntimeTaskPending("");
    }
  }

  async function runRuntimeResolve() {
    const now = new Date().toISOString();
    setRuntimeTaskPending("resolve");
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus((current) => ({
      ...current,
      request_status: "running",
      last_step: "resolve",
      started_at: current.started_at || now,
      updated_at: now,
      detail: "Resolving service through Core...",
    }));
    try {
      const payload = await fetchJson("/api/core/services/resolve", {
        method: "POST",
        body: JSON.stringify(buildRuntimeResolvePayload()),
      });
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "resolved",
        last_step: "resolve",
        detail: `Resolved ${payload.selected_service_id || payload.service_id || "service"} for ${payload.task_family || runtimeTaskForm.task_family}.`,
        resolve_response: payload,
        updated_at: new Date().toISOString(),
      }));
      setRuntimeTaskNotice("Core resolve completed.");
      return payload;
    } catch (taskError) {
      setRuntimeTaskError(taskError.message);
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "failed",
        last_step: "resolve",
        detail: taskError.message,
        updated_at: new Date().toISOString(),
      }));
      throw taskError;
    } finally {
      setRuntimeTaskPending("");
    }
  }

  async function runRuntimeAuthorize(resolvePayload = null) {
    const now = new Date().toISOString();
    setRuntimeTaskPending("authorize");
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus((current) => ({
      ...current,
      request_status: "running",
      last_step: "authorize",
      started_at: current.started_at || now,
      updated_at: now,
      detail: "Authorizing service through Core...",
    }));
    try {
      const payload = await fetchJson("/api/core/services/authorize", {
        method: "POST",
        body: JSON.stringify(buildRuntimeAuthorizePayload(resolvePayload)),
      });
      const authorized = runtimeAuthorizationGranted(payload);
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: authorized ? "authorized" : "rejected",
        last_step: "authorize",
        detail: authorized
          ? `Authorized ${payload.service_id || "service"} with ${payload.provider || runtimeTaskForm.preferred_provider}${payload.model_id ? `/${payload.model_id}` : ""}.`
          : "Core did not authorize the requested service.",
        authorize_response: payload,
        updated_at: new Date().toISOString(),
      }));
      setRuntimeTaskNotice(authorized ? "Core authorize completed." : "Core authorize was not granted.");
      return payload;
    } catch (taskError) {
      setRuntimeTaskError(taskError.message);
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "failed",
        last_step: "authorize",
        detail: taskError.message,
        updated_at: new Date().toISOString(),
      }));
      throw taskError;
    } finally {
      setRuntimeTaskPending("");
    }
  }

  async function runRuntimeResolveFlow() {
    const now = new Date().toISOString();
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus({
      request_status: "running",
      last_step: "start",
      detail: "Starting runtime resolve flow...",
      preview_response: null,
      resolve_response: null,
      authorize_response: null,
      started_at: now,
      updated_at: now,
    });
    try {
      await runRuntimePreview();
      await runRuntimeResolve();
      setRuntimeTaskNotice("Runtime resolve flow completed.");
    } catch {
      // Step handlers already set status and error.
    }
  }

  async function runRuntimeRegisterPrompt() {
    const now = new Date().toISOString();
    setRuntimeTaskPending("register");
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus((current) => ({
      ...current,
      request_status: "running",
      last_step: "register",
      started_at: current.started_at || now,
      updated_at: now,
      detail: "Syncing prompt JSON files with the AI node prompt service...",
      registration_request_payload: null,
    }));
    try {
      const payload = await fetchJson("/api/runtime/prompts/sync", {
        method: "POST",
        body: JSON.stringify({
          target_api_base_url: runtimeTaskForm.target_api_base_url,
        }),
      });
      const syncActions = Array.isArray(payload.sync_actions) ? payload.sync_actions : [];
      const registeredCount = syncActions.filter((item) => item.action === "registered").length;
      const replacedCount = syncActions.filter((item) => item.action === "replaced").length;
      const unchangedCount = syncActions.filter((item) => item.action === "unchanged").length;
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "registered",
        last_step: "register",
        detail: `Prompt sync completed: ${registeredCount} registered, ${replacedCount} replaced, ${unchangedCount} unchanged.`,
        registration_request_payload: payload.request_payload || null,
        execution_response: {
          registrations: payload.registrations || [],
          retirements: payload.retirements || [],
          sync_actions: syncActions,
        },
        usage_summary_response: payload.usage_summary || null,
        updated_at: new Date().toISOString(),
      }));
      setRuntimeTaskNotice("Prompt sync completed.");
      return payload;
    } catch (taskError) {
      setRuntimeTaskError(taskError.message);
      const serverDetail = taskError.serverPayload?.detail;
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "failed",
        last_step: "register",
        detail: taskError.message,
        registration_request_payload:
          (serverDetail && typeof serverDetail === "object" && serverDetail.request_payload) ||
          current.registration_request_payload,
        execution_response:
          (serverDetail && typeof serverDetail === "object" && serverDetail.response_payload) ||
          current.execution_response,
        updated_at: new Date().toISOString(),
      }));
      throw taskError;
    } finally {
      setRuntimeTaskPending("");
    }
  }

  async function runRuntimeExecuteEmailClassifier() {
    const now = new Date().toISOString();
    setRuntimeTaskPending("execute");
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus((current) => ({
      ...current,
      request_status: "running",
      last_step: "execute",
      started_at: current.started_at || now,
      updated_at: now,
      detail: "Sending the newest unknown Gmail message to prompt.email.classifier on the AI node...",
    }));
    try {
      const payload = await fetchJson("/api/runtime/execute-email-classifier", {
        method: "POST",
        body: JSON.stringify({
          target_api_base_url: runtimeTaskForm.target_api_base_url,
        }),
      });
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "executed",
        last_step: "execute",
        detail: `Executed prompt.email.classifier for newest unknown email ${payload.message_id || "-"}.`,
        execution_request_payload: payload.request_payload || null,
        execution_response: payload.execution || null,
        usage_summary_response: null,
        updated_at: new Date().toISOString(),
      }));
      setRuntimeTaskNotice(`Email classification request completed for ${payload.message_id || "latest unknown message"}.`);
      return payload;
    } catch (taskError) {
      setRuntimeTaskError(taskError.message);
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "failed",
        last_step: "execute",
        detail: taskError.message,
        updated_at: new Date().toISOString(),
      }));
      throw taskError;
    } finally {
      setRuntimeTaskPending("");
    }
  }

  async function runRuntimeExecuteEmailClassifierBatch() {
    const now = new Date().toISOString();
    setRuntimeTaskPending("execute_batch");
    setRuntimeTaskError("");
    setRuntimeTaskNotice("");
    setRuntimeTaskStatus((current) => ({
      ...current,
      request_status: "running",
      last_step: "execute_batch",
      started_at: current.started_at || now,
      updated_at: now,
      detail: "Running local classification for 100 mails and sending remaining unknown mails to the AI node...",
      execution_response: {
        mode: "batch",
        stage: "local",
        batch_size: 0,
        local_processed: 0,
        local_classified: 0,
        ai_total: 0,
        ai_completed: 0,
        progress_percent: 0,
      },
    }));
    try {
      const payload = await fetchJson("/api/runtime/execute-email-classifier-batch", {
        method: "POST",
        body: JSON.stringify({
          target_api_base_url: runtimeTaskForm.target_api_base_url,
        }),
      });
      const refreshedStatus = await fetchJson("/api/gmail/status");
      setGmailStatus(refreshedStatus);
        setRuntimeTaskStatus((current) => ({
          ...current,
          request_status: "executed",
          last_step: "execute_batch",
          detail: `Runtime batch classification completed. Local classified ${payload.local_classified ?? 0} emails successfully, AI attempted ${payload.ai_attempted ?? 0}, and classified ${payload.ai_completed ?? 0} emails.`,
          execution_response: payload,
          updated_at: new Date().toISOString(),
        }));
        setRuntimeTaskNotice(
          `Runtime batch completed. Local classified ${payload.local_classified ?? 0} emails successfully, AI attempted ${payload.ai_attempted ?? 0}, and classified ${payload.ai_completed ?? 0} emails.`,
        );
      return payload;
    } catch (taskError) {
      setRuntimeTaskError(taskError.message);
      setRuntimeTaskStatus((current) => ({
        ...current,
        request_status: "failed",
        last_step: "execute_batch",
        detail: taskError.message,
        updated_at: new Date().toISOString(),
      }));
      throw taskError;
    } finally {
      setRuntimeTaskPending("");
    }
  }

  async function runGmailFetch(window, successLabel) {
    setGmailActionPending(window);
    setGmailActionError("");
    setGmailActionNotice("");
    try {
      const payload = await fetchJson(`/api/gmail/fetch/${window}`, { method: "POST" });
      const refreshedStatus = await fetchJson("/api/gmail/status");
      setGmailStatus(refreshedStatus);
      const newMailCount = Number(payload.stored_count ?? 0);
      const fetchedCount = Number(payload.fetched_count ?? 0);
      const pipelineDetail =
        payload.pipeline?.detail &&
        payload.pipeline.detail !== "Last-hour Gmail pipeline completed."
          ? ` ${payload.pipeline.detail}`
          : "";
      const resultDetail =
        newMailCount > 0
          ? `Added ${newMailCount} new emails to the SQL store.`
          : fetchedCount > 0
            ? "No new emails were added to the SQL store."
            : "No emails matched this fetch window.";
      setGmailActionNotice(`${successLabel} completed. ${resultDetail}${pipelineDetail}`);
    } catch (actionError) {
      setGmailActionError(actionError.message);
    } finally {
      setGmailActionPending("");
    }
  }

  async function runSpamhausCheck() {
    setGmailActionPending("spamhaus");
    setGmailActionError("");
    setGmailActionNotice("");
    try {
      const payload = await fetchJson("/api/gmail/spamhaus/check", { method: "POST" });
      const refreshedStatus = await fetchJson("/api/gmail/status");
      setGmailStatus(refreshedStatus);
      setGmailActionNotice(
        `Spamhaus check completed. Checked ${payload.checked_count ?? 0} senders, flagged ${payload.listed_count ?? 0}.`,
      );
    } catch (actionError) {
      setGmailActionError(actionError.message);
    } finally {
      setGmailActionPending("");
    }
  }

  async function runSenderReputationRefresh() {
    setGmailActionPending("sender_reputation");
    setGmailActionError("");
    setGmailActionNotice("");
    try {
      const payload = await fetchJson("/api/gmail/reputation/refresh", { method: "POST" });
      const refreshedStatus = await fetchJson("/api/gmail/status");
      setGmailStatus(refreshedStatus);
      setGmailActionNotice(
        `Sender reputation refreshed. Updated ${payload.refreshed_count ?? 0} sender records.`,
      );
    } catch (actionError) {
      setGmailActionError(actionError.message);
    } finally {
      setGmailActionPending("");
    }
  }

  async function loadTrainingManualBatch() {
    setTrainingBatchLoading(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson("/api/gmail/training/manual-batch", { method: "POST" });
      setTrainingBatch(payload);
      setTrainingSelections(
        Object.fromEntries(
          (payload.items || []).map((item) => [
            item.message_id,
            {
              label: item.local_label || "unknown",
              confidence: 1.0,
            },
          ]),
        ),
      );
    } catch (loadError) {
      setTrainingBatchError(loadError.message);
    } finally {
      setTrainingBatchLoading(false);
    }
  }

  async function loadTrainingSemiAutoBatch() {
    return loadTrainingSemiAutoBatchWithLimit(20);
  }

  async function loadTrainingSemiAutoBatch300() {
    return loadTrainingSemiAutoBatchWithLimit(300);
  }

  async function loadTrainingSemiAutoBatchWithLimit(limit) {
    setTrainingBatchLoading(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson(`/api/gmail/training/semi-auto-batch?limit=${encodeURIComponent(limit)}`, { method: "POST" });
      setTrainingBatch(payload);
      setTrainingSelections(
        Object.fromEntries(
          (payload.items || []).map((item) => [
            item.message_id,
            {
              label: item.predicted_label || "unknown",
              confidence: item.predicted_confidence ?? payload.threshold ?? 0.6,
            },
          ]),
        ),
      );
    } catch (loadError) {
      setTrainingBatchError(loadError.message);
    } finally {
      setTrainingBatchLoading(false);
    }
  }

  async function loadClassifiedLabelBatch(label) {
    setTrainingBatchLoading(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson(`/api/gmail/training/classified-batch?label=${encodeURIComponent(label)}`, { method: "POST" });
      setTrainingBatch(payload);
      setTrainingSelections(
        Object.fromEntries(
          (payload.items || []).map((item) => [
            item.message_id,
            {
              label: item.local_label || "unknown",
              confidence: item.local_label_confidence ?? trainingStatus?.threshold ?? 0.6,
            },
          ]),
        ),
      );
    } catch (loadError) {
      setTrainingBatchError(loadError.message);
    } finally {
      setTrainingBatchLoading(false);
    }
  }

  async function loadSenderReputationDetail(entityType, senderValue) {
    if (!senderValue) {
      return;
    }
    setSenderReputationLoading(true);
    setSenderReputationError("");
    try {
      const payload = await fetchJson(
        `/api/gmail/reputation/detail?entity_type=${encodeURIComponent(entityType)}&sender_value=${encodeURIComponent(senderValue)}`,
      );
      setSenderReputationDetail(payload);
      setSenderReputationManualNote(payload.record?.manual_rating_note || "");
      setSenderReputationNotice("");
    } catch (loadError) {
      setSenderReputationError(loadError.message);
    } finally {
      setSenderReputationLoading(false);
    }
  }

  function clearSenderReputationDetail() {
    setSenderReputationDetail(null);
    setSenderReputationError("");
    setSenderReputationManualNote("");
  }

  function openSenderReputation() {
    setView("training_reputation");
  }

  function toggleSenderReputationGroup(groupKey) {
    setSenderReputationCollapsedGroups((current) => ({
      ...current,
      [groupKey]: !current[groupKey],
    }));
  }

  async function applySenderReputationManualRating(manualRating) {
    const selectedRecord = senderReputationDetail?.record || null;
    if (!selectedRecord) {
      return;
    }
    setSenderReputationManualSavePending(true);
    setSenderReputationError("");
    setSenderReputationNotice("");
    try {
      const payload = await fetchJson("/api/gmail/reputation/manual-rating", {
        method: "POST",
        body: JSON.stringify({
          entity_type: selectedRecord.entity_type,
          sender_value: selectedRecord.sender_value,
          manual_rating: manualRating,
          note: senderReputationManualNote,
        }),
      });
      setSenderReputationSummary(payload.summary || null);
      setSenderReputationDetail((current) => (
        current
          ? {
              ...current,
              record: payload.record,
            }
          : current
      ));
      setSenderReputationNotice(
        manualRating === null
          ? `Cleared manual reputation rating for ${selectedRecord.sender_value}.`
          : `Saved manual reputation rating for ${selectedRecord.sender_value}.`,
      );
    } catch (saveError) {
      setSenderReputationError(saveError.message);
    } finally {
      setSenderReputationManualSavePending(false);
    }
  }

  async function trainLocalModel() {
    setTrainingModelPending(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson("/api/gmail/training/train-model", { method: "POST" });
      const [refreshedTraining, refreshedStatus] = await Promise.all([
        fetchJson("/api/gmail/training"),
        fetchJson("/api/gmail/status"),
      ]);
      setTrainingStatus(refreshedTraining);
      setGmailStatus(refreshedStatus);
      setTrainingNotice(
        `Model trained with ${payload.model_status?.sample_count ?? refreshedTraining?.model_status?.sample_count ?? 0} samples.`,
      );
    } catch (trainError) {
      setTrainingBatchError(trainError.message);
    } finally {
      setTrainingModelPending(false);
    }
  }

  async function trainHighConfidenceModel() {
    setTrainingModelPending(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson("/api/gmail/training/train-model?minimum_confidence=0.92", { method: "POST" });
      const [refreshedTraining, refreshedStatus] = await Promise.all([
        fetchJson("/api/gmail/training"),
        fetchJson("/api/gmail/status"),
      ]);
      setTrainingStatus(refreshedTraining);
      setGmailStatus(refreshedStatus);
      setTrainingNotice(
        `High-confidence model trained with ${payload.model_status?.sample_count ?? refreshedTraining?.model_status?.sample_count ?? 0} samples.`,
      );
    } catch (trainError) {
      setTrainingBatchError(trainError.message);
    } finally {
      setTrainingModelPending(false);
    }
  }

  function handleTrainingSelectionChange(messageId, field, value) {
    setTrainingSelections((current) => ({
      ...current,
      [messageId]: {
        ...(current[messageId] || {}),
        [field]: field === "confidence" ? value : value,
      },
    }));
  }

  async function saveTrainingBatch() {
    const isSemiAuto = trainingBatch?.source === "semi_auto";
    const items = Object.entries(trainingSelections).map(([message_id, selection]) => {
      const originalItem = (trainingBatch?.items || []).find((item) => item.message_id === message_id) || {};
      if (isSemiAuto) {
        return {
          message_id,
          selected_label: selection.label || "unknown",
          predicted_label: originalItem.predicted_label || "unknown",
          predicted_confidence: Number(originalItem.predicted_confidence ?? trainingStatus?.threshold ?? 0.6),
        };
      }
      return {
        message_id,
        label: selection.label || "unknown",
        confidence: 1.0,
      };
    });
    setTrainingSavePending(true);
    setTrainingBatchError("");
    setTrainingNotice("");
    try {
      const payload = await fetchJson(isSemiAuto ? "/api/gmail/training/semi-auto-review" : "/api/gmail/training/manual-classify", {
        method: "POST",
        body: JSON.stringify({ items }),
      });
      setTrainingNotice(`Saved ${payload.saved_count ?? 0} manual classifications.`);
      const [refreshedStatus, refreshedTraining] = await Promise.all([
        fetchJson("/api/gmail/status"),
        fetchJson("/api/gmail/training"),
      ]);
      setGmailStatus(refreshedStatus);
      setTrainingStatus(refreshedTraining);
      await loadTrainingManualBatch();
    } catch (saveError) {
      setTrainingBatchError(saveError.message);
    } finally {
      setTrainingSavePending(false);
    }
  }

  function handleChange(event) {
    const { name, value } = event.target;
    setTouched(true);
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function handleCapabilityToggle(capability) {
    setTouched(true);
    setForm((current) => {
      const selected = current.selected_task_capabilities.includes(capability);
      return {
        ...current,
        selected_task_capabilities: selected
          ? current.selected_task_capabilities.filter((item) => item !== capability)
          : [...current.selected_task_capabilities, capability],
      };
    });
  }

  function handleProviderChange(event) {
    const { name, value, type, checked } = event.target;
    setProviderDirty(true);
    setProviderError("");
    setProviderNotice("");
    setConnectUrl("");
    setProviderForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function refreshProviderState() {
    setProviderLoading(true);
    setProviderError("");
    try {
      const [configPayload, statusPayload] = await Promise.all([
        fetchJson("/providers/gmail/config"),
        fetchJson("/providers"),
      ]);
      setProviderConfig(configPayload);
      setProviderStatus(statusPayload);
      if (!providerDirty) {
        setProviderForm(normalizeProviderForm(configPayload.config));
      }
    } catch (refreshError) {
      setProviderError(refreshError.message);
    } finally {
      setProviderLoading(false);
    }
  }

  async function saveConfiguration() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = await fetchJson("/api/node/config", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setTouched(false);
      setNotice(
        bootstrap?.status?.trust_state === "trusted"
          ? "Capability selection saved."
          : `Saved onboarding configuration for ${payload.node_name || "this node"}.`,
      );
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function declareCapabilities() {
    setDeclaringCapabilities(true);
    setError("");
    setNotice("");
    try {
      const payload = await fetchJson("/api/capabilities/declare", {
        method: "POST",
      });
      setNotice(
        payload.capability_declaration_status === "accepted"
          ? "Capability declaration submitted."
          : `Capability declaration status: ${payload.capability_declaration_status || "pending"}.`,
      );
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (declareError) {
      setError(declareError.message);
    } finally {
      setDeclaringCapabilities(false);
    }
  }

  async function startOnboarding() {
    setStarting(true);
    setError("");
    setNotice("");
    try {
      await fetchJson("/api/node/config", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      const payload = await fetchJson("/api/onboarding/start", {
        method: "POST",
      });
      setTouched(false);
      setNotice(`Onboarding started for ${payload.node_name || "this node"}.`);
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (startError) {
      setError(startError.message);
    } finally {
      setStarting(false);
    }
  }

  async function restartOnboarding() {
    setRestarting(true);
    setError("");
    setNotice("");
    try {
      const payload = await fetchJson("/api/onboarding/restart", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setTouched(false);
      setNotice(`Setup restarted for ${payload.node_name || "this node"}.`);
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (restartError) {
      setError(restartError.message);
    } finally {
      setRestarting(false);
    }
  }

  async function saveProviderConfig() {
    setProviderSaving(true);
    setProviderError("");
    setProviderNotice("");
    try {
      const payload = await fetchJson("/providers/gmail/config", {
        method: "PUT",
        body: JSON.stringify(buildProviderPayload(providerForm)),
      });
      setProviderConfig(payload);
      setProviderStatus(await fetchJson("/providers"));
      setProviderForm(normalizeProviderForm(payload.config));
      setProviderDirty(false);
      setProviderNotice("Gmail provider configuration saved.");
    } catch (saveError) {
      setProviderError(saveError.message);
    } finally {
      setProviderSaving(false);
    }
  }

  async function validateProviderConfig() {
    setProviderValidating(true);
    setProviderError("");
    setProviderNotice("");
    try {
      const payload = await fetchJson("/providers/gmail/config", {
        method: "PUT",
        body: JSON.stringify(buildProviderPayload(providerForm)),
      });
      setProviderConfig(payload);
      setProviderForm(normalizeProviderForm(payload.config));
      setProviderDirty(false);
      setProviderNotice(
        payload.validation.ok
          ? "Gmail provider configuration is valid."
          : `Gmail provider configuration is incomplete: ${payload.validation.missing_fields.join(", ")}.`,
      );
    } catch (validateError) {
      setProviderError(validateError.message);
    } finally {
      setProviderValidating(false);
    }
  }

  async function startProviderConnect() {
    setProviderConnecting(true);
    setProviderError("");
    setProviderNotice("");
    try {
      const payload = await fetchJson("/providers/gmail/accounts/primary/connect/start", {
        method: "POST",
      });
      setConnectUrl(payload.connect_url);
      setProviderNotice("Gmail connect URL created for the primary account.");
      setProviderStatus(await fetchJson("/providers"));
    } catch (connectError) {
      setProviderError(connectError.message);
    } finally {
      setProviderConnecting(false);
    }
  }

  async function copyNodeId() {
    const nodeId = bootstrap?.status?.node_id;
    if (!nodeId || typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      return;
    }
    await navigator.clipboard.writeText(nodeId);
    setCopyNotice("Copied");
    window.setTimeout(() => setCopyNotice(""), 1600);
  }

  async function refreshDashboardState(message = "") {
    setError("");
    try {
      if (message) {
        setNotice(message);
      }
      const refreshed = await fetchJson("/api/node/bootstrap");
      startTransition(() => {
        setBootstrap(refreshed);
        setProviderStatus(refreshed.status);
        setUiUpdatedAt(new Date().toISOString());
      });
    } catch (refreshError) {
      setError(refreshError.message);
    }
  }

  async function restartRuntimeService(target) {
    const normalizedTarget = String(target || "").trim().toLowerCase();
    if (!normalizedTarget) {
      return;
    }
    setServiceControlPending(normalizedTarget);
    setServiceControlError("");
    setServiceControlNotice("");
    try {
      const payload = await fetchJson("/api/services/restart", {
        method: "POST",
        body: JSON.stringify({ target: normalizedTarget }),
      });
      if (payload.status === "manual_required") {
        setServiceControlNotice(
          `${normalizedTarget} restart requires an operator command: ${payload.recommended_command || "manual restart required"}.`,
        );
      } else {
        setServiceControlNotice(`${normalizedTarget} restart requested successfully.`);
      }
    } catch (restartError) {
      setServiceControlError(restartError.message);
    } finally {
      setServiceControlPending("");
    }
  }

  const onboarding = bootstrap?.onboarding;
  const status = bootstrap?.status;
  const requiredInputs = bootstrap?.required_inputs || [];
  const nodeState = deriveNodeState(bootstrap);
  const setupFlow = deriveSetupFlow(bootstrap);
  const nodeSetupVisible = isNodeSetupVisible(bootstrap);
  const dashboardEnabled = Boolean(status?.operational_readiness);
  const providerSummary = status?.provider_account_summaries?.gmail || {};
  const providerConnected = providerSummary?.provider_state === "connected";
  const gmailPrimary = gmailStatus?.accounts?.[0] || null;
  const gmailPrimaryMailboxStatus = gmailPrimary?.mailbox_status || null;
  const gmailPrimaryAccount = gmailPrimary?.account || null;
  const gmailPrimaryStore = gmailPrimary?.message_store || null;
  const gmailPrimaryClassification = gmailPrimary?.classification_summary || null;
  const gmailPrimarySenderReputation = gmailPrimary?.sender_reputation || null;
  const gmailPrimaryModelStatus = resolvePrimaryModelStatus(gmailPrimary?.model_status || null, trainingStatus?.model_status || null);
  const gmailPrimarySpamhaus = gmailPrimary?.spamhaus || null;
  const gmailPrimaryQuotaUsage = gmailPrimary?.quota_usage || null;
  const gmailFetchSchedule = gmailStatus?.fetch_schedule || null;
  const gmailFetchScheduler = gmailStatus?.fetch_scheduler || null;
  const gmailLastHourPipeline = gmailStatus?.last_hour_pipeline || null;
  const gmailLastHourPipelinePills = buildGmailLastHourPipelinePills(gmailLastHourPipeline);
  const gmailWindowSettings = buildGmailWindowSettings(gmailFetchSchedule);
  const scheduledTasks = Array.isArray(bootstrap?.scheduled_tasks) ? bootstrap.scheduled_tasks : [];
  const scheduledTasksSorted = [...scheduledTasks].sort((left, right) => {
    const leftTime = left?.next_execution_at ? new Date(left.next_execution_at).getTime() : Number.POSITIVE_INFINITY;
    const rightTime = right?.next_execution_at ? new Date(right.next_execution_at).getTime() : Number.POSITIVE_INFINITY;
    const safeLeftTime = Number.isNaN(leftTime) ? Number.POSITIVE_INFINITY : leftTime;
    const safeRightTime = Number.isNaN(rightTime) ? Number.POSITIVE_INFINITY : rightTime;
    if (safeLeftTime !== safeRightTime) {
      return safeLeftTime - safeRightTime;
    }
    return String(left?.title || left?.task_id || "").localeCompare(String(right?.title || right?.task_id || ""));
  });
  const scheduledTaskLegend = Array.isArray(bootstrap?.scheduled_task_legend) ? bootstrap.scheduled_task_legend : [];
  const mqttHealth = status?.mqtt_health || {};
  const lastHeartbeatAt = mqttHealth?.last_status_report_at || status?.last_heartbeat_at || null;
  const mqttConnected = status?.mqtt_connection_status === "connected" || mqttHealth?.health_status === "connected";
  const mqttTelemetryFresh = mqttHealth?.status_freshness_state === "fresh";
  const modelTrainingState = deriveModelTrainingState(gmailPrimaryModelStatus, providerConnected);
  const runtimeResolved = runtimeTaskStatus?.resolve_response || null;
  const runtimeAuthorized = runtimeTaskStatus?.authorize_response || null;
  const runtimePreview = runtimeTaskStatus?.preview_response || null;
  const runtimeRegistrationRequest = runtimeTaskStatus?.registration_request_payload || null;
  const runtimeExecutionRequest = runtimeTaskStatus?.execution_request_payload || null;
  const runtimeExecution = runtimeTaskStatus?.execution_response || null;
  const runtimeUsageSummary = runtimeTaskStatus?.usage_summary_response || null;
  const runtimeExecutionMetrics = runtimeExecution?.metrics || null;
  const runtimeExecutionOutput = parseRuntimeExecutionOutput(runtimeExecution?.output);
  const runtimeLastStep = runtimeTaskStatus?.last_step || "none";
  const runtimeBatchExecution = runtimeLastStep === "execute_batch" ? runtimeExecution : null;
  const runtimeBatchProgressPercent = Math.max(0, Math.min(100, Number(runtimeBatchExecution?.progress_percent ?? 0)));
  let runtimeLastPayloadLabel = "";
  let runtimeLastPayload = null;
  let runtimeLastResponseLabel = "";
  let runtimeLastResponse = null;

  if (runtimeLastStep === "register") {
    runtimeLastPayloadLabel = "Prompt Registration Payload";
    runtimeLastPayload = runtimeRegistrationRequest;
    runtimeLastResponseLabel = "Prompt Registration Response";
    runtimeLastResponse = runtimeExecution;
  } else if (runtimeLastStep === "execute") {
    runtimeLastPayloadLabel = "Direct AI Request Payload";
    runtimeLastPayload = runtimeExecutionRequest;
    runtimeLastResponseLabel = "Execution Response";
    runtimeLastResponse = runtimeExecution;
  } else if (runtimeLastStep === "execute_batch") {
    runtimeLastPayloadLabel = "Last Direct AI Request Payload";
    runtimeLastPayload = runtimeExecutionRequest;
    runtimeLastResponseLabel = "Batch Execution Response";
    runtimeLastResponse = runtimeExecution;
  } else if (runtimeLastStep === "authorize") {
    runtimeLastResponseLabel = "Authorize Response";
    runtimeLastResponse = runtimeAuthorized;
  } else if (runtimeLastStep === "resolve") {
    runtimeLastResponseLabel = "Resolve Response";
    runtimeLastResponse = runtimeResolved;
  } else if (runtimeLastStep === "preview") {
    runtimeLastResponseLabel = "Preview Response";
    runtimeLastResponse = runtimePreview;
  }
  const dashboardWarnings = deriveDashboardWarnings({
    status,
    providerConnected,
    mqttConnected,
    mqttHealth,
  });
  const mqttIndicatorClass = mqttConnected || mqttTelemetryFresh
    ? "health-connected"
    : mqttHealth?.status_freshness_state === "unknown"
      ? "health-fresh"
      : "health-pending";
  const mqttSeverityClass = mqttConnected || mqttTelemetryFresh
    ? healthSeverityClass("connected", ["connected"])
    : healthSeverityClass(mqttHealth?.status_freshness_state, [], ["unknown"]);
  if (view === "provider") {
    return (
      <div className="shell">
        <ProviderSetupPage
          bootstrap={bootstrap}
          providerConfig={providerConfig}
          providerStatus={providerStatus}
          gmailStatus={gmailStatus}
          providerForm={providerForm}
          providerDirty={providerDirty}
          providerLoading={providerLoading}
          providerSaving={providerSaving}
          providerValidating={providerValidating}
          providerConnecting={providerConnecting}
          providerNotice={providerNotice}
          providerError={providerError}
          connectUrl={connectUrl}
          onProviderChange={handleProviderChange}
          onRefresh={refreshProviderState}
          onSave={saveProviderConfig}
          onValidate={validateProviderConfig}
          onConnect={startProviderConnect}
          onBack={() => (dashboardEnabled ? openDashboard() : openSetup())}
        />
      </div>
    );
  }

  if (view === "training") {
    return (
      <div className="shell">
        <TrainingPage
          trainingStatus={trainingStatus}
          trainingLoading={trainingLoading}
          trainingError={trainingError}
          trainingBatch={trainingBatch}
          trainingBatchLoading={trainingBatchLoading}
          trainingBatchError={trainingBatchError}
          trainingSavePending={trainingSavePending}
          trainingModelPending={trainingModelPending}
          trainingNotice={trainingNotice}
          trainingSelections={trainingSelections}
          onBack={() => (dashboardEnabled ? openDashboard() : openSetup())}
          onOpenSenderReputation={openSenderReputation}
          onLoadClassifiedLabelBatch={loadClassifiedLabelBatch}
          onLoadManualBatch={loadTrainingManualBatch}
          onLoadSemiAutoBatch={loadTrainingSemiAutoBatch}
          onLoadSemiAutoBatch300={loadTrainingSemiAutoBatch300}
          onTrainModel={trainLocalModel}
          onTrainHighConfidenceModel={trainHighConfidenceModel}
          onSelectionChange={handleTrainingSelectionChange}
          onSaveBatch={saveTrainingBatch}
        />
      </div>
    );
  }

  if (view === "training_reputation") {
    return (
      <div className="shell">
        <SenderReputationPage
          summary={senderReputationSummary}
          loading={senderReputationSummaryLoading}
          error={senderReputationSummaryError}
          detail={senderReputationDetail}
          detailLoading={senderReputationLoading}
          detailError={senderReputationError}
          notice={senderReputationNotice}
          onBack={() => setView("training")}
          onInspect={loadSenderReputationDetail}
          onClear={clearSenderReputationDetail}
          filterValue={senderReputationFilter}
          onFilterChange={setSenderReputationFilter}
          collapsedGroups={senderReputationCollapsedGroups}
          onToggleGroup={toggleSenderReputationGroup}
          manualNote={senderReputationManualNote}
          onManualNoteChange={setSenderReputationManualNote}
          manualSavePending={senderReputationManualSavePending}
          onApplyManualRating={applySenderReputationManualRating}
          onClearManualRating={() => applySenderReputationManualRating(null)}
        />
      </div>
    );
  }

  if (view === "dashboard" && dashboardEnabled) {
    return (
      <div className="shell">
        <main className="app-frame">
          <section className="card app-header">
            <div className="app-header-top">
              <div>
                <h1>Hexe Email Node</h1>
              </div>
              <div className="app-header-status-pills">
                <span className={healthSeverityClass(status?.operational_readiness ? "operational" : "pending", ["operational"])}>
                  <span className="status-badge status-operational">
                    {status?.operational_readiness ? "operational" : nodeState.label}
                  </span>
                </span>
                <span className={healthSeverityClass(providerSummary?.provider_state, ["connected"], ["configured"])}>
                  <span className="status-badge">
                    {providerSummary?.provider_state === "connected" ? "Gmail connected" : "Gmail pending"}
                  </span>
                </span>
                {modelTrainingState ? (
                  <span className={`status-pill tone-${modelTrainingState.tone}`}>
                    model: {modelTrainingState.label}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="app-header-bottom">
              <button className="btn btn-ghost app-header-theme-btn" type="button">
                Theme: {currentThemeLabel()}
              </button>
              <div className="app-header-actions">
                <button className="btn btn-ghost" type="button" onClick={restartOnboarding} disabled={restarting}>
                  {restarting ? "Restarting..." : "Restart Setup"}
                </button>
                <button className="btn btn-ghost" type="button" onClick={openSetup}>
                  Open Setup
                </button>
                <button className="btn btn-ghost" type="button" onClick={openProvider}>
                  Setup Provider
                </button>
                <button className="btn btn-ghost" type="button" onClick={copyNodeId} disabled={!status?.node_id}>
                  {copyNotice || "Copy Node ID"}
                </button>
              </div>
            </div>
            <div className="app-header-meta">
              <span className="muted tiny">
                Updated: <code>{formatTelemetryTimestamp(uiUpdatedAt)}</code>
              </span>
              <span className="muted tiny">
                Quota: <code>{gmailPrimaryQuotaUsage ? `${gmailPrimaryQuotaUsage.used_last_minute}/${gmailPrimaryQuotaUsage.limit_per_minute}` : "0/15000"}</code>
              </span>
              <span className="muted tiny">
                Node: <code>{status?.node_id || "pending"}</code>
              </span>
              {modelTrainingState ? (
                <span className="muted tiny">
                  Model: <code>{modelTrainingState.detail}</code>
                </span>
              ) : null}
            </div>
          </section>

          <section className="operational-shell">
            <aside className="card operational-shell-nav-card">
              <nav className="operational-shell-nav" aria-label="Operational sections">
                <button
                  type="button"
                  className={`btn operational-nav-btn ${dashboardSection === "overview" ? "btn-primary" : ""}`}
                  onClick={() => openDashboard("overview")}
                >
                  Overview
                </button>
                <button
                  type="button"
                  className={`btn operational-nav-btn ${dashboardSection === "gmail" ? "btn-primary" : ""}`}
                  onClick={() => openDashboard("gmail")}
                >
                  Gmail
                </button>
                <button
                  type="button"
                  className={`btn operational-nav-btn ${dashboardSection === "runtime" ? "btn-primary" : ""}`}
                  onClick={() => openDashboard("runtime")}
                >
                  Runtime
                </button>
                <button
                  type="button"
                  className={`btn operational-nav-btn ${dashboardSection === "scheduled" ? "btn-primary" : ""}`}
                  onClick={() => openDashboard("scheduled")}
                >
                  Scheduled Tasks
                </button>
                <button type="button" className="btn operational-nav-btn">Activity</button>
                <button type="button" className="btn operational-nav-btn">Diagnostics</button>
              </nav>
            </aside>

            <div className="operational-shell-content">
              <article className="card node-health-strip operational-content-header">
                <div className="node-health-strip-grid">
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Lifecycle</span>
                    <span className={healthSeverityClass(status?.operational_readiness ? "operational" : "pending", ["operational"])}>
                      <span className="status-badge status-operational">
                        {status?.operational_readiness ? "operational" : setupFlow.current?.label || "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Trust</span>
                    <span className={healthSeverityClass(status?.trust_state, ["trusted"])}>
                      <span className="status-badge status-trusted">{status?.trust_state || "untrusted"}</span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Core API</span>
                    <span className={healthSeverityClass(bootstrap?.config?.core_base_url ? "connected" : "pending", ["connected"])}>
                      <span className={`health-indicator ${bootstrap?.config?.core_base_url ? "health-connected" : "health-pending"}`}>
                        <span className="health-dot" />
                        {bootstrap?.config?.core_base_url ? "connected" : "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">MQTT</span>
                    <span className={mqttSeverityClass}>
                      <span className={`health-indicator ${mqttIndicatorClass}`}>
                        <span className="health-dot" />
                        {mqttConnected ? "connected" : mqttHealth?.status_freshness_state || status?.mqtt_connection_status || "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Governance</span>
                    <span className={healthSeverityClass(status?.governance_sync_status, [], ["ok"])}>
                      <span className={`health-indicator ${status?.governance_sync_status === "ok" ? "health-fresh" : "health-pending"}`}>
                        <span className="health-dot" />
                        {status?.governance_sync_status === "ok" ? "fresh" : status?.governance_sync_status || "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Providers</span>
                    <span className={healthSeverityClass(status?.enabled_providers?.length ? "configured" : "pending", [], ["configured"])}>
                      <span className="status-badge status-configured">
                        {providerConnected ? "configured" : "pending"}
                      </span>
                    </span>
                  </div>
                  <div className="node-health-strip-item">
                    <span className="muted tiny">Last Heartbeat</span>
                    <code>{formatRelativeTime(lastHeartbeatAt)}</code>
                  </div>
                </div>
              </article>

              {dashboardSection === "gmail" ? (
                <section className="grid operational-dashboard-grid">
                  <article className="card dashboard-primary-card">
                    <div className="card-header">
                      <h2>Gmail Status</h2>
                      <p className="muted">Background Gmail inbox status and unread counts.</p>
                    </div>
                    {gmailStatusError ? <div className="callout callout-danger">{gmailStatusError}</div> : null}
                    <dl className="facts">
                      <div>
                        <dt>Provider State</dt>
                        <dd>{gmailStatus?.provider_state || providerSummary?.provider_state || "pending"}</dd>
                      </div>
                      <div>
                        <dt>Account</dt>
                        <dd>{gmailPrimaryAccount?.email_address || gmailPrimaryAccount?.account_id || "Pending"}</dd>
                      </div>
                      <div>
                        <dt>Unread Today</dt>
                        <dd>{gmailPrimaryMailboxStatus?.unread_today_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd>
                      </div>
                      <div>
                        <dt>Unread Yesterday</dt>
                        <dd>{gmailPrimaryMailboxStatus?.unread_yesterday_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd>
                      </div>
                      <div>
                        <dt>Stored Emails</dt>
                        <dd>{gmailPrimaryStore?.total_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Classified Emails</dt>
                        <dd>{gmailPrimaryClassification?.classified_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>High Confidence</dt>
                        <dd>{gmailPrimaryClassification?.high_confidence_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Spamhaus Checked</dt>
                        <dd>{gmailPrimarySpamhaus?.checked_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Spamhaus Pending</dt>
                        <dd>{gmailPrimarySpamhaus?.pending_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Spamhaus Listed</dt>
                        <dd>{gmailPrimarySpamhaus?.listed_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Quota Used / Min</dt>
                        <dd>{gmailPrimaryQuotaUsage ? `${gmailPrimaryQuotaUsage.used_last_minute}/${gmailPrimaryQuotaUsage.limit_per_minute}` : 0}</dd>
                      </div>
                      <div>
                        <dt>Quota Remaining</dt>
                        <dd>{gmailPrimaryQuotaUsage?.remaining_last_minute ?? 15000}</dd>
                      </div>
                    </dl>
                  </article>

                  <div className="content-stack">
                    <article className="card">
                      <div className="card-header">
                        <h2>Sender Reputation</h2>
                        <p className="muted">Sender email and domain reputation derived from local classifications and Spamhaus checks.</p>
                      </div>
                    <SenderReputationPanel
                      summary={gmailPrimarySenderReputation}
                      detail={null}
                      loading={false}
                      error=""
                      onInspect={() => {}}
                      onClear={() => {}}
                      showRecords={false}
                      showDetail={false}
                    />
                  </article>

                    <article className="card">
                      <div className="card-header">
                        <h2>Gmail Action</h2>
                        <p className="muted">Manual Gmail fetch actions for initial learning and time-window refresh.</p>
                      </div>
                      <div className="stack compact-stack">
                        {gmailActionError ? <div className="callout callout-danger">{gmailActionError}</div> : null}
                        {gmailActionNotice ? <div className="callout callout-success">{gmailActionNotice}</div> : null}
                        <button
                          type="button"
                          className="btn"
                          disabled={gmailActionPending !== ""}
                          onClick={() => runGmailFetch("initial_learning", "Initial learning fetch")}
                        >
                          Fetch Initial Learning
                        </button>
                        <button
                          type="button"
                          className="btn"
                          disabled={gmailActionPending !== "" || (gmailPrimaryStore?.total_count ?? 0) === 0}
                        onClick={runSpamhausCheck}
                      >
                        Check With Spamhaus
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={gmailActionPending !== "" || (gmailPrimaryStore?.total_count ?? 0) === 0}
                        onClick={runSenderReputationRefresh}
                      >
                        Calculate Sender Reputation
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={openTraining}
                        >
                          Open Training
                        </button>
                        <div className="row gmail-fetch-row">
                          <button
                            type="button"
                            className="btn"
                            disabled={gmailActionPending !== ""}
                          onClick={() => runGmailFetch("today", "Today poll")}
                        >
                          Poll Today
                        </button>
                        <button
                          type="button"
                          className="btn"
                          disabled={gmailActionPending !== ""}
                          onClick={() => runGmailFetch("yesterday", "Yesterday poll")}
                        >
                          Poll Yesterday
                        </button>
                        <button
                          type="button"
                          className="btn"
                          disabled={gmailActionPending !== ""}
                          onClick={() => runGmailFetch("last_hour", "Last hour poll")}
                        >
                          Poll Last Hour
                        </button>
                        </div>
                        <button
                          type="button"
                          className="btn"
                          disabled={runtimeTaskPending !== "" || gmailActionPending !== ""}
                          onClick={runRuntimeExecuteEmailClassifierBatch}
                        >
                          {runtimeTaskPending === "execute_batch" ? "Processing..." : "Local Classify 100, Send Unknown To AI"}
                        </button>
                        {runtimeBatchExecution ? (
                          <div className="stack compact-stack">
                            <div className="muted tiny">
                              AI Batch Progress: {runtimeBatchExecution?.ai_attempted ?? runtimeBatchExecution?.ai_completed ?? 0}/{runtimeBatchExecution?.ai_total ?? 0}
                            </div>
                            <div className="runtime-progress-shell">
                              <div
                                className="runtime-progress-bar"
                                style={{ width: `${runtimeBatchProgressPercent}%` }}
                              />
                            </div>
                            <div className="muted tiny">
                              Stage: {runtimeBatchExecution?.stage || "-"} | Local Classified: {runtimeBatchExecution?.local_classified ?? 0} | Batch Size: {runtimeBatchExecution?.batch_size ?? 0}
                            </div>
                            {runtimeBatchExecution?.last_execution?.error_code || runtimeBatchExecution?.last_execution?.error_message ? (
                              <div className="callout callout-danger">
                                Last AI execution failed: {runtimeBatchExecution?.last_execution?.error_code || "error"}
                                {runtimeBatchExecution?.last_execution?.error_message
                                  ? ` (${runtimeBatchExecution.last_execution.error_message})`
                                  : ""}
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                        <p className="muted tiny">
                          {gmailActionPending
                            ? gmailActionPending === "spamhaus"
                              ? "Spamhaus check in progress..."
                              : gmailActionPending === "sender_reputation"
                                ? "Sender reputation refresh in progress..."
                              : "Fetch in progress..."
                            : "Scheduled fetches use the node local timezone and store up to six months of mail."}
                        </p>
                        <div className="row gmail-fetch-row gmail-pipeline-row">
                          {gmailLastHourPipelinePills.map((stage) => (
                            <span key={stage.key} className={pipelineStageClass(stage.value)}>
                              {stage.label}
                            </span>
                          ))}
                        </div>
                      </div>
                    </article>
                  </div>

                  <article className="card">
                    <div className="card-header">
                      <h2>Gmail Settings</h2>
                      <p className="muted">Scheduled Gmail fetch windows for operational refresh.</p>
                    </div>
                    <dl className="facts">
                      <div>
                        <dt>Scheduler</dt>
                        <dd>
                          <span className={healthSeverityClass(gmailFetchScheduler?.status, ["completed"], ["running"])}>
                            <span className="status-badge">
                              {gmailFetchScheduler?.loop_active ? "active" : "inactive"}
                            </span>
                          </span>
                        </dd>
                      </div>
                      <div>
                        <dt>Last Check</dt>
                        <dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_checked_at)}</dd>
                      </div>
                      <div>
                        <dt>Last Success</dt>
                        <dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_success_at)}</dd>
                      </div>
                      <div>
                        <dt>Last Error</dt>
                        <dd>{gmailFetchScheduler?.last_error || "-"}</dd>
                      </div>
                    </dl>
                    <p className="muted tiny">{gmailFetchScheduler?.detail || "Scheduler status unavailable."}</p>
                    <div className="gmail-settings-grid">
                      {gmailWindowSettings.map((windowSetting) => (
                        <section key={windowSetting.key} className="gmail-settings-window">
                          <div className="gmail-settings-window-header">
                            <h3>{windowSetting.label}</h3>
                            <span className="status-pill">{windowSetting.runReason || "pending"}</span>
                          </div>
                          <dl className="facts single-column-facts gmail-settings-facts">
                            <div>
                              <dt>Fetched</dt>
                              <dd>{formatScheduleTimestamp(windowSetting.fetchedAt)}</dd>
                            </div>
                            <div>
                              <dt>Schedule</dt>
                              <dd>{windowSetting.schedule}</dd>
                            </div>
                          </dl>
                        </section>
                      ))}
                    </div>
                  </article>
                </section>
              ) : dashboardSection === "runtime" ? (
                <section className="grid operational-dashboard-grid">
                  <article className="card dashboard-primary-card">
                    <div className="card-header">
                      <h2>Runtime Status</h2>
                      <p className="muted">Latest Core routing state and AI-node prompt registration status for the current task request.</p>
                    </div>
                    {runtimeTaskError ? <div className="callout callout-danger">{runtimeTaskError}</div> : null}
                    {runtimeTaskNotice ? <div className="callout callout-success">{runtimeTaskNotice}</div> : null}
                    <dl className="facts">
                      <div>
                        <dt>Request Status</dt>
                        <dd>{runtimeTaskStatus?.request_status || "idle"}</dd>
                      </div>
                      <div>
                        <dt>Last Step</dt>
                        <dd>{runtimeTaskStatus?.last_step || "none"}</dd>
                      </div>
                      <div>
                        <dt>Requested Node Type</dt>
                        <dd>{runtimeTaskForm.requested_node_type}</dd>
                      </div>
                      <div>
                        <dt>Task Family</dt>
                        <dd>{runtimeTaskForm.task_family}</dd>
                      </div>
                      <div>
                        <dt>Resolved Service</dt>
                        <dd>{runtimeResolved?.selected_service_id || runtimeResolved?.service_id || "-"}</dd>
                      </div>
                      <div>
                        <dt>Resolved Provider</dt>
                        <dd>{runtimeResolved?.provider || "-"}</dd>
                      </div>
                      <div>
                        <dt>Resolved Model</dt>
                        <dd>{runtimeResolved?.model_id || "-"}</dd>
                      </div>
                      <div>
                        <dt>Authorization</dt>
                        <dd>{runtimeAuthorized ? (runtimeAuthorizationGranted(runtimeAuthorized) ? "authorized" : "rejected") : "-"}</dd>
                      </div>
                      <div>
                        <dt>Authorization ID</dt>
                        <dd>{runtimeAuthorized?.authorization_id || "-"}</dd>
                      </div>
                      <div>
                        <dt>Grant ID</dt>
                        <dd>{runtimeAuthorized?.grant_id || "-"}</dd>
                      </div>
                      <div>
                        <dt>Started</dt>
                        <dd>{formatTelemetryTimestamp(runtimeTaskStatus?.started_at)}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{formatTelemetryTimestamp(runtimeTaskStatus?.updated_at)}</dd>
                      </div>
                      <div>
                        <dt>Execution Status</dt>
                        <dd>{runtimeExecution?.status || "-"}</dd>
                      </div>
                      <div>
                        <dt>Output Label</dt>
                        <dd>{runtimeExecutionOutput?.label || "-"}</dd>
                      </div>
                      <div>
                        <dt>Output Confidence</dt>
                        <dd>{runtimeExecutionOutput?.confidence ?? "-"}</dd>
                      </div>
                      <div>
                        <dt>Output Rationale</dt>
                        <dd>{runtimeExecutionOutput?.rationale || "-"}</dd>
                      </div>
                      <div>
                        <dt>Provider Used</dt>
                        <dd>{runtimeExecution?.provider_used || "-"}</dd>
                      </div>
                      <div>
                        <dt>Model Used</dt>
                        <dd>{runtimeExecution?.model_used || "-"}</dd>
                      </div>
                      <div>
                        <dt>Total Tokens</dt>
                        <dd>{runtimeExecutionMetrics?.total_tokens ?? "-"}</dd>
                      </div>
                      <div>
                        <dt>Completed</dt>
                        <dd>{formatTelemetryTimestamp(runtimeExecution?.completed_at)}</dd>
                      </div>
                    </dl>
                    <div className="callout">
                      {runtimeTaskStatus?.detail || "No runtime task request has been started yet."}
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Runtime Settings</h2>
                      <p className="muted">Configure the task request that will be previewed, resolved, and authorized through Core.</p>
                    </div>
                    <div className="stack compact-stack">
                      <label className="field">
                        <span className="field-label">Requested Node Type</span>
                        <select name="requested_node_type" value={runtimeTaskForm.requested_node_type} onChange={handleRuntimeTaskFormChange}>
                          <option value="ai">ai</option>
                          <option value="email">email</option>
                        </select>
                      </label>
                      <label className="field">
                        <span className="field-label">Task Family</span>
                        <select name="task_family" value={runtimeTaskForm.task_family} onChange={handleRuntimeTaskFormChange}>
                          <option value="task.classification">task.classification</option>
                          <option value="task.summarization">task.summarization</option>
                          <option value="task.tracking">task.tracking</option>
                        </select>
                      </label>
                      <label className="field">
                        <span className="field-label">Content Type</span>
                        <input name="content_type" value={runtimeTaskForm.content_type} onChange={handleRuntimeTaskFormChange} />
                      </label>
                      <label className="field">
                        <span className="field-label">Preferred Provider</span>
                        <input name="preferred_provider" value={runtimeTaskForm.preferred_provider} onChange={handleRuntimeTaskFormChange} />
                      </label>
                      <label className="field">
                        <span className="field-label">Preferred Model</span>
                        <input name="preferred_model" value={runtimeTaskForm.preferred_model} onChange={handleRuntimeTaskFormChange} />
                      </label>
                      <label className="field">
                        <span className="field-label">Service ID</span>
                        <input
                          name="service_id"
                          value={runtimeTaskForm.service_id}
                          onChange={handleRuntimeTaskFormChange}
                          placeholder="node-service:node-123e4567-e89b-42d3-a456-426614174000:openai"
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">AI Node API Base URL</span>
                        <input
                          name="target_api_base_url"
                          value={runtimeTaskForm.target_api_base_url}
                          onChange={handleRuntimeTaskFormChange}
                          placeholder={
                            (Array.isArray(runtimeResolved?.candidates) && runtimeResolved.candidates[0]?.provider_api_base_url) ||
                            "http://10.0.0.100:9002/api"
                          }
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">Email Subject</span>
                        <input name="email_subject" value={runtimeTaskForm.email_subject} onChange={handleRuntimeTaskFormChange} />
                      </label>
                      <label className="field">
                        <span className="field-label">Email Body</span>
                        <textarea name="email_body" rows="6" value={runtimeTaskForm.email_body} onChange={handleRuntimeTaskFormChange} />
                      </label>
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Runtime Actions</h2>
                      <p className="muted">Start with preview + resolve, then authorize the selected or manually provided service through Core.</p>
                    </div>
                    <div className="stack compact-stack">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={runtimeTaskPending !== ""}
                        onClick={runRuntimeResolveFlow}
                      >
                        {runtimeTaskPending === "preview" || runtimeTaskPending === "resolve" || runtimeTaskPending === "authorize"
                          ? "Running..."
                          : "Start Task Resolve"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={
                          runtimeTaskPending !== "" ||
                          !(
                            runtimeTaskForm.service_id ||
                            runtimeResolved?.selected_service_id ||
                            runtimeResolved?.service_id
                          )
                        }
                        onClick={() => runRuntimeAuthorize()}
                      >
                        {runtimeTaskPending === "authorize" ? "Authorizing..." : "Start Task Authorize"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={runtimeTaskPending !== ""}
                        onClick={runRuntimeRegisterPrompt}
                      >
                        {runtimeTaskPending === "register" ? "Syncing..." : "Sync Prompts On AI Node"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={runtimeTaskPending !== ""}
                        onClick={runRuntimeExecuteEmailClassifier}
                      >
                        {runtimeTaskPending === "execute" ? "Sending..." : "Send Newest Unknown Mail To Classifier"}
                      </button>
                      <div className="row gmail-fetch-row">
                        <button type="button" className="btn" disabled={runtimeTaskPending !== ""} onClick={runRuntimePreview}>
                          Debug Preview
                        </button>
                        <button type="button" className="btn" disabled={runtimeTaskPending !== ""} onClick={runRuntimeResolve}>
                          Debug Resolve
                        </button>
                        <button
                          type="button"
                          className="btn"
                          disabled={runtimeTaskPending !== ""}
                          onClick={() => runRuntimeAuthorize(runtimeResolved)}
                        >
                          Debug Authorize
                        </button>
                      </div>
                      <p className="muted tiny">
                        {runtimeTaskPending
                          ? `Running ${runtimeTaskPending} step...`
                          : "Use the main buttons for resolve, authorize, prompt registration, sending the newest unknown stored Gmail message to the classifier, or running the 100-mail local-plus-AI batch."}
                      </p>
                      {(runtimePreview || runtimeResolved || runtimeAuthorized || runtimeExecution) ? (
                        <div className="callout">
                          Preview: <code>{runtimePreview?.detail || "-"}</code><br />
                          Resolve: <code>{runtimeResolved?.selected_service_id || runtimeResolved?.service_id || "-"}</code><br />
                          Authorize: <code>{runtimeAuthorized?.grant_id || runtimeAuthorized?.authorization_id || "-"}</code><br />
                          Execute: <code>{runtimeExecution?.status || "-"}</code>
                        </div>
                      ) : null}
                    </div>
                  </article>
                </section>
              ) : dashboardSection === "scheduled" ? (
                <section className="grid scheduled-tasks-grid">
                  <article className="card scheduled-tasks-card">
                    <div className="card-header">
                      <h2>Scheduled Tasks</h2>
                      <p className="muted">Scheduler-driven background jobs with current cadence and latest execution state.</p>
                    </div>
                    <div className="scheduled-tasks-legend">
                      {scheduledTaskLegend.map((item) => (
                        <div key={item.name} className="scheduled-tasks-legend-item">
                          <code>{item.name}</code>
                          <span className="muted tiny">{item.detail}</span>
                        </div>
                      ))}
                    </div>
                    {scheduledTasksSorted.length ? (
                      <div className="scheduled-tasks-table-wrap">
                        <table className="scheduled-tasks-table">
                          <thead>
                            <tr>
                              <th>Task</th>
                              <th>Group</th>
                              <th>Schedule</th>
                              <th>Status</th>
                              <th>Last Execution</th>
                              <th>Next Execution</th>
                              <th>Last Reason</th>
                              <th>Last Slot</th>
                              <th>Detail</th>
                            </tr>
                          </thead>
                          <tbody>
                            {scheduledTasksSorted.map((task) => (
                              <tr key={task.task_id}>
                                <td><strong>{task.title || task.task_id}</strong></td>
                                <td>{task.group || "-"}</td>
                                <td>
                                  <div><code>{task.schedule_name || "-"}</code></div>
                                  <div className="muted tiny">{task.schedule_detail || "-"}</div>
                                </td>
                                <td>
                                  <span className={`status-pill tone-${scheduledTaskStatusTone(task.status)}`}>
                                    {task.status || "unknown"}
                                  </span>
                                </td>
                                <td>
                                  <div>{formatScheduleTimestamp(task.last_execution_at)}</div>
                                  <div className="muted tiny">{formatRelativeTime(task.last_execution_at)}</div>
                                </td>
                                <td>{formatScheduleTimestamp(task.next_execution_at)}</td>
                                <td>{task.last_reason || "-"}</td>
                                <td><code>{task.last_slot_key || "-"}</code></td>
                                <td>{task.detail || "-"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="callout">No scheduled task data is available yet.</div>
                    )}
                  </article>
                </section>
              ) : (
                <section className="grid operational-dashboard-grid">
                  {dashboardWarnings.length ? (
                    <article className="card degraded-state-banner">
                      <div className="card-header">
                        <h2>Operational With Warnings</h2>
                        <p className="muted">The node is operational, but a few runtime signals still need attention.</p>
                      </div>
                      <div className="stack compact-stack">
                        {dashboardWarnings.map((warning) => (
                          <div key={warning} className="callout callout-warning">
                            {warning}
                          </div>
                        ))}
                        <div className="row">
                          <button className="btn" type="button" onClick={() => refreshDashboardState("Governance status refreshed.")}>
                            Refresh Governance
                          </button>
                          <button className="btn" type="button" onClick={openProvider}>
                            Setup Provider
                          </button>
                        </div>
                      </div>
                    </article>
                  ) : null}
                  <article className="card dashboard-primary-card">
                    <div className="card-header">
                      <h2>Node Overview</h2>
                      <p className="muted">Primary home for identity, lifecycle, and trusted pairing summary.</p>
                    </div>
                    <div className="state-grid">
                      <span>Node ID</span>
                      <code>{formatValue(status?.node_id)}</code>
                      <span>Node Name</span>
                      <code>{formatValue(bootstrap?.config?.node_name)}</code>
                      <span>Lifecycle</span>
                      <span className={healthSeverityClass(status?.operational_readiness ? "operational" : "pending", ["operational"])}>
                        <span className="status-badge status-operational">
                          {status?.operational_readiness ? "operational" : setupFlow.current?.label || "pending"}
                        </span>
                      </span>
                      <span>Trust</span>
                      <span className={healthSeverityClass(status?.trust_state, ["trusted"])}>
                        <span className="status-badge status-trusted">{formatValue(status?.trust_state, "untrusted")}</span>
                      </span>
                      <span>Paired Hexe Core</span>
                      <code>{formatValue(status?.paired_core_id)}</code>
                      <span>Software</span>
                      <code>{formatValue(bootstrap?.config?.node_software_version || status?.node_software_version, "0.1.0")}</code>
                      <span>Pairing Timestamp</span>
                      <code>{formatTelemetryTimestamp(status?.trusted_at)}</code>
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Core Connection</h2>
                      <p className="muted">Trusted Core endpoint metadata and current onboarding linkage.</p>
                    </div>
                    <div className="state-grid">
                      <span>Core ID</span>
                      <code>{formatValue(status?.paired_core_id)}</code>
                      <span>Core API</span>
                      <code>{formatValue(bootstrap?.config?.core_base_url)}</code>
                      <span>Operational MQTT</span>
                      <code>
                        {status?.operational_mqtt_host && status?.operational_mqtt_port
                          ? `${status.operational_mqtt_host}:${status.operational_mqtt_port}`
                          : mqttConnected
                            ? "connected"
                            : "pending"}
                      </code>
                      <span>Connection</span>
                      <span className={mqttSeverityClass}>
                        <span className={`health-indicator ${mqttIndicatorClass}`}>
                          <span className="health-dot" />
                          {mqttConnected ? "connected" : formatValue(mqttHealth?.health_status)}
                        </span>
                      </span>
                      <span>Onboarding Ref</span>
                      <code>{maskOnboardingRef(formatValue(onboarding?.session_id, status?.operational_readiness ? "operational" : "pending"))}</code>
                      <span>Telemetry Freshness</span>
                      <span className={healthSeverityClass(mqttHealth?.status_freshness_state, [], ["fresh"])}>
                        <span
                          className={`health-indicator ${telemetryFreshnessIndicatorClass(
                            mqttHealth?.status_freshness_state,
                          )}`}
                        >
                          <span className="health-dot" />
                          {formatValue(mqttHealth?.status_freshness_state)}
                        </span>
                      </span>
                      <span>Telemetry Age</span>
                      <code>{formatAge(mqttHealth?.status_age_s)}</code>
                    </div>
                  </article>

                  <article className="card">
                    <div className="card-header">
                      <h2>Actions</h2>
                      <p className="muted">
                        Operational controls are grouped by purpose so routine actions stay separate from diagnostics and admin tools.
                      </p>
                    </div>
                    <div className="action-groups">
                      <section className="action-group">
                        <div className="action-group-header">
                          <h3>Configuration</h3>
                          <p className="muted tiny">Everyday sync and reconfiguration actions.</p>
                        </div>
                        <div className="row action-group-buttons">
                          <button className="btn" type="button" onClick={openSetup}>Open Setup</button>
                          <button className="btn" type="button" onClick={openProvider}>Setup Gmail Provider</button>
                          <button className="btn" type="button" onClick={() => refreshDashboardState("Governance status refreshed.")}>
                            Refresh Governance
                          </button>
                          <button className="btn" type="button" onClick={() => refreshDashboardState("Provider status refreshed.")}>
                            Refresh Provider Status
                          </button>
                          <button
                            className="btn"
                            type="button"
                            onClick={declareCapabilities}
                            disabled={declaringCapabilities || !form.selected_task_capabilities.length}
                          >
                            {declaringCapabilities ? "Redeclaring..." : "Redeclare Capabilities"}
                          </button>
                        </div>
                      </section>

                      <section className="action-group">
                        <div className="action-group-header">
                          <h3>Runtime Controls</h3>
                          <p className="muted tiny">Service restarts and runtime recovery actions.</p>
                        </div>
                        {serviceControlError ? <div className="callout callout-danger">{serviceControlError}</div> : null}
                        {serviceControlNotice ? <div className="callout callout-success">{serviceControlNotice}</div> : null}
                        <div className="row action-group-buttons">
                          <button
                            className="btn"
                            type="button"
                            onClick={() => restartRuntimeService("backend")}
                            disabled={serviceControlPending !== ""}
                          >
                            {serviceControlPending === "backend" ? "Restarting Backend..." : "Restart Backend"}
                          </button>
                          <button
                            className="btn"
                            type="button"
                            onClick={() => restartRuntimeService("frontend")}
                            disabled={serviceControlPending !== ""}
                          >
                            {serviceControlPending === "frontend" ? "Restarting Frontend..." : "Restart Frontend"}
                          </button>
                          <button className="btn btn-primary" type="button" disabled>Restart Node</button>
                        </div>
                      </section>

                      <section className="action-group action-group-admin">
                        <div className="action-group-header">
                          <h3>Admin &amp; Diagnostics</h3>
                          <p className="muted tiny">Advanced rebuild and inspection actions stay on the diagnostics page.</p>
                        </div>
                        <div className="row action-group-buttons">
                          <button className="btn" type="button" disabled>Open Diagnostics</button>
                        </div>
                      </section>
                    </div>
                  </article>
              </section>
              )}
            </div>
          </section>
        </main>
      </div>
    );
  }

  if (!backendReachable) {
    return (
      <div className="shell">
        <main className="app-frame">
          <BackendUnavailableScreen
            apiBase="/api/node/bootstrap"
            error={error}
            lastUpdatedAt={formatTelemetryTimestamp(uiUpdatedAt) || "never"}
            retrying={retryingBackend}
            onRetry={retryBackendConnection}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="shell">
      <main className="app-frame">
        <section className="hero card">
          <div>
            <div className="hero-topline">
              <div className="eyebrow">Hexe Email Node</div>
              <div className={`status-pill tone-${nodeState.tone}`}>state: {nodeState.label}</div>
            </div>
            <h1>Hexe Email Node Setup</h1>
            <p className="hero-copy">
              Configure the target Core, start onboarding, and watch the node move from local setup to trusted
              operational status.
            </p>
          </div>
          <div className="hero-actions">
            <div className="hero-status">
              <div className={`status-pill tone-${statusTone(onboarding?.onboarding_status)}`}>
                onboarding: {onboarding?.onboarding_status || "loading"}
              </div>
              <div className={`status-pill tone-${statusTone(status?.mqtt_connection_status)}`}>
                mqtt: {status?.mqtt_connection_status || "loading"}
              </div>
            </div>
            <button className="btn btn-ghost" type="button" onClick={restartOnboarding} disabled={restarting}>
              {restarting ? "Restarting..." : "Restart Setup"}
            </button>
            {dashboardEnabled ? (
              <button className="btn btn-ghost" type="button" onClick={openDashboard}>
                Dashboard
              </button>
            ) : null}
            <button className="btn btn-ghost" type="button" onClick={openProvider}>
              Setup Provider
            </button>
          </div>
        </section>

        <section className="app-shell">
          <SetupSidebar flow={setupFlow} />
          <div className="main-column">
            <section className="content-stack">
              {!nodeSetupVisible ? (
                <article className="card stack">
                  <div className="section-heading">
                    <h2>Node Identity</h2>
                    <span className="pill">UI {bootstrap?.config.ui_port || 8083}</span>
                  </div>
                  <Field
                    label="Core base URL"
                    name="core_base_url"
                    value={form.core_base_url}
                    onChange={handleChange}
                    placeholder="http://192.168.1.10:8000"
                    required
                  />
                  <Field
                    label="Node name"
                    name="node_name"
                    value={form.node_name}
                    onChange={handleChange}
                    placeholder="front-desk-email-node"
                    required
                  />
                  <div className="actions">
                    <button className="btn btn-ghost" type="button" onClick={saveConfiguration} disabled={saving}>
                      {saving ? "Saving..." : "Save"}
                    </button>
                    <button className="btn btn-primary" type="button" onClick={startOnboarding} disabled={starting}>
                      {starting ? "Starting..." : "Start Onboarding"}
                    </button>
                  </div>
                  {requiredInputs.length > 0 ? <div className="callout callout-warning">Required before onboarding: {requiredInputs.join(", ")}</div> : null}
                </article>
              ) : null}

              {nodeSetupVisible ? (
                <article className="card stack">
                  <div className="section-heading">
                    <h2>Node Setup</h2>
                    <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
                  </div>
                  <div className="status-rail">
                    <div className={`status-pill tone-${statusTone(onboarding?.onboarding_status)}`}>
                      lifecycle: {onboarding?.onboarding_status || "not_started"}
                    </div>
                    <div className={`status-pill tone-${statusTone(status?.trust_state)}`}>trust: {status?.trust_state || "untrusted"}</div>
                    <div className={`status-pill tone-${statusTone(status?.governance_sync_status)}`}>
                      governance: {status?.governance_sync_status || "pending"}
                    </div>
                    <div className={`status-pill tone-${status?.trust_state === "trusted" ? "success" : "neutral"}`}>
                      core: {status?.trust_state === "trusted" ? "paired" : "not paired"}
                    </div>
                  </div>
                  {renderCurrentStageCard({
                    flow: setupFlow,
                    bootstrap,
                    status,
                    onboarding,
                    requiredInputs,
                    notice,
                    error,
                    setView,
                    form,
                    saving,
                    declaringCapabilities,
                    onCapabilityToggle: handleCapabilityToggle,
                    onSaveConfiguration: saveConfiguration,
                    onDeclareCapabilities: declareCapabilities,
                  })}
                </article>
              ) : null}

              <section className="grid setup-secondary-grid">
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

                <article className="card stack">
                  <div className="section-heading">
                    <h2>Operator Prompts</h2>
                    <span className="pill">{setupFlow.current?.label || "Idle"}</span>
                  </div>
                  <ul className="prompt-list">
                    {requiredInputs.length > 0 ? <li>Enter the Core base URL and node name, then save or start onboarding.</li> : null}
                    {onboarding?.approval_url ? <li>Open the approval URL in Core and approve the node.</li> : null}
                    {onboarding?.onboarding_status === "pending" ? <li>Keep this page open while finalize polling continues.</li> : null}
                    <li>Use Restart Setup if you need a fresh onboarding session.</li>
                    {status?.trust_state === "trusted" ? <li>The node is trusted. Use Setup Provider to configure Gmail.</li> : null}
                    {!requiredInputs.length && !onboarding?.approval_url && status?.trust_state !== "trusted" ? <li>Start onboarding when you are ready.</li> : null}
                  </ul>
                </article>
              </section>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}
