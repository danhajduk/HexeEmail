import { TrackedOrdersCard } from "./cards/TrackedOrdersCard";

export function TrackedOrdersSection({
  trackedOrdersSorted,
  formatScheduleTimestamp,
  title,
  description,
  emptyMessage,
}) {
  return (
    <section className="grid scheduled-tasks-grid">
      <TrackedOrdersCard
        trackedOrdersSorted={trackedOrdersSorted}
        formatScheduleTimestamp={formatScheduleTimestamp}
        title={title}
        description={description}
        emptyMessage={emptyMessage}
      />
    </section>
  );
}
