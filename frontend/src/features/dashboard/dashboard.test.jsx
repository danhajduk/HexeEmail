import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GmailDashboardSection } from "./GmailDashboardSection";
import { OverviewDashboardSection } from "./OverviewDashboardSection";
import { RuntimeDashboardSection } from "./RuntimeDashboardSection";
import { ScheduledTasksSection } from "./ScheduledTasksSection";
import { TrackedOrdersSection } from "./TrackedOrdersSection";
import { ReviewOutputsSection } from "./ReviewOutputsSection";
import { ActionRequiredSection } from "./ActionRequiredSection";

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
        runtimeTaskForm={{
          ai_calls_enabled: true,
          provider_calls_enabled: true,
          user_notifications_enabled: true,
          classification_enabled: true,
          order_checks_enabled: true,
          action_required_flow_enabled: true,
          financial_flow_enabled: true,
          invoice_flow_enabled: true,
          shipment_flow_enabled: true,
          security_flow_enabled: true,
        }}
        runtimeBatchExecution={null}
        runtimeBatchProgressPercent={0}
        gmailLastHourPipelinePills={[{ key: "fetch", label: "fetch", value: "done" }]}
        pipelineStageClass={() => "status-pill"}
        gmailFetchScheduler={{ status: "completed", loop_active: true, detail: "ok" }}
        healthSeverityClass={() => "status-pill"}
        formatScheduleTimestamp={(value) => value || "-"}
        gmailWindowSettings={[{ key: "today", label: "Today", runReason: "scheduled", fetchedAt: "now", schedule: "00:00" }]}
        gmailPrimaryRules={{
          label_overrides: [{ match_type: "domain", value: "parcelpending.com", label: "action_required", enabled: true }],
          full_html_required: [{ match_type: "domain", value: "c.visionworks.com", enabled: true }],
        }}
        onSaveGmailRules={() => {}}
        senderReputationTone={() => "success"}
        formatSenderReputationInputs={() => "signals"}
        formatTelemetryTimestamp={() => "-"}
      />,
    );

    expect(html).toContain("Gmail Status");
    expect(html).toContain("Fetch Initial Learning");
    expect(html).toContain("Gmail Settings");
    expect(html).toContain("Sender Label Rules");
    expect(html).toContain("Full HTML Extraction");
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
        runtimeTaskStatus={{
          ai_calls_enabled: true,
          provider_calls_enabled: true,
          user_notifications_enabled: true,
          classification_enabled: true,
          order_checks_enabled: true,
          action_required_flow_enabled: true,
          financial_flow_enabled: true,
          invoice_flow_enabled: true,
          shipment_flow_enabled: true,
          security_flow_enabled: true,
          request_status: "idle",
          last_step: "none",
          detail: "ready",
        }}
        runtimeTaskForm={{
          ai_calls_enabled: true,
          provider_calls_enabled: true,
          user_notifications_enabled: true,
          classification_enabled: true,
          order_checks_enabled: true,
          action_required_flow_enabled: true,
          financial_flow_enabled: true,
          invoice_flow_enabled: true,
          shipment_flow_enabled: true,
          security_flow_enabled: true,
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
        updateRuntimeProviderCallsEnabled={() => {}}
        updateRuntimeUserNotificationsEnabled={() => {}}
        updateRuntimeClassificationEnabled={() => {}}
        updateRuntimeOrderChecksEnabled={() => {}}
        updateRuntimeActionRequiredFlowEnabled={() => {}}
        updateRuntimeFinancialFlowEnabled={() => {}}
        updateRuntimeInvoiceFlowEnabled={() => {}}
        updateRuntimeShipmentFlowEnabled={() => {}}
        updateRuntimeSecurityFlowEnabled={() => {}}
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
        scheduledTasksSorted={[{ task_id: "task-1", title: "Fetch", kind: "provider_recurring_work", owner: "background_task_manager", schedule_name: "daily", schedule_label: "Every day", schedule_detail: "00:01", status: "running", last_success_at: "now", last_failure_at: null, last_error: null, next_execution_at: "later", detail: "ok" }]}
        scheduledTaskLegend={[{ name: "heartbeat_5_seconds", detail: "Heartbeat every 5 seconds" }, { name: "every_10_seconds", detail: "Every 10 seconds" }, { name: "telemetry_60_seconds", detail: "Telemetry every 60 seconds" }, { name: "interval_seconds", detail: "Every N seconds (requires integer seconds)" }]}
        scheduledTaskStatusTone={(value) => (value === "running" ? "success-strong" : "warning")}
        formatScheduleTimestamp={(value) => value}
        formatRelativeTime={() => "just now"}
      />,
    );
    const ordersHtml = render(
      <TrackedOrdersSection
        trackedOrdersSorted={[{ account_id: "acct", record_id: "1", seller: "Amazon", carrier: "UPS", order_number: "123", tracking_number: "", last_known_status: "Delivered to locker; awaiting pickup", domain: "amazon.com", last_seen_at: "now", status_updated_at: "now", updated_at: "now" }]}
        formatScheduleTimestamp={(value) => value}
      />,
    );
    const shipmentsHtml = render(
      <TrackedOrdersSection
        trackedOrdersSorted={[{ account_id: "acct", record_id: "1", seller: "Amazon", carrier: "UPS", order_number: "123", tracking_number: "1Z", last_known_status: "shipped", live_tracking_enabled: true, live_tracking_status: "in transit", live_tracking_location: "Memphis, TN, US", live_tracking_expected_delivery: "soon", live_tracking_events: [{ detail: "Departed FedEx hub", location: "Memphis, TN, US", time: "now", status_code: "IN_TRANSIT_01" }, { detail: "Picked up", location: "Toronto, ON, CA", time: "earlier", status_code: "INFO_RECEIVED_01" }], domain: "amazon.com", last_seen_at: "now", status_updated_at: "now", updated_at: "now" }]}
        formatScheduleTimestamp={(value) => value}
        title="Tracked Shipments"
        description="Shipment-focused records"
        emptyMessage="No tracked shipment records are available yet."
        trackingIntegrations={{ track123: { enabled: true, configured: true } }}
        showSeller={false}
      />,
    );
    const reviewHtml = render(
      <ReviewOutputsSection
        reviewOutputsSorted={[{ flow_family: "shipment", message_id: "msg-1", subject: "Tracking update", decision_reason: "no_structured_extraction", profile_id: "label_created", confidence: 0, confidence_level: "low", extracted_field_keys: [], sender_email: "tracking@example.com", persisted_at: "now", record_path: "runtime/flow_families/shipment/outputs/review_needed/msg-1.json" }]}
        formatScheduleTimestamp={(value) => value}
      />,
    );
    const actionHtml = render(
      <ActionRequiredSection
        actionItems={[{ item_id: "act-1", sender: "billing@example.com", subject: "Payment due", received_at: "now", state: "review_needed", profile_type: "payment_due", confidence: 0.91, priority_score: 86, review_reasons: ["missing_action_url"], due_at: "later", reminder_at: "soon", grouped_message_count: 2, ai_decision_summary: "Pay invoice" }]}
        actionItemsLoading={false}
        actionItemsError=""
        selectedActionItemId="act-1"
        selectedActionItem={{
          item_id: "act-1",
          sender: "billing@example.com",
          subject: "Payment due",
          received_at: "now",
          state: "review_needed",
          profile_type: "payment_due",
          confidence: 0.91,
          priority_score: 86,
          review_reasons: ["missing_action_url"],
          due_at: "later",
          action_url: "https://example.com/pay",
          extracted_fields: { amount: { value: "$12.00" }, document_id: "INV-1" },
          flow_output: { template_id: "payment_due.v1", diagnostics: ["needs url"] },
          ai_decision_payload: {
            primary_label: "action_required",
            recommended_action: "Pay invoice",
            human_review_required: true,
            risk_notes: ["missing link"],
            recommended_actions: [{ action: "pay", confidence: 0.9, reason: "due soon" }],
          },
          source_message: {
            message_id: "msg-1",
            subject: "Payment due",
            sender: "billing@example.com",
            recipients: ["ops@example.com"],
            label_ids: ["INBOX"],
            received_at: "now",
            snippet: "Please pay",
            raw_payload: JSON.stringify({ text: "Plain body", html: "<strong>Pay</strong>" }),
          },
        }}
        selectedActionItemLoading={false}
        selectedActionItemError=""
        onSelectActionItem={() => {}}
        onRefreshActionItems={() => {}}
        formatScheduleTimestamp={(value) => value || "-"}
      />,
    );

    expect(runtimeHtml).toContain("Runtime Status");
    expect(runtimeHtml).toContain("Runtime Actions");
    expect(runtimeHtml).toContain("Notify");
    expect(runtimeHtml).toContain("Analysis");
    expect(runtimeHtml).toContain("Label Family Flows");
    expect(runtimeHtml).toContain("Clasify");
    expect(runtimeHtml).toContain("Order");
    expect(runtimeHtml).toContain("Action");
    expect(runtimeHtml).toContain("Financial");
    expect(runtimeHtml).toContain("Invoice");
    expect(runtimeHtml).toContain("Shipment");
    expect(runtimeHtml).toContain("Security");
    expect(runtimeHtml).not.toContain("AI Node API Base URL");
    expect(runtimeHtml).not.toContain("Email Body");
    expect(scheduledHtml).toContain("Scheduled Tasks");
    expect(scheduledHtml).toContain("Last Success");
    expect(scheduledHtml).toContain("Last Failure");
    expect(scheduledHtml).toContain("Last Error");
    expect(scheduledHtml).toContain("tone-success-strong");
    expect(scheduledHtml).toContain("heartbeat_5_seconds");
    expect(scheduledHtml).toContain("every_10_seconds");
    expect(scheduledHtml).toContain("telemetry_60_seconds");
    expect(scheduledHtml).toContain("interval_seconds");
    expect(scheduledHtml).toContain("Provider");
    expect(scheduledHtml).toContain("background_task_manager");
    expect(ordersHtml).toContain("Tracked Orders");
    expect(ordersHtml).toContain("Seller");
    expect(ordersHtml).toContain("Tracking");
    expect(ordersHtml).toContain("Added");
    expect(ordersHtml).toContain("delivered");
    expect(ordersHtml).not.toContain("no number");
    expect(ordersHtml).not.toContain("Delivered to locker; awaiting pickup");
    expect(ordersHtml).not.toContain("Live Tracking");
    expect(shipmentsHtml).toContain("Tracked Shipments");
    expect(shipmentsHtml).toContain("Departed FedEx hub");
    expect(shipmentsHtml).toContain("Memphis, TN, US");
    expect(shipmentsHtml.match(/Memphis, TN, US/g)).toHaveLength(1);
    expect(shipmentsHtml).toContain("Expected delivery: soon");
    expect(shipmentsHtml).toContain("in transit");
    expect(shipmentsHtml).not.toContain("Picked up");
    expect(shipmentsHtml).not.toContain(">Track</button>");
    expect(shipmentsHtml).not.toContain("Refresh");
    expect(shipmentsHtml).not.toContain("Live Tracking");
    expect(shipmentsHtml).not.toContain("Seller");
    expect(shipmentsHtml).not.toContain("Amazon");
    expect(reviewHtml).toContain("Review Needed Outputs");
    expect(reviewHtml).toContain("no_structured_extraction");
    expect(reviewHtml).toContain("runtime/flow_families/shipment/outputs/review_needed/msg-1.json");
    expect(actionHtml).toContain("Action Required");
    expect(actionHtml).toContain("payment_due");
    expect(actionHtml).toContain("AI Decision");
    expect(actionHtml).toContain("Extracted Data");
    expect(actionHtml).toContain("Mail");
    expect(actionHtml).toContain("missing action url");
    expect(actionHtml).toContain("Pay invoice");
  });
});
