import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GmailSetupPage } from "./providers/GmailSetupPage";
import { renderCurrentStageCard, SetupSidebar } from "./setup/SetupComponents";
import { SenderReputationPage } from "./training/SenderReputationPage";
import { TrainingPage } from "./training/TrainingPage";

function render(element) {
  return renderToStaticMarkup(element);
}

describe("extracted feature pages", () => {
  it("renders the Gmail setup page", () => {
    const html = render(
      <GmailSetupPage
        bootstrap={{ config: { api_port: 9003 }, status: { trust_state: "trusted" } }}
        providerConfig={{ config: { enabled: true, redirect_uri: "http://localhost/callback" }, validation: { ok: true } }}
        providerStatus={{ provider_account_summaries: { gmail: { provider_state: "connected", configured: true, accounts: [] } } }}
        gmailStatus={{ accounts: [{ labels: { labels: [{ id: "INBOX", name: "INBOX" }] } }] }}
        providerForm={{ enabled: true, client_id: "id", client_secret_ref: "env:SECRET", redirect_uri: "http://localhost/callback", requested_scopes: "scope" }}
        providerLoading={false}
        providerSaving={false}
        providerValidating={false}
        providerConnecting={false}
        providerNotice=""
        providerError=""
        connectUrl=""
        onProviderChange={() => {}}
        onRefresh={() => {}}
        onSave={() => {}}
        onValidate={() => {}}
        onConnect={() => {}}
        onBack={() => {}}
        ToggleField={({ label }) => <div>{label}</div>}
        Field={({ label }) => <div>{label}</div>}
        TextareaField={({ label }) => <div>{label}</div>}
        statusTone={() => "success"}
      />,
    );

    expect(html).toContain("Gmail Status");
    expect(html).toContain("Gmail Settings");
    expect(html).toContain("Gmail Action");
  });

  it("renders training and sender reputation pages", () => {
    const trainingHtml = render(
      <TrainingPage
        trainingStatus={{ threshold: 0.6, classification_summary: { classified_count: 4, manual_count: 1, high_confidence_count: 2, per_label: { order: 2 } }, model_status: { trained: true, train_count: 10, test_count: 2 } }}
        trainingLoading={false}
        trainingError=""
        trainingBatch={{ count: 1, items: [{ message_id: "m1", subject: "Order", sender_email: "seller@example.com", raw_text: "hello", local_label: "unknown" }] }}
        trainingBatchLoading={false}
        trainingBatchError=""
        trainingSavePending={false}
        trainingModelPending={false}
        trainingNotice=""
        trainingSelections={{}}
        trainingLabelOptions={["order", "unknown"]}
        onBack={() => {}}
        onOpenSenderReputation={() => {}}
        onLoadClassifiedLabelBatch={() => {}}
        onLoadManualBatch={() => {}}
        onLoadSemiAutoBatch={() => {}}
        onLoadSemiAutoBatch300={() => {}}
        onTrainModel={() => {}}
        onTrainHighConfidenceModel={() => {}}
        onSelectionChange={() => {}}
        onSaveBatch={() => {}}
      />,
    );
    const reputationHtml = render(
      <SenderReputationPage
        summary={{ total_count: 1, by_state: { trusted: 1, neutral: 0, risky: 0, blocked: 0 }, records: [] }}
        loading={false}
        error=""
        detail={null}
        detailLoading={false}
        detailError=""
        notice=""
        onBack={() => {}}
        onInspect={() => {}}
        onClear={() => {}}
        filterValue="all"
        onFilterChange={() => {}}
        collapsedGroups={{}}
        onToggleGroup={() => {}}
        manualNote=""
        onManualNoteChange={() => {}}
        manualSavePending={false}
        onApplyManualRating={() => {}}
        onClearManualRating={() => {}}
        groupSenderReputationRecords={() => []}
        senderReputationTone={() => "success"}
        senderReputationEntityLabel={() => "domain"}
        formatSenderReputationInputs={() => "signals"}
        formatTelemetryTimestamp={() => "now"}
        senderReputationFilters={[{ value: "all", label: "All" }]}
        senderReputationManualActions={[{ value: 1, label: "Trust", tone: "success" }]}
      />,
    );

    expect(trainingHtml).toContain("Training");
    expect(trainingHtml).toContain("Manual Classification");
    expect(reputationHtml).toContain("Sender Reputation");
  });

  it("renders setup helpers", () => {
    const sidebarHtml = render(<SetupSidebar flow={{ current: { label: "Provider Setup" }, steps: [{ id: "one", label: "One", complete: false, current: true }] }} />);
    const stageHtml = render(renderCurrentStageCard({
      flow: { current: { id: "provider_setup" } },
      status: { provider_account_summaries: { gmail: { provider_state: "connected" } } },
      onboarding: {},
      requiredInputs: [],
      notice: "",
      error: "",
      onOpenProvider: () => {},
      form: { selected_task_capabilities: [] },
      saving: false,
      declaringCapabilities: false,
      onCapabilityToggle: () => {},
      onSaveConfiguration: () => {},
      onDeclareCapabilities: () => {},
      taskCapabilityOptions: ["task.classification"],
      statusTone: () => "success",
      boolTone: () => "success",
    }));

    expect(sidebarHtml).toContain("Setup Flow");
    expect(stageHtml).toContain("Provider Setup");
  });
});
