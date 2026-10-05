import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/dashboard.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "";

function Dashboard() {
  const navigate = useNavigate();

  const [summary, setSummary] = useState(null);
  const [cases, setCases] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError("");

      const [summaryResponse, casesResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/dashboard/summary`),
        fetch(`${API_BASE_URL}/api/cases?page=1&page_size=5`),
      ]);

      if (!summaryResponse.ok) {
        throw new Error(
          `Dashboard API returned ${summaryResponse.status}`
        );
      }

      if (!casesResponse.ok) {
        throw new Error(
          `Cases API returned ${casesResponse.status}`
        );
      }

      const summaryData = await summaryResponse.json();
      const casesData = await casesResponse.json();

      setSummary(summaryData);
      setCases(casesData.items || []);
    } catch (err) {
      console.error("Dashboard error:", err);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load dashboard data."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const getPatientName = (item) => {
    if (!item.patient) return "—";

    return `${item.patient.first_name || ""} ${
      item.patient.last_name || ""
    }`.trim();
  };

  const formatDate = (date) => {
    if (!date) return "—";

    return new Date(date).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  const formatStatus = (status) => {
    if (!status) return "Unknown";

    return status
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  };

  const getStatusClass = (status) => {
    const value = (status || "").toUpperCase();

    if (
      value.includes("REPORT") ||
      value.includes("SUCCESS") ||
      value.includes("ACK")
    ) {
      return "status-green";
    }

    if (
      value.includes("PENDING") ||
      value.includes("REVIEW") ||
      value.includes("OPEN")
    ) {
      return "status-orange";
    }

    if (
      value.includes("FAIL") ||
      value.includes("REJECT")
    ) {
      return "status-red";
    }

    return "status-gray";
  };

  const metrics = summary
    ? [
        {
          label: "Total Cases",
          value: summary.cases,
          description: "Persisted cases",
          className: "metric-blue",
        },
        {
          label: "Reportable Cases",
          value: summary.reportable_cases,
          description: "Decision: report",
          className: "metric-green",
        },
        {
          label: "Needs Review",
          value: summary.needs_review,
          description: "Requires attention",
          className: "metric-orange",
        },
        {
          label: "Submitted Cases",
          value: summary.submitted_cases,
          description: "At least one submission",
          className: "metric-purple",
        },
        {
          label: "PHA Follow-ups",
          value: summary.follow_up_cases,
          description: "Follow-up recorded",
          className: "metric-blue",
        },
        {
          label: "Upcoming Deadlines",
          value: summary.upcoming_deadlines,
          description: "Marked upcoming",
          className: "metric-orange",
        },
      ]
    : [];

  return (
    <div className="dashboard-page">

      {/* MAIN */}

      <div className="dashboard-main">

        {/* CONTENT */}

        <div className="dashboard-content">

          <div className="dashboard-heading">

            <div>
              <span className="page-eyebrow">
                OVERVIEW
              </span>

              <h1>
                Dashboard
              </h1>

              <p>
                Overview of reporting activity and
                workflow status.
              </p>
            </div>

            <div className="live-indicator">
              <span />
              Live operational data
            </div>

          </div>


          {/* ERROR */}

          {error && (
            <div className="dashboard-error">

              <div>
                <strong>
                  We couldn't load the dashboard
                </strong>

                <p>
                  {error}
                </p>
              </div>

              <button onClick={loadDashboard}>
                Try again
              </button>

            </div>
          )}


          {/* LOADING */}

          {loading && (
            <SignalLoading title="Loading Dashboard" message="Retrieving current reporting activity and workflow status." />
          )}


          {/* DASHBOARD DATA */}

          {!loading && !error && summary && (
            <>

              {/* KPI CARDS */}

              <section className="metric-grid">

                {metrics.map((metric) => (
                  <article
                    className={`metric-card ${metric.className}`}
                    key={metric.label}
                  >

                    <div className="metric-top">
                      <span className="metric-label">
                        {metric.label}
                      </span>

                      <span className="metric-dot" />
                    </div>

                    <div className="metric-value">
                      {metric.value}
                    </div>

                    <div className="metric-description">
                      {metric.description}
                    </div>

                  </article>
                ))}

              </section>


              {/* WORKFLOW */}

              <section className="workflow-card">

                <div className="section-header">

                  <div>
                    <span className="section-eyebrow">
                      SIGNAL WORKFLOW
                    </span>

                    <h2>
                      Reporting lifecycle
                    </h2>
                  </div>

                  <span className="workflow-label">
                    8 stages
                  </span>

                </div>


                <div className="workflow">

                  {[
                    "Data Ingestion",
                    "Detection",
                    "Reportability",
                    "Case",
                    "Validation",
                    "Reporting",
                    "Submission",
                    "PHA Follow-up",
                  ].map((stage, index) => (
                    <div
                      className="workflow-stage"
                      key={stage}
                    >

                      <div className="workflow-number">
                        {String(index + 1).padStart(2, "0")}
                      </div>

                      <span>
                        {stage}
                      </span>

                    </div>
                  ))}

                </div>

              </section>


              {/* RECENT CASES */}

              <section className="cases-card">

                <div className="section-header">

                  <div>
                    <span className="section-eyebrow">
                      CASE MANAGEMENT
                    </span>

                    <h2>
                      Recent cases
                    </h2>
                  </div>

                  <button
                    className="view-all-button"
                    onClick={() => navigate("/cases")}
                  >
                    View all cases →
                  </button>

                </div>


                {cases.length === 0 ? (
                  <div className="empty-cases">
                    <strong>
                      No cases available
                    </strong>

                    <span>
                      The backend returned no cases.
                    </span>
                  </div>
                ) : (

                  <div className="cases-table-wrapper">

                    <table className="cases-table">

                      <thead>
                        <tr>
                          <th>Case ID</th>
                          <th>Patient</th>
                          <th>Disease</th>
                          <th>Jurisdiction</th>
                          <th>Status</th>
                          <th>Created</th>
                          <th></th>
                        </tr>
                      </thead>

                      <tbody>

                        {cases.map((item) => (
                          <tr key={item.case_id}>

                            <td>
                              <strong className="case-id">
                                {item.case_id}
                              </strong>
                            </td>

                            <td>
                              {getPatientName(item)}
                            </td>

                            <td>
                              {item.disease || "—"}
                            </td>

                            <td>
                              {item.jurisdiction || "—"}
                            </td>

                            <td>
                              <span
                                className={`case-status ${getStatusClass(
                                  item.status
                                )}`}
                              >
                                <span />
                                {formatStatus(item.status)}
                              </span>
                            </td>

                            <td>
                              {formatDate(item.created_at)}
                            </td>

                            <td>

                              <button
                                className="case-open-button"
                                onClick={() =>
                                  navigate(
                                    `/cases/${encodeURIComponent(item.case_id)}`
                                  )
                                }
                              >
                                Open
                              </button>

                            </td>

                          </tr>
                        ))}

                      </tbody>

                    </table>

                  </div>

                )}

              </section>

            </>
          )}

        </div>

      </div>

    </div>
  );
}

export default Dashboard;
