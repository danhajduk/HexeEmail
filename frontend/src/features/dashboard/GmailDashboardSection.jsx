import { SenderReputationPanel } from "../training/SenderReputationPage";

export function GmailDashboardSection({
  gmailStatusError,
  gmailStatus,
  providerSummary,
  gmailPrimaryAccount,
  gmailPrimaryMailboxStatus,
  gmailStatusLoading,
  gmailPrimaryStore,
  gmailPrimaryClassification,
  gmailPrimarySpamhaus,
  gmailPrimaryQuotaUsage,
  gmailPrimarySenderReputation,
  gmailActionError,
  gmailActionNotice,
  gmailActionPending,
  runGmailFetch,
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
  gmailFetchScheduler,
  healthSeverityClass,
  formatScheduleTimestamp,
  gmailWindowSettings,
  senderReputationTone,
  formatSenderReputationInputs,
  formatTelemetryTimestamp,
}) {
  return (
    <section className="grid operational-dashboard-grid">
      <article className="card dashboard-primary-card">
        <div className="card-header">
          <h2>Gmail Status</h2>
          <p className="muted">Background Gmail inbox status and unread counts.</p>
        </div>
        {gmailStatusError ? <div className="callout callout-danger">{gmailStatusError}</div> : null}
        <dl className="facts">
          <div><dt>Provider State</dt><dd>{gmailStatus?.provider_state || providerSummary?.provider_state || "pending"}</dd></div>
          <div><dt>Account</dt><dd>{gmailPrimaryAccount?.email_address || gmailPrimaryAccount?.account_id || "Pending"}</dd></div>
          <div><dt>Unread Today</dt><dd>{gmailPrimaryMailboxStatus?.unread_today_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd></div>
          <div><dt>Unread Yesterday</dt><dd>{gmailPrimaryMailboxStatus?.unread_yesterday_count ?? (gmailStatusLoading ? "Loading..." : 0)}</dd></div>
          <div><dt>Stored Emails</dt><dd>{gmailPrimaryStore?.total_count ?? 0}</dd></div>
          <div><dt>Classified Emails</dt><dd>{gmailPrimaryClassification?.classified_count ?? 0}</dd></div>
          <div><dt>High Confidence</dt><dd>{gmailPrimaryClassification?.high_confidence_count ?? 0}</dd></div>
          <div><dt>Spamhaus Checked</dt><dd>{gmailPrimarySpamhaus?.checked_count ?? 0}</dd></div>
          <div><dt>Spamhaus Pending</dt><dd>{gmailPrimarySpamhaus?.pending_count ?? 0}</dd></div>
          <div><dt>Spamhaus Listed</dt><dd>{gmailPrimarySpamhaus?.listed_count ?? 0}</dd></div>
          <div><dt>Quota Used / Min</dt><dd>{gmailPrimaryQuotaUsage ? `${gmailPrimaryQuotaUsage.used_last_minute}/${gmailPrimaryQuotaUsage.limit_per_minute}` : 0}</dd></div>
          <div><dt>Quota Remaining</dt><dd>{gmailPrimaryQuotaUsage?.remaining_last_minute ?? 15000}</dd></div>
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
            senderReputationTone={senderReputationTone}
            formatSenderReputationInputs={formatSenderReputationInputs}
            formatTelemetryTimestamp={formatTelemetryTimestamp}
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
          <div><dt>Last Check</dt><dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_checked_at)}</dd></div>
          <div><dt>Last Success</dt><dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_success_at)}</dd></div>
          <div><dt>Last Error</dt><dd>{gmailFetchScheduler?.last_error || "-"}</dd></div>
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
                <div><dt>Fetched</dt><dd>{formatScheduleTimestamp(windowSetting.fetchedAt)}</dd></div>
                <div><dt>Schedule</dt><dd>{windowSetting.schedule}</dd></div>
              </dl>
            </section>
          ))}
        </div>
      </article>
    </section>
  );
}
