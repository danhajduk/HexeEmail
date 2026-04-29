export function NodeIdentityFormCard({
  bootstrap,
  Field,
  form,
  handleChange,
  saveConfiguration,
  saving,
  startOnboarding,
  starting,
  requiredInputs,
}) {
  return (
    <article className="card stack">
      <div className="section-heading">
        <h2>Node Identity</h2>
        <span className="pill">UI {bootstrap?.config.ui_port || 8083}</span>
      </div>
      <Field
        label="Core base URL"
        name="core_base_url"
        value={form.core_base_url}
        onChange={handleChange}
        placeholder="http://192.168.1.10:8000"
        required
      />
      <Field
        label="Node name"
        name="node_name"
        value={form.node_name}
        onChange={handleChange}
        placeholder="front-desk-email-node"
        required
      />
      <div className="actions">
        <button className="btn btn-ghost" type="button" onClick={saveConfiguration} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
        <button className="btn btn-primary" type="button" onClick={startOnboarding} disabled={starting}>
          {starting ? "Starting..." : "Start Onboarding"}
        </button>
      </div>
      {requiredInputs.length > 0 ? <div className="callout callout-warning">Required before onboarding: {requiredInputs.join(", ")}</div> : null}
    </article>
  );
}
