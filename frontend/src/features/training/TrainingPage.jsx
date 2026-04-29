import { useEffect, useState } from "react";
import { ManualClassificationCard } from "./cards/ManualClassificationCard";
import { TrainingHeroCard } from "./cards/TrainingHeroCard";
import { TrainingSidebarCard } from "./cards/TrainingSidebarCard";

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
  const modelStatus = trainingStatus?.model_status || null;
  const modelScore = typeof modelStatus?.test_accuracy === "number" ? modelStatus.test_accuracy : null;
  const trainingStateLabel = trainingModelPending
    ? "Training model..."
    : trainingSavePending
      ? "Saving labels..."
      : trainingBatchLoading || trainingLoading
        ? "Refreshing training data..."
        : modelStatus?.trained
          ? "Model ready"
          : "Model not trained";
  const trainingStateTone = trainingModelPending || trainingSavePending || trainingBatchLoading || trainingLoading
    ? "warning"
    : modelStatus?.trained
      ? "success"
      : "neutral";
  const trainingScoreLabel = modelScore !== null ? `${(modelScore * 100).toFixed(1)}%` : "Not available";

  useEffect(() => {
    setTrainingPage(0);
  }, [trainingBatch?.count]);

  return (
    <main className="app-frame">
      <TrainingHeroCard />

      <section className="app-shell">
        <TrainingSidebarCard
          trainingBatch={trainingBatch}
          onBack={onBack}
          onLoadManualBatch={onLoadManualBatch}
          trainingBatchLoading={trainingBatchLoading}
          onTrainModel={onTrainModel}
          trainingModelPending={trainingModelPending}
          onTrainHighConfidenceModel={onTrainHighConfidenceModel}
          onLoadSemiAutoBatch={onLoadSemiAutoBatch}
          onLoadSemiAutoBatch300={onLoadSemiAutoBatch300}
          onOpenSenderReputation={onOpenSenderReputation}
          trainingStateTone={trainingStateTone}
          trainingStateLabel={trainingStateLabel}
          trainingScoreLabel={trainingScoreLabel}
          trainingStatus={trainingStatus}
          onLoadClassifiedLabelBatch={onLoadClassifiedLabelBatch}
          trainingLoading={trainingLoading}
          trainingError={trainingError}
          trainingBatchError={trainingBatchError}
          trainingNotice={trainingNotice}
        />

        <div className="main-column">
          <ManualClassificationCard
            trainingModelPending={trainingModelPending}
            trainingBatch={trainingBatch}
            onSaveBatch={onSaveBatch}
            trainingSavePending={trainingSavePending}
            currentPage={currentPage}
            setTrainingPage={setTrainingPage}
            pageCount={pageCount}
            pageStart={pageStart}
            visibleItems={visibleItems}
            items={items}
            trainingSelections={trainingSelections}
            trainingStatus={trainingStatus}
            onSelectionChange={onSelectionChange}
            trainingLabelOptions={trainingLabelOptions}
          />
        </div>
      </section>
    </main>
  );
}
