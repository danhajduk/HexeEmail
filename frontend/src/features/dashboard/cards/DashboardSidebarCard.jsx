export function DashboardSidebarCard({ dashboardSection, openDashboard }) {
  return (
    <aside className="card operational-shell-nav-card">
      <nav className="operational-shell-nav" aria-label="Operational sections">
        <button
          type="button"
          className={`btn operational-nav-btn ${dashboardSection === "overview" ? "btn-primary" : ""}`}
          onClick={() => openDashboard("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          className={`btn operational-nav-btn ${dashboardSection === "gmail" ? "btn-primary" : ""}`}
          onClick={() => openDashboard("gmail")}
        >
          Gmail
        </button>
        <button
          type="button"
          className={`btn operational-nav-btn ${dashboardSection === "runtime" ? "btn-primary" : ""}`}
          onClick={() => openDashboard("runtime")}
        >
          Runtime
        </button>
        <button
          type="button"
          className={`btn operational-nav-btn ${dashboardSection === "scheduled" ? "btn-primary" : ""}`}
          onClick={() => openDashboard("scheduled")}
        >
          Scheduled Tasks
        </button>
        <button
          type="button"
          className={`btn operational-nav-btn ${dashboardSection === "orders" ? "btn-primary" : ""}`}
          onClick={() => openDashboard("orders")}
        >
          Tracked Orders
        </button>
        <button
          type="button"
          className={`btn operational-nav-btn ${dashboardSection === "shipments" ? "btn-primary" : ""}`}
          onClick={() => openDashboard("shipments")}
        >
          Shipments
        </button>
        <button type="button" className="btn operational-nav-btn">Activity</button>
        <button type="button" className="btn operational-nav-btn">Diagnostics</button>
      </nav>
    </aside>
  );
}
