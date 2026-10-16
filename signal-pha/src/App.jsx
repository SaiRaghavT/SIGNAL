
import {
  Activity,
  FileText,
  ShieldCheck,
} from "lucide-react";
import {
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import IncomingReports from "./pages/IncomingReports";
import ReportReview from "./pages/ReportReview";
import "./App.css";

function DashboardPlaceholder() {
  const navigate = useNavigate();

  return (
    <main className="pha-page dashboard-placeholder">
      <div className="eyebrow">PUBLIC HEALTH AUTHORITY</div>
      <h1>Dashboard</h1>
      <p>
        The dashboard will be connected after the incoming reports workflow
        is verified.
      </p>
      <button
        className="refresh-button"
        onClick={() => navigate("/reports")}
      >
        <FileText size={16} />
        Open Incoming Reports
      </button>
    </main>
  );
}

export default function App() {
  const location = useLocation();
  const isReview = /^\/reports\/[^/]+/.test(location.pathname);

  return (
    <div className="pha-app">
      <section className="main-shell">
        <header className="pha-site-header">
          <div className="utility-bar">
            <Link to="/reports" className="pha-brand" aria-label="SIGNAL-PHA home">
              <span className="pha-brand-mark"><Activity size={21} /></span>
              <span className="pha-brand-copy">
                <strong>Texas-PHA</strong>
                <small>Public Health Authority</small>
              </span>
            </Link>
            <span className="demonstration-label"><ShieldCheck size={15} /> Demonstration application</span>
          </div>
          <nav className="primary-navigation" aria-label="Primary navigation">
            <NavLink to="/reports" end>Incoming Reports</NavLink>
            {isReview && <NavLink to={location.pathname} end>Reporting Review</NavLink>}
          </nav>
        </header>

        <Routes>
          <Route path="/" element={<Navigate to="/reports" replace />} />
          <Route path="/reports" element={<IncomingReports />} />
          <Route
            path="/reports/:submissionId"
            element={<ReportReview />}
          />
          <Route path="/dashboard" element={<DashboardPlaceholder />} />
          <Route path="*" element={<Navigate to="/reports" replace />} />
        </Routes>
      </section>
    </div>
  );
}
