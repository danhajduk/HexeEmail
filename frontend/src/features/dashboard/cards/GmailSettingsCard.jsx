import { useEffect, useState } from "react";

const TRAINING_LABEL_OPTIONS = [
  "action_required",
  "direct_human",
  "financial",
  "order",
  "invoice",
  "shipment",
  "security",
  "system",
  "newsletter",
  "marketing",
  "unknown",
];

const MATCH_TYPE_OPTIONS = ["domain", "sender"];

function normalizeRules(rules) {
  return {
    label_overrides: Array.isArray(rules?.label_overrides) ? rules.label_overrides : [],
    full_html_required: Array.isArray(rules?.full_html_required) ? rules.full_html_required : [],
  };
}

function emptyLabelOverrideRule() {
  return { match_type: "domain", value: "", label: "action_required", enabled: true, note: "" };
}

function emptyFullHtmlRule() {
  return { match_type: "domain", value: "", enabled: true, note: "" };
}

function cleanRules(form) {
  return {
    label_overrides: form.label_overrides
      .filter((rule) => String(rule.value || "").trim())
      .map((rule) => ({
        match_type: rule.match_type,
        value: String(rule.value || "").trim(),
        label: rule.label,
        enabled: rule.enabled !== false,
        note: String(rule.note || "").trim() || null,
      })),
    full_html_required: form.full_html_required
      .filter((rule) => String(rule.value || "").trim())
      .map((rule) => ({
        match_type: rule.match_type,
        value: String(rule.value || "").trim(),
        enabled: rule.enabled !== false,
        note: String(rule.note || "").trim() || null,
      })),
  };
}

export function GmailSettingsCard({
  gmailFetchScheduler,
  healthSeverityClass,
  formatScheduleTimestamp,
  gmailWindowSettings,
  gmailRules,
  onSaveGmailRules,
}) {
  const incomingRules = normalizeRules(gmailRules);
  const incomingRulesSignature = JSON.stringify(incomingRules);
  const [rulesForm, setRulesForm] = useState(() => incomingRules);
  const [savingRules, setSavingRules] = useState(false);
  const [rulesError, setRulesError] = useState("");
  const [rulesNotice, setRulesNotice] = useState("");

  useEffect(() => {
    setRulesForm(normalizeRules(gmailRules));
  }, [incomingRulesSignature]);

  function updateLabelOverride(index, field, value) {
    setRulesForm((current) => ({
      ...current,
      label_overrides: current.label_overrides.map((rule, ruleIndex) => (
        ruleIndex === index ? { ...rule, [field]: value } : rule
      )),
    }));
  }

  function updateFullHtmlRule(index, field, value) {
    setRulesForm((current) => ({
      ...current,
      full_html_required: current.full_html_required.map((rule, ruleIndex) => (
        ruleIndex === index ? { ...rule, [field]: value } : rule
      )),
    }));
  }

  async function saveRules() {
    if (!onSaveGmailRules) {
      return;
    }
    setSavingRules(true);
    setRulesError("");
    setRulesNotice("");
    try {
      const saved = await onSaveGmailRules(cleanRules(rulesForm));
      setRulesForm(normalizeRules(saved));
      setRulesNotice("Gmail sender rules saved.");
    } catch (error) {
      setRulesError(error.message);
    } finally {
      setSavingRules(false);
    }
  }

  return (
    <article className="card">
      <div className="card-header">
        <h2>Gmail Settings</h2>
        <p className="muted">Scheduled Gmail fetch windows for operational refresh.</p>
      </div>
      <dl className="facts">
        <div>
          <dt>Scheduler</dt>
          <dd>
            <span className={healthSeverityClass(gmailFetchScheduler?.status, ["completed"], ["running"])}>
              <span className="status-badge">
                {gmailFetchScheduler?.loop_active ? "active" : "inactive"}
              </span>
            </span>
          </dd>
        </div>
        <div><dt>Last Check</dt><dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_checked_at)}</dd></div>
        <div><dt>Last Success</dt><dd>{formatScheduleTimestamp(gmailFetchScheduler?.last_success_at)}</dd></div>
        <div><dt>Last Error</dt><dd>{gmailFetchScheduler?.last_error || "-"}</dd></div>
      </dl>
      <p className="muted tiny">{gmailFetchScheduler?.detail || "Scheduler status unavailable."}</p>
      <div className="gmail-settings-grid">
        {gmailWindowSettings.map((windowSetting) => (
          <section key={windowSetting.key} className="gmail-settings-window">
            <div className="gmail-settings-window-header">
              <h3>{windowSetting.label}</h3>
              <span className="status-pill">{windowSetting.runReason || "pending"}</span>
            </div>
            <dl className="facts single-column-facts gmail-settings-facts">
              <div><dt>Fetched</dt><dd>{formatScheduleTimestamp(windowSetting.fetchedAt)}</dd></div>
              <div><dt>Schedule</dt><dd>{windowSetting.schedule}</dd></div>
            </dl>
          </section>
        ))}
      </div>

      <div className="gmail-rule-editor">
        <section className="gmail-rule-section">
          <div className="gmail-rule-section-header">
            <h3>Sender Label Rules</h3>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => setRulesForm((current) => ({
                ...current,
                label_overrides: [...current.label_overrides, emptyLabelOverrideRule()],
              }))}
            >
              Add Rule
            </button>
          </div>
          {rulesForm.label_overrides.length ? (
            <div className="gmail-rule-list">
              {rulesForm.label_overrides.map((rule, index) => (
                <div className="gmail-rule-row" key={`label-${index}`}>
                  <select
                    value={rule.match_type || "domain"}
                    onChange={(event) => updateLabelOverride(index, "match_type", event.target.value)}
                  >
                    {MATCH_TYPE_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                  <input
                    value={rule.value || ""}
                    onChange={(event) => updateLabelOverride(index, "value", event.target.value)}
                    placeholder="parcelpending.com"
                  />
                  <select
                    value={rule.label || "action_required"}
                    onChange={(event) => updateLabelOverride(index, "label", event.target.value)}
                  >
                    {TRAINING_LABEL_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                  <label className="gmail-rule-check">
                    <input
                      type="checkbox"
                      checked={rule.enabled !== false}
                      onChange={(event) => updateLabelOverride(index, "enabled", event.target.checked)}
                    />
                    enabled
                  </label>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setRulesForm((current) => ({
                      ...current,
                      label_overrides: current.label_overrides.filter((_, ruleIndex) => ruleIndex !== index),
                    }))}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted tiny">No forced sender labels configured.</p>
          )}
        </section>

        <section className="gmail-rule-section">
          <div className="gmail-rule-section-header">
            <h3>Full HTML Extraction</h3>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => setRulesForm((current) => ({
                ...current,
                full_html_required: [...current.full_html_required, emptyFullHtmlRule()],
              }))}
            >
              Add Sender
            </button>
          </div>
          {rulesForm.full_html_required.length ? (
            <div className="gmail-rule-list">
              {rulesForm.full_html_required.map((rule, index) => (
                <div className="gmail-rule-row gmail-rule-row-compact" key={`html-${index}`}>
                  <select
                    value={rule.match_type || "domain"}
                    onChange={(event) => updateFullHtmlRule(index, "match_type", event.target.value)}
                  >
                    {MATCH_TYPE_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                  <input
                    value={rule.value || ""}
                    onChange={(event) => updateFullHtmlRule(index, "value", event.target.value)}
                    placeholder="c.visionworks.com"
                  />
                  <label className="gmail-rule-check">
                    <input
                      type="checkbox"
                      checked={rule.enabled !== false}
                      onChange={(event) => updateFullHtmlRule(index, "enabled", event.target.checked)}
                    />
                    enabled
                  </label>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setRulesForm((current) => ({
                      ...current,
                      full_html_required: current.full_html_required.filter((_, ruleIndex) => ruleIndex !== index),
                    }))}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted tiny">No full HTML extraction senders configured.</p>
          )}
        </section>

        {rulesError ? <p className="callout callout-danger">{rulesError}</p> : null}
        {rulesNotice ? <p className="callout callout-success">{rulesNotice}</p> : null}
        <button className="btn btn-primary" type="button" onClick={saveRules} disabled={savingRules}>
          {savingRules ? "Saving..." : "Save Gmail Rules"}
        </button>
      </div>
    </article>
  );
}
