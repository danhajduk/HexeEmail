import { GmailActionCard } from "./cards/GmailActionCard";
import { GmailSettingsCard } from "./cards/GmailSettingsCard";
import { GmailStatusCard } from "./cards/GmailStatusCard";
import { SenderReputationDashboardCard } from "./cards/SenderReputationDashboardCard";

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
  gmailPrimaryRules,
  onSaveGmailRules,
  senderReputationTone,
  formatSenderReputationInputs,
  formatTelemetryTimestamp,
}) {
  return (
    <section className="grid operational-dashboard-grid">
      <GmailStatusCard
        gmailStatusError={gmailStatusError}
        gmailStatus={gmailStatus}
        providerSummary={providerSummary}
        gmailPrimaryAccount={gmailPrimaryAccount}
        gmailPrimaryMailboxStatus={gmailPrimaryMailboxStatus}
        gmailStatusLoading={gmailStatusLoading}
        gmailPrimaryStore={gmailPrimaryStore}
        gmailPrimaryClassification={gmailPrimaryClassification}
        gmailPrimarySpamhaus={gmailPrimarySpamhaus}
        gmailPrimaryQuotaUsage={gmailPrimaryQuotaUsage}
      />

      <div className="content-stack">
        <SenderReputationDashboardCard
          gmailPrimarySenderReputation={gmailPrimarySenderReputation}
          senderReputationTone={senderReputationTone}
          formatSenderReputationInputs={formatSenderReputationInputs}
          formatTelemetryTimestamp={formatTelemetryTimestamp}
        />
        <GmailActionCard
          gmailActionError={gmailActionError}
          gmailActionNotice={gmailActionNotice}
          gmailActionPending={gmailActionPending}
          runGmailFetch={runGmailFetch}
          gmailPrimaryStore={gmailPrimaryStore}
          runSpamhausCheck={runSpamhausCheck}
          runSenderReputationRefresh={runSenderReputationRefresh}
          openTraining={openTraining}
          runtimeTaskPending={runtimeTaskPending}
          runRuntimeExecuteEmailClassifierBatch={runRuntimeExecuteEmailClassifierBatch}
          runtimeTaskForm={runtimeTaskForm}
          runtimeBatchExecution={runtimeBatchExecution}
          runtimeBatchProgressPercent={runtimeBatchProgressPercent}
          gmailLastHourPipelinePills={gmailLastHourPipelinePills}
          pipelineStageClass={pipelineStageClass}
        />
      </div>

      <GmailSettingsCard
        gmailFetchScheduler={gmailFetchScheduler}
        healthSeverityClass={healthSeverityClass}
        formatScheduleTimestamp={formatScheduleTimestamp}
        gmailWindowSettings={gmailWindowSettings}
        gmailRules={gmailPrimaryRules}
        onSaveGmailRules={onSaveGmailRules}
      />
    </section>
  );
}
