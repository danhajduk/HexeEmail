export function TrainingSidebarCard({
  trainingBatch,
  onBack,
  onLoadManualBatch,
  trainingBatchLoading,
  onTrainModel,
  trainingModelPending,
  onTrainHighConfidenceModel,
  onLoadSemiAutoBatch,
  onLoadSemiAutoBatch300,
  onOpenSenderReputation,
  trainingStateTone,
  trainingStateLabel,
  trainingScoreLabel,
  trainingStatus,
  onLoadClassifiedLabelBatch,
  trainingLoading,
  trainingError,
  trainingBatchError,
  trainingNotice,
}) {
  return (
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
        <div className={`callout training-status-card tone-${trainingStateTone}`}>
          <strong>Training Status</strong>
          <div>{trainingStateLabel}</div>
          <div>Score: {trainingScoreLabel}</div>
        </div>
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
        {trainingStatus?.classification_summary?.per_label ? (
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
        ) : null}
        {trainingLoading ? <div className="callout">Loading training status...</div> : null}
        {trainingError ? <div className="callout callout-danger">{trainingError}</div> : null}
        {trainingBatchError ? <div className="callout callout-danger">{trainingBatchError}</div> : null}
        {trainingNotice ? <div className="callout callout-success">{trainingNotice}</div> : null}
      </div>
    </aside>
  );
}
