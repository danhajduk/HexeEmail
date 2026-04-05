export const DASHBOARD_SECTIONS = new Set(["overview", "gmail", "runtime", "scheduled", "orders"]);

export function parseHashRoute(hash) {
  const normalized = String(hash || "").replace(/^#\/?/, "").replace(/^\/+|\/+$/g, "");
  if (!normalized) {
    return { view: "dashboard", dashboardSection: "overview" };
  }

  const [head, tail] = normalized.split("/");
  if (head === "dashboard") {
    const section = DASHBOARD_SECTIONS.has(tail) ? tail : "overview";
    return { view: "dashboard", dashboardSection: section };
  }
  if (head === "provider") {
    return { view: "provider", dashboardSection: "overview" };
  }
  if (head === "training" && tail === "reputation") {
    return { view: "training_reputation", dashboardSection: "overview" };
  }
  if (head === "training") {
    return { view: "training", dashboardSection: "overview" };
  }
  return { view: "setup", dashboardSection: "overview" };
}

export function buildHashRoute(view, dashboardSection) {
  if (view === "dashboard") {
    const section = DASHBOARD_SECTIONS.has(dashboardSection) ? dashboardSection : "overview";
    return `#/dashboard/${section}`;
  }
  if (view === "provider") {
    return "#/provider";
  }
  if (view === "training") {
    return "#/training";
  }
  if (view === "training_reputation") {
    return "#/training/reputation";
  }
  return "#/setup";
}
