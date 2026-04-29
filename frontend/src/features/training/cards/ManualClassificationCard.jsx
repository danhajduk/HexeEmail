export function ManualClassificationCard({
  trainingModelPending,
  trainingBatch,
  onSaveBatch,
  trainingSavePending,
  currentPage,
  setTrainingPage,
  pageCount,
  pageStart,
  visibleItems,
  items,
  trainingSelections,
  trainingStatus,
  onSelectionChange,
  trainingLabelOptions,
}) {
  return (
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
  );
}
