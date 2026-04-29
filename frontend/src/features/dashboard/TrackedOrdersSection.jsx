import { TrackedOrdersCard } from "./cards/TrackedOrdersCard";

export function TrackedOrdersSection({
  trackedOrdersSorted,
  formatScheduleTimestamp,
  title,
  description,
  emptyMessage,
  trackingIntegrations,
  liveTrackingPending,
  enableLiveTracking,
  refreshLiveTracking,
}) {
  return (
    <section className="grid scheduled-tasks-grid">
      <TrackedOrdersCard
        trackedOrdersSorted={trackedOrdersSorted}
        formatScheduleTimestamp={formatScheduleTimestamp}
        title={title}
        description={description}
        emptyMessage={emptyMessage}
        trackingIntegrations={trackingIntegrations}
        liveTrackingPending={liveTrackingPending}
        enableLiveTracking={enableLiveTracking}
        refreshLiveTracking={refreshLiveTracking}
      />
    </section>
  );
}
