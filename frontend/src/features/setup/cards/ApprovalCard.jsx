import { StageCard } from "./StageCard";

export function ApprovalCard({ onboarding, approvalLink }) {
  return (
    <StageCard title="Approval" tone="warning" action={approvalLink}>
      <div className="callout">
        Open the Core approval URL and approve the node. Keep this page open while finalize polling continues.
      </div>
      {onboarding?.last_error ? <div className="callout callout-danger">{onboarding.last_error}</div> : null}
    </StageCard>
  );
}
