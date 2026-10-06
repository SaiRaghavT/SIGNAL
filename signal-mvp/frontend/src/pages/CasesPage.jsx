import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases } from "../api/cases.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { StatusBadge } from "../components/ui/StatusBadge.jsx";
import "../styles/cases.css";

const PAGE_SIZE = 20;
const EMPTY_VALUE = "—";

function formatDate(value) {
  if (!value) return EMPTY_VALUE;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? EMPTY_VALUE
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function CasesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const result = await listCases({
          page, page_size: PAGE_SIZE, search: debouncedSearch || undefined,
          status: status || undefined, signal: controller.signal,
        });
        if (active) setData(result);
      } catch (err) {
        if (active && err?.name !== "AbortError") setError(err?.message || "Unable to load cases.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; controller.abort(); };
  }, [page, debouncedSearch, status, refreshKey]);

  function updateSearch(value) { setSearch(value); setPage(1); }
  function updateStatus(value) { setStatus(value); setPage(1); }

  const items = Array.isArray(data?.items) ? data.items : [];
  const total = Number(data?.total || 0);
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const first = total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const last = Math.min(page * PAGE_SIZE, total);

  return (
    <section className="cases-page">
      <PageHeader title="Cases" subtitle={`${total} ${total === 1 ? "case" : "cases"} in the registry`}>
        <button className="cases-refresh" type="button" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </PageHeader>
      <div className="cases-card">
        <div className="cases-toolbar">
          <label className="cases-search">
            <span className="sr-only">Search cases</span>
            <input type="search" value={search} onChange={(event) => updateSearch(event.target.value)} placeholder="Search case ID, patient, or disease…" />
          </label>
          <label className="cases-status">
            <span className="sr-only">Filter by status</span>
            <select value={status} onChange={(event) => updateStatus(event.target.value)}>
              <option value="">All statuses</option>
              <option value="REPORT">Report</option>
              <option value="HOLD">Hold</option>
              <option value="NEEDS_REVIEW">Needs review</option>
            </select>
          </label>
        </div>

        {loading ? <SignalLoading title="Loading cases…" message="Retrieving case records and reporting information." /> : error ? (
          <div className="cases-error" role="alert">
            <strong>Unable to load cases</strong><span>{error}</span>
            <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>Retry</button>
          </div>
        ) : items.length === 0 ? (
          <div className="cases-empty"><strong>{search || status ? "No matching cases" : "No cases yet"}</strong>
            <span>{search || status ? "Try changing your search or status filter." : "Cases will appear here when they are added to the registry."}</span>
          </div>
        ) : (
          <>
            <div className="patients-table-scroll">
              <table className="cases-table">
                <thead><tr>
                  <th scope="col">Case / Candidate</th><th scope="col">Disease</th><th scope="col">Jurisdiction</th>
                  <th scope="col">Status</th><th scope="col">Reportability</th><th scope="col">Updated</th>
                </tr></thead>
                <tbody>{items.map((item) => (
                  <tr key={item.case_id}>
                    <td><Link className="cases-link" to={`/cases/${encodeURIComponent(item.case_id)}`}>{item.case_id}</Link>
                      <span className="cases-patient">Candidate {item.candidate_id || EMPTY_VALUE}</span></td>
                    <td>{item.disease || EMPTY_VALUE}</td>
                    <td>{item.jurisdiction || EMPTY_VALUE}</td>
                    <td><StatusBadge value={item.status} /></td>
                    <td><StatusBadge value={item.reportability_decision} /></td>
                    <td>{formatDate(item.updated_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <nav className="cases-pagination" aria-label="Case pages">
              <span>Showing {first}–{last} of {total} cases</span>
              <div>
                <button type="button" onClick={() => setPage((current) => current - 1)} disabled={page <= 1}>Previous</button>
                <span aria-live="polite">Page {page} of {Math.max(1, totalPages)}</span>
                <button type="button" onClick={() => setPage((current) => current + 1)} disabled={page >= totalPages}>Next</button>
              </div>
            </nav>
          </>
        )}
      </div>
    </section>
  );
}
