import { StageCard } from "./StageCard";

export function GovernanceSyncCard({ status, statusTone }) {
  return (
    <StageCard title="Governance Sync" tone={statusTone(status?.governance_sync_status)}>
      <div className="callout">Governance sync status: {status?.governance_sync_status || "pending"}.</div>
    </StageCard>
  );
}
