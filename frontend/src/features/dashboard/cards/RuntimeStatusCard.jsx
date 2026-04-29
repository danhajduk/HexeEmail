export function RuntimeStatusCard({
  runtimeTaskError,
  runtimeTaskNotice,
  runtimeTaskStatus,
  runtimeTaskForm,
  runtimeResolved,
  runtimeAuthorized,
  runtimeExecution,
  runtimeExecutionOutput,
  runtimeExecutionMetrics,
  runtimeAuthorizationGranted,
  formatTelemetryTimestamp,
}) {
  return (
    <article className="card dashboard-primary-card">
      <div className="card-header">
        <h2>Runtime Status</h2>
        <p className="muted">Latest Core routing state and AI-node prompt registration status for the current task request.</p>
      </div>
      {runtimeTaskError ? <div className="callout callout-danger">{runtimeTaskError}</div> : null}
      {runtimeTaskNotice ? <div className="callout callout-success">{runtimeTaskNotice}</div> : null}
      <dl className="facts">
        <div><dt>AI Calls</dt><dd>{runtimeTaskStatus?.ai_calls_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Provider Calls</dt><dd>{runtimeTaskStatus?.provider_calls_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>User Notifications</dt><dd>{runtimeTaskStatus?.user_notifications_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Clasify</dt><dd>{runtimeTaskStatus?.classification_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Check Orders</dt><dd>{runtimeTaskStatus?.order_checks_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Action Required Flow</dt><dd>{runtimeTaskStatus?.action_required_flow_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Financial Flow</dt><dd>{runtimeTaskStatus?.financial_flow_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Invoice Flow</dt><dd>{runtimeTaskStatus?.invoice_flow_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Shipment Flow</dt><dd>{runtimeTaskStatus?.shipment_flow_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Security Flow</dt><dd>{runtimeTaskStatus?.security_flow_enabled === false ? "disabled" : "enabled"}</dd></div>
        <div><dt>Request Status</dt><dd>{runtimeTaskStatus?.request_status || "idle"}</dd></div>
        <div><dt>Last Step</dt><dd>{runtimeTaskStatus?.last_step || "none"}</dd></div>
        <div><dt>Requested Node Type</dt><dd>{runtimeTaskForm.requested_node_type}</dd></div>
        <div><dt>Task Family</dt><dd>{runtimeTaskForm.task_family}</dd></div>
        <div><dt>Resolved Service</dt><dd>{runtimeResolved?.selected_service_id || runtimeResolved?.service_id || "-"}</dd></div>
        <div><dt>Resolved Provider</dt><dd>{runtimeResolved?.provider || "-"}</dd></div>
        <div><dt>Resolved Model</dt><dd>{runtimeResolved?.model_id || "-"}</dd></div>
        <div><dt>Authorization</dt><dd>{runtimeAuthorized ? (runtimeAuthorizationGranted(runtimeAuthorized) ? "authorized" : "rejected") : "-"}</dd></div>
        <div><dt>Authorization ID</dt><dd>{runtimeAuthorized?.authorization_id || "-"}</dd></div>
        <div><dt>Grant ID</dt><dd>{runtimeAuthorized?.grant_id || "-"}</dd></div>
        <div><dt>Started</dt><dd>{formatTelemetryTimestamp(runtimeTaskStatus?.started_at)}</dd></div>
        <div><dt>Updated</dt><dd>{formatTelemetryTimestamp(runtimeTaskStatus?.updated_at)}</dd></div>
        <div><dt>Execution Status</dt><dd>{runtimeExecution?.status || "-"}</dd></div>
        <div><dt>Output Label</dt><dd>{runtimeExecutionOutput?.label || "-"}</dd></div>
        <div><dt>Output Confidence</dt><dd>{runtimeExecutionOutput?.confidence ?? "-"}</dd></div>
        <div><dt>Output Rationale</dt><dd>{runtimeExecutionOutput?.rationale || "-"}</dd></div>
        <div><dt>Provider Used</dt><dd>{runtimeExecution?.provider_used || "-"}</dd></div>
        <div><dt>Model Used</dt><dd>{runtimeExecution?.model_used || "-"}</dd></div>
        <div><dt>Total Tokens</dt><dd>{runtimeExecutionMetrics?.total_tokens ?? "-"}</dd></div>
        <div><dt>Completed</dt><dd>{formatTelemetryTimestamp(runtimeExecution?.completed_at)}</dd></div>
      </dl>
      <div className="callout">
        {runtimeTaskStatus?.detail || "No runtime task request has been started yet."}
      </div>
    </article>
  );
}
