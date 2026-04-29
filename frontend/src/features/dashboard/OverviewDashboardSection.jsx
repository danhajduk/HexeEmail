import { CoreConnectionCard } from "./cards/CoreConnectionCard";
import { DashboardActionsCard } from "./cards/DashboardActionsCard";
import { NodeOverviewCard } from "./cards/NodeOverviewCard";
import { OperationalWarningsCard } from "./cards/OperationalWarningsCard";

export function OverviewDashboardSection({
  dashboardWarnings,
  refreshDashboardState,
  openProvider,
  status,
  bootstrap,
  setupFlow,
  formatValue,
  healthSeverityClass,
  formatTelemetryTimestamp,
  mqttConnected,
  mqttHealth,
  mqttSeverityClass,
  mqttIndicatorClass,
  maskOnboardingRef,
  onboarding,
  telemetryFreshnessIndicatorClass,
  formatAge,
  serviceControlError,
  serviceControlNotice,
  restartRuntimeService,
  serviceControlPending,
  openSetup,
  declareCapabilities,
  declaringCapabilities,
  form,
}) {
  return (
    <section className="grid operational-dashboard-grid">
      <OperationalWarningsCard dashboardWarnings={dashboardWarnings} refreshDashboardState={refreshDashboardState} openProvider={openProvider} />
      <NodeOverviewCard
        status={status}
        bootstrap={bootstrap}
        setupFlow={setupFlow}
        formatValue={formatValue}
        healthSeverityClass={healthSeverityClass}
        formatTelemetryTimestamp={formatTelemetryTimestamp}
      />
      <CoreConnectionCard
        status={status}
        bootstrap={bootstrap}
        mqttConnected={mqttConnected}
        mqttHealth={mqttHealth}
        mqttSeverityClass={mqttSeverityClass}
        mqttIndicatorClass={mqttIndicatorClass}
        maskOnboardingRef={maskOnboardingRef}
        onboarding={onboarding}
        telemetryFreshnessIndicatorClass={telemetryFreshnessIndicatorClass}
        healthSeverityClass={healthSeverityClass}
        formatValue={formatValue}
        formatAge={formatAge}
      />
      <DashboardActionsCard
        openSetup={openSetup}
        openProvider={openProvider}
        refreshDashboardState={refreshDashboardState}
        declareCapabilities={declareCapabilities}
        declaringCapabilities={declaringCapabilities}
        form={form}
        serviceControlError={serviceControlError}
        serviceControlNotice={serviceControlNotice}
        restartRuntimeService={restartRuntimeService}
        serviceControlPending={serviceControlPending}
      />
    </section>
  );
}
