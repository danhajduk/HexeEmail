import { describe, expect, it } from "vitest";
import { buildHashRoute, DASHBOARD_SECTIONS, parseHashRoute } from "./router";

describe("router helpers", () => {
  it("parses dashboard sections and falls back to overview", () => {
    expect(parseHashRoute("#/dashboard/gmail")).toEqual({ view: "dashboard", dashboardSection: "gmail" });
    expect(parseHashRoute("#/dashboard/not-real")).toEqual({ view: "dashboard", dashboardSection: "overview" });
  });

  it("parses provider and training routes", () => {
    expect(parseHashRoute("#/provider")).toEqual({ view: "provider", dashboardSection: "overview" });
    expect(parseHashRoute("#/training")).toEqual({ view: "training", dashboardSection: "overview" });
    expect(parseHashRoute("#/training/reputation")).toEqual({ view: "training_reputation", dashboardSection: "overview" });
  });

  it("builds hashes from known views", () => {
    expect(buildHashRoute("dashboard", "scheduled")).toBe("#/dashboard/scheduled");
    expect(buildHashRoute("dashboard", "unknown")).toBe("#/dashboard/overview");
    expect(buildHashRoute("provider")).toBe("#/provider");
    expect(buildHashRoute("training")).toBe("#/training");
    expect(buildHashRoute("training_reputation")).toBe("#/training/reputation");
    expect(buildHashRoute("setup")).toBe("#/setup");
  });

  it("keeps the standards dashboard section set", () => {
    expect(Array.from(DASHBOARD_SECTIONS)).toEqual(["overview", "gmail", "runtime", "scheduled", "orders"]);
  });
});
