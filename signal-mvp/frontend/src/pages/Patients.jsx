import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listCanonicalPatients } from "../api/canonical.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/patients.css";

const PAGE_SIZE = 10;

function formatDate(value) {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(year, month - 1, day));
}

function formatDeadline(value) {
  if (!value) return "—";
  const deadline = typeof value === "string" ? value : value.deadline;
  if (!deadline) return "—";
  if (value.reporting_timing?.toUpperCase() === "IMMEDIATE") {
    return "IMMEDIATE";
  }
  const date = new Date(deadline);
  return Number.isNaN(date.getTime())
    ? deadline
    : new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(date);
}

function PatientTableSkeleton() {
  return (
    <div
      className="patients-table-scroll"
      role="status"
      aria-label="Loading patients"
      aria-live="polite"
    >
      <table className="patients-table">
        <thead>
          <tr>
            <th>First Name</th>
            <th>DOB</th>
            <th>Condition</th>
            <th>Deadline</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody aria-hidden="true">
          {Array.from({ length: 6 }, (_, index) => (
            <tr key={index}>
              <td><span className="patient-skeleton patient-skeleton-name" /></td>
              <td><span className="patient-skeleton patient-skeleton-date" /></td>
              <td><span className="patient-skeleton patient-skeleton-condition" /></td>
              <td><span className="patient-skeleton patient-skeleton-deadline" /></td>
              <td><span className="patient-skeleton patient-skeleton-action" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function visiblePages(currentPage, totalPages) {
  const first = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
  return Array.from(
    { length: Math.min(5, totalPages) },
    (_, index) => first + index,
  );
}

export default function Patients() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [facility, setFacility] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function loadPatients() {
      setLoading(true);
      setError(null);
      try {
        const data = await listCanonicalPatients({
          page,
          page_size: PAGE_SIZE,
          search: debouncedSearch || undefined,
          facility: facility || undefined,
          signal: controller.signal,
        });
        if (active) setResult(data);
      } catch (requestError) {
        if (active && requestError.name !== "AbortError") {
          setError(requestError);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadPatients();
    return () => {
      active = false;
      controller.abort();
    };
  }, [page, debouncedSearch, facility, refreshKey]);

  function updateSearch(value) {
    setSearch(value);
    setPage(1);
  }

  function updateFacility(value) {
    setFacility(value);
    setPage(1);
  }

  return (
    <section className="patients-page">
      <PageHeader
        title="Patients"
        subtitle="Manage and review patients from canonical clinical data."
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
        <div className="patients-toolbar">
          <label className="patients-search">
            <span className="sr-only">Search patients</span>
            <input
              type="search"
              value={search}
              onChange={(event) => updateSearch(event.target.value)}
              placeholder="Search patient, ID, DOB..."
            />
          </label>
          <label className="patients-facility">
            <span className="sr-only">Filter by facility</span>
            <select
              value={facility}
              onChange={(event) => updateFacility(event.target.value)}
            >
              <option value="">All Facilities</option>
              {(result?.facilities ?? []).map((facilityName) => (
                <option key={facilityName} value={facilityName}>
                  {facilityName}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <SignalLoading title="Loading Patients" message="Retrieving patient records and reporting information." />
        ) : error ? (
          <div className="patients-error" role="alert">
            <p>Unable to load patients.</p>
            <span>{error.message}</span>
            <button
              type="button"
              onClick={() => setRefreshKey((key) => key + 1)}
            >
              Retry
            </button>
          </div>
        ) : result.items.length === 0 ? (
          <div className="patients-empty">
            <strong>No patients found</strong>
            <p>Try adjusting your search or facility filter.</p>
          </div>
        ) : (
          <>
            <div className="patients-table-scroll">
              <table className="patients-table">
                <thead>
                  <tr>
                    <th scope="col">First Name</th>
                    <th scope="col">DOB</th>
                    <th scope="col">Condition</th>
                    <th scope="col">Deadline</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((patient) => (
                    <tr key={patient.patient_id}>
                      <td>
                        <span
                          className={`patient-name${patient.first_name ? "" : " patient-name-missing"}`}
                        >
                          {patient.first_name || "Name not provided"}
                        </span>
                        {patient.source_patient_id && (
                          <span className="patient-source-id">
                            {patient.source_patient_id}
                          </span>
                        )}
                      </td>
                      <td>{formatDate(patient.date_of_birth)}</td>
                      <td>{patient.condition || "—"}</td>
                      <td title={patient.deadline_reason || undefined}>
                        <span className="patient-deadline-value">
                          {formatDeadline(patient.deadline)}
                        </span>
                        {(patient.deadline?.status || patient.deadline?.urgency) && (
                          <span className="patient-deadline-urgency">
                            {[patient.deadline.status, patient.deadline.urgency]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        )}
                      </td>
                      <td>
                        <button
                          className="patients-view"
                          type="button"
                          onClick={() =>
                            navigate(
                              `/patients/${encodeURIComponent(patient.patient_id)}`,
                              {
                                state: {
                                  patientNavigation: {
                                    page: result.page,
                                    pageSize: result.page_size,
                                    pages: result.pages,
                                    search: debouncedSearch || undefined,
                                    facility: facility || undefined,
                                    patientIds: result.items.map((item) => item.patient_id),
                                  },
                                },
                              },
                            )
                          }
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <nav className="patients-pagination" aria-label="Patient pages">
              <span className="patients-count">
                {result.total} {result.total === 1 ? "patient" : "patients"}
              </span>
              <div className="patients-page-controls">
                <button
                  type="button"
                  onClick={() => setPage((current) => current - 1)}
                  disabled={page <= 1}
                >
                  Previous
                </button>
                {visiblePages(page, result.pages).map((pageNumber) => (
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
                <button
                  type="button"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={page >= result.pages}
                >
                  Next
                </button>
              </div>
            </nav>
          </>
        )}
      </div>
    </section>
  );
}
