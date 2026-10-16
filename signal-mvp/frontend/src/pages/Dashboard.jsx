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
import { useDailyRefresh } from "../hooks/useDailyRefresh.js";
import { cleanPatientName } from "../utils/patientNames.js";
import "../styles/dashboard.css";

const EMPTY_VALUE = "—";
function responseItems(response) {
  return Array.isArray(response?.items) ? response.items : [];
}

const DASHBOARD_SECTIONS = ["summary", "reporting", "activity", "deadlines", "patients"];

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
    .map(cleanPatientName)
    .filter(Boolean)
    .join(" ") || "Patient name unavailable";
}

function patientPriority(patient) {
  const urgency = patient?.deadline?.urgency;
  return typeof urgency === "string" && urgency.trim() ? titleCase(urgency) : EMPTY_VALUE;
}

function SectionState({ loading, error, onRetry, children, empty }) {
  if (loading) return <div className="dashboard-empty" role="status">Loading…</div>;
  if (error) return <div className="dashboard-section-error" role="alert">{error}<button className="dashboard-retry" type="button" onClick={onRetry}>Retry</button></div>;
  return children || <div className="dashboard-empty">{empty || "No records are currently available."}</div>;
}

function DashboardListCard({ title, subtitle, rows, loading, error, onRetry, action, empty }) {
  return (
    <section className="dash-card">
      <div className="dash-card-header">
        <div><h2>{title}</h2><p>{subtitle}</p></div>
        {action}
      </div>
      <SectionState loading={loading} error={error} onRetry={onRetry} empty={empty}>
        {rows?.length ? <div className="status-list">
          {rows.map((row) => (
            <div className="status-row" key={row.label}>
              <span>{titleCase(row.label)}</span><strong>{row.value}</strong>
            </div>
          ))}
        </div> : null}
      </SectionState>
    </section>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState({
    summary: null,
    reporting: null,
    activity: null,
    deadlines: null,
    patients: null,
    loading: Object.fromEntries(DASHBOARD_SECTIONS.map((key) => [key, true])),
    errors: {},
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [activityVisible, setActivityVisible] = useState(true);
  const currentDay = useDailyRefresh();

  const loadSection = useCallback(async (key, signal) => {
    setData((current) => ({
      ...current,
      loading: { ...current.loading, [key]: true },
      errors: { ...current.errors, [key]: "" },
    }));
    try {
      let value;
      if (key === "summary") value = await getDashboardSummary({ signal });
      else if (key === "reporting") value = await request("/api/dashboard/reporting-status", { signal });
      else if (key === "activity") value = responseItems(await request("/api/dashboard/activity", { signal }));
      else if (key === "deadlines") value = await request("/api/dashboard/deadlines", { signal });
      else value = await listCanonicalPatients({ page: 1, page_size: 5, signal });

      if (signal?.aborted) return;
      setData((current) => ({
        ...current,
        [key]: value,
        loading: { ...current.loading, [key]: false },
      }));
    } catch (error) {
      if (signal?.aborted || error?.name === "AbortError") return;
      setData((current) => ({
        ...current,
        loading: { ...current.loading, [key]: false },
        errors: { ...current.errors, [key]: error?.message || "This dashboard data is unavailable." },
      }));
    }
  }, []);

  const loadDashboard = useCallback((signal) => {
    setData((current) => ({
      ...current,
      loading: Object.fromEntries(DASHBOARD_SECTIONS.map((key) => [key, true])),
      errors: {},
    }));
    DASHBOARD_SECTIONS.forEach((key) => { void loadSection(key, signal); });
  }, [loadSection]);

  useEffect(() => {
    const controller = new AbortController();
    loadDashboard(controller.signal);
    return () => controller.abort();
  }, [loadDashboard, refreshKey, currentDay]);

  const reportingRows = useMemo(() => countRows(data?.reporting?.cases), [data]);
  const submissionRows = useMemo(() => countRows(data?.reporting?.submissions), [data]);
  const deadlineRiskRows = useMemo(() => countRows(data?.deadlines?.by_status), [data]);
  const conditionRows = useMemo(() => countRows(data?.reporting?.case_conditions), [data]);
  const jurisdictionRows = useMemo(() => countRows(data?.reporting?.jurisdictions), [data]);
  const priorityPatients = useMemo(() => responseItems(data?.patients), [data]);
  const activityItems = activityVisible ? data?.activity?.slice(0, 5) || [] : [];
  const deadlineItems = responseItems(data?.deadlines).slice(0, 3);
  const summary = data?.summary;
  const quality = data?.reporting?.quality || {};
  const loading = Object.values(data.loading).some(Boolean);
  const retryQuality = () => {
    if (data.errors.summary) void loadSection("summary");
    if (data.errors.reporting) void loadSection("reporting");
  };
  const qualityRows = [
    { label: "Cases in registry", value: summary?.cases ?? EMPTY_VALUE, tone: "green" },
    { label: "Cases needing review", value: quality.cases_needing_review ?? summary?.needs_review ?? EMPTY_VALUE, tone: "orange" },
    { label: "Reportable cases", value: summary?.reportable_cases ?? EMPTY_VALUE, tone: "blue" },
    { label: "Cases with submission", value: summary?.submitted_cases ?? EMPTY_VALUE, tone: "green" },
  ];
  const maxCondition = Math.max(1, ...conditionRows.map((row) => Number(row.value) || 0));
  const metrics = [
    { label: "Total Patients", field: "total_patients", detail: "Patients across all conditions", tone: "total", Icon: Users },
    { label: "Active Cases", field: "active_cases", detail: "Open cases requiring action", tone: "active", Icon: ClipboardList },
    { label: "Patients Due Today", field: "patients_due_today", detail: "Patient deadlines due today", tone: "due", Icon: Clock3 },
    { label: "Reported Cases", field: "reported_cases", detail: "Cases with submitted or acknowledged records", tone: "reported", Icon: Send },
  ];

  if (loading) {
    return (
      <section className="dashboard-page">
        <SignalLoading title="Loading Dashboard" message="Retrieving current reporting activity and workflow status." />
      </section>
    );
  }

  return (
    <section className="dashboard-page">
      <header className="dashboard-heading">
        <div><span className="dashboard-eyebrow">SIGNAL</span><h1>Dashboard</h1><p>Public health reporting operations at a glance</p></div>
        <button className="dashboard-refresh" type="button" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}>
          <RefreshCw size={15} aria-hidden="true" /> {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      <section className="dashboard-kpis" aria-label="Patient and case summary">
        {metrics.map(({ label, field, detail, tone, Icon }) => (
          <article className={`dashboard-kpi tone-${tone}`} key={label}>
            <div className="dashboard-kpi-heading"><span className="dashboard-kpi-label">{label}</span><Icon size={16} aria-hidden="true" /></div>
            <strong>{data.loading.summary ? "Loading…" : data.errors.summary ? "Unavailable" : summary?.[field] ?? EMPTY_VALUE}</strong><p>{detail}</p>
          </article>
        ))}
        {data.errors.summary && <div className="dashboard-section-error" role="alert">{data.errors.summary}<button className="dashboard-retry" type="button" onClick={() => loadSection("summary")}>Retry summary</button></div>}
      </section>

      <section className="dashboard-priority-card" aria-labelledby="priority-work-heading">
        <header className="dashboard-card-header">
          <div><h2 id="priority-work-heading">Priority Work</h2><p>Top 5 patients in the reporting worklist</p></div>
          <button className="dashboard-view-all" type="button" onClick={() => navigate("/patients")}>View All Patients <ArrowRight size={14} aria-hidden="true" /></button>
        </header>
        <SectionState loading={data.loading.patients} error={data.errors.patients} onRetry={() => loadSection("patients")} empty="No patients are currently in the reporting worklist.">
          {priorityPatients.length ? <>
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
                    <td><span className={badgeClass}>{priority}</span></td>
                    <td>
                      {patient.deadline?.reporting_timeline && <div>{patient.deadline.reporting_timeline}</div>}
                      {deadline && <small>{formatDeadline(deadline)}</small>}
                      {!patient.deadline?.reporting_timeline && !deadline && EMPTY_VALUE}
                    </td>
                    <td><button className="row-action" type="button" onClick={() => navigate(`/patients/${encodeURIComponent(patient.patient_id)}`)}>View</button></td>
                  </tr>;
                })}</tbody>
              </table>
            </div>
            <footer className="dashboard-priority-footer"><span>Showing {priorityPatients.length} of {data.patients.total} patients</span><span>Patients in Patients page order</span></footer>
          </> : null}
        </SectionState>
      </section>

      <div className="dashboard-grid">
        <DashboardListCard title="Reporting Status" subtitle="Current case status from SIGNAL" rows={reportingRows} loading={data.loading.reporting} error={data.errors.reporting} onRetry={() => loadSection("reporting")} />
        <DashboardListCard title="Timeliness & Deadline Risk" subtitle="Persisted deadline escalation records by status" rows={deadlineRiskRows} loading={data.loading.deadlines} error={data.errors.deadlines} onRetry={() => loadSection("deadlines")} empty="No deadline escalation records are currently available." />
        <DashboardListCard title="Completeness & Quality" subtitle="Backend-recorded case indicators" rows={qualityRows} loading={data.loading.summary || data.loading.reporting} error={data.errors.summary || data.errors.reporting} onRetry={retryQuality} />
        <DashboardListCard title="Submission Operations" subtitle="Submission packages by recorded status" rows={submissionRows} loading={data.loading.reporting} error={data.errors.reporting} onRetry={() => loadSection("reporting")} action={<button className="small-action" type="button" onClick={() => navigate("/submissions")}>View</button>} />

        <section className="dash-card">
          <div className="dash-card-header"><div><h2>Cases by Condition</h2><p>Case disease counts returned by the backend</p></div><span className="small-count">N={conditionRows.reduce((sum, row) => sum + (Number(row.value) || 0), 0)}</span></div>
          <SectionState loading={data.loading.reporting} error={data.errors.reporting} onRetry={() => loadSection("reporting")} empty="No case condition records are currently available.">
            {conditionRows.length ? <div className="distribution-list">{conditionRows.map((row, index) => <div className="distribution-row" key={row.label}>
              <div className="distribution-label"><span>{row.label}</span><strong>{row.value}</strong></div>
              <div className="progress-track"><span className={`progress-fill fill-${index % 4}`} style={{ width: `${Math.max(3, (Number(row.value) || 0) / maxCondition * 100)}%` }} /></div>
            </div>)}</div> : null}
          </SectionState>
        </section>

        <DashboardListCard title="Cases by Jurisdiction" subtitle="Active reporting jurisdictions" rows={jurisdictionRows} loading={data.loading.reporting} error={data.errors.reporting} onRetry={() => loadSection("reporting")} />

        <section className="dash-card">
          <div className="dash-card-header"><div><h2>Recent Activity</h2><p>Backend audit events</p></div><button className="small-action" type="button" onClick={() => setActivityVisible(false)}>Clear</button></div>
          {data.loading.activity ? <div className="dashboard-empty" role="status">Loading…</div> : data.errors.activity ? <div className="dashboard-section-error" role="alert">{data.errors.activity}<button className="dashboard-retry" type="button" onClick={() => loadSection("activity")}>Retry</button></div>
            : <div className="activity-list">{activityItems.length ? activityItems.map((item) => <div className="activity-row" key={item.event_id || `${item.entity_id}-${item.timestamp}`}>
              <span className="activity-mark"><Activity size={13} aria-hidden="true" /></span>
              <div className="activity-copy"><strong>{item.description || titleCase(item.event_type)}</strong><span>{item.entity_type || "Event"} · {item.entity_id || EMPTY_VALUE} · {titleCase(item.status)}</span></div>
              <time>{formatDateTime(item.timestamp)}</time>
            </div>) : <div className="dashboard-empty">No audit activity is currently available.</div>}</div>}
        </section>

        <section className="dash-card">
          <div className="dash-card-header"><div><h2>Upcoming Deadlines</h2><p>Deadlines returned by the backend</p></div><span className="imminent-badge">{data?.errors?.deadlines ? "Unavailable" : `${deadlineItems.length} listed`}</span></div>
          {data.loading.deadlines ? <div className="dashboard-empty" role="status">Loading…</div> : data.errors.deadlines ? <div className="dashboard-section-error" role="alert">{data.errors.deadlines}<button className="dashboard-retry" type="button" onClick={() => loadSection("deadlines")}>Retry</button></div>
            : <div className="deadline-list">{deadlineItems.length ? deadlineItems.map((item) => <div className="deadline-row" key={`${item.case_id}-${item.deadline}`}>
              <span className="deadline-icon"><CalendarClock size={15} aria-hidden="true" /></span>
              <div className="deadline-copy"><strong>{item.case_id}</strong><span>{item.message || `${item.jurisdiction || "Jurisdiction not recorded"} · ${titleCase(item.status)}`}</span></div>
              <time>{formatDateTime(item.deadline)}</time>
            </div>) : <div className="dashboard-empty">No deadline records are currently available.</div>}</div>}
        </section>
      </div>

      <footer className="dashboard-footer"><span><CheckCircle2 size={13} aria-hidden="true" /> Values shown are from available SIGNAL backend records.</span><span>{summary ? `${summary.total_patients} patients in the worklist` : data.loading.summary ? "Loading patient total…" : "Patient total unavailable"}</span></footer>
    </section>
  );
}
