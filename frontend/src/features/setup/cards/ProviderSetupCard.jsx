import { StageCard } from "./StageCard";

export function ProviderSetupCard({ status, statusTone, onOpenProvider }) {
  return (
    <StageCard
      title="Provider Setup"
      tone={statusTone(status?.provider_account_summaries?.gmail?.provider_state)}
      action={<button className="btn btn-primary" type="button" onClick={onOpenProvider}>Setup Provider</button>}
    >
      <div className="callout">
        Trust is active. Configure Gmail and complete the connect flow to move the node into provider-ready state.
      </div>
    </StageCard>
  );
}
