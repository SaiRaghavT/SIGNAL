import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import "../styles/patients.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const PAGE_SIZE = 10;

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(", ")
      : data.detail || data.message;
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return data;
}

function displayDate(value) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

export default function Patients() {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [facility, setFacility] = useState("");
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (search) params.set("search", search);
    if (facility) params.set("facility", facility);

    setLoading(true);
    setError("");
    fetch(`${API_BASE_URL}/api/canonical/patients?${params}`, { signal: controller.signal })
      .then(readJson)
      .then(setResult)
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [page, search, facility, refreshKey]);

  const facilities = useMemo(() => result?.facilities || [], [result]);
  const patients = result?.items || [];
  const pages = Math.max(1, result?.pages || 1);
  const retry = () => setRefreshKey((value) => value + 1);

  return (
    <section className="patients-screen">
      <PageHeader
        title="Patients"
        subtitle="View patients and their available clinical information."
      >
        <button className="patients-refresh" onClick={retry} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </PageHeader>

      <div className="patients-filter-card">
        <label className="patients-search">
          <span>Search patients</span>
          <input
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search patient, ID, DOB..."
          />
        </label>
        <label className="patients-facility">
          <span>Facility</span>
          <select
            value={facility}
            onChange={(event) => {
              setPage(1);
              setFacility(event.target.value);
            }}
          >
            <option value="">All Facilities</option>
            {facilities.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <div className="patients-result-count">
          {loading ? "Loading patients…" : `${result?.total || 0} patients`}
        </div>
      </div>

      {error ? (
        <div className="patients-state patients-error" role="alert">
          <strong>Patients could not be loaded</strong>
          <span>{error}</span>
          <button onClick={retry}>Retry</button>
        </div>
      ) : loading && !result ? (
        <div className="patients-state" aria-live="polite">Loading patients…</div>
      ) : !loading && patients.length === 0 ? (
        <div className="patients-state">
          <strong>No patients found</strong>
          <span>No patients match the current search and facility filters.</span>
        </div>
      ) : (
        <>
          <div className="patients-table-wrap" aria-busy={loading}>
            <table className="patients-table">
              <thead>
                <tr><th>First Name</th><th>DOB</th><th>Condition</th><th>Severity</th><th>View Details</th></tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr key={patient.patient_id}>
                    <td>
                      <strong>{patient.first_name || patient.source_patient_id || "Name not available"}</strong>
                      <small>{patient.last_name || patient.patient_id.slice(0, 8)}</small>
                    </td>
                    <td>{displayDate(patient.date_of_birth)}</td>
                    <td>{patient.condition || <span className="patients-muted">No condition recorded</span>}</td>
                    <td>{patient.severity || "Unknown"}</td>
                    <td><button className="patients-open" onClick={() => navigate(`/patients/${encodeURIComponent(patient.patient_id)}`)}>View Details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav className="patients-pagination" aria-label="Patient pages">
            <span>Page {page} of {pages}</span>
            <div>
              <button onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1 || loading}>Previous</button>
              <button onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages || loading}>Next</button>
            </div>
          </nav>
        </>
      )}

    </section>
  );
}
