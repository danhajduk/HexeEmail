export function RuntimeDashboardSection({
  runtimeTaskError,
  runtimeTaskNotice,
  runtimeTaskStatus,
  runtimeTaskForm,
  runtimeResolved,
  runtimeAuthorized,
  runtimeExecution,
  runtimeExecutionOutput,
  runtimeExecutionMetrics,
  runtimeTaskPending,
  handleRuntimeTaskFormChange,
  updateRuntimeAiCallsEnabled,
  runRuntimeResolveFlow,
  runRuntimeAuthorize,
  runRuntimeRegisterPrompt,
  runRuntimeExecuteEmailClassifier,
  runRuntimeExecuteLatestEmailActionDecision,
  runRuntimePreview,
  runRuntimeResolve,
  runtimePreview,
  runtimeAuthorizationGranted,
  formatTelemetryTimestamp,
}) {
  return (
    <section className="grid operational-dashboard-grid">
      <article className="card dashboard-primary-card">
        <div className="card-header">
          <h2>Runtime Status</h2>
          <p className="muted">Latest Core routing state and AI-node prompt registration status for the current task request.</p>
        </div>
        {runtimeTaskError ? <div className="callout callout-danger">{runtimeTaskError}</div> : null}
        {runtimeTaskNotice ? <div className="callout callout-success">{runtimeTaskNotice}</div> : null}
        <dl className="facts">
          <div><dt>AI Calls</dt><dd>{runtimeTaskStatus?.ai_calls_enabled === false ? "disabled" : "enabled"}</dd></div>
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

      <article className="card">
        <div className="card-header">
          <h2>Runtime Settings</h2>
          <p className="muted">Configure the task request that will be previewed, resolved, and authorized through Core.</p>
        </div>
        <div className="stack compact-stack">
          <label className="field">
            <span className="field-label">AI Calls</span>
            <button
              type="button"
              className={`toggle ${runtimeTaskForm.ai_calls_enabled ? "is-on" : ""}`}
              aria-pressed={runtimeTaskForm.ai_calls_enabled}
              disabled={runtimeTaskPending !== ""}
              onClick={() => updateRuntimeAiCallsEnabled(!runtimeTaskForm.ai_calls_enabled)}
            >
              <span className="toggle-thumb" />
              <span>{runtimeTaskForm.ai_calls_enabled ? "Enabled" : "Disabled"}</span>
            </button>
          </label>
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
          <button type="button" className="btn btn-primary" disabled={runtimeTaskPending !== ""} onClick={runRuntimeResolveFlow}>
            {runtimeTaskPending === "preview" || runtimeTaskPending === "resolve" || runtimeTaskPending === "authorize"
              ? "Running..."
              : "Start Task Resolve"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={runtimeTaskPending !== "" || !(runtimeTaskForm.service_id || runtimeResolved?.selected_service_id || runtimeResolved?.service_id)}
            onClick={() => runRuntimeAuthorize()}
          >
            {runtimeTaskPending === "authorize" ? "Authorizing..." : "Start Task Authorize"}
          </button>
          <button type="button" className="btn btn-primary" disabled={runtimeTaskPending !== ""} onClick={runRuntimeRegisterPrompt}>
            {runtimeTaskPending === "register" ? "Syncing..." : "Sync Prompts On AI Node"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={runtimeTaskPending !== "" || !runtimeTaskForm.ai_calls_enabled}
            onClick={runRuntimeExecuteEmailClassifier}
          >
            {runtimeTaskPending === "execute" ? "Sending..." : "Send Newest Unknown Mail To Classifier"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={runtimeTaskPending !== "" || !runtimeTaskForm.ai_calls_enabled}
            onClick={runRuntimeExecuteLatestEmailActionDecision}
          >
            {runtimeTaskPending === "execute" ? "Sending..." : "Send Latest Action Needed / Order To AI"}
          </button>
          <div className="row gmail-fetch-row">
            <button type="button" className="btn" disabled={runtimeTaskPending !== ""} onClick={runRuntimePreview}>
              Debug Preview
            </button>
            <button type="button" className="btn" disabled={runtimeTaskPending !== ""} onClick={runRuntimeResolve}>
              Debug Resolve
            </button>
            <button type="button" className="btn" disabled={runtimeTaskPending !== ""} onClick={() => runRuntimeAuthorize(runtimeResolved)}>
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
  );
}
