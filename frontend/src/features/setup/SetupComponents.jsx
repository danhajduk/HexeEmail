export function StageCard({ title, tone, children, action }) {
  return (
    <article className={`card stack stage-card tone-${tone}`}>
      <div className="section-heading">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </article>
  );
}

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
  const capabilitySetup = status?.capability_setup || {};
  const capabilitySelection = capabilitySetup?.task_capability_selection || {};
  const approvalLink = onboarding?.approval_url ? (
    <a className="approval-link" href={onboarding.approval_url} target="_blank" rel="noreferrer">
      Open approval URL
    </a>
  ) : null;

  if (stepId === "core_connection") {
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

  if (stepId === "bootstrap_discovery" || stepId === "registration") {
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

  if (stepId === "approval") {
    return (
      <StageCard title="Approval" tone="warning" action={approvalLink}>
        <div className="callout">
          Open the Core approval URL and approve the node. Keep this page open while finalize polling continues.
        </div>
        {onboarding?.last_error ? <div className="callout callout-danger">{onboarding.last_error}</div> : null}
      </StageCard>
    );
  }

  if (stepId === "trust_activation") {
    return (
      <StageCard title="Trust Activation" tone={statusTone(status?.trust_state)}>
        <dl className="facts single-column-facts">
          <div><dt>Trust state</dt><dd>{status?.trust_state || "untrusted"}</dd></div>
          <div><dt>Node ID</dt><dd>{status?.node_id || "Pending"}</dd></div>
          <div><dt>MQTT</dt><dd>{status?.mqtt_connection_status || "disconnected"}</dd></div>
        </dl>
      </StageCard>
    );
  }

  if (stepId === "provider_setup") {
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

  if (stepId === "capability_declaration") {
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

  if (stepId === "governance_sync") {
    return (
      <StageCard title="Governance Sync" tone={statusTone(status?.governance_sync_status)}>
        <div className="callout">Governance sync status: {status?.governance_sync_status || "pending"}.</div>
      </StageCard>
    );
  }

  if (stepId === "ready") {
    return (
      <StageCard title="Ready" tone={boolTone(status?.operational_readiness)}>
        <div className="callout callout-success">
          The node is fully ready. Gmail is connected, capability declaration is current, and governance sync is healthy.
        </div>
      </StageCard>
    );
  }

  return (
    <StageCard title="Node Identity" tone={requiredInputs.length > 0 ? "warning" : "success"}>
      <div className="callout">Set the local node name and keep this workstation open during the rest of the setup flow.</div>
      {notice ? <div className="callout callout-success">{notice}</div> : null}
      {error ? <div className="callout callout-danger">{error}</div> : null}
    </StageCard>
  );
}
