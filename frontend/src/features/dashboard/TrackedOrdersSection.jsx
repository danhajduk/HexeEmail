import { TrackedOrdersCard } from "./cards/TrackedOrdersCard";

export function TrackedOrdersSection({ trackedOrdersSorted, formatScheduleTimestamp }) {
  return (
    <section className="grid scheduled-tasks-grid">
      <TrackedOrdersCard trackedOrdersSorted={trackedOrdersSorted} formatScheduleTimestamp={formatScheduleTimestamp} />
    </section>
  );
}
