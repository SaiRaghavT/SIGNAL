
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ChevronDown,
  CheckCircle2,
  Clock3,
  FileText,
  RefreshCw,
  Send,
} from "lucide-react";

import {
  acknowledgePhaReceipt,
  getReportDetails,
  submitPhaDecision,
  getPhaDecisionHistory,
  getPhaResourceUrl,
} from "../services/phaApi";
import { cleanPatientName } from "../utils/patientNames.js";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString();
}

function formatDecision(value) {
  if (!value) return "—";

  return value
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const REPORTING_FIELD_LABELS = new Map([
  ["reportinginvestigatingagency", "Reporting Investigating Agency"],
  ["investigatingagency", "Reporting Investigating Agency"],
  ["reportingearliestdatereported", "Reporting Earliest Date Reported"],
  ["earliestdatereported", "Reporting Earliest Date Reported"],
  ["reportinginvestigationstartdate", "Reporting Investigation Start Date"],
  ["investigationstartdate", "Reporting Investigation Start Date"],
  ["reportinginvestigatingagencyemail", "Reporting Investigating Agency Email"],
  ["investigatingagencyemail", "Reporting Investigating Agency Email"],
  ["reportinginvestigatingagencyphone", "Reporting Investigating Agency Phone"],
  ["investigatingagencyphone", "Reporting Investigating Agency Phone"],
]);

function getReportingFieldLabel(key) {
  const normalizedKey = String(key ?? "")
    .replace(/([a-z0-9])([A-Z])/g, "$1$2")
    .replace(/[^a-z0-9]/gi, "")
    .toLowerCase();

  return REPORTING_FIELD_LABELS.get(normalizedKey);
}

function getValue(object, ...keys) {
  if (!object || typeof object !== "object") return undefined;

  for (const key of keys) {
    const value = object[key];

    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      return value;
    }
  }

  return undefined;
}

function displayValue(value) {
  if (value === undefined || value === null || value === "") {
    return "—";
  }

  if (Array.isArray(value)) {
    return value.map(displayValue).join(", ");
  }

  if (typeof value === "object") {
    const display = getValue(value, "display", "name", "text", "label");
    if (display !== undefined) return displayValue(display);

    if (Array.isArray(value.coding)) {
      const codingLabels = value.coding
        .map(displayValue)
        .filter((label) => label !== "—");
      if (codingLabels.length > 0) return codingLabels.join(", ");
    }

    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function Detail({ label, value }) {
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <span className="detail-value">
        {displayValue(value)}
      </span>
    </div>
  );
}

function SectionCard({ title, icon: Icon, children, showCheck = false, collapsible = false }) {
  const heading = (
    <>
      {Icon && <Icon size={18} />}
      <h2>{title}</h2>
      {showCheck && (
        <CheckCircle2
          className="review-section-check"
          size={21}
          aria-label="Section complete"
        />
      )}
      {collapsible && <ChevronDown className="review-card-chevron" size={18} aria-hidden="true" />}
    </>
  );

  if (collapsible) {
    return (
      <details className="review-card review-card-dropdown">
        <summary className="review-card-heading">{heading}</summary>
        {children}
      </details>
    );
  }

  return (
    <section className="review-card">
      <div className="review-card-heading">{heading}</div>

      {children}
    </section>
  );
}

export default function ReportReview() {
  const { submissionId } = useParams();

  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [reviewer, setReviewer] = useState("");
  const [selectedDecision, setSelectedDecision] =
    useState("ACCEPTED");
  const [reason, setReason] = useState("");
  const [requestedInformation, setRequestedInformation] =
    useState("");

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const reportResult = await getReportDetails(submissionId);
      setReport(reportResult);

      try {
        const historyResult =
          await getPhaDecisionHistory(submissionId);

        // The API returns an object containing a decisions array.
        // Also support a direct array response.
        const decisions = Array.isArray(historyResult)
          ? historyResult
          : Array.isArray(historyResult?.decisions)
            ? historyResult.decisions
            : [];

        setHistory(decisions);
      } catch (historyError) {
        console.error(
          "Unable to load PHA decision history:",
          historyError
        );
        setHistory([]);
      }
    } catch (loadError) {
      setError(
        loadError.message || "Unable to load report details."
      );
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [submissionId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!reviewer.trim()) {
      setError("Enter the reviewer's name.");
      return;
    }

    if (
      selectedDecision === "REJECTED" &&
      !reason.trim()
    ) {
      setError("Provide a reason for rejecting this report.");
      return;
    }

    if (
      selectedDecision === "INFORMATION_REQUESTED" &&
      !requestedInformation.trim()
    ) {
      setError(
        "Specify the additional information required."
      );
      return;
    }

    const confirmed = window.confirm(
      `Submit the PHA decision: ${formatDecision(
        selectedDecision
      )}?`
    );

    if (!confirmed) return;

    setSaving(true);

    try {
      await submitPhaDecision(submissionId, {
        decision: selectedDecision,
        reviewer: reviewer.trim(),
        reason: reason.trim() || null,
        requested_information:
          requestedInformation.trim() || null,
      });

      setSuccess(
        "PHA decision recorded successfully. The Admin Submission Journey will show the review outcome separately from receipt acknowledgement."
      );

      setReason("");
      setRequestedInformation("");

      await loadReport();
    } catch (submitError) {
      setError(
        submitError.message || "Unable to save the decision."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAcknowledgeReceipt = async () => {
    setError("");
    setSuccess("");

    if (report?.status === "ACKNOWLEDGED") return;

    const confirmed = window.confirm(
      "Acknowledge receipt of this report and update its status in SIGNAL?"
    );
    if (!confirmed) return;

    setAcknowledging(true);
    try {
      await acknowledgePhaReceipt(submissionId);
      setSuccess("Receipt acknowledged. SIGNAL will update the submission journey.");
      await loadReport();
    } catch (acknowledgementError) {
      setError(
        acknowledgementError.message || "Unable to acknowledge report receipt."
      );
    } finally {
      setAcknowledging(false);
    }
  };

  if (loading) {
    return (
      <main className="pha-page review-page">
        <div className="review-muted">
          <RefreshCw className="spin" size={18} />
          Loading report details...
        </div>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="pha-page review-page">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link to="/reports">Public Health</Link><span aria-hidden="true">/</span>
          <Link to="/reports">Incoming Reports</Link><span aria-hidden="true">/</span>
          <strong>Reporting Review</strong>
        </nav>
        <Link to="/reports" className="back-link">
          <ArrowLeft size={16} />
          Back to incoming reports
        </Link>

        <div className="review-error">
          {error || "Report not found."}
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={loadReport}
        >
          Try again
        </button>
      </main>
    );
  }

  const patient =
    report.patient ||
    report.patient_data ||
    report.payload?.patient ||
    {};

  const payload = report.ecr_payload || report.payload || {};

  const latestDecision =
    report.latest_pha_decision ||
    history[0] ||
    null;

  const patientName =
    cleanPatientName(report.patient_name) ||
    getValue(patient, "name", "patient_name", "patientName", "full_name", "display_name") ||
    [
      getValue(patient, "first_name", "firstName"),
      getValue(patient, "last_name", "lastName"),
    ]
      .filter(Boolean)
      .join(" ");
  const displayPatientName = cleanPatientName(patientName) ||
    "Unknown patient";

  const patientId =
    getValue(
      patient,
      "patient_id",
      "patientId",
      "source_patient_id",
      "sourcePatientId"
    ) ||
    report.patient_id ||
    report.case_id ||
    "—";

  const reportForm = payload.report_form || report.report_form || {};
  const reportFields = payload.report_fields || {};
  const visibleReportFields = Object.entries(reportFields)
    .map(([key, value]) => ({ key, value, label: getReportingFieldLabel(key) }))
    .filter((field) => field.label);

  const address =
    patient.address ||
    patient.patient_address ||
    payload.address ||
    null;

  return (
    <main className="pha-page review-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/reports">Public Health</Link><span aria-hidden="true">/</span>
        <Link to="/reports">Incoming Reports</Link><span aria-hidden="true">/</span>
        <strong>Reporting Review</strong>
      </nav>
      <Link to="/reports" className="back-link">
          <ArrowLeft size={16} />
          Back to Incoming Reports
      </Link>

      <header className="review-page-header">
        <div>
          <h1>Reporting Review</h1>
          <p>
            Review submitted case information and record the
            public health agency's decision.
          </p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={loadReport}
          disabled={loading}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </header>

      <section className="submission-summary">
        <div>
          <span className="detail-label">Patient</span>
          <h2>{displayPatientName}</h2>
          <span className="review-muted">
            Patient ID: {displayValue(patientId)}
          </span>
        </div>

        <div>
          <span className="detail-label">Submission ID</span>
          <strong>{report.submission_id || submissionId}</strong>
        </div>

        <div>
          <span className="detail-label">SIGNAL Status</span>
          <strong>
            {report.submission_status ||
              report.status ||
              "—"}
          </strong>
        </div>
      </section>

      {error && (
        <div className="review-error" role="alert">
          {error}
        </div>
      )}

      {success && (
        <div className="decision-success" role="status">
          <CheckCircle2 size={18} />
          <span>{success}</span>
        </div>
      )}

      <div className="review-content-grid">
        <div className="review-main-column">
          <SectionCard title="Patient Information" icon={FileText}>
            <div className="detail-grid">
              <Detail label="Patient name" value={displayPatientName} />

              <Detail
                label="Patient ID"
                value={patientId}
              />

              <Detail
                label="Date of birth"
                value={getValue(
                  patient,
                  "date_of_birth",
                  "dateOfBirth",
                  "birth_date",
                  "birthDate"
                )}
              />

              <Detail
                label="Gender"
                value={getValue(
                  patient,
                  "gender",
                  "sex"
                )}
              />

            </div>

            {address && (
              <div className="detail-stack">
                <Detail
                  label="Address"
                  value={address}
                />
              </div>
            )}
          </SectionCard>

          <SectionCard title="Clinical Information" icon={FileText} showCheck />

          <SectionCard title="Laboratory Information" icon={FileText} showCheck />

          <SectionCard title="Reporting Form PDF" icon={FileText}>
            {visibleReportFields.length > 0 ? (
              <div className="detail-grid">
                {visibleReportFields.map(({ key, value, label }) => (
                  <Detail key={key} label={label} value={value} />
                ))}
              </div>
            ) : (
              <p className="review-muted">The five selected reporting fields are not available for this submission.</p>
            )}

            {reportForm.document_url && (
              <a
                className="primary-button report-pdf-button"
                href={getPhaResourceUrl(reportForm.document_url)}
                target="_blank"
                rel="noreferrer"
              >
                <FileText size={16} />
                Open submitted form PDF
              </a>
            )}
            {!reportForm.document_url && (
              <p className="review-muted">No reporting form PDF was included with this submission.</p>
            )}
          </SectionCard>

        </div>

        <aside className="review-side-column">
          <SectionCard
            title="Latest PHA Decision"
            icon={CheckCircle2}
            collapsible
          >
            <div className="detail-grid latest-decision-grid">
              {latestDecision ? (
                <>
                <Detail
                  label="Decision"
                  value={formatDecision(
                    latestDecision.decision
                  )}
                />

                <Detail
                  label="Reviewer"
                  value={latestDecision.reviewer}
                />

                <Detail
                  label="Decision time"
                  value={formatDate(
                    latestDecision.created_at
                  )}
                />

                <Detail
                  label="Reason"
                  value={latestDecision.reason}
                />

                <Detail
                  label="Information requested"
                  value={
                    latestDecision.requested_information
                  }
                />
                </>
              ) : (
                <p className="review-muted">
                  No PHA decision has been recorded yet.
                </p>
              )}
              <Detail
                label="SIGNAL submission status"
                value={
                  report.submission_status ||
                  report.status ||
                  "—"
                }
              />
            </div>
          </SectionCard>

          <SectionCard title="Acknowledge Receipt" icon={CheckCircle2}>
            {report.acknowledgement?.status === "ACKNOWLEDGED" ? (
              <div className="detail-stack">
                <Detail label="Receipt status" value="Acknowledged" />
                <Detail
                  label="Acknowledgement ID"
                  value={report.acknowledgement.acknowledgement_id}
                />
                <Detail
                  label="Received at"
                  value={formatDate(report.acknowledgement.received_at)}
                />
                <p className="review-muted">Receipt acknowledgement confirms delivery only. Clinical acceptance is recorded separately below.</p>
              </div>
            ) : (
              <>
                <p className="review-muted">
                  Confirm receipt of this report. Receipt acknowledgement is separate from clinical acceptance and updates the SIGNAL submission status.
                </p>
                <button
                  type="button"
                  className="primary-button"
                  onClick={handleAcknowledgeReceipt}
                  disabled={acknowledging || report.status !== "SUBMITTED"}
                >
                  {acknowledging ? (
                    <>
                      <RefreshCw size={16} className="spin" />
                      Recording acknowledgement...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} />
                      Acknowledge Receipt
                    </>
                  )}
                </button>
              </>
            )}
          </SectionCard>

          <SectionCard
            title="Record PHA Decision"
            icon={Send}
          >
            <form
              className="pha-decision-form"
              onSubmit={handleSubmit}
            >
              <label htmlFor="reviewer">
                Reviewer name *
              </label>

              <input
                id="reviewer"
                type="text"
                value={reviewer}
                onChange={(event) =>
                  setReviewer(event.target.value)
                }
                placeholder="Enter reviewer name"
                required
              />

              <label htmlFor="decision">
                Decision *
              </label>

              <select
                id="decision"
                value={selectedDecision}
                onChange={(event) =>
                  setSelectedDecision(event.target.value)
                }
                required
              >
                <option value="ACCEPTED">
                  Accept report
                </option>

                <option value="REJECTED">
                  Reject report
                </option>

                <option value="INFORMATION_REQUESTED">
                  Request more information
                </option>
              </select>

              {selectedDecision === "REJECTED" && (
                <>
                  <label htmlFor="reason">
                    Rejection reason *
                  </label>

                  <textarea
                    id="reason"
                    value={reason}
                    onChange={(event) =>
                      setReason(event.target.value)
                    }
                    placeholder="Explain why the report is rejected"
                    rows={3}
                    required
                  />
                </>
              )}

              {selectedDecision ===
                "INFORMATION_REQUESTED" && (
                <>
                  <label htmlFor="requestedInformation">
                    Additional information required *
                  </label>

                  <textarea
                    id="requestedInformation"
                    value={requestedInformation}
                    onChange={(event) =>
                      setRequestedInformation(
                        event.target.value
                      )
                    }
                    placeholder="Describe the missing information"
                    rows={3}
                    required
                  />
                </>
              )}

              <button
                type="submit"
                className="primary-button"
                disabled={saving}
              >
                {saving ? (
                  <>
                    <RefreshCw
                      size={16}
                      className="spin"
                    />
                    Saving...
                  </>
                ) : (
                  <>
                    <Send size={16} />
                    Submit Decision
                  </>
                )}
              </button>

              <p className="review-muted">
                The review decision is tracked separately from receipt
                acknowledgement and appears in the Admin Submission Journey.
              </p>
            </form>
          </SectionCard>

          <SectionCard
            title="Decision History"
            icon={Clock3}
            collapsible
          >
            {history.length > 0 ? (
              <div className="decision-history-list">
                {history.map((decision) => (
                  <article
                    className="decision-history-item"
                    key={decision.decision_id}
                  >
                    <div>
                      <strong>
                        {formatDecision(decision.decision)}
                      </strong>

                      <span className="review-muted">
                        {formatDate(decision.created_at)}
                      </span>
                    </div>

                    <Detail
                      label="Reviewer"
                      value={decision.reviewer}
                    />

                    {decision.reason && (
                      <Detail
                        label="Reason"
                        value={decision.reason}
                      />
                    )}

                    {decision.requested_information && (
                      <Detail
                        label="Information requested"
                        value={
                          decision.requested_information
                        }
                      />
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="review-muted">
                No decision history available.
              </p>
            )}

            <p className="review-muted">
              {history.length} decision
              {history.length === 1 ? "" : "s"} recorded
            </p>
          </SectionCard>
        </aside>
      </div>
    </main>
  );
}
