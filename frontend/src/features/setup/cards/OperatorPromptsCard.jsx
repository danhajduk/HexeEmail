export function OperatorPromptsCard({ requiredInputs, onboarding, status, setupFlow }) {
  return (
    <article className="card stack">
      <div className="section-heading">
        <h2>Operator Prompts</h2>
        <span className="pill">{setupFlow.current?.label || "Idle"}</span>
      </div>
      <ul className="prompt-list">
        {requiredInputs.length > 0 ? <li>Enter the Core base URL and node name, then save or start onboarding.</li> : null}
        {onboarding?.approval_url ? <li>Open the approval URL in Core and approve the node.</li> : null}
        {onboarding?.onboarding_status === "pending" ? <li>Keep this page open while finalize polling continues.</li> : null}
        <li>Use Restart Setup if you need a fresh onboarding session.</li>
        {status?.trust_state === "trusted" ? <li>The node is trusted. Use Setup Provider to configure Gmail.</li> : null}
        {!requiredInputs.length && !onboarding?.approval_url && status?.trust_state !== "trusted" ? <li>Start onboarding when you are ready.</li> : null}
      </ul>
    </article>
  );
}
