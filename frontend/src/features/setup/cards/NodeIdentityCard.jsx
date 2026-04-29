import { StageCard } from "./StageCard";

export function NodeIdentityCard({ requiredInputs, notice, error }) {
  return (
    <StageCard title="Node Identity" tone={requiredInputs.length > 0 ? "warning" : "success"}>
      <div className="callout">Set the local node name and keep this workstation open during the rest of the setup flow.</div>
      {notice ? <div className="callout callout-success">{notice}</div> : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
    </StageCard>
  );
}
