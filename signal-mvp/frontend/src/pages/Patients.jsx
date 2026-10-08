import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listCanonicalPatients } from "../api/canonical.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/patients.css";

const PAGE_SIZE = 10;
const EMPTY_VALUE = "—";

function formatDate(value) {
  if (!value) return EMPTY_VALUE;
  const [year, month, day] = String(value).slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return EMPTY_VALUE;
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return EMPTY_VALUE;
  }
  const parts = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).formatToParts(date);
  const part = Object.fromEntries(parts.map(({ type, value: partValue }) => [type, partValue]));
  return `${part.day} ${part.month} ${part.year}`;
}

function formatDeadline(value) {
  const deadline = typeof value === "string" ? value : value?.deadline;
  if (typeof deadline !== "string" || !deadline.trim()) return EMPTY_VALUE;
  const date = new Date(deadline);
  if (Number.isNaN(date.getTime())) return EMPTY_VALUE;
  const parts = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(date);
  const part = Object.fromEntries(parts.map(({ type, value: partValue }) => [type, partValue]));
  return `${part.day} ${part.month} ${part.year}, ${part.hour}:${part.minute} ${part.dayPeriod?.toUpperCase() || ""}`.trim();
}

function formatPatientName(patient) {
  return [patient.first_name, patient.last_name]
    .map((name) => String(name || "").replace(/\d+/g, "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join(" ");
}

function formatCondition(value) {
  return String(value || "")
    .replace(/\s*\(disorder\)$/i, "")
    .trim();
}

function visiblePages(currentPage, totalPages) {
  const first = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
  return Array.from({ length: Math.min(5, totalPages) }, (_, index) => first + index);
}

export default function Patients() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function loadPatients() {
      setLoading(true);
      setError(null);
      try {
        const response = await listCanonicalPatients({
          page,
          page_size: PAGE_SIZE,
          signal: controller.signal,
        });
        if (active) setResult(response);
      } catch (requestError) {
        if (active && requestError.name !== "AbortError") setError(requestError);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadPatients();
    return () => {
      active = false;
      controller.abort();
    };
  }, [page, refreshKey]);

  const visiblePatients = Array.isArray(result?.items) ? result.items : [];
  const totalPages = result?.pages || 0;
  const firstVisiblePatient = result?.total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const lastVisiblePatient = Math.min(page * PAGE_SIZE, result?.total || 0);

  return (
    <section className="patients-page">
      <PageHeader
        title="Patients"
        subtitle={result
          ? `${result.total} patients from canonical clinical data.`
          : "Manage and review patients from canonical clinical data."}
      >
        <button
          className="patients-refresh"
          type="button"
          onClick={() => setRefreshKey((key) => key + 1)}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </PageHeader>

      <div className="patients-card">
        {loading ? (
          <SignalLoading title="Loading patients..." message="Retrieving patient records." />
        ) : error ? (
          <div className="patients-error" role="alert">
            <p>Unable to load patients.</p>
            <span>{error.message}</span>
            <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>Retry</button>
          </div>
        ) : visiblePatients.length === 0 ? (
          <div className="patients-empty">
            <strong>No patients found</strong>
          </div>
        ) : (
          <>
            <div className="patients-table-scroll">
              <table className="patients-table">
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">DOB</th>
                    <th scope="col">Condition</th>
                    <th scope="col">Last Encounter</th>
                    <th scope="col">Deadline</th>
                    <th scope="col">View Patient</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePatients.map((patient) => {
                    const fullName = formatPatientName(patient);
                    return (
                      <tr key={patient.patient_id}>
                        <td><span className={`patient-name${fullName ? "" : " patient-name-missing"}`}>{fullName || EMPTY_VALUE}</span></td>
                        <td>{formatDate(patient.date_of_birth)}</td>
                        <td>{formatCondition(patient.condition) || EMPTY_VALUE}</td>
                        <td>{formatDate(patient.last_encounter)}</td>
                        <td title={patient.deadline_reason || undefined}>
                          <span className="patient-deadline-value">{formatDeadline(patient.deadline?.deadline)}</span>
                          {patient.deadline?.deadline_status && (
                            <span className="patient-deadline-state">
                              {patient.deadline.deadline_status}
                              {Number.isFinite(patient.deadline.minutes_remaining)
                                ? ` · ${patient.deadline.minutes_remaining} min`
                                : ""}
                            </span>
                          )}
                        </td>
                        <td>
                          <button
                            className="patients-view"
                            type="button"
                            onClick={() => navigate(`/patients/${encodeURIComponent(patient.patient_id)}`)}
                          >
                            View Patient
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <nav className="patients-pagination" aria-label="Patient pages">
              <span className="patients-count">
                Showing {firstVisiblePatient}–{lastVisiblePatient} of {result?.total || 0} patients
              </span>
              <div className="patients-page-controls">
                <button type="button" onClick={() => setPage((current) => current - 1)} disabled={page <= 1}>Previous</button>
                {visiblePages(page, totalPages).map((pageNumber) => (
                  <button
                    key={pageNumber}
                    type="button"
                    className={pageNumber === page ? "active" : ""}
                    aria-current={pageNumber === page ? "page" : undefined}
                    onClick={() => setPage(pageNumber)}
                  >
                    {pageNumber}
                  </button>
                ))}
                <button type="button" onClick={() => setPage((current) => current + 1)} disabled={page >= totalPages}>Next</button>
              </div>
            </nav>
          </>
        )}
      </div>
    </section>
  );
}
