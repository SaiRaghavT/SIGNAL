import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity,
  ClipboardList,
  Clock3,
  FileCheck2,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { clearAdminQueueEntries } from "../../utils/adminQueueLocalStorage.js";
import { clearClinicalInformationRequests } from "../../utils/clinicalInformationRequests.js";
import "../../styles/AdminShell.css";

const TEMPORARY_WORKFLOW_PREFIXES = [
  "signal:missing-information:",
  "signal:reporting-preview:",
  "signal:case-workflow-session:",
  "signal:demo-workflow:",
];

function clearTemporaryWorkflowValues() {
  for (const storage of [window.sessionStorage, window.localStorage]) {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (key && TEMPORARY_WORKFLOW_PREFIXES.some((prefix) => key.startsWith(prefix))) {
        storage.removeItem(key);
      }
    }
  }
}

const NAVIGATION = [
  {
    label: "Dashboard",
    path: "/admin/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Reporting Queue",
    path: "/admin/queue",
    icon: ClipboardList,
  },
  {
    label: "Submissions",
    path: "/admin/submissions",
    icon: FileCheck2,
  },
  {
    label: "Deadlines",
    path: "/admin/deadlines",
    icon: Clock3,
  },
  {
    label: "Audit Trails",
    path: "/admin/audit",
    icon: ShieldCheck,
  },
];

export default function AdminShell() {
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  const storedUser =
    sessionStorage.getItem("signal-user") ||
    localStorage.getItem("signal-user");

  let user = {
    name: "SIGNAL Administrator",
    role: "Administrator",
  };

  try {
    if (storedUser) {
      user = {
        ...user,
        ...JSON.parse(storedUser),
      };
    }
  } catch {
    // Keep default administrator information.
  }

  const handleLogout = () => {
    if (loggingOut) return;
    setLoggingOut(true);

    clearAdminQueueEntries();
    clearClinicalInformationRequests();
    clearTemporaryWorkflowValues();
    sessionStorage.clear();
    localStorage.clear();

    navigate("/login", { replace: true });
  };

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        {/* BRAND */}
        <div className="admin-brand">
          <div className="admin-brand-mark">S</div>

          <div className="admin-brand-copy">
            <div className="admin-brand-title">
              SIGNAL
            </div>

            <div className="admin-brand-subtitle">
              PUBLIC HEALTH REPORTING
              <br />
              INTELLIGENCE LAYER
            </div>
          </div>
        </div>

        {/* WORKSPACE */}
        <div className="admin-workspace-label">
          WORKSPACE
        </div>

        <nav className="admin-navigation">
          {NAVIGATION.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `admin-nav-item ${
                    isActive ? "active" : ""
                  }`
                }
              >
                <Icon
                  size={17}
                  strokeWidth={1.8}
                />

                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* BOTTOM USER AREA */}
        <div className="admin-sidebar-bottom">
          <div className="admin-system-status">
            <span className="admin-status-dot" />

            <div>
              <strong>System Operational</strong>
              <small>Reporting services active</small>
            </div>
          </div>

          <div className="admin-user">
            <div className="admin-user-avatar">
              <Activity size={17} />
            </div>

            <div className="admin-user-info">
              <strong>{user.name}</strong>
              <span>{user.role}</span>
            </div>
          </div>

          <button
            type="button"
            className="admin-logout-button"
            onClick={handleLogout}
            disabled={loggingOut}
          >
            <LogOut size={16} />
            <span>{loggingOut ? "Signing out..." : "Sign out"}</span>
          </button>
        </div>
      </aside>

      {/* MAIN WORKSPACE */}
      <div className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar-title">
            <span>ADMINISTRATOR</span>
            <strong>Public Health Reporting</strong>
          </div>

          <div className="admin-topbar-status">
            <span className="admin-topbar-dot" />
            Operational
          </div>
        </header>

        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
