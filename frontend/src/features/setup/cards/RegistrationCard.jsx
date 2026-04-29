import { StageCard } from "./StageCard";

export function RegistrationCard({ onboarding, notice, error, statusTone }) {
  return (
    <StageCard title="Registration" tone={statusTone(onboarding?.onboarding_status)}>
      <dl className="facts single-column-facts">
        <div><dt>Session</dt><dd>{onboarding?.session_id || "No session yet"}</dd></div>
        <div><dt>Approval URL</dt><dd>{onboarding?.approval_url || "Will appear after session creation"}</dd></div>
      </dl>
      {notice ? <div className="callout callout-success">{notice}</div> : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
    </StageCard>
  );
}
