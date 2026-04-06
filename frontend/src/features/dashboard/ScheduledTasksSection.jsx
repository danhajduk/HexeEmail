export function ScheduledTasksSection({
  scheduledTasksSorted,
  scheduledTaskLegend,
  scheduledTaskStatusTone,
  formatScheduleTimestamp,
  formatRelativeTime,
}) {
  const taskKindLabel = (value) => {
    if (value === "node_local_recurring_work") return "Node-local";
    if (value === "provider_recurring_work") return "Provider";
    if (value === "core_leased_recurring_work") return "Core-leased";
    return value || "-";
  };

  return (
    <section className="grid scheduled-tasks-grid">
      <article className="card scheduled-tasks-card">
        <div className="card-header">
          <h2>Scheduled Tasks</h2>
          <p className="muted">Scheduler-driven background jobs with current cadence and latest execution state.</p>
        </div>
        {scheduledTasksSorted.length ? (
          <div className="scheduled-tasks-table-wrap">
            <table className="scheduled-tasks-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Kind</th>
                  <th>Schedule</th>
                  <th>Status</th>
                  <th>Last Execution</th>
                  <th>Next Execution</th>
                  <th>Last Reason</th>
                  <th>Last Slot</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {scheduledTasksSorted.map((task) => (
                  <tr key={task.task_id}>
                    <td><strong>{task.title || task.task_id}</strong></td>
                    <td>
                      <div>{taskKindLabel(task.kind)}</div>
                      <div className="muted tiny">{task.owner || "-"}</div>
                    </td>
                    <td>
                      <div><code>{task.schedule_name || "-"}</code></div>
                      <div className="muted tiny">{task.schedule_detail || "-"}</div>
                    </td>
                    <td>
                      <span className={`status-pill tone-${scheduledTaskStatusTone(task.status)}`}>
                        {task.status || "unknown"}
                      </span>
                    </td>
                    <td>
                      <div>{formatScheduleTimestamp(task.last_execution_at)}</div>
                      <div className="muted tiny">{formatRelativeTime(task.last_execution_at)}</div>
                    </td>
                    <td>{formatScheduleTimestamp(task.next_execution_at)}</td>
                    <td>{task.last_reason || "-"}</td>
                    <td><code>{task.last_slot_key || "-"}</code></td>
                    <td>{task.detail || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="callout">No scheduled task data is available yet.</div>
        )}
        <div className="scheduled-tasks-legend">
          {scheduledTaskLegend.map((item) => (
            <div key={item.name} className="scheduled-tasks-legend-item">
              <code>{item.name}</code>
              <span className="muted tiny">{item.detail}</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
