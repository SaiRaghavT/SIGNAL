import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { getAdminSubmissions } from "../../services/adminService.js";
import "../../styles/AdminSubmissions.css";

const STATUS_OPTIONS = [
  "ALL",
  "SUBMITTED",
  "AWAITING_ACKNOWLEDGEMENT",
  "ACKNOWLEDGED",
  "FAILED",
  "RETRY_REQUIRED",
];

const MODE_OPTIONS = ["ALL", "IMMEDIATE", "INDIVIDUAL", "BATCH"];

function normalizeItems(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.items)) return response.items;
  if (Array.isArray(response?.submissions)) return response.submissions;
  if (Array.isArray(response?.data)) return response.data;
  return [];
}

function textValue(...values) {
  const value = values.find(
    (item) => item !== undefined && item !== null && String(item).trim() !== "",
  );

  return value === undefined || value === null ? "—" : String(value);
}

function conditionLabel(...values) {
  for (const value of values) {
    const label = conditionValueLabel(value);
    if (label !== "\u2014") return label;
  }
  return "\u2014";
}

function conditionValueLabel(value) {
  if (Array.isArray(value)) return conditionLabel(...value);
  if (typeof value === "number") return value === 14189004 ? "Measles" : "\u2014";
  if (value && typeof value === "object") {
    for (const key of ["display", "name", "condition_name", "disease_name", "text", "label", "title", "description"]) {
      const label = conditionValueLabel(value[key]);
      if (label !== "\u2014") return label;
    }
    for (const key of ["concept", "condition", "disease", "coding", "codeableConcept", "code", "value"]) {
      const label = conditionValueLabel(value[key]);
      if (label !== "\u2014") return label;
    }
    return "\u2014";
  }
  if (typeof value !== "string" || !value.trim()) return "\u2014";

  const candidate = value.trim();
  const codeMatch = candidate.match(/(?:^|[|/])\s*(\d{5,})\s*$/);
  if (codeMatch) return codeMatch[1] === "14189004" ? "Measles" : "\u2014";
  if (/^\d+$/.test(candidate) || /(?:snomed|^https?:\/\/)/i.test(candidate)) return "\u2014";
  if (candidate.toLowerCase() === "measles") return "Measles";
  return candidate;
}

function normalizeStatus(value) {
  return String(value || "UNKNOWN")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "_");
}

function formatStatus(value) {
  const status = normalizeStatus(value);

  const labels = {
    SUBMITTED: "Submitted",
    AWAITING_ACKNOWLEDGEMENT: "Awaiting Acknowledgement",
    AWAITING_ACK: "Awaiting Acknowledgement",
    ACKNOWLEDGED: "Acknowledged",
    FAILED: "Failed",
    RETRY_REQUIRED: "Retry Required",
  };

  return labels[status] || String(value || "Unknown");
}

function statusClass(value) {
  const status = normalizeStatus(value);

  if (status === "ACKNOWLEDGED") return "success";
  if (
    status === "FAILED" ||
    status === "RETRY_REQUIRED"
  ) {
    return "danger";
  }

  if (
    status === "SUBMITTED" ||
    status === "AWAITING_ACKNOWLEDGEMENT" ||
    status === "AWAITING_ACK"
  ) {
    return "info";
  }

  return "neutral";
}

function normalizeSubmission(item) {
  const payload =
    item && typeof item === "object"
      ? item
      : {};

  const patient =
    payload.patient && typeof payload.patient === "object"
      ? payload.patient
      : {};

  const caseData =
    payload.case && typeof payload.case === "object"
      ? payload.case
      : {};

  const patientId =
    payload.patient_id ||
    payload.patientId ||
    patient.patient_id ||
    caseData.patient_id ||
    caseData.patient?.patient_id ||
    null;

  return {
    submissionId: textValue(
      payload.submission_id,
      payload.submissionId,
      payload.id,
    ),

    caseId: textValue(
      payload.case_id,
      payload.caseId,
      caseData.case_id,
      caseData.caseId,
    ),

    patient: textValue(
      payload.patient_name,
      payload.patientName,
      patient.name,
      [patient.first_name, patient.last_name]
        .filter(Boolean)
        .join(" "),
    ),

    patientId,

    condition: conditionLabel(
      payload.condition_name,
      payload.disease_name,
      payload.condition,
      payload.disease,
      caseData.condition_name,
      caseData.disease_name,
      caseData.condition,
      caseData.disease,
    ),

    mode: textValue(
      payload.submission_mode,
      payload.submissionMode,
      caseData.submission_mode,
      caseData.submissionMode,
    ),

    destination: textValue(
      payload.destination,
      payload.destination_name,
      payload.destinationName,
    ),

    createdAt: textValue(
      payload.created_at,
      payload.createdAt,
    ),

    status: payload.status || "UNKNOWN",

    raw: payload,
  };
}

function deduplicatePatientConditions(items) {
  const newestFirst = [...items].sort((left, right) => {
    const leftTime = Date.parse(left.createdAt);
    const rightTime = Date.parse(right.createdAt);
    if (!Number.isFinite(leftTime)) return Number.isFinite(rightTime) ? 1 : 0;
    if (!Number.isFinite(rightTime)) return -1;
    return rightTime - leftTime;
  });
  const seen = new Set();

  return newestFirst.filter((item) => {
    const patientIdentity = item.patientId || item.patient;
    const normalizedCondition = String(item.condition || "").trim().toLowerCase();
    if (!patientIdentity || patientIdentity === "—" || !normalizedCondition || normalizedCondition === "—") {
      return true;
    }

    const key = `${String(patientIdentity).trim().toLowerCase()}::${normalizedCondition}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function formatDate(value) {
  if (!value || value === "—") return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function AdminSubmissions() {
  const [submissions, setSubmissions] = useState([]);
  const [submissionRecords, setSubmissionRecords] = useState([]);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [modeFilter, setModeFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadSubmissions = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      const response = await getAdminSubmissions();

      const records = normalizeItems(response).map(normalizeSubmission);
      setSubmissionRecords(records);
      const items = deduplicatePatientConditions(records);

      setSubmissions(items);
    } catch (err) {
      setError(
        err?.message ||
          "Unable to load submissions.",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadSubmissions();
  }, [loadSubmissions]);

  const filteredSubmissions = useMemo(() => {
    const query = search.trim().toLowerCase();

    return submissions.filter((submission) => {
      const status = normalizeStatus(submission.status);
      const mode = normalizeStatus(submission.mode);

      const matchesStatus =
        statusFilter === "ALL" ||
        status === statusFilter;

      const matchesMode =
        modeFilter === "ALL" ||
        mode === modeFilter;

      const matchesSearch =
        !query ||
        [
          submission.submissionId,
          submission.caseId,
          submission.patient,
          submission.condition,
          submission.destination,
        ]
          .join(" ")
          .toLowerCase()
          .includes(query);

      return (
        matchesStatus &&
        matchesMode &&
        matchesSearch
      );
    });
  }, [
    submissions,
    statusFilter,
    modeFilter,
    search,
  ]);

  const metrics = useMemo(() => {
    return {
      total: submissionRecords.length,

      submitted: submissionRecords.filter(
        (item) =>
          normalizeStatus(item.status) === "SUBMITTED",
      ).length,

      awaiting: submissionRecords.filter((item) => {
        const status = normalizeStatus(item.status);

        return (
          status === "AWAITING_ACKNOWLEDGEMENT" ||
          status === "AWAITING_ACK"
        );
      }).length,

      acknowledged: submissionRecords.filter(
        (item) =>
          normalizeStatus(item.status) === "ACKNOWLEDGED",
      ).length,

      failedRetryRequired: submissionRecords.filter((item) =>
        ["FAILED", "ERROR", "REJECTED", "RETRY_REQUIRED"].includes(
          normalizeStatus(item.status),
        ),
      ).length,
    };
  }, [submissionRecords]);

  return (
    <main className="admin-submissions-page">
      <div className="admin-submissions-header">
        <div>
          <div className="admin-page-eyebrow">
            ADMINISTRATOR / SUBMISSIONS
          </div>

          <h1>Submissions</h1>

          <p>
            Monitor dispatched public health submissions
            and acknowledgement status.
          </p>
        </div>

        <button
          type="button"
          className="admin-refresh-button"
          onClick={() => loadSubmissions(true)}
          disabled={loading || refreshing}
        >
          <RefreshCw
            size={15}
            className={
              refreshing
                ? "admin-spin"
                : ""
            }
          />

          {refreshing ? "Refreshing" : "Refresh"}
        </button>
      </div>

      <section className="submission-metrics">
        <div className="submission-metric-card">
          <span>Total Submissions</span>
          <strong>{metrics.total}</strong>
        </div>

        <div className="submission-metric-card">
          <span>Submitted</span>
          <strong>{metrics.submitted}</strong>
        </div>

        <div className="submission-metric-card">
          <span>Awaiting Acknowledgement</span>
          <strong>{metrics.awaiting}</strong>
        </div>

        <div className="submission-metric-card">
          <span>Acknowledged</span>
          <strong>{metrics.acknowledged}</strong>
        </div>

        <div className="submission-metric-card">
          <span>Failed / Retry Required</span>
          <strong>{metrics.failedRetryRequired}</strong>
        </div>
      </section>

      <section className="submission-panel">
        <div className="submission-toolbar">
          <div className="submission-search">
            <Search size={16} />

            <input
              type="text"
              placeholder="Search submissions..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />
          </div>

          <select
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value)
            }
          >
            {STATUS_OPTIONS.map((status) => (
              <option
                key={status}
                value={status}
              >
                {status === "ALL"
                  ? "All Statuses"
                  : formatStatus(status)}
              </option>
            ))}
          </select>

          <select
            value={modeFilter}
            onChange={(event) =>
              setModeFilter(event.target.value)
            }
          >
            {MODE_OPTIONS.map((mode) => (
              <option
                key={mode}
                value={mode}
              >
                {mode === "ALL"
                  ? "All Modes"
                  : mode}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div className="submission-error">
            {error}
          </div>
        )}

        {loading ? (
          <div className="submission-state">
            Loading submissions...
          </div>
        ) : filteredSubmissions.length === 0 ? (
          <div className="submission-empty">
            <strong>No submissions yet</strong>

            <span>
              Authorized cases will appear here after
              they are dispatched.
            </span>
          </div>
        ) : (
          <div className="submission-table-wrapper">
            <table className="submission-table">
              <thead>
                <tr>
                  <th>Submission ID</th>
                  <th>Case ID</th>
                  <th>Patient</th>
                  <th>Condition</th>
                  <th>Mode</th>
                  <th>Destination</th>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {filteredSubmissions.map(
                  (submission) => (
                    <tr
                      key={
                        submission.submissionId
                      }
                    >
                      <td className="mono">
                        {submission.submissionId}
                      </td>

                      <td className="mono">
                        {submission.caseId}
                      </td>

                      <td>
                        <strong>
                          {submission.patient}
                        </strong>
                      </td>

                      <td>
                        {submission.condition}
                      </td>

                      <td>
                        <span className="mode-badge">
                          {submission.mode}
                        </span>
                      </td>

                      <td>
                        {submission.destination}
                      </td>

                      <td>
                        {formatDate(
                          submission.createdAt,
                        )}
                      </td>

                      <td>
                        <span
                          className={`status-pill ${statusClass(
                            submission.status,
                          )}`}
                        >
                          {formatStatus(
                            submission.status,
                          )}
                        </span>
                      </td>

                      <td>
                        <button
                          type="button"
                          className="view-submission-button"
                          disabled
                          title="Submission detail page will be added next"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
