import { useEffect, useState } from "react";

export function TrainingPage({
  trainingStatus,
  trainingLoading,
  trainingError,
  trainingBatch,
  trainingBatchLoading,
  trainingBatchError,
  trainingSavePending,
  trainingModelPending,
  trainingNotice,
  trainingSelections,
  trainingLabelOptions,
  onBack,
  onOpenSenderReputation,
  onLoadClassifiedLabelBatch,
  onLoadManualBatch,
  onLoadSemiAutoBatch,
  onLoadSemiAutoBatch300,
  onTrainModel,
  onTrainHighConfidenceModel,
  onSelectionChange,
  onSaveBatch,
}) {
  const [trainingPage, setTrainingPage] = useState(0);
  const items = trainingBatch?.items || [];
  const pageSize = 5;
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(trainingPage, pageCount - 1);
  const pageStart = currentPage * pageSize;
  const visibleItems = items.slice(pageStart, pageStart + pageSize);

  useEffect(() => {
    setTrainingPage(0);
  }, [trainingBatch?.count]);

  return (
    <main className="app-frame">
      <section className="hero card">
        <div>
          <div className="hero-topline">
            <div className="eyebrow">Hexe Email Node</div>
            <div className="status-pill tone-warning">gmail: training</div>
          </div>
          <h1>Training</h1>
          <p className="hero-copy">
            Review flattened local mail and apply manual labels for future local classification work.
          </p>
        </div>
      </section>

      <section className="app-shell">
        <aside className="card stack flow-sidebar">
          <div className="section-heading">
            <h2>Training</h2>
            <span className="pill">{trainingBatch?.count ?? 0} mails</span>
          </div>
          <div className="stack compact-stack">
            <button className="btn btn-ghost" type="button" onClick={onBack}>
              Back To Dashboard
            </button>
            <button className="btn btn-primary" type="button" onClick={onLoadManualBatch} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Manual Classify"}
            </button>
            <button className="btn" type="button" onClick={onTrainModel} disabled={trainingModelPending}>
              {trainingModelPending ? "Training..." : "Train Model"}
            </button>
            <button className="btn" type="button" onClick={onTrainHighConfidenceModel} disabled={trainingModelPending}>
              {trainingModelPending ? "Training..." : "Train 92%+"}
            </button>
            <button className="btn" type="button" onClick={onLoadSemiAutoBatch} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Semi Auto Classify"}
            </button>
            <button className="btn" type="button" onClick={onLoadSemiAutoBatch300} disabled={trainingBatchLoading}>
              {trainingBatchLoading ? "Loading..." : "Semi Auto 300"}
            </button>
            <button className="btn" type="button" onClick={onOpenSenderReputation}>
              Show Sender Reputation
            </button>
            <div className="callout">
              Threshold: {trainingStatus?.threshold ?? 0.6}
            </div>
            <div className="callout">
              Classified: {trainingStatus?.classification_summary?.classified_count ?? 0}
            </div>
            <div className="callout">
              Manual Labels: {trainingStatus?.classification_summary?.manual_count ?? 0}
            </div>
            <div className="callout">
              High Confidence: {trainingStatus?.classification_summary?.high_confidence_count ?? 0}
            </div>
            <div className="callout">
              Model: {trainingStatus?.model_status?.trained
                ? `trained (${trainingStatus?.model_status?.train_count ?? 0} train / ${trainingStatus?.model_status?.test_count ?? 0} test)`
                : "not trained"}
            </div>
            {trainingStatus?.classification_summary?.per_label
              ? (
                <div className="training-sidebar-stats">
                  {Object.entries(trainingStatus.classification_summary.per_label).map(([label, count]) => (
                    <div key={label} className="training-sidebar-stat">
                      <button className="btn btn-ghost" type="button" onClick={() => onLoadClassifiedLabelBatch(label)}>
                        {label}
                      </button>
                      <strong>{count}</strong>
                    </div>
                  ))}
                </div>
                )
              : null}
            {trainingLoading ? <div className="callout">Loading training status...</div> : null}
            {trainingError ? <div className="callout callout-danger">{trainingError}</div> : null}
            {trainingBatchError ? <div className="callout callout-danger">{trainingBatchError}</div> : null}
            {trainingNotice ? <div className="callout callout-success">{trainingNotice}</div> : null}
          </div>
        </aside>

        <div className="main-column">
          <article className="card stack">
            <div className="card-header">
              <h2>Manual Classification</h2>
              <p className="muted">
                {trainingModelPending
                  ? "Training in progress..."
                  : trainingBatch?.source === "classified_label"
                    ? `Showing stored mails already classified as ${trainingBatch?.selected_label || "selected"}`
                    : trainingBatch?.source === "semi_auto"
                      ? "Oldest unclassified mails are pre-labeled by the local model and shown here for review."
                      : "Random unknown or low-confidence mails are flattened into a consistent training format for local review."}
              </p>
            </div>
            {!trainingBatch?.items?.length ? (
              <div className="callout">
                Use <code>Manual Classify</code> to load up to 40 local emails for review.
              </div>
            ) : (
              <>
                <div className="actions">
                  <button className="btn btn-primary" type="button" onClick={onSaveBatch} disabled={trainingSavePending}>
                    {trainingSavePending ? "Saving..." : "Save Manual Labels"}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.max(page - 1, 0))}
                    disabled={currentPage === 0}
                  >
                    Previous 5
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.min(page + 1, pageCount - 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next 5
                  </button>
                  <span className="muted tiny training-page-meta">
                    Showing {pageStart + 1}-{Math.min(pageStart + visibleItems.length, items.length)} of {items.length}
                  </span>
                </div>
                <div className="training-list">
                  {visibleItems.map((item) => {
                    const selected = trainingSelections[item.message_id] || {
                      label: item.selected_label || item.predicted_label || item.local_label || "unknown",
                      confidence: item.predicted_confidence ?? item.local_label_confidence ?? trainingStatus?.threshold ?? 0.6,
                    };
                    return (
                      <section key={item.message_id} className="training-item">
                        <div className="training-item-top">
                          <div>
                            <strong>{item.subject || "(no subject)"}</strong>
                            <div className="muted tiny">{item.sender_email || "-"}</div>
                          </div>
                          <span className="pill">{item.message_id}</span>
                        </div>
                        {trainingBatch?.source === "semi_auto" && (item.predicted_label || item.raw_predicted_label) ? (
                          <div className="callout">
                            Model Prediction: {item.predicted_label || "unknown"} ({Number(item.predicted_confidence || 0).toFixed(2)})
                            {item.predicted_label === "unknown" && item.raw_predicted_label ? `, top guess was ${item.raw_predicted_label}` : ""}
                          </div>
                        ) : null}
                        <pre className="training-flat-text">{item.raw_text || item.flat_text}</pre>
                        <div className="training-controls">
                          <label className="field">
                            <span className="field-label">Label</span>
                            <select
                              name="label"
                              value={selected.label}
                              onChange={(event) => onSelectionChange(item.message_id, "label", event.target.value)}
                            >
                              {trainingLabelOptions.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span className="field-label">Confidence</span>
                            <input
                              type="number"
                              min="0"
                              max="1"
                              step="0.05"
                              value={selected.confidence}
                              onChange={(event) => onSelectionChange(item.message_id, "confidence", event.target.value)}
                            />
                          </label>
                        </div>
                      </section>
                    );
                  })}
                </div>
                <div className="actions">
                  <button className="btn btn-primary" type="button" onClick={onSaveBatch} disabled={trainingSavePending}>
                    {trainingSavePending ? "Saving..." : "Save Manual Labels"}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.max(page - 1, 0))}
                    disabled={currentPage === 0}
                  >
                    Previous 5
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => setTrainingPage((page) => Math.min(page + 1, pageCount - 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next 5
                  </button>
                  <span className="muted tiny training-page-meta">
                    Showing {pageStart + 1}-{Math.min(pageStart + visibleItems.length, items.length)} of {items.length}
                  </span>
                </div>
              </>
            )}
          </article>
        </div>
      </section>
    </main>
  );
}
