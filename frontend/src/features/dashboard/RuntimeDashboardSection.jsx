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
  updateRuntimeProviderCallsEnabled,
  updateRuntimeUserNotificationsEnabled,
  updateRuntimeClassificationEnabled,
  updateRuntimeOrderChecksEnabled,
  updateRuntimeActionRequiredFlowEnabled,
  updateRuntimeFinancialFlowEnabled,
  updateRuntimeInvoiceFlowEnabled,
  updateRuntimeShipmentFlowEnabled,
  updateRuntimeSecurityFlowEnabled,
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

      <article className="card">
        <div className="card-header">
          <h2>Runtime Settings</h2>
          <p className="muted">Configure the task request that will be previewed, resolved, and authorized through Core.</p>
        </div>
        <div className="stack compact-stack">
          <div className="runtime-switch-groups">
            <div className="runtime-switch-group">
              <div className="runtime-switch-group-header">Calls</div>
              <div className="runtime-switch-card">
                <div className="runtime-switch-grid">
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.ai_calls_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.ai_calls_enabled}
                    aria-label={runtimeTaskForm.ai_calls_enabled ? "Disable AI calls" : "Enable AI calls"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeAiCallsEnabled(!runtimeTaskForm.ai_calls_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>AI</span>
                    <span className="sr-only">{runtimeTaskForm.ai_calls_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                  </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.provider_calls_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.provider_calls_enabled}
                    aria-label={runtimeTaskForm.provider_calls_enabled ? "Disable provider calls" : "Enable provider calls"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeProviderCallsEnabled(!runtimeTaskForm.provider_calls_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Provider</span>
                    <span className="sr-only">{runtimeTaskForm.provider_calls_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                  </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.user_notifications_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.user_notifications_enabled}
                    aria-label={runtimeTaskForm.user_notifications_enabled ? "Disable user notifications" : "Enable user notifications"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeUserNotificationsEnabled(!runtimeTaskForm.user_notifications_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Notify</span>
                    <span className="sr-only">{runtimeTaskForm.user_notifications_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                </div>
              </div>
            </div>
            <div className="runtime-switch-group">
              <div className="runtime-switch-group-header">Analysis</div>
              <div className="runtime-switch-card">
                <div className="runtime-switch-grid">
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.classification_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.classification_enabled}
                    aria-label={runtimeTaskForm.classification_enabled ? "Disable classification" : "Enable classification"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeClassificationEnabled(!runtimeTaskForm.classification_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Clasify</span>
                    <span className="sr-only">{runtimeTaskForm.classification_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                <div className="field runtime-switch-item runtime-switch-item-disabled" aria-hidden="true">
                  <span className="runtime-switch-pill is-off">
                    <span className="runtime-switch-led" />
                    <span>Local</span>
                  </span>
                </div>
                </div>
              </div>
            </div>
            <div className="runtime-switch-group">
              <div className="runtime-switch-group-header">Label Family Flows</div>
              <div className="runtime-switch-card">
                <div className="runtime-switch-grid">
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.action_required_flow_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.action_required_flow_enabled}
                    aria-label={runtimeTaskForm.action_required_flow_enabled ? "Disable action required flow" : "Enable action required flow"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeActionRequiredFlowEnabled(!runtimeTaskForm.action_required_flow_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Action</span>
                    <span className="sr-only">{runtimeTaskForm.action_required_flow_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.order_checks_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.order_checks_enabled}
                    aria-label={runtimeTaskForm.order_checks_enabled ? "Disable order analysis" : "Enable order analysis"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeOrderChecksEnabled(!runtimeTaskForm.order_checks_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Order</span>
                    <span className="sr-only">{runtimeTaskForm.order_checks_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.financial_flow_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.financial_flow_enabled}
                    aria-label={runtimeTaskForm.financial_flow_enabled ? "Disable financial flow" : "Enable financial flow"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeFinancialFlowEnabled(!runtimeTaskForm.financial_flow_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Financial</span>
                    <span className="sr-only">{runtimeTaskForm.financial_flow_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.invoice_flow_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.invoice_flow_enabled}
                    aria-label={runtimeTaskForm.invoice_flow_enabled ? "Disable invoice flow" : "Enable invoice flow"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeInvoiceFlowEnabled(!runtimeTaskForm.invoice_flow_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Invoice</span>
                    <span className="sr-only">{runtimeTaskForm.invoice_flow_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.shipment_flow_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.shipment_flow_enabled}
                    aria-label={runtimeTaskForm.shipment_flow_enabled ? "Disable shipment flow" : "Enable shipment flow"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeShipmentFlowEnabled(!runtimeTaskForm.shipment_flow_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Shipment</span>
                    <span className="sr-only">{runtimeTaskForm.shipment_flow_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                  <label className="field runtime-switch-item">
                  <button
                    type="button"
                    className={`runtime-switch-pill runtime-switch-button ${runtimeTaskForm.security_flow_enabled ? "is-on" : "is-off"}`}
                    aria-pressed={runtimeTaskForm.security_flow_enabled}
                    aria-label={runtimeTaskForm.security_flow_enabled ? "Disable security flow" : "Enable security flow"}
                    disabled={runtimeTaskPending !== ""}
                    onClick={() => updateRuntimeSecurityFlowEnabled(!runtimeTaskForm.security_flow_enabled)}
                  >
                    <span className="runtime-switch-led" />
                    <span>Security</span>
                    <span className="sr-only">{runtimeTaskForm.security_flow_enabled ? "Enabled" : "Disabled"}</span>
                  </button>
                </label>
                </div>
              </div>
            </div>
          </div>
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
          <button
            type="button"
            className="btn btn-primary"
            disabled={runtimeTaskPending !== "" || !runtimeTaskForm.ai_calls_enabled}
            onClick={runRuntimeRegisterPrompt}
          >
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
