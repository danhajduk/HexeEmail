import { StageCard } from "./StageCard";

export function CapabilityDeclarationCard({
  status,
  form,
  saving,
  declaringCapabilities,
  onCapabilityToggle,
  onSaveConfiguration,
  onDeclareCapabilities,
  taskCapabilityOptions,
  notice,
  error,
  statusTone,
}) {
  const capabilitySetup = status?.capability_setup || {};
  const capabilitySelection = capabilitySetup?.task_capability_selection || {};

  return (
    <StageCard
      title="Capability Declaration"
      tone={statusTone(status?.capability_declaration_status)}
      action={(
        <div className="actions">
          <button className="btn btn-ghost" type="button" onClick={onSaveConfiguration} disabled={saving}>
            {saving ? "Saving..." : "Save Selection"}
          </button>
          <button className="btn btn-primary" type="button" onClick={onDeclareCapabilities} disabled={declaringCapabilities}>
            {declaringCapabilities ? "Declaring..." : "Declare Capabilities"}
          </button>
        </div>
      )}
    >
      <div className="callout">Select the task families this node should declare to Core once Gmail is connected.</div>
      <div className="capability-list">
        {taskCapabilityOptions.map((capability) => {
          const selected = form.selected_task_capabilities.includes(capability);
          return (
            <button key={capability} className={`capability-option ${selected ? "is-selected" : ""}`} type="button" onClick={() => onCapabilityToggle(capability)}>
              <span className="capability-check">{selected ? "✓" : ""}</span>
              <span className="capability-copy"><strong>{capability}</strong></span>
            </button>
          );
        })}
      </div>
      <div className="callout">
        Capability declaration status: {status?.capability_declaration_status || "pending"}. Selected: {capabilitySelection.selected_count ?? form.selected_task_capabilities.length}.
      </div>
      {(capabilitySetup?.blocking_reasons || []).length > 0 ? (
        <ul className="prompt-list">
          {capabilitySetup.blocking_reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      ) : null}
      {notice ? <div className="callout callout-success">{notice}</div> : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
    </StageCard>
  );
}
