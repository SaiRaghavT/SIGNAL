import { Activity, BarChart3, ClipboardCheck, FolderKanban, Inbox, LayoutDashboard, ScanSearch, ScrollText, Send, Users } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const nav = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/information", "Information Received", Inbox],
  ["/patients", "Patients", Users],
  ["/candidates", "Candidates", ScanSearch],
  ["/cases", "Cases", FolderKanban],
  ["/submissions", "Submissions", Send],
  ["/follow-ups", "Follow-ups", ClipboardCheck],
  ["/analytics", "Analytics", BarChart3],
  ["/audit", "Technical / Audit", ScrollText],
];

export function AppShell() {
  const { pathname } = useLocation();
  const onPatients = pathname === "/patients";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={18} /></div>
          <div><strong>SIGNAL</strong><small>Public Health Intelligence</small></div>
        </div>
        <nav>
          {nav.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot"><span className="dot ok" /> Backend connected through API</div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">{onPatients ? "Workspace" : "SIGNAL MVP"}</span>
            <h1>{onPatients ? "Patients" : "Public Health Reporting Intelligence Layer"}</h1>
          </div>
          {onPatients ? (
            <div className="role-chip"><span className="dot ok" /> System Online</div>
          ) : <div className="role-chip">Reporting User</div>}
        </header>
        <Outlet />
      </main>
    </div>
  );
}
