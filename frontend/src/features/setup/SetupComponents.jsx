import { ApprovalCard } from "./cards/ApprovalCard";
import { CapabilityDeclarationCard } from "./cards/CapabilityDeclarationCard";
import { CoreConnectionCard } from "./cards/CoreConnectionCard";
import { GovernanceSyncCard } from "./cards/GovernanceSyncCard";
import { NodeIdentityCard } from "./cards/NodeIdentityCard";
import { ProviderSetupCard } from "./cards/ProviderSetupCard";
import { ReadyCard } from "./cards/ReadyCard";
import { RegistrationCard } from "./cards/RegistrationCard";
import { TrustActivationCard } from "./cards/TrustActivationCard";

export function SetupSidebar({ flow }) {
  return (
    <aside className="card stack flow-sidebar">
      <div className="section-heading">
        <h2>Setup Flow</h2>
        <span className="pill">{flow.current?.label || "Idle"}</span>
      </div>
      <div className="flow-steps">
        {flow.steps.map((step, index) => {
          const state = step.complete ? "success" : step.current ? "warning" : "neutral";
          return (
            <div key={step.id} className={`flow-step is-${state}`}>
              {step.complete ? <span className="flow-step-check" aria-label="Completed">✓</span> : null}
              <div className="flow-step-index">{index + 1}</div>
              <div className="flow-step-body">
                <strong>{step.label}</strong>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

export function renderCurrentStageCard({
  flow,
  status,
  onboarding,
  requiredInputs,
  notice,
  error,
  onOpenProvider,
  form,
  saving,
  declaringCapabilities,
  onCapabilityToggle,
  onSaveConfiguration,
  onDeclareCapabilities,
  taskCapabilityOptions,
  statusTone,
  boolTone,
}) {
  const stepId = flow.current?.id;
  const approvalLink = onboarding?.approval_url ? (
    <a className="approval-link" href={onboarding.approval_url} target="_blank" rel="noreferrer">
      Open approval URL
    </a>
  ) : null;

  if (stepId === "core_connection") {
    return <CoreConnectionCard requiredInputs={requiredInputs} />;
  }

  if (stepId === "bootstrap_discovery" || stepId === "registration") {
    return (
      <RegistrationCard onboarding={onboarding} notice={notice} error={error} statusTone={statusTone} />
    );
  }

  if (stepId === "approval") {
    return <ApprovalCard onboarding={onboarding} approvalLink={approvalLink} />;
  }

  if (stepId === "trust_activation") {
    return <TrustActivationCard status={status} statusTone={statusTone} />;
  }

  if (stepId === "provider_setup") {
    return (
      <ProviderSetupCard status={status} statusTone={statusTone} onOpenProvider={onOpenProvider} />
    );
  }

  if (stepId === "capability_declaration") {
    return (
      <CapabilityDeclarationCard
        status={status}
        form={form}
        saving={saving}
        declaringCapabilities={declaringCapabilities}
        onCapabilityToggle={onCapabilityToggle}
        onSaveConfiguration={onSaveConfiguration}
        onDeclareCapabilities={onDeclareCapabilities}
        taskCapabilityOptions={taskCapabilityOptions}
        notice={notice}
        error={error}
        statusTone={statusTone}
      />
    );
  }

  if (stepId === "governance_sync") {
    return <GovernanceSyncCard status={status} statusTone={statusTone} />;
  }

  if (stepId === "ready") {
    return <ReadyCard status={status} boolTone={boolTone} />;
  }

  return <NodeIdentityCard requiredInputs={requiredInputs} notice={notice} error={error} />;
}
