import { Activity, BarChart3, FolderKanban, LayoutDashboard, Send, ShieldCheck, Users } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { WorkflowBreadcrumb } from "../navigation/WorkflowBreadcrumb.jsx";

const nav = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/patients", "Patients", Users],
  ["/cases", "Cases", FolderKanban],
  ["/submissions", "Submissions", Send],
  ["/analytics", "Analytics", BarChart3],
  ["/governance", "AI Governance", ShieldCheck],
];

export function AppShell() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const onPatients = pathname === "/patients" || pathname.startsWith("/patients/");
  const onCaseWorkspace = /^\/cases\/[^/]+(?:\/(?:reporting-form|completion))?$/.test(pathname);

  return (
    <div className={`shell${onPatients ? " patients-shell" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={18} /></div>
          <div><strong>SIGNAL</strong><small>Public Health Intelligence</small></div>
        </div>
        <nav>
          {nav.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={false} className={({ isActive }) => `nav-item${isActive ? " active" : ""}${to === "/cases" && onCaseWorkspace ? " contextual" : ""}`}>
              <Icon size={18} /><span>{label}{to === "/cases" && onCaseWorkspace && <small className="nav-context">Case Workspace</small>}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button type="button" className="sidebar-signout" onClick={() => {
            sessionStorage.removeItem("signal-auth");
            sessionStorage.removeItem("signal-user");
            localStorage.removeItem("signal-auth");
            localStorage.removeItem("signal-user");
            navigate("/login", { replace: true });
          }}>Sign out</button>
          <span><span className="dot ok" /> Backend connected through API</span>
        </div>
      </aside>
      <main className="main">
       
        <WorkflowBreadcrumb />
        <Outlet />
      </main>
    </div>
  );
}
