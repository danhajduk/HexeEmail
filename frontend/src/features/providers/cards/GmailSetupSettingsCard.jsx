export function GmailSetupSettingsCard({
  providerSummary,
  statusTone,
  ToggleField,
  providerForm,
  onProviderChange,
  Field,
  TextareaField,
  onValidate,
  providerValidating,
  onSave,
  providerSaving,
  validation,
}) {
  return (
    <article className="card stack">
      <div className="section-heading">
        <h2>Gmail Settings</h2>
        <span className={`status-pill tone-${statusTone(providerSummary?.provider_state)}`}>
          {providerSummary?.provider_state || "unknown"}
        </span>
      </div>
      <ToggleField label="Provider Enabled" name="enabled" checked={providerForm.enabled} onChange={onProviderChange} />
      <Field label="Client ID" name="client_id" value={providerForm.client_id} onChange={onProviderChange} placeholder="Google OAuth client id" required />
      <Field label="Client Secret Ref" name="client_secret_ref" value={providerForm.client_secret_ref} onChange={onProviderChange} placeholder="env:GMAIL_CLIENT_SECRET" required />
      <Field label="Redirect URI" name="redirect_uri" value={providerForm.redirect_uri} onChange={onProviderChange} placeholder="https://your-domain/google/callback" required />
      <TextareaField label="Requested Scopes" name="requested_scopes" value={providerForm.requested_scopes} onChange={onProviderChange} placeholder="One scope per line" />
      <div className="actions">
        <button className="btn btn-ghost" type="button" onClick={onValidate} disabled={providerValidating}>
          {providerValidating ? "Validating..." : "Validate"}
        </button>
        <button className="btn btn-primary" type="button" onClick={onSave} disabled={providerSaving}>
          {providerSaving ? "Saving..." : "Save Gmail Config"}
        </button>
      </div>
      {validation ? (
        <div className={`callout ${validation.ok ? "callout-success" : "callout-warning"}`}>
          {validation.ok ? "Configuration looks valid." : `Missing required fields: ${(validation.missing_fields || []).join(", ") || "unknown"}.`}
        </div>
      ) : null}
    </article>
  );
}
