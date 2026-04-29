export function RuntimeActionsCard({
  runtimeTaskPending,
  runRuntimeResolveFlow,
  runtimeTaskForm,
  runtimeResolved,
  runRuntimeAuthorize,
  runRuntimeRegisterPrompt,
  runRuntimeExecuteEmailClassifier,
  runRuntimeExecuteLatestEmailActionDecision,
  runRuntimePreview,
  runRuntimeResolve,
  runtimePreview,
  runtimeAuthorized,
  runtimeExecution,
}) {
  return (
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
  );
}
