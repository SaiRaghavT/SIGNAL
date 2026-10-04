import {
  LayoutDashboard,
  Users,
  FolderKanban,
  Send,
  ClipboardCheck,
  ScrollText,
  Activity,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const nav = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/patients", "Patients", Users],
  ["/cases", "Cases", FolderKanban],
  ["/submissions", "Submissions", Send],
  ["/follow-ups", "PHA Follow-up", ClipboardCheck],
  ["/audit", "Audit", ScrollText],
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="brand">
        <div className="brand-mark">
          <span>S</span>
        </div>

        <div className="brand-copy">
          <strong>SIGNAL</strong>
          <small>INTELLIGENCE LAYER</small>
        </div>
      </div>

      {/* Navigation */}
      <div className="sidebar-section-label">
        WORKSPACE
      </div>

      <nav className="sidebar-nav">
        {nav.map(([to, label, Icon]) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive
                ? "nav-item active"
                : "nav-item"
            }
          >
            <Icon
              size={18}
              strokeWidth={1.8}
            />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="sidebar-bottom">
        <div className="sidebar-signal-badge">
          <div className="sidebar-signal-icon">
            <Activity size={17} />
          </div>

          <div>
            <strong>SIGNAL</strong>
            <span>
              Public Health Intelligence
            </span>
          </div>
        </div>

        <div className="sidebar-status">
          <span className="status-dot online" />
          <span>System Online</span>
        </div>
      </div>
    </aside>
  );
}