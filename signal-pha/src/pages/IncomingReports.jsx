
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  FileText,
  RefreshCw,
  Search,
} from "lucide-react";
import { getIncomingReports } from "../services/phaApi";
import { cleanPatientName } from "../utils/patientNames.js";

export default function IncomingReports() {
  const navigate = useNavigate();

  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  async function loadReports() {
    try {
      setLoading(true);
      setError("");

      const result = await getIncomingReports();
      setReports(result.reports ?? []);
    } catch (err) {
      setError(err.message || "Unable to load incoming reports.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadReports();
  }, []);

  const filteredReports = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) return reports;

    return reports.filter((report) =>
      [
        report.patient_name,
        report.submission_id,
        report.case_id,
        report.ecr_id,
        report.channel,
        report.pha_case_id,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    );
  }, [reports, search]);

  const submittedCount = reports.filter(
    (report) => report.status === "SUBMITTED"
  ).length;

  const acknowledgedCount = reports.filter(
    (report) => report.status === "ACKNOWLEDGED"
  ).length;

  function openReport(report) {
    navigate(`/reports/${encodeURIComponent(report.submission_id)}`);
  }

  return (
    <main className="pha-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <span>Public Health</span><span aria-hidden="true">/</span><strong>Incoming Reports</strong>
      </nav>
      <header className="page-header">
        <div>
          <h1>Incoming Reports</h1>
          <p>
            Review electronic case reports received by the public health authority.
          </p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={loadReports}
          disabled={loading}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </header>

      <section className="metrics-grid">
        <article className="metric-card">
          <span className="metric-icon">
            <FileText size={20} />
          </span>

          <span className="metric-label">Unique patients</span>
          <strong>{reports.length}</strong>
          <small>Latest submission per patient</small>
        </article>

        <article className="metric-card">
          <span className="metric-icon pending">
            <Clock3 size={20} />
          </span>

          <span className="metric-label">Submitted</span>
          <strong>{submittedCount}</strong>
          <small>Recorded by SIGNAL as submitted</small>
        </article>

        <article className="metric-card">
          <span className="metric-icon received">
            <CheckCircle2 size={20} />
          </span>

          <span className="metric-label">Receipt acknowledged</span>
          <strong>{acknowledgedCount}</strong>
          <small>Receipt acknowledgement recorded</small>
        </article>
      </section>

      <section className="reports-panel">
        <div className="panel-heading">
          <div>
            <h2>Report queue</h2>
            <p>One latest submission per unique patient</p>
          </div>

          <label className="search-box">
            <Search size={17} />

            <input
              type="search"
              aria-label="Search incoming reports"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search patient, submission, case, ECR, or channel"
            />
          </label>
        </div>

        {error && (
          <div className="error-message">
            <AlertCircle size={18} />
            <span>{error}</span>

            <button type="button" onClick={loadReports}>Retry</button>
          </div>
        )}

        {loading ? (
          <div className="empty-state">
            <RefreshCw size={22} />
            <p>Loading reports from SIGNAL...</p>
          </div>
        ) : !error && filteredReports.length === 0 ? (
          <div className="empty-state">
            <FileText size={28} />
            <p>
              {search
                ? "No matching patients or reports found."
                : "No incoming reports found."}
            </p>
          </div>
        ) : (
          !error && (
            <div className="table-scroll">
              <table className="reports-table">
                <thead>
                  <tr>
                    <th>Patient Name</th>
                    <th>Submission</th>
                    <th>ECR ID</th>
                    <th>Case ID</th>
                    <th>Created</th>
                    <th>PHA Case</th>
                    <th>Action</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredReports.map((report) => (
                    <tr key={report.submission_id}>
                      <td>
                        <strong>{cleanPatientName(report.patient_name) || "Unknown patient"}</strong>
                      </td>

                      <td>
                        <strong>{report.submission_id}</strong>
                        <small>{report.channel || "Electronic report"}</small>
                      </td>

                      <td>{report.ecr_id || "—"}</td>
                      <td>{report.case_id || "—"}</td>

                      <td>
                        {report.created_at
                          ? new Date(report.created_at).toLocaleString()
                          : "—"}
                      </td>

                      <td>{report.pha_case_id || "Not assigned"}</td>

                      <td>
                        <button
                          type="button"
                          className="view-button"
                          onClick={() => openReport(report)}
                        >
                          Review <ArrowUpRight size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        <footer className="table-footer">
          Showing {filteredReports.length} of {reports.length} unique patients
        </footer>
      </section>

      <p className="demo-note">
        <AlertCircle size={15} />
        Local demonstration environment. Receipt acknowledgement does not
        imply PHA acceptance or clinical verification.
      </p>
    </main>
  );
}
