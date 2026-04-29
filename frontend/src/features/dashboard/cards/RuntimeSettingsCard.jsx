function RuntimeSwitchButton({
  label,
  enabled,
  disabled,
  onClick,
  ariaLabel,
}) {
  return (
    <label className="field runtime-switch-item">
      <button
        type="button"
        className={`runtime-switch-pill runtime-switch-button ${enabled ? "is-on" : "is-off"}`}
        aria-pressed={enabled}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={onClick}
      >
        <span className="runtime-switch-led" />
        <span>{label}</span>
        <span className="sr-only">{enabled ? "Enabled" : "Disabled"}</span>
      </button>
    </label>
  );
}

export function RuntimeSettingsCard({
  runtimeTaskForm,
  runtimeTaskPending,
  updateRuntimeAiCallsEnabled,
  updateRuntimeProviderCallsEnabled,
  updateRuntimeUserNotificationsEnabled,
  updateRuntimeClassificationEnabled,
  updateRuntimeOrderChecksEnabled,
  updateRuntimeActionRequiredFlowEnabled,
  updateRuntimeFinancialFlowEnabled,
  updateRuntimeInvoiceFlowEnabled,
  updateRuntimeShipmentFlowEnabled,
  updateRuntimeSecurityFlowEnabled,
}) {
  const disabled = runtimeTaskPending !== "";

  return (
    <article className="card">
      <div className="card-header">
        <h2>Runtime Settings</h2>
        <p className="muted">Configure the task request that will be previewed, resolved, and authorized through Core.</p>
      </div>
      <div className="stack compact-stack">
        <div className="runtime-switch-groups">
          <div className="runtime-switch-group">
            <div className="runtime-switch-group-header">Calls</div>
            <div className="runtime-switch-card">
              <div className="runtime-switch-grid">
                <RuntimeSwitchButton
                  label="AI"
                  enabled={runtimeTaskForm.ai_calls_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeAiCallsEnabled(!runtimeTaskForm.ai_calls_enabled)}
                  ariaLabel={runtimeTaskForm.ai_calls_enabled ? "Disable AI calls" : "Enable AI calls"}
                />
                <RuntimeSwitchButton
                  label="Provider"
                  enabled={runtimeTaskForm.provider_calls_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeProviderCallsEnabled(!runtimeTaskForm.provider_calls_enabled)}
                  ariaLabel={runtimeTaskForm.provider_calls_enabled ? "Disable provider calls" : "Enable provider calls"}
                />
                <RuntimeSwitchButton
                  label="Notify"
                  enabled={runtimeTaskForm.user_notifications_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeUserNotificationsEnabled(!runtimeTaskForm.user_notifications_enabled)}
                  ariaLabel={runtimeTaskForm.user_notifications_enabled ? "Disable user notifications" : "Enable user notifications"}
                />
              </div>
            </div>
          </div>
          <div className="runtime-switch-group">
            <div className="runtime-switch-group-header">Analysis</div>
            <div className="runtime-switch-card">
              <div className="runtime-switch-grid">
                <RuntimeSwitchButton
                  label="Clasify"
                  enabled={runtimeTaskForm.classification_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeClassificationEnabled(!runtimeTaskForm.classification_enabled)}
                  ariaLabel={runtimeTaskForm.classification_enabled ? "Disable classification" : "Enable classification"}
                />
                <div className="field runtime-switch-item runtime-switch-item-disabled" aria-hidden="true">
                  <span className="runtime-switch-pill is-off">
                    <span className="runtime-switch-led" />
                    <span>Local</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div className="runtime-switch-group">
            <div className="runtime-switch-group-header">Label Family Flows</div>
            <div className="runtime-switch-card">
              <div className="runtime-switch-grid">
                <RuntimeSwitchButton
                  label="Action"
                  enabled={runtimeTaskForm.action_required_flow_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeActionRequiredFlowEnabled(!runtimeTaskForm.action_required_flow_enabled)}
                  ariaLabel={runtimeTaskForm.action_required_flow_enabled ? "Disable action required flow" : "Enable action required flow"}
                />
                <RuntimeSwitchButton
                  label="Order"
                  enabled={runtimeTaskForm.order_checks_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeOrderChecksEnabled(!runtimeTaskForm.order_checks_enabled)}
                  ariaLabel={runtimeTaskForm.order_checks_enabled ? "Disable order analysis" : "Enable order analysis"}
                />
                <RuntimeSwitchButton
                  label="Financial"
                  enabled={runtimeTaskForm.financial_flow_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeFinancialFlowEnabled(!runtimeTaskForm.financial_flow_enabled)}
                  ariaLabel={runtimeTaskForm.financial_flow_enabled ? "Disable financial flow" : "Enable financial flow"}
                />
                <RuntimeSwitchButton
                  label="Invoice"
                  enabled={runtimeTaskForm.invoice_flow_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeInvoiceFlowEnabled(!runtimeTaskForm.invoice_flow_enabled)}
                  ariaLabel={runtimeTaskForm.invoice_flow_enabled ? "Disable invoice flow" : "Enable invoice flow"}
                />
                <RuntimeSwitchButton
                  label="Shipment"
                  enabled={runtimeTaskForm.shipment_flow_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeShipmentFlowEnabled(!runtimeTaskForm.shipment_flow_enabled)}
                  ariaLabel={runtimeTaskForm.shipment_flow_enabled ? "Disable shipment flow" : "Enable shipment flow"}
                />
                <RuntimeSwitchButton
                  label="Security"
                  enabled={runtimeTaskForm.security_flow_enabled}
                  disabled={disabled}
                  onClick={() => updateRuntimeSecurityFlowEnabled(!runtimeTaskForm.security_flow_enabled)}
                  ariaLabel={runtimeTaskForm.security_flow_enabled ? "Disable security flow" : "Enable security flow"}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
