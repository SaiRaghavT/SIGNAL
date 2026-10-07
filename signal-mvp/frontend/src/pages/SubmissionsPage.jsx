import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listSubmissions } from "../api/submissions.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/submissions.css";

const PAGE_SIZE = 100;
const ROWS_PER_PAGE = 10;
const EMPTY_VALUE = "—";
const RETRYABLE_STATUSES = ["FAILED", "REJECTED", "ERROR"];

const FILTERS = [
  { id: "all", label: "All" },
  { id: "pending", label: "Pending" },
  { id: "acknowledged", label: "Acknowledged" },
  { id: "failed", label: "Failed" },
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
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function normalizedStatus(item) {
  return String(item.status || "").trim().toUpperCase();
}

function statusTone(status) {
  if (status === "ACKNOWLEDGED") return "acknowledged";
  if (status === "SUBMITTED") return "pending";
  if (RETRYABLE_STATUSES.includes(status)) return "failed";
  return "neutral";
}

async function loadAllSubmissions() {
  const firstPage = await listSubmissions({ page: 1, page_size: PAGE_SIZE });
  const pages = firstPage.pages || Math.ceil((firstPage.total || 0) / PAGE_SIZE);
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, pages - 1) }, (_, index) =>
      listSubmissions({ page: index + 2, page_size: PAGE_SIZE }),
    ),
  );
  return [...(firstPage.items || []), ...rest.flatMap((page) => page.items || [])];
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
      setError(loadError?.message || "We couldn't retrieve submission records from the reporting service.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const counts = useMemo(() => ({
    all: submissions.length,
    pending: submissions.filter((item) => normalizedStatus(item) === "SUBMITTED").length,
    acknowledged: submissions.filter((item) => normalizedStatus(item) === "ACKNOWLEDGED").length,
    failed: submissions.filter((item) => RETRYABLE_STATUSES.includes(normalizedStatus(item))).length,
  }), [submissions]);

  const visibleSubmissions = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return submissions.filter((item) => {
      const status = normalizedStatus(item);
      const matchesStatus = statusFilter === "all"
        || (statusFilter === "pending" && status === "SUBMITTED")
        || (statusFilter === "acknowledged" && status === "ACKNOWLEDGED")
        || (statusFilter === "failed" && RETRYABLE_STATUSES.includes(status));
      if (!matchesStatus) return false;
      if (!query) return true;
      return [
        patientName(item.patient),
        item.disease,
        item.jurisdiction,
        item.case_id,
        item.submission_id,
      ].some((value) => String(value || "").toLocaleLowerCase().includes(query));
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
      <PageHeader
        title="Submissions"
        subtitle="Track report packages dispatched to public-health authorities and monitor their acknowledgement status."
      />

      {loading ? (
        <SignalLoading title="Loading Submissions" message="Retrieving reporting submission records." />
      ) : error ? (
        <div className="submissions-error" role="alert">
          <strong>Unable to load submissions</strong>
          <p>We couldn't retrieve submission records from the reporting service.</p>
          <button type="button" onClick={load}>Retry</button>
        </div>
      ) : (
        <>
          <div className="submissions-kpis" aria-label="Submission metrics">
            <article className="submissions-kpi">
              <span>TOTAL SUBMISSIONS</span><strong>{counts.all}</strong><small>All submission records returned by the backend.</small>
            </article>
            <article className="submissions-kpi pending">
              <span>PENDING ACKNOWLEDGEMENT</span><strong>{counts.pending}</strong><small>Dispatched submissions awaiting acknowledgement.</small>
            </article>
            <article className="submissions-kpi acknowledged">
              <span>ACKNOWLEDGED</span><strong>{counts.acknowledged}</strong><small>Submissions with successful acknowledgement.</small>
            </article>
            <article className="submissions-kpi failed">
              <span>FAILED / RETRY</span><strong>{counts.failed}</strong><small>Failed or rejected submissions eligible for retry.</small>
            </article>
          </div>

          <section className="submissions-operations" aria-labelledby="submission-operations-title">
            <header className="submissions-operations-header">
              <div>
                <h2 id="submission-operations-title">Submission Operations</h2>
                <p>Track reports dispatched through approved reporting channels and monitor acknowledgement outcomes.</p>
              </div>
              <span className="submissions-record-count">{counts.all} {counts.all === 1 ? "record" : "records"}</span>
            </header>

            <div className="submissions-toolbar">
              <nav className="submissions-filters" aria-label="Filter submissions by status">
                {FILTERS.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    className={statusFilter === filter.id ? "active" : ""}
                    aria-pressed={statusFilter === filter.id}
                    onClick={() => chooseFilter(filter.id)}
                  >
                    {filter.label} ({counts[filter.id]})
                  </button>
                ))}
              </nav>
              <label className="submissions-search">
                <span>Search</span>
                <input
                  type="search"
                  value={search}
                  onChange={(event) => { setSearch(event.target.value); setPage(1); }}
                  placeholder="Search patient / case / submission..."
                />
              </label>
            </div>

            {visibleRows.length === 0 ? (
              <div className="submissions-empty">
                <strong>{counts.all === 0 ? "No submissions yet" : "No matching submissions"}</strong>
                <p>{counts.all === 0 ? "There are currently no reporting submissions to display." : "Try another status filter or search term."}</p>
              </div>
            ) : (
              <div className="submissions-table-wrap">
                <table className="submissions-table">
                  <thead>
                    <tr>
                      <th scope="col">PATIENT</th>
                      <th scope="col">CONDITION</th>
                      <th scope="col">JURISDICTION</th>
                      <th scope="col">SUBMITTED</th>
                      <th scope="col">CHANNEL</th>
                      <th scope="col">STATUS</th>
                      <th scope="col">ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((item) => {
                      const status = normalizedStatus(item);
                      return (
                        <tr key={item.submission_id}>
                          <td>{patientName(item.patient)}</td>
                          <td>{item.disease || EMPTY_VALUE}</td>
                          <td>{item.jurisdiction || EMPTY_VALUE}</td>
                          <td>{formatDate(item.created_at)}</td>
                          <td>{item.channel || EMPTY_VALUE}</td>
                          <td><span className={`submissions-status ${statusTone(status)}`}>{item.status || EMPTY_VALUE}</span></td>
                          <td><Link className="submissions-view" to={`/submissions/case/${encodeURIComponent(item.case_id)}`}>View →</Link></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {visibleSubmissions.length > ROWS_PER_PAGE && (
              <footer className="submissions-pagination">
                <span>Showing {firstVisible}–{lastVisible} of {visibleSubmissions.length} submissions</span>
                <div>
                  <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>Previous</button>
                  <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount}>Next</button>
                </div>
              </footer>
            )}
          </section>
        </>
      )}
    </section>
  );
}
