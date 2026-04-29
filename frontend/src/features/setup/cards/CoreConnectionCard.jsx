import { StageCard } from "./StageCard";

export function CoreConnectionCard({ requiredInputs }) {
  return (
    <StageCard title="Core Connection" tone="warning">
      <div className="callout callout-warning">
        {requiredInputs.includes("core_base_url")
          ? "Enter the Core base URL, then save or start onboarding."
          : "Core URL is configured and ready for bootstrap discovery."}
      </div>
    </StageCard>
  );
}
