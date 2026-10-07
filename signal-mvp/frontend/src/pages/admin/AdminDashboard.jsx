import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Layers3,
  RefreshCw,
  Send,
  Timer,
  UserRoundCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { getAdminDashboard } from "../../services/adminService.js";
import "../../styles/AdminDashboard.css";

const EMPTY_DASHBOARD = {
  ready_for_submission: 0,
  immediate_reports: 0,
  individual_reports: 0,
  pending_batches: 0,
  submitted_today: 0,
  awaiting_acknowledgement: 0,
  failed: 0,
  retry_required: 0,
  overdue: 0,
  due_today: 0,
  due_soon: 0,
};

function MetricCard({ label, value, icon: Icon, tone = "default" }) {
  return (
    <div className={`admin-metric-card ${tone}`}>
      <div className="admin-metric-icon">
        <Icon size={18} />
      </div>

      <div className="admin-metric-content">
        <span className="admin-metric-label">{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [dashboard, setDashboard] = useState(EMPTY_DASHBOARD);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await getAdminDashboard();

      setDashboard({
        ...EMPTY_DASHBOARD,
        ...(data || {}),
      });
    } catch (err) {
      setError(err.message || "Unable to load Admin Dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const totalOperationalWork =
    dashboard.ready_for_submission +
    dashboard.immediate_reports +
    dashboard.individual_reports +
    dashboard.pending_batches;

  const totalDeadlineRisk =
    dashboard.overdue +
    dashboard.due_today +
    dashboard.due_soon;

  return (
    <section className="admin-dashboard-page">
      <div className="admin-page-header">
        <div>
          <span className="admin-page-kicker">SUPER ADMIN</span>

          <h2>Dashboard</h2>

          <p>
            Monitor reporting operations, submission readiness,
            deadlines, and public-health reporting activity.
          </p>
        </div>

        <button
          type="button"
          className="admin-refresh-button"
          onClick={loadDashboard}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? "is-spinning" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="admin-dashboard-error">
          <AlertCircle size={17} />
          <span>{error}</span>

          <button type="button" onClick={loadDashboard}>
            Retry
          </button>
        </div>
      )}

      <div className="admin-section">
        <div className="admin-section-heading">
          <div>
            <span className="admin-section-kicker">
              REPORTING OPERATIONS
            </span>

            <h3>Submission Overview</h3>
          </div>

          <span className="admin-section-total">
            {totalOperationalWork} active items
          </span>
        </div>

        <div className="admin-metric-grid">
          <MetricCard
            label="Ready for Submission"
            value={dashboard.ready_for_submission}
            icon={FileCheck2}
            tone="success"
          />

          <MetricCard
            label="Immediate Reports"
            value={dashboard.immediate_reports}
            icon={AlertCircle}
            tone="danger"
          />

          <MetricCard
            label="Individual Reports"
            value={dashboard.individual_reports}
            icon={Send}
            tone="info"
          />

          <MetricCard
            label="Pending Batches"
            value={dashboard.pending_batches}
            icon={Layers3}
            tone="purple"
          />

          <MetricCard
            label="Submitted Today"
            value={dashboard.submitted_today}
            icon={CheckCircle2}
            tone="success"
          />

          <MetricCard
            label="Awaiting Acknowledgement"
            value={dashboard.awaiting_acknowledgement}
            icon={Clock3}
            tone="warning"
          />

          <MetricCard
            label="Failed"
            value={dashboard.failed}
            icon={AlertCircle}
            tone="danger"
          />

          <MetricCard
            label="Retry Required"
            value={dashboard.retry_required}
            icon={RefreshCw}
            tone="warning"
          />
        </div>
      </div>

      <div className="admin-dashboard-columns">
        <section className="admin-panel">
          <div className="admin-panel-header">
            <div>
              <span className="admin-section-kicker">WORK QUEUE</span>
              <h3>Reporting Queue</h3>
              <p>
                Review cases that require administrative reporting action.
              </p>
            </div>

            <Link to="/admin/queue" className="admin-panel-link">
              Open Queue
              <ArrowRight size={15} />
            </Link>
          </div>

          <div className="admin-queue-summary">
            <div className="admin-queue-row">
              <div>
                <span className="admin-status-dot immediate" />
                <span>Immediate</span>
              </div>

              <strong>{dashboard.immediate_reports}</strong>
            </div>

            <div className="admin-queue-row">
              <div>
                <span className="admin-status-dot individual" />
                <span>Individual</span>
              </div>

              <strong>{dashboard.individual_reports}</strong>
            </div>

            <div className="admin-queue-row">
              <div>
                <span className="admin-status-dot batch" />
                <span>Batch</span>
              </div>

              <strong>{dashboard.pending_batches}</strong>
            </div>

            <div className="admin-queue-row">
              <div>
                <span className="admin-status-dot ready" />
                <span>Ready for Submission</span>
              </div>

              <strong>{dashboard.ready_for_submission}</strong>
            </div>
          </div>
        </section>

        <section className="admin-panel">
          <div className="admin-panel-header">
            <div>
              <span className="admin-section-kicker">COMPLIANCE</span>
              <h3>Reporting Deadlines</h3>
              <p>
                Monitor cases approaching or exceeding reporting deadlines.
              </p>
            </div>

            <Link to="/admin/deadlines" className="admin-panel-link">
              View Deadlines
              <ArrowRight size={15} />
            </Link>
          </div>

          <div className="deadline-summary">
            <div className="deadline-item overdue">
              <div className="deadline-icon">
                <AlertCircle size={17} />
              </div>

              <div>
                <span>Overdue</span>
                <strong>{dashboard.overdue}</strong>
              </div>
            </div>

            <div className="deadline-item today">
              <div className="deadline-icon">
                <Timer size={17} />
              </div>

              <div>
                <span>Due Today</span>
                <strong>{dashboard.due_today}</strong>
              </div>
            </div>

            <div className="deadline-item soon">
              <div className="deadline-icon">
                <Clock3 size={17} />
              </div>

              <div>
                <span>Due Soon</span>
                <strong>{dashboard.due_soon}</strong>
              </div>
            </div>
          </div>

          <div className="deadline-footer">
            <span>Total deadline attention</span>
            <strong>{totalDeadlineRisk}</strong>
          </div>
        </section>
      </div>

      <div className="admin-dashboard-columns">
        <section className="admin-panel admin-status-panel">
          <div className="admin-panel-header">
            <div>
              <span className="admin-section-kicker">TRANSMISSION</span>
              <h3>Submission Status</h3>
            </div>

            <Link to="/admin/submissions" className="admin-panel-link">
              View Submissions
              <ArrowRight size={15} />
            </Link>
          </div>

          <div className="admin-status-grid">
            <div>
              <span>Submitted Today</span>
              <strong>{dashboard.submitted_today}</strong>
            </div>

            <div>
              <span>Awaiting Acknowledgement</span>
              <strong>{dashboard.awaiting_acknowledgement}</strong>
            </div>

            <div>
              <span>Failed</span>
              <strong>{dashboard.failed}</strong>
            </div>

            <div>
              <span>Retry Required</span>
              <strong>{dashboard.retry_required}</strong>
            </div>
          </div>
        </section>

        <section className="admin-panel admin-actions-panel">
          <div className="admin-panel-header">
            <div>
              <span className="admin-section-kicker">ADMINISTRATION</span>
              <h3>Quick Actions</h3>
              <p>Move directly to operational reporting areas.</p>
            </div>
          </div>

          <div className="admin-action-list">
            <Link to="/admin/queue" className="admin-action">
              <span className="admin-action-icon">
                <UserRoundCheck size={17} />
              </span>

              <span>
                <strong>Review Reporting Queue</strong>
                <small>
                  Review cases ready for administrative action.
                </small>
              </span>

              <ArrowRight size={15} />
            </Link>

            <Link to="/admin/submissions" className="admin-action">
              <span className="admin-action-icon">
                <Send size={17} />
              </span>

              <span>
                <strong>Track Submissions</strong>
                <small>
                  Monitor submitted reports and acknowledgements.
                </small>
              </span>

              <ArrowRight size={15} />
            </Link>

            <Link to="/admin/deadlines" className="admin-action">
              <span className="admin-action-icon">
                <Clock3 size={17} />
              </span>

              <span>
                <strong>Monitor Deadlines</strong>
                <small>
                  Review overdue, due today, and upcoming reports.
                </small>
              </span>

              <ArrowRight size={15} />
            </Link>
          </div>
        </section>
      </div>

      <div className="admin-dashboard-footer">
        <span>
          SIGNAL Administrative Reporting Operations
        </span>

        <span>
          Backend-driven operational view
        </span>
      </div>
    </section>
  );
}

export default AdminDashboard;