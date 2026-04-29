import { SenderReputationPanel } from "../../training/SenderReputationPage";

export function SenderReputationDashboardCard({
  gmailPrimarySenderReputation,
  senderReputationTone,
  formatSenderReputationInputs,
  formatTelemetryTimestamp,
}) {
  return (
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
  );
}
