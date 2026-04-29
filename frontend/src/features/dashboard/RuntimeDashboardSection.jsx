import { RuntimeActionsCard } from "./cards/RuntimeActionsCard";
import { RuntimeSettingsCard } from "./cards/RuntimeSettingsCard";
import { RuntimeStatusCard } from "./cards/RuntimeStatusCard";

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
      <RuntimeStatusCard
        runtimeTaskError={runtimeTaskError}
        runtimeTaskNotice={runtimeTaskNotice}
        runtimeTaskStatus={runtimeTaskStatus}
        runtimeTaskForm={runtimeTaskForm}
        runtimeResolved={runtimeResolved}
        runtimeAuthorized={runtimeAuthorized}
        runtimeExecution={runtimeExecution}
        runtimeExecutionOutput={runtimeExecutionOutput}
        runtimeExecutionMetrics={runtimeExecutionMetrics}
        runtimeAuthorizationGranted={runtimeAuthorizationGranted}
        formatTelemetryTimestamp={formatTelemetryTimestamp}
      />
      <RuntimeSettingsCard
        runtimeTaskForm={runtimeTaskForm}
        runtimeTaskPending={runtimeTaskPending}
        updateRuntimeAiCallsEnabled={updateRuntimeAiCallsEnabled}
        updateRuntimeProviderCallsEnabled={updateRuntimeProviderCallsEnabled}
        updateRuntimeUserNotificationsEnabled={updateRuntimeUserNotificationsEnabled}
        updateRuntimeClassificationEnabled={updateRuntimeClassificationEnabled}
        updateRuntimeOrderChecksEnabled={updateRuntimeOrderChecksEnabled}
        updateRuntimeActionRequiredFlowEnabled={updateRuntimeActionRequiredFlowEnabled}
        updateRuntimeFinancialFlowEnabled={updateRuntimeFinancialFlowEnabled}
        updateRuntimeInvoiceFlowEnabled={updateRuntimeInvoiceFlowEnabled}
        updateRuntimeShipmentFlowEnabled={updateRuntimeShipmentFlowEnabled}
        updateRuntimeSecurityFlowEnabled={updateRuntimeSecurityFlowEnabled}
      />
      <RuntimeActionsCard
        runtimeTaskPending={runtimeTaskPending}
        runRuntimeResolveFlow={runRuntimeResolveFlow}
        runtimeTaskForm={runtimeTaskForm}
        runtimeResolved={runtimeResolved}
        runRuntimeAuthorize={runRuntimeAuthorize}
        runRuntimeRegisterPrompt={runRuntimeRegisterPrompt}
        runRuntimeExecuteEmailClassifier={runRuntimeExecuteEmailClassifier}
        runRuntimeExecuteLatestEmailActionDecision={runRuntimeExecuteLatestEmailActionDecision}
        runRuntimePreview={runRuntimePreview}
        runRuntimeResolve={runRuntimeResolve}
        runtimePreview={runtimePreview}
        runtimeAuthorized={runtimeAuthorized}
        runtimeExecution={runtimeExecution}
      />
    </section>
  );
}
