import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listClinicalSubmissionTracking } from "../api/submissions.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/submissions.css";

const PAGE_SIZE = 100;
const ROWS_PER_PAGE = 10;
const EMPTY_VALUE = "—";
const RETRYABLE_STATUSES = ["FAILED", "REJECTED", "ERROR"];
const IN_PROGRESS = new Set(["PENDING ADMIN VERIFICATION", "VERIFIED", "READY FOR SUBMISSION", "SUBMITTED"]);
const NEEDS_ATTENTION = new Set(["FAILED", "ERROR", "REJECTED", "RETURNED FOR CORRECTION"]);
const FILTERS = [
  { id: "all", label: "All" },
  { id: "pending", label: "In progress" },
  { id: "acknowledged", label: "Acknowledged" },
  { id: "failed", label: "Needs attention" },
];

function patientName(patient = {}) {
  const direct = patient.name || patient.full_name || patient.patient_name;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  const first = patient.first_name || patient.given_name || "";
  const last = patient.last_name || patient.family_name || "";
  return [first, last].filter(Boolean).join(" ") || EMPTY_VALUE;
}

function formatDate(value) {
  if (!value) return EMPTY_VALUE;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return EMPTY_VALUE;
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
  }).format(date);
}

function normalizedStatus(item) {
  return String(item.workflow_status || item.status || "").trim().toUpperCase();
}

function statusTone(status) {
  if (["ACKNOWLEDGED", "ACCEPTED"].includes(status)) return "acknowledged";
  if (IN_PROGRESS.has(status)) return "pending";
  if (NEEDS_ATTENTION.has(status) || RETRYABLE_STATUSES.includes(status)) return "failed";
  return "neutral";
}

async function loadAllSubmissions() {
  const first = await listClinicalSubmissionTracking({ page: 1, page_size: PAGE_SIZE });
  const pages = first.pages || Math.ceil((first.total || 0) / PAGE_SIZE);
  const rest = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, index) =>
    listClinicalSubmissionTracking({ page: index + 2, page_size: PAGE_SIZE })));
  return [...(first.items || []), ...rest.flatMap((page) => page.items || [])];
}

export function SubmissionsPage() {
  const [submissions, setSubmissions] = useState([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSubmissions(await loadAllSubmissions());
      setPage(1);
    } catch (loadError) {
      setError(loadError?.message || "We couldn't retrieve cases and submission records from the reporting service.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const counts = useMemo(() => ({
    all: submissions.length,
    pending: submissions.filter((item) => IN_PROGRESS.has(normalizedStatus(item))).length,
    acknowledged: submissions.filter((item) => ["ACKNOWLEDGED", "ACCEPTED"].includes(normalizedStatus(item))).length,
    failed: submissions.filter((item) => NEEDS_ATTENTION.has(normalizedStatus(item)) || RETRYABLE_STATUSES.includes(String(item.status || "").toUpperCase())).length,
  }), [submissions]);

  const visibleSubmissions = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return submissions.filter((item) => {
      const status = normalizedStatus(item);
      const matchesStatus = statusFilter === "all"
        || (statusFilter === "pending" && IN_PROGRESS.has(status))
        || (statusFilter === "acknowledged" && ["ACKNOWLEDGED", "ACCEPTED"].includes(status))
        || (statusFilter === "failed" && NEEDS_ATTENTION.has(status));
      if (!matchesStatus) return false;
      if (!query) return true;
      return [patientName(item.patient), item.disease, item.jurisdiction, item.case_id, item.submission_id, item.destination]
        .some((value) => String(value || "").toLocaleLowerCase().includes(query));
    });
  }, [search, statusFilter, submissions]);

  const pageCount = Math.max(1, Math.ceil(visibleSubmissions.length / ROWS_PER_PAGE));
  const visibleRows = visibleSubmissions.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE);
  const firstVisible = visibleSubmissions.length ? (page - 1) * ROWS_PER_PAGE + 1 : 0;
  const lastVisible = Math.min(page * ROWS_PER_PAGE, visibleSubmissions.length);

  function chooseFilter(filterId) {
    setStatusFilter(filterId);
    setPage(1);
  }

  return (
    <section className="submissions-page">
      <PageHeader title="Submissions" subtitle="Follow each case from administrator review through PHA submission and acknowledgement." />
      {loading ? (
        <SignalLoading title="Loading Submissions" message="Retrieving queued cases and persisted PHA submission records." />
      ) : error ? (
        <div className="submissions-error" role="alert">
          <strong>Unable to load submissions</strong>
          <p>{error}</p>
          <button type="button" onClick={load}>Retry</button>
        </div>
      ) : (
        <>
          <div className="submissions-kpis" aria-label="Submission metrics">
            <article className="submissions-kpi"><span>CASES &amp; SUBMISSIONS</span><strong>{counts.all}</strong><small>Queued cases and persisted transmission attempts.</small></article>
            <article className="submissions-kpi pending"><span>IN PROGRESS</span><strong>{counts.pending}</strong><small>In administrator review or awaiting PHA acknowledgement.</small></article>
            <article className="submissions-kpi acknowledged"><span>ACKNOWLEDGED</span><strong>{counts.acknowledged}</strong><small>PHA acknowledgements recorded in SIGNAL.</small></article>
            <article className="submissions-kpi failed"><span>NEEDS ATTENTION</span><strong>{counts.failed}</strong><small>Returned cases or unsuccessful submissions.</small></article>
          </div>
          <section className="submissions-operations" aria-labelledby="submission-operations-title">
            <header className="submissions-operations-header">
              <div><h2 id="submission-operations-title">Submission Tracking</h2><p>Cases appear when added to the Reporting Queue. Their persisted PHA status updates after administrator dispatch.</p></div>
              <button type="button" className="submissions-refresh" onClick={load} disabled={loading}>Refresh</button>
            </header>
            <div className="submissions-toolbar">
              <nav className="submissions-filters" aria-label="Filter submissions by status">
                {FILTERS.map((filter) => <button key={filter.id} type="button" className={statusFilter === filter.id ? "active" : ""} aria-pressed={statusFilter === filter.id} onClick={() => chooseFilter(filter.id)}>{filter.label} ({counts[filter.id]})</button>)}
              </nav>
              <label className="submissions-search"><span>Search</span><input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search patient / case / submission..." /></label>
            </div>
            {visibleRows.length === 0 ? (
              <div className="submissions-empty">
                <strong>{counts.all === 0 ? "No cases have reached reporting yet" : "No matching cases or submissions"}</strong>
                <p>{counts.all === 0 ? "When Clinical Staff adds a case to the Reporting Queue, it will appear here. Start from Patients to prepare a report." : "Try another status filter or search term."}</p>
                {counts.all === 0 && <Link className="submissions-view" to="/patients">Open Patients</Link>}
              </div>
            ) : (
              <div className="submissions-table-wrap"><table className="submissions-table">
                <thead><tr><th scope="col">PATIENT / CASE</th><th scope="col">CONDITION</th><th scope="col">JURISDICTION</th><th scope="col">LAST UPDATED</th><th scope="col">PHA / CHANNEL</th><th scope="col">WORKFLOW STATUS</th><th scope="col">ACTION</th></tr></thead>
                <tbody>{visibleRows.map((item) => {
                  const status = normalizedStatus(item);
                  const href = item.submission_id ? `/submissions/case/${encodeURIComponent(item.case_id)}` : `/cases/${encodeURIComponent(item.case_id)}`;
                  return <tr key={item.record_id || item.submission_id || item.case_id}>
                    <td><strong>{patientName(item.patient)}</strong><small>{item.case_id}{item.submission_id ? ` · ${item.submission_id}` : " · Not yet submitted"}</small></td>
                    <td>{item.disease || EMPTY_VALUE}</td><td>{item.jurisdiction || EMPTY_VALUE}</td>
                    <td>{formatDate(item.updated_at || item.created_at)}</td>
                    <td>{item.destination || item.jurisdiction || EMPTY_VALUE}{item.channel && <small>{item.channel}</small>}</td>
                    <td><span className={`submissions-status ${statusTone(status)}`}>{item.workflow_status || item.status || EMPTY_VALUE}</span></td>
                    <td><Link className="submissions-view" to={href}>{item.submission_id ? "View submission →" : "View case →"}</Link></td>
                  </tr>;
                })}</tbody>
              </table></div>
            )}
            {visibleSubmissions.length > ROWS_PER_PAGE && <footer className="submissions-pagination"><span>Showing {firstVisible}–{lastVisible} of {visibleSubmissions.length} records</span><div><button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>Previous</button><button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount}>Next</button></div></footer>}
          </section>
        </>
      )}
    </section>
  );
}
