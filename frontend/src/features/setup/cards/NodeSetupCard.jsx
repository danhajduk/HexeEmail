import { renderCurrentStageCard } from "../SetupComponents";

export function NodeSetupCard({
  bootstrap,
  onboarding,
  status,
  statusTone,
  setupFlow,
  requiredInputs,
  notice,
  error,
  openProvider,
  form,
  saving,
  declaringCapabilities,
  handleCapabilityToggle,
  saveConfiguration,
  declareCapabilities,
  taskCapabilityOptions,
  boolTone,
}) {
  return (
    <article className="card stack">
      <div className="section-heading">
        <h2>Node Setup</h2>
        <span className="pill">API {bootstrap?.config.api_port || 9003}</span>
      </div>
      <div className="status-rail">
        <div className={`status-pill tone-${statusTone(onboarding?.onboarding_status)}`}>
          lifecycle: {onboarding?.onboarding_status || "not_started"}
        </div>
        <div className={`status-pill tone-${statusTone(status?.trust_state)}`}>trust: {status?.trust_state || "untrusted"}</div>
        <div className={`status-pill tone-${statusTone(status?.governance_sync_status)}`}>
          governance: {status?.governance_sync_status || "pending"}
        </div>
        <div className={`status-pill tone-${status?.trust_state === "trusted" ? "success" : "neutral"}`}>
          core: {status?.trust_state === "trusted" ? "paired" : "not paired"}
        </div>
      </div>
      {renderCurrentStageCard({
        flow: setupFlow,
        status,
        onboarding,
        requiredInputs,
        notice,
        error,
        onOpenProvider: openProvider,
        form,
        saving,
        declaringCapabilities,
        onCapabilityToggle: handleCapabilityToggle,
        onSaveConfiguration: saveConfiguration,
        onDeclareCapabilities: declareCapabilities,
        taskCapabilityOptions,
        statusTone,
        boolTone,
      })}
    </article>
  );
}
