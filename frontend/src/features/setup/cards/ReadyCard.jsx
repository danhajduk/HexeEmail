import { StageCard } from "./StageCard";

export function ReadyCard({ status, boolTone }) {
  return (
    <StageCard title="Ready" tone={boolTone(status?.operational_readiness)}>
      <div className="callout callout-success">
        The node is fully ready. Gmail is connected, capability declaration is current, and governance sync is healthy.
      </div>
    </StageCard>
  );
}
