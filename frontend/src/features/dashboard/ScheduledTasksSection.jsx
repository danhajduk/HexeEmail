import { ScheduledTasksCard } from "./cards/ScheduledTasksCard";

export function ScheduledTasksSection({
  scheduledTasksSorted,
  scheduledTaskLegend,
  scheduledTaskStatusTone,
  formatScheduleTimestamp,
  formatRelativeTime,
}) {
  return (
    <section className="grid scheduled-tasks-grid">
      <ScheduledTasksCard
        scheduledTasksSorted={scheduledTasksSorted}
        scheduledTaskLegend={scheduledTaskLegend}
        scheduledTaskStatusTone={scheduledTaskStatusTone}
        formatScheduleTimestamp={formatScheduleTimestamp}
        formatRelativeTime={formatRelativeTime}
      />
    </section>
  );
}
