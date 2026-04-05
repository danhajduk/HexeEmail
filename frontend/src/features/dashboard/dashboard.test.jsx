import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GmailDashboardSection } from "./GmailDashboardSection";
import { OverviewDashboardSection } from "./OverviewDashboardSection";
import { RuntimeDashboardSection } from "./RuntimeDashboardSection";
import { ScheduledTasksSection } from "./ScheduledTasksSection";
import { TrackedOrdersSection } from "./TrackedOrdersSection";

function render(element) {
  return renderToStaticMarkup(element);
}

describe("dashboard feature sections", () => {
  it("renders the Gmail dashboard section", () => {
    const html = render(
      <GmailDashboardSection
        gmailStatusError=""
        gmailStatus={{ provider_state: "connected" }}
        providerSummary={{ provider_state: "connected" }}
        gmailPrimaryAccount={{ email_address: "test@example.com" }}
        gmailPrimaryMailboxStatus={{ unread_today_count: 3, unread_yesterday_count: 2 }}
        gmailStatusLoading={false}
        gmailPrimaryStore={{ total_count: 42 }}
        gmailPrimaryClassification={{ classified_count: 20, high_confidence_count: 12 }}
        gmailPrimarySpamhaus={{ checked_count: 10, pending_count: 1, listed_count: 0 }}
        gmailPrimaryQuotaUsage={{ used_last_minute: 12, limit_per_minute: 15000, remaining_last_minute: 14988 }}
        gmailPrimarySenderReputation={{ total_count: 1, by_state: { trusted: 1, risky: 0, blocked: 0 } }}
        gmailActionError=""
        gmailActionNotice=""
        gmailActionPending=""
        runGmailFetch={() => {}}
        runSpamhausCheck={() => {}}
        runSenderReputationRefresh={() => {}}
        openTraining={() => {}}
        runtimeTaskPending=""
        runRuntimeExecuteEmailClassifierBatch={() => {}}
        runtimeTaskForm={{ ai_calls_enabled: true }}
        runtimeBatchExecution={null}
        runtimeBatchProgressPercent={0}
        gmailLastHourPipelinePills={[{ key: "fetch", label: "fetch", value: "done" }]}
        pipelineStageClass={() => "status-pill"}
        gmailFetchScheduler={{ status: "completed", loop_active: true, detail: "ok" }}
        healthSeverityClass={() => "status-pill"}
        formatScheduleTimestamp={(value) => value || "-"}
        gmailWindowSettings={[{ key: "today", label: "Today", runReason: "scheduled", fetchedAt: "now", schedule: "00:00" }]}
        senderReputationTone={() => "success"}
        formatSenderReputationInputs={() => "signals"}
        formatTelemetryTimestamp={() => "-"}
      />,
    );

    expect(html).toContain("Gmail Status");
    expect(html).toContain("Fetch Initial Learning");
    expect(html).toContain("Gmail Settings");
  });

  it("renders the overview dashboard section", () => {
    const html = render(
      <OverviewDashboardSection
        dashboardWarnings={["governance lagging"]}
        refreshDashboardState={() => {}}
        openProvider={() => {}}
        status={{ node_id: "node-1", trust_state: "trusted", paired_core_id: "core-1", operational_readiness: true }}
        bootstrap={{ config: { node_name: "email-node", core_base_url: "http://core", node_software_version: "1.0.0" } }}
        setupFlow={{ current: { label: "Ready" } }}
        formatValue={(value, fallback = "pending") => value || fallback}
        healthSeverityClass={() => "status-pill"}
        formatTelemetryTimestamp={() => "now"}
        mqttConnected
        mqttHealth={{ health_status: "ok", status_freshness_state: "fresh", status_age_s: 5 }}
        mqttSeverityClass="status-pill"
        mqttIndicatorClass="health-connected"
        maskOnboardingRef={(value) => value}
        onboarding={{ session_id: "session-1" }}
        telemetryFreshnessIndicatorClass={() => "health-fresh"}
        formatAge={() => "5s"}
        serviceControlError=""
        serviceControlNotice=""
        restartRuntimeService={() => {}}
        serviceControlPending=""
        openSetup={() => {}}
        declareCapabilities={() => {}}
        declaringCapabilities={false}
        form={{ selected_task_capabilities: ["task.classification"] }}
      />,
    );

    expect(html).toContain("Node Overview");
    expect(html).toContain("Core Connection");
    expect(html).toContain("Operational With Warnings");
  });

  it("renders runtime, scheduled, and tracked-order sections", () => {
    const runtimeHtml = render(
      <RuntimeDashboardSection
        runtimeTaskError=""
        runtimeTaskNotice=""
        runtimeTaskStatus={{ ai_calls_enabled: true, request_status: "idle", last_step: "none", detail: "ready" }}
        runtimeTaskForm={{
          ai_calls_enabled: true,
          requested_node_type: "ai",
          task_family: "task.classification",
          content_type: "email",
          preferred_provider: "openai",
          preferred_model: "",
          service_id: "",
          target_api_base_url: "http://127.0.0.1:9002",
          email_subject: "",
          email_body: "",
        }}
        runtimeResolved={{}}
        runtimeAuthorized={null}
        runtimeExecution={{}}
        runtimeExecutionOutput={{}}
        runtimeExecutionMetrics={{}}
        runtimeTaskPending=""
        handleRuntimeTaskFormChange={() => {}}
        updateRuntimeAiCallsEnabled={() => {}}
        runRuntimeResolveFlow={() => {}}
        runRuntimeAuthorize={() => {}}
        runRuntimeRegisterPrompt={() => {}}
        runRuntimeExecuteEmailClassifier={() => {}}
        runRuntimeExecuteLatestEmailActionDecision={() => {}}
        runRuntimePreview={() => {}}
        runRuntimeResolve={() => {}}
        runtimePreview={{}}
        runtimeAuthorizationGranted={() => false}
        formatTelemetryTimestamp={() => "now"}
      />,
    );
    const scheduledHtml = render(
      <ScheduledTasksSection
        scheduledTasksSorted={[{ task_id: "task-1", title: "Fetch", group: "gmail", schedule_name: "daily", schedule_detail: "00:01", status: "active", last_execution_at: "now", next_execution_at: "later", last_reason: "schedule", last_slot_key: "slot-1", detail: "ok" }]}
        scheduledTaskLegend={[{ name: "daily", detail: "Every day" }]}
        scheduledTaskStatusTone={() => "success"}
        formatScheduleTimestamp={(value) => value}
        formatRelativeTime={() => "just now"}
      />,
    );
    const ordersHtml = render(
      <TrackedOrdersSection
        trackedOrdersSorted={[{ account_id: "acct", record_id: "1", seller: "Amazon", carrier: "UPS", order_number: "123", tracking_number: "1Z", last_known_status: "shipped", domain: "amazon.com", last_seen_at: "now", status_updated_at: "now", updated_at: "now" }]}
        formatScheduleTimestamp={(value) => value}
      />,
    );

    expect(runtimeHtml).toContain("Runtime Status");
    expect(runtimeHtml).toContain("Runtime Actions");
    expect(scheduledHtml).toContain("Scheduled Tasks");
    expect(ordersHtml).toContain("Tracked Orders");
  });
});
