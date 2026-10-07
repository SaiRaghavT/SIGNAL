import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRight, CalendarClock, CheckCircle2, FileCheck2, RefreshCw, Users } from "lucide-react";
import { request } from "../api/client.js";
import { listCanonicalPatients } from "../api/canonical.js";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/dashboard.css";
const unwrapItems = data => Array.isArray(data?.items) ? data.items : [];
const asCounts = obj => Object.entries(obj || {}).map(([label, value]) => ({
  label: String(label).replaceAll("_", " "),
  value: Number(value) || 0
}));
function formatDeadline(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const parts = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true
  }).formatToParts(date);
  const part = Object.fromEntries(parts.map(({
    type,
    value: partValue
  }) => [type, partValue]));
  return `${part.day} ${part.month} ${part.year}, ${part.hour}:${part.minute} ${part.dayPeriod?.toUpperCase() || ""}`.trim();
}
const formatDateTime = value => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
};
const titleCase = value => String(value || "Not recorded").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, char => char.toUpperCase()); /* * Remove synthetic numeric suffixes from Synthea demo names. * * Example: * Óscar156 Lomeli256 * becomes: * Óscar Lomeli */
const patientName = patient => [patient?.first_name, patient?.last_name].map(name => String(name || "").replace(/\d+/g, "").replace(/\s+/g, " ").trim()).filter(Boolean).join(" ") || "Patient name unavailable"; /* * IMPORTANT: * The frontend does not calculate deadlines. * * It only reads the deadline returned by the backend. */
const parseDeadline = patient => {
  const value = patient?.deadline?.deadline || (typeof patient?.deadline === "string" ? patient.deadline : null);
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};
const deadlineValue = patient => parseDeadline(patient);
const calculatePriority = deadline => {
  if (!deadline) return null;
  const hoursRemaining = (deadline.getTime() - Date.now()) / (1000 * 60 * 60);
  if (hoursRemaining <= 24) return "High";
  if (hoursRemaining <= 72) return "Medium";
  return "Low";
};
const patientCondition = patient => {
  if (patient?.condition) {
    return patient.condition;
  }
  const measlesCondition = patient?.conditions?.find(condition => String(condition?.display || "").toLowerCase().includes("measles"));
  return measlesCondition?.display || "Measles";
};
const patientJurisdiction = patient => patient?.jurisdiction ?? patient?.deadline?.jurisdiction ?? "—";
function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [activityVisible, setActivityVisible] = useState(true); /*   * Load all dashboard information.   *   * IMPORTANT:   * The patient worklist comes from the SAME canonical endpoint   * used by the Patients page.   */
  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryResult, casesResult, reportingResult, activityResult, deadlinesResult, submissionsResult, patientsResult] = await Promise.allSettled([request("/api/dashboard/summary"), request("/api/cases?page=1&page_size=100"), request("/api/dashboard/reporting-status"), request("/api/dashboard/activity"), request("/api/dashboard/deadlines"), request("/api/submissions?page=1&page_size=100"), /*         * THIS IS THE IMPORTANT PART.         *         * Dashboard Priority Work uses the exact same         * Measles patient worklist as /patients.         */listCanonicalPatients({
        page: 1,
        page_size: 100,
        condition: "measles"
      })]);
      const summary = summaryResult.status === "fulfilled" ? summaryResult.value : null;
      const cases = casesResult.status === "fulfilled" ? unwrapItems(casesResult.value) : [];
      const reporting = reportingResult.status === "fulfilled" ? reportingResult.value : null;
      const activity = activityResult.status === "fulfilled" ? unwrapItems(activityResult.value) : [];
      const deadlines = deadlinesResult.status === "fulfilled" ? unwrapItems(deadlinesResult.value) : [];
      const submissions = submissionsResult.status === "fulfilled" ? unwrapItems(submissionsResult.value) : [];
      const patients = patientsResult.status === "fulfilled" ? patientsResult.value : null;
      if (!summary) {
        throw new Error(summaryResult.status === "rejected" ? summaryResult.reason?.message || "Dashboard summary request failed." : "Dashboard summary is unavailable.");
      }
      setData({
        summary,
        cases,
        reporting,
        activity,
        deadlines,
        submissions,
        patients,
        patientError: patientsResult.status === "rejected" ? patientsResult.reason : null
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]); /*   * ============================================================   * KPI METRICS   * ============================================================   */
  const metrics = useMemo(() => {
    if (!data) return [];
    const patientTotal = data.patients?.total ?? "—";
    const active = data.cases.filter(item => {
      const disease = String(item?.disease || "").toLowerCase();
      const status = String(item?.status || "").toUpperCase();
      return disease.includes("measles") && !["RESOLVED", "CLOSED", "COMPLETED"].includes(status);
    }).length;
    const today = new Date();
    const dueToday = unwrapItems(data.patients).filter(patient => {
      const value = deadlineValue(patient);
      if (!value) return false;
      const date = new Date(value);
      return date.toDateString() === today.toDateString();
    }).length;
    const reportedCases = new Set(data.submissions.filter(item => {
      const disease = String(item?.disease || "").toLowerCase();
      const status = String(item?.status || "").toUpperCase();
      return disease.includes("measles") && ["SUBMITTED", "ACKNOWLEDGED"].includes(status);
    }).map(item => item?.case_id).filter(Boolean)).size;
    return [{
      label: "Total Measles Patients",
      value: patientTotal,
      text: "Patients in the Measles reporting worklist",
      icon: Users,
      tone: "blue"
    }, {
      label: "Active Measles Cases",
      value: active,
      text: "Open Measles cases returned by the case API",
      icon: Activity,
      tone: "orange"
    }, {
      label: "Measles Patients Due Today",
      value: dueToday,
      text: "Patient-record deadlines due today",
      icon: CalendarClock,
      tone: "red"
    }, {
      label: "Reported Measles Cases",
      value: reportedCases,
      text: "Measles cases with a submitted or acknowledged record",
      icon: FileCheck2,
      tone: "green"
    }];
  }, [data]); /*   * ============================================================   * REPORTING DATA   * ============================================================   */
  const reportingRows = useMemo(() => asCounts(data?.reporting?.cases), [data]);
  const submissionRows = useMemo(() => asCounts(data?.reporting?.submissions), [data]);
  const deadlineRiskRows = useMemo(() => {
    const counts = data?.deadlines?.reduce((all, item) => {
      const status = String(item?.status || "Not recorded");
      all[status] = (all[status] || 0) + 1;
      return all;
    }, {}) || {};
    return asCounts(counts);
  }, [data]); /*   * ============================================================   * CASE CONDITIONS   * ============================================================   */
  const conditionRows = useMemo(() => {
    const counts = data?.cases?.reduce((all, item) => {
      if (item?.disease) {
        all[item.disease] = (all[item.disease] || 0) + 1;
      }
      return all;
    }, {}) || {};
    return asCounts(counts).sort((a, b) => b.value - a.value).slice(0, 5);
  }, [data]);
  const jurisdictionRows = useMemo(() => asCounts(data?.reporting?.jurisdictions).sort((a, b) => b.value - a.value).slice(0, 5), [data]);
  const maxCondition = Math.max(1, ...conditionRows.map(row => row.value)); /*   * ============================================================   * MEASLES PATIENT WORKLIST   * ============================================================   *   * DO NOT calculate deadline here.   *   * Backend owns:   *   - qualifying evidence   *   - event time   *   - rule   *   - deadline timestamp   *   * Frontend only:   *   - reads   *   - validates   *   - sorts   *   - displays   */
  const patients = useMemo(() => unwrapItems(data?.patients), [data?.patients]);
  const priorityPatients = useMemo(() => {
    return patients.slice(0, 5).map(patient => ({
      patient,
      deadline: parseDeadline(patient)
    }));
  }, [patients]); /*   * ============================================================   * OTHER DASHBOARD DATA   * ============================================================   */
  const deadlineItems = data?.deadlines?.slice(0, 3) || [];
  const activityItems = activityVisible ? data?.activity?.slice(0, 5) || [] : [];
  const quality = data?.reporting?.quality || {};
  const submitted = Number(data?.summary?.submitted_cases || 0);
  const totalCases = Number(data?.summary?.cases || 0);
  const qualityRows = [{
    label: "Cases in registry",
    value: totalCases,
    tone: "green"
  }, {
    label: "Cases needing review",
    value: quality.cases_needing_review ?? data?.summary?.needs_review ?? 0,
    tone: "orange"
  }, {
    label: "Reportable cases",
    value: data?.summary?.reportable_cases ?? 0,
    tone: "blue"
  }, {
    label: "Follow-ups recorded",
    value: data?.summary?.follow_up_cases ?? 0,
    tone: "purple"
  }, {
    label: "Cases with submission",
    value: submitted,
    tone: "green"
  }]; /*   * ============================================================   * RENDER   * ============================================================   */
  return <section className="dashboard-content">      <header className="dashboard-heading">        <div>          <span className="page-eyebrow">            PUBLIC HEALTH OPERATIONS          </span>          <h1>Dashboard</h1>          <p>            Public health reporting operations at a glance          </p>        </div>        <button className="dashboard-refresh" onClick={loadDashboard} disabled={loading}>          <RefreshCw size={15} />          Refresh        </button>      </header>      {error && <div className="dashboard-error">          <div>            <strong>              We couldn’t load the dashboard            </strong>            <p>{error}</p>          </div>          <button onClick={loadDashboard}>            Try again          </button>        </div>}      {loading && <SignalLoading title="Loading Dashboard" message="Retrieving current reporting activity and workflow status." />}      {!loading && data && <>          {/* =====================================================              KPI CARDS              ===================================================== */}          <div className="dashboard-kpis">            {metrics.map(({
          label,
          value,
          text,
          icon: Icon,
          tone
        }) => <article className={`dashboard-kpi tone-${tone}`} key={label}>                  <div className="kpi-icon">                    <Icon size={18} />                  </div>                  <span className="kpi-label">                    {label}                  </span>                  <strong>{value}</strong>                  <p>{text}</p>                </article>)}          </div>          {/* =====================================================              PRIORITY WORK              ===================================================== */}          <section className="dash-card priority-card">            <div className="dash-card-header">              <div>                <h2>                  Priority Work                </h2>                <p>                  Top 5 Measles patients from the Patients page                </p>              </div>              <button className="text-action" onClick={() => navigate("/patients")}>                View All Patients                <ArrowRight size={14} />              </button>            </div>            <div className="priority-meta">              Showing{" "}              {priorityPatients.length}{" "}              of{" "}              {patients.length}{" "}              Measles patients              <span>•</span>              In Patients page order            </div>            {data.patientError ? <div className="dashboard-empty">                <span>                  Unable to load priority work.                </span>                <button className="small-action" onClick={loadDashboard}>                  Retry                </button>              </div> : priorityPatients.length > 0 ? <div className="dashboard-table-wrap">                <table className="priority-table">                  <colgroup>                    <col style={{
                width: "25%"
              }} />                    <col style={{
                width: "17%"
              }} />                    <col style={{
                width: "16%"
              }} />                    <col style={{
                width: "14%"
              }} />                    <col style={{
                width: "18%"
              }} />                    <col style={{
                width: "10%"
              }} />                  </colgroup>                  <thead>                    <tr>                      <th>Patient</th>                      <th>Work Item</th>                      <th>Jurisdiction</th>                      <th>Priority</th>                      <th>Deadline</th>                      <th>Action</th>                    </tr>                  </thead>                  <tbody>                    {priorityPatients.map(({
                patient,
                deadline
              }) => {
                const priority = calculatePriority(deadline);
                return <tr key={patient.patient_id}>                            <td>                              <strong>                                {patientName(patient)}                              </strong>                              <small>                                {patient.source_patient_id || patient.patient_id}                              </small>                            </td>                            <td>Measles</td>                            <td>                              {patientJurisdiction(patient)}                            </td>                            <td>                              <span className={`priority-badge ${priority ? String(priority).toLowerCase() : "not-set"}`}>                                {priority ? titleCase(priority) : "—"}                              </span>                            </td>                            <td>                              {formatDeadline(deadlineValue(patient))}                            </td>                            <td>                              <button className="row-action" onClick={() => navigate(`/patients/${encodeURIComponent(patient.patient_id)}`)}>                                View                              </button>                            </td>                          </tr>;
              })}                  </tbody>                </table>              </div> : <div className="dashboard-empty">                No patients with recorded deadlines.              </div>}          </section>          {/* =====================================================              DASHBOARD GRID              ===================================================== */}          <div className="dashboard-grid">            <DashboardListCard title="Reporting Status" subtitle="Current case status from SIGNAL" rows={reportingRows} />            <DashboardListCard title="Timeliness & Deadline Risk" subtitle="Persisted deadline escalation records by status" rows={deadlineRiskRows} empty="No deadline escalation records are currently available." />            <DashboardListCard title="Completeness & Quality" subtitle="Backend-recorded case indicators" rows={qualityRows} />            <DashboardListCard title="Submission Operations" subtitle="Submission packages by recorded status" rows={submissionRows} action={<button className="small-action" onClick={() => navigate("/submissions")}>                  View                </button>} />            {/* =================================================                CASES BY CONDITION                ================================================= */}            <section className="dash-card">              <div className="dash-card-header">                <div>                  <h2>                    Cases by Condition                  </h2>                  <p>                    Case disease counts returned by the backend                  </p>                </div>                <span className="small-count">                  N=                  {conditionRows.reduce((sum, row) => sum + row.value, 0)}                </span>              </div>              {conditionRows.length ? <div className="distribution-list">                  {conditionRows.map((row, index) => <div className="distribution-row" key={row.label}>                        <div className="distribution-label">                          <span>                            {row.label}                          </span>                          <strong>                            {row.value}                          </strong>                        </div>                        <div className="progress-track">                          <span className={`progress-fill fill-${index % 4}`} style={{
                  width: `${Math.max(3, row.value / maxCondition * 100)}%`
                }} />                        </div>                      </div>)}                </div> : <div className="dashboard-empty">                  Condition aggregates are unavailable.                </div>}            </section>            {/* =================================================                CASES BY JURISDICTION                ================================================= */}            <section className="dash-card">              <div className="dash-card-header">                <div>                  <h2>                    Cases by Jurisdiction                  </h2>                  <p>                    Active reporting jurisdictions                  </p>                </div>              </div>              <div className="jurisdiction-list">                {jurisdictionRows.length ? jurisdictionRows.map(row => <div className="jurisdiction-row" key={row.label}>                        <span>                          {row.label}                        </span>                        <strong>                          {row.value}                        </strong>                      </div>) : <div className="dashboard-empty">                    Jurisdiction aggregates are unavailable.                  </div>}              </div>            </section>            {/* =================================================                RECENT ACTIVITY                ================================================= */}            <section className="dash-card">              <div className="dash-card-header">                <div>                  <h2>                    Recent Activity                  </h2>                  <p>                    Backend audit events                  </p>                </div>                <button className="small-action" onClick={() => setActivityVisible(false)}>                  Clear                </button>              </div>              <div className="activity-list">                {activityItems.length ? activityItems.map(item => <div className="activity-row" key={item.event_id || `${item.entity_id}-${item.timestamp}`}>                        <span className="activity-mark">                          <Activity size={13} />                        </span>                        <div className="activity-copy">                          <strong>                            {item.description || titleCase(item.event_type)}                          </strong>                          <span>                            {item.entity_type || "Event"}{" "}                            ·{" "}                            {item.entity_id || "—"}{" "}                            ·{" "}                            {titleCase(item.status)}                          </span>                        </div>                        <time>                          {formatDateTime(item.timestamp)}                        </time>                      </div>) : <div className="dashboard-empty">                    No audit activity is currently available.                  </div>}              </div>            </section>            {/* =================================================                UPCOMING DEADLINES                ================================================= */}            <section className="dash-card">              <div className="dash-card-header">                <div>                  <h2>                    Upcoming Deadlines                  </h2>                  <p>                    Deadlines returned by the backend                  </p>                </div>                <span className="imminent-badge">                  {deadlineItems.length} listed                </span>              </div>              <div className="deadline-list">                {deadlineItems.length ? deadlineItems.map(item => <div className="deadline-row" key={`${item.case_id}-${item.deadline}`}>                        <span className="deadline-icon">                          <CalendarClock size={15} />                        </span>                        <div className="deadline-copy">                          <strong>                            {item.case_id}                          </strong>                          <span>                            {item.message || `${item.jurisdiction || "Jurisdiction not recorded"} · ${titleCase(item.status)}`}                          </span>                        </div>                        <time>                          {formatDateTime(item.deadline)}                        </time>                      </div>) : <div className="dashboard-empty">                    No deadline records are currently available.                  </div>}              </div>            </section>          </div>          {/* =====================================================              FOOTER              ===================================================== */}          <footer className="dashboard-footer">            <span>              <CheckCircle2 size={13} />              Values shown are from available SIGNAL backend records.            </span>            <span>              {data.submissions.length} submissions loaded            </span>          </footer>        </>}    </section>;
} /* * ================================================================ * REUSABLE DASHBOARD LIST CARD * ================================================================ */
function DashboardListCard({
  title,
  subtitle,
  rows,
  action,
  empty
}) {
  return <section className="dash-card">      <div className="dash-card-header">        <div>          <h2>{title}</h2>          <p>{subtitle}</p>        </div>        {action}      </div>      {rows?.length ? <div className="status-list">          {rows.map(row => <div className="status-row" key={row.label}>              <span>                {titleCase(row.label)}              </span>              <strong>                {row.value}              </strong>            </div>)}        </div> : <div className="dashboard-empty">          {empty || "No records are currently available."}        </div>}    </section>;
}
export default Dashboard;
