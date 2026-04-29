import { StageCard } from "./StageCard";

export function TrustActivationCard({ status, statusTone }) {
  return (
    <StageCard title="Trust Activation" tone={statusTone(status?.trust_state)}>
      <dl className="facts single-column-facts">
        <div><dt>Trust state</dt><dd>{status?.trust_state || "untrusted"}</dd></div>
        <div><dt>Node ID</dt><dd>{status?.node_id || "Pending"}</dd></div>
        <div><dt>MQTT</dt><dd>{status?.mqtt_connection_status || "disconnected"}</dd></div>
      </dl>
    </StageCard>
  );
}
