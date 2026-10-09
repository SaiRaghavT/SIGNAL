import { useCallback, useEffect, useState } from "react";
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
import { request } from "../../api/client.js";
import { getAdminDashboard, getAdminQueue, getAdminSubmissions } from "../../services/adminService.js";
import { DEMO_DEADLINES } from "./AdminDeadlines.jsx";
import "../../styles/AdminDashboard.css";

const DASHBOARD_FIELDS = [
  "ready_for_submission",
  "immediate_reports",
  "individual_reports",
  "dispatched_reports",
  "completed_submissions",
  "pending_batches",
  "submitted_today",
  "awaiting_acknowledgement",
  "failed",
  "overdue",
  "due_today",
  "due_soon",
];

function displayCount(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : "—";
}

function statusKey(value) {
  return String(value || "").trim().toUpperCase().replace(/[\s-]+/g, "_");
}

function conditionLabel(value) {
  if (Array.isArray(value)) return value.map(conditionLabel).find((item) => item !== "—") || "—";
  if (value && typeof value === "object") {
    for (const key of ["display", "name", "condition_name", "disease_name", "text", "label", "title", "description", "concept", "condition", "disease", "coding", "code", "value"]) {
      const label = conditionLabel(value[key]);
      if (label !== "—") return label;
    }
    return "—";
  }
  if (typeof value === "number") return value === 14189004 ? "Measles" : "—";
  if (typeof value !== "string" || !value.trim()) return "—";

  const candidate = value.trim();
  const code = candidate.match(/(?:^|[|/])\s*(\d{5,})\s*$/)?.[1];
  if (code) return code === "14189004" ? "Measles" : "—";
  if (/^\d+$/.test(candidate) || /(?:snomed|^https?:\/\/)/i.test(candidate)) return "—";
  return candidate;
}

function priorityLabel(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value).trim().replaceAll("_", " ").toUpperCase();
}

function summarizePriority(items) {
  const priorities = items.map((item) => priorityLabel(item.priority)).filter((value) => value !== "—");
  const rank = { URGENT: 5, CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
  return priorities.sort((a, b) => (rank[b] || 0) - (rank[a] || 0))[0] || "—";
}

function deadlineStatus(deadline, now) {
  if (!deadline) return null;
  const date = new Date(deadline);
  if (Number.isNaN(date.getTime())) return null;
  const difference = date.getTime() - now.getTime();
  if (difference < 0) return "OVERDUE";
  if (date.toDateString() === now.toDateString()) return "DUE TODAY";
  if (difference <= 48 * 60 * 60 * 1000) return "DUE SOON";
  return null;
}

function formatDeadline(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function getDeadlineRecord(item, now, isDemo = false) {
  const status = isDemo ? item.status : deadlineStatus(item.deadline, now);
  if (!status || status === "ON TRACK") return null;
  return {
    caseId: item.case_id || item.caseId || "—",
    condition: conditionLabel(item.condition || item.disease),
    destination: item.destination || item.jurisdiction || "—",
    deadline: formatDeadline(item.deadline),
    status,
  };
}

function submissionCounts(rows) {
  return rows.reduce((counts, row) => {
    const status = statusKey(row.status || row.submission_status || row.acknowledgement_status);
    if (status === "ACKNOWLEDGED") counts.acknowledged += 1;
    else if (["FAILED", "ERROR", "REJECTED", "RETRY_REQUIRED", "INFORMATION_REQUESTED", "INFO_REQUESTED"].includes(status)) counts.followUp += 1;
    else if (["SUBMITTED", "PENDING", "AWAITING_ACKNOWLEDGEMENT", "AWAITING_ACK"].includes(status)) counts.pending += 1;
    return counts;
  }, { acknowledged: 0, pending: 0, followUp: 0 });
}

function serviceStatus(agent) {
  if (!agent) return { text: "Status unavailable", healthy: false };
  if (agent.error) return { text: agent.error, healthy: false };
  if (agent.available !== true) return { text: "Unavailable", healthy: false };
  if (agent.configured === false) return { text: "Needs configuration", healthy: false };
  return { text: agent.simulated ? "Operational · simulated" : "Operational", healthy: true };
}

function KpiCard({ label, value, subtitle, icon: Icon, tone, badge }) {
  return (
    <article className={`admin-dashboard-kpi ${tone}`}>
      <div className="admin-dashboard-kpi-top">
        <span>{label}</span>
        <Icon size={17} aria-hidden="true" />
      </div>
      <div className="admin-dashboard-kpi-value-row">
        <strong>{value}</strong>
        {badge && <span className="admin-dashboard-priority-badge">{badge}</span>}
      </div>
      <small>{subtitle}</small>
    </article>
  );
}

function EngineRow({ label, status, healthy }) {
  return (
    <div className="admin-engine-row">
      <span className={`admin-engine-check${healthy === true ? " is-healthy" : healthy === false ? " is-unavailable" : " is-neutral"}`} aria-hidden="true">
        {healthy === true ? "✓" : healthy === false ? "!" : "·"}
      </span>
      <span className="admin-engine-label">{label}</span>
      <small>{status}</small>
    </div>
  );
}

function AdminDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [queueRows, setQueueRows] = useState([]);
  const [queueAvailable, setQueueAvailable] = useState(false);
  const [submissionRows, setSubmissionRows] = useState(null);
  const [agents, setAgents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    const [dashboardResult, queueResult, submissionResult, agentResult] = await Promise.allSettled([
      getAdminDashboard(),
      getAdminQueue(),
      getAdminSubmissions(),
      request("/api/agents/status"),
    ]);

    if (dashboardResult.status === "rejected") {
      setDashboard(null);
      setError(dashboardResult.reason?.message || "Unable to load Admin Dashboard.");
    } else {
      const response = dashboardResult.value || {};
      setDashboard(Object.fromEntries(DASHBOARD_FIELDS.map((key) => [key, response[key]])));
    }

    if (queueResult.status === "fulfilled") {
      setQueueRows(Array.isArray(queueResult.value?.items) ? queueResult.value.items : []);
      setQueueAvailable(true);
    } else {
      setQueueRows([]);
      setQueueAvailable(false);
    }

    if (submissionResult.status === "fulfilled") {
      setSubmissionRows(Array.isArray(submissionResult.value?.items) ? submissionResult.value.items : []);
    } else {
      setSubmissionRows(null);
    }

    if (agentResult.status === "fulfilled" && Array.isArray(agentResult.value?.agents)) {
      setAgents(agentResult.value.agents);
    } else {
      setAgents(null);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const now = new Date();
  const deadlineSource = queueAvailable ? queueRows : DEMO_DEADLINES;
  const deadlineRows = deadlineSource
    .map((item) => getDeadlineRecord(item, now, !queueAvailable))
    .filter(Boolean)
    .sort((left, right) => {
      const order = { OVERDUE: 0, "DUE TODAY": 1, "DUE SOON": 2 };
      return order[left.status] - order[right.status];
    });

  const liveDeadlineCounts = deadlineRows.reduce((counts, row) => {
    if (row.status === "OVERDUE") counts.overdue += 1;
    if (row.status === "DUE TODAY") counts.today += 1;
    if (row.status === "DUE SOON") counts.soon += 1;
    return counts;
  }, { overdue: 0, today: 0, soon: 0 });

  const dashboardDeadlineCounts = {
    overdue: displayCount(dashboard?.overdue),
    today: displayCount(dashboard?.due_today),
    soon: displayCount(dashboard?.due_soon),
  };
  const deadlineCounts = queueAvailable ? liveDeadlineCounts : dashboardDeadlineCounts;
  const deadlineRiskTotal = [deadlineCounts.overdue, deadlineCounts.today, deadlineCounts.soon]
    .every((value) => typeof value === "number")
    ? deadlineCounts.overdue + deadlineCounts.today + deadlineCounts.soon
    : "—";

  const immediateRows = queueRows.filter((item) => statusKey(item.submission_mode) === "IMMEDIATE");
  const individualRows = queueRows.filter((item) => statusKey(item.submission_mode) === "INDIVIDUAL");
  const immediatePriority = summarizePriority(immediateRows);
  const queueReadyCount = typeof dashboard?.ready_for_submission === "number"
    ? dashboard.ready_for_submission
    : null;
  const batchCount = typeof dashboard?.pending_batches === "number"
    ? dashboard.pending_batches
    : null;
  const combinedReady = queueReadyCount !== null && batchCount !== null
    ? queueReadyCount + batchCount
    : "—";
  const statusCounts = submissionRows ? submissionCounts(submissionRows) : null;
  const agentMap = Object.fromEntries((agents || []).map((agent) => [agent.agent_name, agent]));
  const coreAgentNames = ["case_assembly", "reportability_workflow", "deadline_calculation", "ecr_submission", "acknowledgement"];
  const engineHealthy = Array.isArray(agents) && coreAgentNames.every((name) => serviceStatus(agentMap[name]).healthy);
  const engineStatusText = !Array.isArray(agents)
    ? "SIGNAL Engine Status Unavailable"
    : engineHealthy
      ? "SIGNAL Engine Operational"
      : "SIGNAL Engine Needs Attention";

  const queueTypes = [
    { name: "Immediate", count: displayCount(dashboard?.immediate_reports), priority: immediatePriority, source: "SIGNAL Engine" },
    { name: "Individual", count: displayCount(dashboard?.individual_reports), priority: summarizePriority(individualRows), source: "SIGNAL Engine" },
    { name: "Batch", count: displayCount(dashboard?.pending_batches), priority: "—", source: "Backend-generated" },
  ];

  const statusItems = [
    { label: "Case Detection", agent: "case_assembly" },
    { label: "Reportability Engine", agent: "reportability_workflow" },
    { label: "Jurisdiction Rules", agent: "deadline_calculation" },
  ].map((item) => ({ ...item, ...serviceStatus(agentMap[item.agent]) }));

  const submissionService = serviceStatus(agentMap.ecr_submission);
  const acknowledgementService = serviceStatus(agentMap.acknowledgement);

  return (
    <section className="admin-dashboard-page">
      <header className="admin-dashboard-header">
        <div>
          <span className="admin-page-kicker">SUPER ADMIN</span>
          <h1>Dashboard</h1>
          <p>Real-time overview of reporting operations, pending submissions, deadlines and SIGNAL Engine activity.</p>
        </div>
        <div className="admin-dashboard-header-actions">
          <div className={`admin-engine-overall${engineHealthy ? " is-healthy" : agents ? " is-attention" : " is-unavailable"}`} role="status">
            <span />
            {engineStatusText}
          </div>
          <button type="button" className="admin-refresh-button" onClick={loadDashboard} disabled={loading} aria-label="Refresh dashboard">
            <RefreshCw size={15} className={loading ? "is-spinning" : ""} />
          </button>
        </div>
      </header>

      {error && <div className="admin-dashboard-error" role="alert"><AlertCircle size={16} />{error}<button type="button" onClick={loadDashboard}>Retry</button></div>}

      <section className="admin-dashboard-kpis" aria-label="Reporting overview">
        <KpiCard
          label="READY FOR SUBMISSION"
          value={loading && !dashboard ? "—" : combinedReady}
          subtitle="Individual/immediate + backend batches"
          icon={FileCheck2}
          tone="success"
        />
        <KpiCard
          label="IMMEDIATE REPORTS"
          value={displayCount(dashboard?.immediate_reports)}
          subtitle="Deadline priority"
          icon={Timer}
          tone="danger"
          badge={immediatePriority === "—" ? null : immediatePriority}
        />
        <KpiCard
          label="BACKEND-GENERATED BATCHES"
          value={displayCount(dashboard?.pending_batches)}
          subtitle="Cases grouped by SIGNAL Engine"
          icon={Layers3}
          tone="warning"
        />
        <KpiCard
          label="SUBMISSION STATUS"
          value={submissionRows ? submissionRows.length : "—"}
          subtitle={statusCounts
            ? `Acknowledged ${statusCounts.acknowledged} · Completed cases ${displayCount(dashboard?.completed_submissions)} · Pending ${statusCounts.pending} · Follow-up ${statusCounts.followUp} · Dispatched ${displayCount(dashboard?.dispatched_reports)}`
            : "Acknowledged · Pending · Follow-up"}
          icon={Send}
          tone="info"
        />
      </section>

      <div className="admin-dashboard-main-grid">
        <div className="admin-dashboard-left-column">
          <section className="admin-panel">
            <div className="admin-panel-header">
              <div>
                <span className="admin-section-kicker">WORK QUEUE</span>
                <h2>Reporting Queue</h2>
                <p>Cases and backend-generated batches awaiting Super Admin review and authorization.</p>
              </div>
              <div className="admin-ready-badge"><strong>{displayCount(combinedReady)}</strong><span>READY</span></div>
            </div>
            <div className="admin-dashboard-table-wrap">
              <table className="admin-dashboard-table admin-queue-table">
                <thead><tr><th>REPORTING TYPE</th><th>PENDING</th><th>PRIORITY</th><th>SOURCE</th><th>ACTION</th></tr></thead>
                <tbody>{queueTypes.map((row) => (
                  <tr key={row.name}>
                    <td><strong>{row.name}</strong></td>
                    <td>{row.count}</td>
                    <td><span className={`admin-priority-tag ${row.priority.toLowerCase()}`}>{row.priority}</span></td>
                    <td>{row.source}</td>
                    <td><Link className="admin-table-action" to="/admin/queue">Review <ArrowRight size={13} /></Link></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>

          <section className="admin-panel">
            <div className="admin-panel-header">
              <div>
                <span className="admin-section-kicker">COMPLIANCE</span>
                <h2>Reporting Deadlines</h2>
                <p>Cases requiring attention based on reporting windows.</p>
              </div>
              <Link to="/admin/deadlines" className="admin-panel-link">View All <ArrowRight size={14} /></Link>
            </div>
            {!queueAvailable && <div className="admin-demo-note">Showing the existing deadline demo rows; dashboard totals remain backend-reported.</div>}
            <div className="admin-deadline-kpis">
              <article className="overdue"><span>OVERDUE</span><strong>{deadlineCounts.overdue}</strong><small>Requires action</small></article>
              <article className="today"><span>DUE TODAY</span><strong>{deadlineCounts.today}</strong><small>Reporting window closes today</small></article>
              <article className="soon"><span>DUE SOON</span><strong>{deadlineCounts.soon}</strong><small>Next 48 hours</small></article>
            </div>
            <div className="admin-dashboard-table-wrap">
              <table className="admin-dashboard-table admin-deadline-table">
                <thead><tr><th>CASE</th><th>CONDITION</th><th>DESTINATION</th><th>DEADLINE</th><th>STATUS</th></tr></thead>
                <tbody>{deadlineRows.slice(0, 5).map((row, index) => (
                  <tr key={`${row.caseId}-${index}`}>
                    <td title={row.caseId}>{row.caseId}</td><td>{row.condition}</td><td>{row.destination}</td><td>{row.deadline}</td>
                    <td><span className={`admin-deadline-status ${row.status.toLowerCase().replaceAll(" ", "-")}`}>{row.status}</span></td>
                  </tr>
                ))}</tbody>
              </table>
              {deadlineRows.length === 0 && <div className="admin-table-empty">No deadline cases requiring attention are available.</div>}
            </div>
          </section>
        </div>

        <aside className="admin-dashboard-right-column">
          <section className="admin-panel">
            <div className="admin-panel-header compact"><div><span className="admin-section-kicker">SHORTCUTS</span><h2>Quick Actions</h2></div></div>
            <div className="admin-quick-actions">
              <Link to="/admin/queue"><span><UserRoundCheck size={15} />Review Immediate Reports</span><strong>{displayCount(dashboard?.immediate_reports)}</strong></Link>
              <Link to="/admin/queue"><span><Layers3 size={15} />Review Backend Batches</span><strong>{displayCount(dashboard?.pending_batches)}</strong></Link>
              <Link to="/admin/queue"><span><FileCheck2 size={15} />Review Individual Reports</span><strong>{displayCount(dashboard?.individual_reports)}</strong></Link>
              <Link to="/admin/deadlines"><span><Clock3 size={15} />View Deadlines</span><strong>{deadlineRiskTotal}</strong></Link>
            </div>
          </section>

          <section className="admin-panel admin-engine-panel">
            <div className="admin-panel-header compact"><div><span className="admin-section-kicker">SYSTEM HEALTH</span><h2>SIGNAL Engine Status</h2></div></div>
            <div className="admin-engine-list">
              {statusItems.map((item) => <EngineRow key={item.agent} label={item.label} status={item.text} healthy={item.healthy} />)}
              <EngineRow label="Batch Generation" status={batchCount === null ? "Status unavailable" : `${batchCount} pending`} healthy={null} />
              <EngineRow label="Reporting Queue" status={`${displayCount(queueReadyCount)} items ready`} healthy={null} />
              <EngineRow label="Submission Service" status={submissionService.text} healthy={submissionService.healthy} />
              <EngineRow label="Acknowledgement Service" status={acknowledgementService.text} healthy={acknowledgementService.healthy} />
            </div>
          </section>

          <section className="admin-panel admin-batches-note">
            <span className="admin-section-kicker">AUTOMATED WORKFLOW</span>
            <h2>Backend-generated batches</h2>
            <p>Batches are created automatically by the SIGNAL Engine. Super Admin reviews, authorizes and submits them.</p>
          </section>
        </aside>
      </div>
    </section>
  );
}

export default AdminDashboard;
