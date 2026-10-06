import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, RefreshCw, Users } from "lucide-react";
import { listCanonicalPatients } from "../api/canonical.js";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/dashboard.css";

const CONDITION_FILTER = "measles";
const WORKLIST_PAGE_SIZE = 100;
const EMPTY_VALUE = "—";
const PRIORITY_LIMIT = 5;

function deadlineDate(patient) {
  const value = patient?.deadline?.deadline
    ?? (typeof patient?.deadline === "string" ? patient.deadline : null);
  if (!value) return null;

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function priorityFor(deadline, now = Date.now()) {
  if (!deadline) return null;

  const hoursRemaining = (deadline.getTime() - now) / (60 * 60 * 1000);
  if (hoursRemaining <= 4) return "Critical";
  if (hoursRemaining <= 24) return "High";
  if (hoursRemaining <= 72) return "Medium";
  return "Low";
}

function formatDue(deadline) {
  if (!deadline) return EMPTY_VALUE;

  const parts = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).formatToParts(deadline);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return values.month + " " + values.day + ", " + values.year + " · "
    + values.hour + ":" + values.minute + " " + (values.dayPeriod || "");
}

function formatPatientName(patient) {
  return [patient?.first_name, patient?.last_name]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join(" ") || EMPTY_VALUE;
}

function orderedPatients(items) {
  return items
    .map((patient, index) => ({ patient, deadline: deadlineDate(patient), index }))
    .sort((left, right) => (
      (left.deadline?.getTime() ?? Number.POSITIVE_INFINITY)
      - (right.deadline?.getTime() ?? Number.POSITIVE_INFINITY)
      || left.index - right.index
    ))
    .slice(0, PRIORITY_LIMIT);
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function loadWorklist() {
      setLoading(true);
      setError("");
      try {
        const response = await listCanonicalPatients({
          page: 1,
          page_size: WORKLIST_PAGE_SIZE,
          condition: CONDITION_FILTER,
          signal: controller.signal,
        });
        if (!Array.isArray(response?.items) || !Number.isInteger(response?.total)) {
          throw new Error("The canonical patient API returned an invalid Measles worklist.");
        }
        if (active) setResult(response);
      } catch (requestError) {
        if (active && requestError.name !== "AbortError") {
          setError(requestError.message || "Unable to load dashboard data.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadWorklist();
    return () => {
      active = false;
      controller.abort();
    };
  }, [refreshKey]);

  const priorityPatients = useMemo(
    () => orderedPatients(result?.items || []),
    [result],
  );

  if (loading && !result) {
    return (
      <section className="dashboard-page">
        <SignalLoading
          title="Loading Dashboard"
          message="Loading the current Measles patient worklist."
        />
      </section>
    );
  }

  if (error) {
    return (
      <section className="dashboard-page">
        <header className="dashboard-heading">
          <div>
            <span className="dashboard-eyebrow">SIGNAL</span>
            <h1>Dashboard</h1>
            <p>Public health reporting operations at a glance</p>
          </div>
          <button
            className="dashboard-refresh"
            type="button"
            onClick={() => setRefreshKey((key) => key + 1)}
            disabled={loading}
          >
            <RefreshCw size={15} aria-hidden="true" />
            Retry
          </button>
        </header>
        <div className="dashboard-error" role="alert">
          <strong>Unable to load dashboard data.</strong>
          <p>{error}</p>
        </div>
      </section>
    );
  }

  const totalPatients = result.total;

  return (
    <section className="dashboard-page">
      <header className="dashboard-heading">
        <div>
          <span className="dashboard-eyebrow">SIGNAL</span>
          <h1>Dashboard</h1>
          <p>Public health reporting operations at a glance</p>
        </div>
        <button
          className="dashboard-refresh"
          type="button"
          onClick={() => setRefreshKey((key) => key + 1)}
          disabled={loading}
        >
          <RefreshCw size={15} aria-hidden="true" />
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      <section className="dashboard-kpis" aria-label="Measles worklist summary">
        <article className="dashboard-kpi">
          <span className="dashboard-kpi-icon"><Users size={18} aria-hidden="true" /></span>
          <span className="dashboard-kpi-label">Measles Patients</span>
          <strong>{totalPatients}</strong>
        </article>
      </section>

      <section className="dashboard-priority-card" aria-labelledby="priority-work-heading">
        <header className="dashboard-card-header">
          <div>
            <h2 id="priority-work-heading">Priority Work</h2>
            <p>Top 5 Measles patients by earliest reporting deadline</p>
          </div>
        </header>

        {totalPatients === 0 ? (
          <div className="dashboard-empty">
            No Measles patients currently require reporting attention.
          </div>
        ) : (
          <>
            <div className="dashboard-table-wrap">
              <table className="priority-table">
                <thead>
                  <tr>
                    <th scope="col">Patient</th>
                    <th scope="col">Work Item</th>
                    <th scope="col">Jurisdiction</th>
                    <th scope="col">Priority</th>
                    <th scope="col">Due</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {priorityPatients.map(({ patient, deadline }) => {
                    const priority = priorityFor(deadline);
                    const badgeClass = "priority-badge " + (priority ? priority.toLowerCase() : "no-deadline");
                    return (
                      <tr key={patient.patient_id}>
                        <td><strong>{formatPatientName(patient)}</strong></td>
                        <td>Measles reporting</td>
                        <td>{patient.jurisdiction || EMPTY_VALUE}</td>
                        <td>
                          <span className={badgeClass}>{priority || EMPTY_VALUE}</span>
                        </td>
                        <td>{formatDue(deadline)}</td>
                        <td>
                          <button
                            className="row-action"
                            type="button"
                            onClick={() => navigate("/patients/" + encodeURIComponent(patient.patient_id))}
                          >
                            View Patient <ArrowRight size={13} aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <footer className="dashboard-priority-footer">
              <span>Showing {priorityPatients.length} of {totalPatients} Measles patients</span>
              <span>Ordered by earliest deadline.</span>
            </footer>
          </>
        )}
      </section>
    </section>
  );
}
