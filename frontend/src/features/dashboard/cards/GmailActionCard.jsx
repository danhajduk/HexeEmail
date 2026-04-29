export function GmailActionCard({
  gmailActionError,
  gmailActionNotice,
  gmailActionPending,
  runGmailFetch,
  gmailPrimaryStore,
  runSpamhausCheck,
  runSenderReputationRefresh,
  openTraining,
  runtimeTaskPending,
  runRuntimeExecuteEmailClassifierBatch,
  runtimeTaskForm,
  runtimeBatchExecution,
  runtimeBatchProgressPercent,
  gmailLastHourPipelinePills,
  pipelineStageClass,
}) {
  return (
    <article className="card">
      <div className="card-header">
        <h2>Gmail Action</h2>
        <p className="muted">Manual Gmail fetch actions for initial learning and time-window refresh.</p>
      </div>
      <div className="stack compact-stack">
        {gmailActionError ? <div className="callout callout-danger">{gmailActionError}</div> : null}
        {gmailActionNotice ? <div className="callout callout-success">{gmailActionNotice}</div> : null}
        <button type="button" className="btn" disabled={gmailActionPending !== ""} onClick={() => runGmailFetch("initial_learning", "Initial learning fetch")}>
          Fetch Initial Learning
        </button>
        <button type="button" className="btn" disabled={gmailActionPending !== "" || (gmailPrimaryStore?.total_count ?? 0) === 0} onClick={runSpamhausCheck}>
          Check With Spamhaus
        </button>
        <button type="button" className="btn" disabled={gmailActionPending !== "" || (gmailPrimaryStore?.total_count ?? 0) === 0} onClick={runSenderReputationRefresh}>
          Calculate Sender Reputation
        </button>
        <button type="button" className="btn" onClick={openTraining}>
          Open Training
        </button>
        <div className="row gmail-fetch-row">
          <button type="button" className="btn" disabled={gmailActionPending !== ""} onClick={() => runGmailFetch("today", "Today poll")}>
            Poll Today
          </button>
          <button type="button" className="btn" disabled={gmailActionPending !== ""} onClick={() => runGmailFetch("yesterday", "Yesterday poll")}>
            Poll Yesterday
          </button>
          <button type="button" className="btn" disabled={gmailActionPending !== ""} onClick={() => runGmailFetch("last_hour", "Last hour poll")}>
            Poll Last Hour
          </button>
        </div>
        <button type="button" className="btn" disabled={runtimeTaskPending !== "" || gmailActionPending !== ""} onClick={runRuntimeExecuteEmailClassifierBatch}>
          {runtimeTaskPending === "execute_batch"
            ? "Processing..."
            : runtimeTaskForm.ai_calls_enabled
              ? "Local Classify 100, Send Unknown To AI"
              : "Local Classify 100, Skip AI"}
        </button>
        {runtimeBatchExecution ? (
          <div className="stack compact-stack">
            <div className="muted tiny">
              AI Batch Progress: {runtimeBatchExecution?.ai_attempted ?? runtimeBatchExecution?.ai_completed ?? 0}/{runtimeBatchExecution?.ai_total ?? 0}
            </div>
            <div className="runtime-progress-shell">
              <div className="runtime-progress-bar" style={{ width: `${runtimeBatchProgressPercent}%` }} />
            </div>
            <div className="muted tiny">
              Stage: {runtimeBatchExecution?.stage || "-"} | Local Classified: {runtimeBatchExecution?.local_classified ?? 0} | Batch Size: {runtimeBatchExecution?.batch_size ?? 0}
            </div>
            {runtimeBatchExecution?.last_execution?.error_code || runtimeBatchExecution?.last_execution?.error_message ? (
              <div className="callout callout-danger">
                Last AI execution failed: {runtimeBatchExecution?.last_execution?.error_code || "error"}
                {runtimeBatchExecution?.last_execution?.error_message ? ` (${runtimeBatchExecution.last_execution.error_message})` : ""}
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
  );
}
