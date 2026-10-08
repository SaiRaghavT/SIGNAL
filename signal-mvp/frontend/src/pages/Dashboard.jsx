import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Clock3,
  FileCheck2,
  RefreshCw,
  Send,
  Users,
} from "lucide-react";
import { listCanonicalPatients } from "../api/canonical.js";
import { getDashboardSummary } from "../api/dashboard.js";
import { request } from "../api/client.js";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/dashboard.css";

const EMPTY_VALUE = "—";
const PATIENT_PAGE_SIZE = 100;

function responseItems(response) {
  return Array.isArray(response?.items) ? response.items : [];
}

async function listAllCanonicalPatients() {
  const firstPage = await listCanonicalPatients({ page: 1, page_size: PATIENT_PAGE_SIZE });
  const pages = Number(firstPage?.pages) || 1;
  if (pages <= 1) return firstPage;

  const remainingPages = await Promise.all(
    Array.from({ length: pages - 1 }, (_, index) =>
      listCanonicalPatients({ page: index + 2, page_size: PATIENT_PAGE_SIZE }),
    ),
  );
  return {
    ...firstPage,
    items: [...responseItems(firstPage), ...remainingPages.flatMap(responseItems)],
  };
}

function countRows(counts) {
  return Object.entries(counts || {}).map(([label, value]) => ({ label, value }));
}

function titleCase(value) {
  return String(value || "Not recorded")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDateTime(value) {
  if (!value) return EMPTY_VALUE;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return EMPTY_VALUE;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function deadlineDate(patient) {
  const value = patient?.deadline?.deadline
    ?? (typeof patient?.deadline === "string" ? patient.deadline : null);
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDeadline(value) {
  if (!value) return EMPTY_VALUE;
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(value);
}

function patientName(patient) {
  return [patient?.first_name, patient?.last_name]
    .map((name) => String(name || "").replace(/\d+/g, "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join(" ") || "Patient name unavailable";
}

function patientPriority(patient) {
  const urgency = patient?.deadline?.urgency;
  return typeof urgency === "string" && urgency.trim() ? titleCase(urgency) : EMPTY_VALUE;
}

function errorMessage(result) {
  return result.status === "rejected"
    ? result.reason?.message || "This dashboard data is unavailable."
    : "";
}

function DashboardListCard({ title, subtitle, rows, error, action, empty }) {
  return (
    <section className="dash-card">
      <div className="dash-card-header">
        <div><h2>{title}</h2><p>{subtitle}</p></div>
        {action}
      </div>
      {error ? <div className="dashboard-section-error" role="alert">{error}</div>
        : rows?.length ? <div className="status-list">
          {rows.map((row) => (
            <div className="status-row" key={row.label}>
              <span>{titleCase(row.label)}</span><strong>{row.value}</strong>
            </div>
          ))}
        </div> : <div className="dashboard-empty">{empty || "No records are currently available."}</div>}
    </section>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activityVisible, setActivityVisible] = useState(true);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    const [summaryResult, reportingResult, qualityResult, submissionsResult, jurisdictionsResult, activityResult, deadlinesResult, patientsResult] = await Promise.allSettled([
      getDashboardSummary(),
      request("/api/dashboard/reporting-status"),
      request("/api/dashboard/quality"),
      request("/api/dashboard/submissions"),
      request("/api/dashboard/jurisdictions"),
      request("/api/dashboard/activity"),
      request("/api/dashboard/deadlines"),
      listCanonicalPatients({ page: 1, page_size: WORKLIST_PAGE_SIZE }),
    ]);
    setData({
      summary: summaryResult.status === "fulfilled" ? summaryResult.value : null,
      reporting: reportingResult.status === "fulfilled" ? reportingResult.value : null,
      quality: qualityResult.status === "fulfilled" ? qualityResult.value : null,
      submissions: submissionsResult.status === "fulfilled" ? submissionsResult.value : null,
      jurisdictions: jurisdictionsResult.status === "fulfilled" ? jurisdictionsResult.value : null,
      activity: activityResult.status === "fulfilled" ? responseItems(activityResult.value) : [],
      deadlines: deadlinesResult.status === "fulfilled" ? responseItems(deadlinesResult.value) : [],
      patients: patientsResult.status === "fulfilled" ? patientsResult.value : null,
      errors: {
        summary: errorMessage(summaryResult),
        reporting: errorMessage(reportingResult),
        quality: errorMessage(qualityResult),
        submissions: errorMessage(submissionsResult),
        jurisdictions: errorMessage(jurisdictionsResult),
        activity: errorMessage(activityResult),
        deadlines: errorMessage(deadlinesResult),
        patients: errorMessage(patientsResult),
      },
    });
    setLoading(false);
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard, refreshKey]);

  const reportingRows = useMemo(() => countRows(data?.reporting?.cases), [data]);
  const submissionRows = useMemo(() => countRows(data?.submissions), [data]);
  const deadlineRiskRows = useMemo(() => countRows(data?.deadlines?.by_status), [data]);
  const conditionRows = useMemo(() => countRows(data?.reporting?.case_conditions), [data]);
  const jurisdictionRows = useMemo(() => countRows(data?.jurisdictions), [data]);
  const priorityPatients = useMemo(() => responseItems(data?.patients), [data]);
  const activityItems = activityVisible ? data?.activity?.slice(0, 5) || [] : [];
  const deadlineItems = data?.deadlines?.slice(0, 3) || [];
  const summary = data?.summary;
  const quality = data?.quality || {};
  const qualityRows = [
    { label: "Cases in registry", value: summary?.cases ?? EMPTY_VALUE, tone: "green" },
    { label: "Cases needing review", value: quality.cases_needing_review ?? summary?.needs_review ?? EMPTY_VALUE, tone: "orange" },
    { label: "Reportable cases", value: summary?.reportable_cases ?? EMPTY_VALUE, tone: "blue" },
    { label: "Cases with submission", value: summary?.submitted_cases ?? EMPTY_VALUE, tone: "green" },
  ];
  const maxCondition = Math.max(1, ...conditionRows.map((row) => Number(row.value) || 0));
  const metrics = [
    { label: "Total Patients", value: summary?.total_patients ?? data?.patients?.total ?? EMPTY_VALUE, detail: "Patients across all conditions", tone: "total", Icon: Users },
    { label: "Active Cases", value: summary?.active_cases ?? EMPTY_VALUE, detail: "Open cases requiring action", tone: "active", Icon: ClipboardList },
    { label: "Patients Due Today", value: summary?.patients_due_today ?? EMPTY_VALUE, detail: "Patient deadlines due today", tone: "due", Icon: Clock3 },
    { label: "Reported Cases", value: summary?.reported_cases ?? EMPTY_VALUE, detail: "Cases with submitted or acknowledged records", tone: "reported", Icon: Send },
  ];

  if (loading && !data) {
    return <section className="dashboard-page"><SignalLoading title="Loading Dashboard" message="Retrieving current reporting activity and workflow status." /></section>;
  }

  return (
    <section className="dashboard-page">
      <header className="dashboard-heading">
        <div><span className="dashboard-eyebrow">SIGNAL</span><h1>Dashboard</h1><p>Public health reporting operations at a glance</p></div>
        <button className="dashboard-refresh" type="button" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}>
          <RefreshCw size={15} aria-hidden="true" /> {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {Object.values(data?.errors || {}).some(Boolean) && <div className="dashboard-error" role="status">Some Dashboard sections could not load. Their individual cards show the related error.</div>}

      <section className="dashboard-kpis" aria-label="Patient and case summary">
        {metrics.map(({ label, value, detail, tone, Icon }) => (
          <article className={`dashboard-kpi tone-${tone}`} key={label}>
            <div className="dashboard-kpi-heading"><span className="dashboard-kpi-label">{label}</span><Icon size={16} aria-hidden="true" /></div>
            <strong>{value}</strong><p>{detail}</p>
          </article>
        ))}
      </section>

      <section className="dashboard-priority-card" aria-labelledby="priority-work-heading">
        <header className="dashboard-card-header">
          <div><h2 id="priority-work-heading">Priority Work</h2><p>Top 5 patients across all conditions</p></div>
          <button className="dashboard-view-all" type="button" onClick={() => navigate("/patients")}>View All Patients <ArrowRight size={14} aria-hidden="true" /></button>
        </header>
        {data?.errors?.patients ? <div className="dashboard-section-error" role="alert">{data.errors.patients}</div>
          : priorityPatients.length ? <>
            <div className="dashboard-table-wrap">
              <table className="priority-table">
                <thead><tr><th scope="col">Patient</th><th scope="col">Work Item</th><th scope="col">Jurisdiction</th><th scope="col">Priority</th><th scope="col">Deadline</th><th scope="col">Action</th></tr></thead>
                <tbody>{priorityPatients.map((patient) => {
                  const deadline = deadlineDate(patient);
                  const priority = patientPriority(patient);
                  const badgeClass = `priority-badge ${priority === EMPTY_VALUE ? "not-set" : priority.toLowerCase()}`;
                  return <tr key={patient.patient_id}>
                    <td><strong>{patientName(patient)}</strong></td><td>{patient.condition || "Patient review"}</td>
                    <td>{patient.jurisdiction || patient.deadline?.jurisdiction || EMPTY_VALUE}</td>
                    <td><span className={badgeClass}>{priority}</span></td><td>{formatDeadline(deadline)}</td>
                    <td><button className="row-action" type="button" onClick={() => navigate(`/patients/${encodeURIComponent(patient.patient_id)}`)}>View</button></td>
                  </tr>;
                })}</tbody>
              </table>
            </div>
            <footer className="dashboard-priority-footer"><span>Showing {priorityPatients.length} of {data.patients.total} patients</span><span>Patients in Patients page order</span></footer>
          </> : <div className="dashboard-empty">No patients are currently in the reporting worklist.</div>}
      </section>

      <div className="dashboard-grid">
        <DashboardListCard title="Reporting Status" subtitle="Current case status from SIGNAL" rows={reportingRows} error={data?.errors?.reporting} />
        <DashboardListCard title="Timeliness & Deadline Risk" subtitle="Persisted deadline escalation records by status" rows={deadlineRiskRows} error={data?.errors?.reporting} empty="No deadline escalation records are currently available." />
        <DashboardListCard title="Completeness & Quality" subtitle="Backend-recorded case indicators" rows={qualityRows} error={data?.errors?.quality || data?.errors?.summary} />
        <DashboardListCard title="Submission Operations" subtitle="Submission packages by recorded status" rows={submissionRows} error={data?.errors?.submissions} action={<button className="small-action" type="button" onClick={() => navigate("/submissions")}>View</button>} />

        <section className="dash-card">
          <div className="dash-card-header"><div><h2>Cases by Condition</h2><p>Case disease counts returned by the backend</p></div><span className="small-count">N={conditionRows.reduce((sum, row) => sum + (Number(row.value) || 0), 0)}</span></div>
          {data?.errors?.reporting ? <div className="dashboard-section-error" role="alert">{data.errors.reporting}</div>
            : conditionRows.length ? <div className="distribution-list">{conditionRows.map((row, index) => <div className="distribution-row" key={row.label}>
              <div className="distribution-label"><span>{row.label}</span><strong>{row.value}</strong></div>
              <div className="progress-track"><span className={`progress-fill fill-${index % 4}`} style={{ width: `${Math.max(3, (Number(row.value) || 0) / maxCondition * 100)}%` }} /></div>
            </div>)}</div> : <div className="dashboard-empty">No case condition records are currently available.</div>}
        </section>

        <DashboardListCard title="Cases by Jurisdiction" subtitle="Active reporting jurisdictions" rows={jurisdictionRows} error={data?.errors?.jurisdictions} />

        <section className="dash-card">
          <div className="dash-card-header"><div><h2>Recent Activity</h2><p>Backend audit events</p></div><button className="small-action" type="button" onClick={() => setActivityVisible(false)}>Clear</button></div>
          {data?.errors?.activity ? <div className="dashboard-section-error" role="alert">{data.errors.activity}</div>
            : <div className="activity-list">{activityItems.length ? activityItems.map((item) => <div className="activity-row" key={item.event_id || `${item.entity_id}-${item.timestamp}`}>
              <span className="activity-mark"><Activity size={13} aria-hidden="true" /></span>
              <div className="activity-copy"><strong>{item.description || titleCase(item.event_type)}</strong><span>{item.entity_type || "Event"} · {item.entity_id || EMPTY_VALUE} · {titleCase(item.status)}</span></div>
              <time>{formatDateTime(item.timestamp)}</time>
            </div>) : <div className="dashboard-empty">No audit activity is currently available.</div>}</div>}
        </section>

        <section className="dash-card">
          <div className="dash-card-header"><div><h2>Upcoming Deadlines</h2><p>Deadlines returned by the backend</p></div><span className="imminent-badge">{data?.errors?.deadlines ? "Unavailable" : `${deadlineItems.length} listed`}</span></div>
          {data?.errors?.deadlines ? <div className="dashboard-section-error" role="alert">{data.errors.deadlines}</div>
            : <div className="deadline-list">{deadlineItems.length ? deadlineItems.map((item) => <div className="deadline-row" key={`${item.case_id}-${item.deadline}`}>
              <span className="deadline-icon"><CalendarClock size={15} aria-hidden="true" /></span>
              <div className="deadline-copy"><strong>{item.case_id}</strong><span>{item.message || `${item.jurisdiction || "Jurisdiction not recorded"} · ${titleCase(item.status)}`}</span></div>
              <time>{formatDateTime(item.deadline)}</time>
            </div>) : <div className="dashboard-empty">No deadline records are currently available.</div>}</div>}
        </section>
      </div>

      <footer className="dashboard-footer"><span><CheckCircle2 size={13} aria-hidden="true" /> Values shown are from available SIGNAL backend records.</span><span>{data?.patients ? `${data.patients.total} patients in the worklist` : "Patient worklist unavailable"}</span></footer>
    </section>
  );
}
