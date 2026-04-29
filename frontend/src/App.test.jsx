import { describe, expect, it } from "vitest";
import { buildGmailLastHourPipelinePills } from "./App";

function valuesByKey(pills) {
  return Object.fromEntries(pills.map((pill) => [pill.key, pill.value]));
}

describe("Gmail pipeline pill state", () => {
  it("turns on fetch while a Gmail fetch is active", () => {
    const values = valuesByKey(buildGmailLastHourPipelinePills(null, { gmailActionPending: "last_hour" }));

    expect(values.fetch).toBe("in_progress");
    expect(values.local).toBe("idle");
    expect(values.ai).toBe("idle");
  });

  it("turns on the current classifier stage from runtime progress", () => {
    const values = valuesByKey(buildGmailLastHourPipelinePills(null, {
      runtimeTaskStatus: {
        request_status: "running",
        updated_at: new Date().toISOString(),
        last_step: "execute_batch",
        execution_response: { stage: "ai" },
        scheduler_task_states: {
          gmail_hourly_batch_classification: { status: "running" },
        },
      },
    }));

    expect(values.local).toBe("completed");
    expect(values.ai).toBe("in_progress");
  });

  it("does not keep classification on for a stopped stale scheduler run", () => {
    const values = valuesByKey(buildGmailLastHourPipelinePills(null, {
      runtimeTaskStatus: {
        request_status: "running",
        updated_at: "2026-01-01T00:00:00.000Z",
        last_step: "execute_batch",
        execution_response: { stage: "ai" },
        scheduler_task_states: {
          gmail_hourly_batch_classification: { status: "stopped" },
        },
      },
    }));

    expect(values.local).toBe("idle");
    expect(values.ai).toBe("idle");
  });
});
