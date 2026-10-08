import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Clock3, FileCheck2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import {
  dispatchCase,
  getAdminQueueCase,
} from "../../services/adminService.js";
import { ensureSubmissionFollowUp } from "../../api/followups.js";
import "../../styles/AdminImmediateReview.css";

function valueOrDash(value) {
  if (
    value === undefined ||
    value === null ||
    String(value).trim() === ""
  ) {
    return "—";
  }

  return String(value);
}

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function getObject(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function getEvidence(value) {
  return value && typeof value === "object" ? value : {};
}

function formatEvidenceValue(value) {
  if (value === undefined || value === null || value === "") return "\u2014";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(formatEvidenceValue).join(", ");
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${formatLabel(key)}: ${formatEvidenceValue(item)}`).join(" · ");
  return String(value);
}

function formatLabel(value) {
  return String(value)
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function statusTone(value) {
  const normalized = String(value || "").toUpperCase();
  if (["REPORT", "VALID", "APPROVE", "ATTESTED", "LAB_POSITIVE"].includes(normalized)) return "positive";
  if (["INVALID", "REJECT", "REJECTED", "FAILED", "HOLD"].includes(normalized)) return "negative";
  if (["NEEDS_REVIEW", "PENDING", "REQUEST_INFORMATION"].includes(normalized)) return "warning";
  return "neutral";
}

function EvidenceValue({ value }) {
  if (Array.isArray(value)) {
    if (!value.length) return <span>—</span>;
    return (
      <details className="admin-immediate-nested">
        <summary>{value.length} {value.length === 1 ? "entry" : "entries"}</summary>
        <div className="admin-immediate-nested-content">
          {value.map((entry, index) => (
            <div className="admin-immediate-nested-item" key={index}>
              <strong>Entry {index + 1}</strong>
              <EvidenceValue value={entry} />
            </div>
          ))}
        </div>
      </details>
    );
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) return <span>—</span>;
    return (
      <details className="admin-immediate-nested">
        <summary>{entries.length} {entries.length === 1 ? "field" : "fields"}</summary>
        <div className="admin-immediate-nested-content">
          {entries.map(([key, nested]) => (
            <div className="admin-immediate-nested-item" key={key}>
              <strong>{formatLabel(key)}</strong>
              <EvidenceValue value={nested} />
            </div>
          ))}
        </div>
      </details>
    );
  }
  return <span>{formatEvidenceValue(value)}</span>;
}

function EvidenceRows({ data, emptyMessage = "\u2014" }) {
  const rows = Array.isArray(data)
    ? data.map((entry, index) => [String(index + 1), entry])
    : Object.entries(getObject(data));

  if (!rows.length) return <span>{emptyMessage}</span>;

  return (
    <div className="admin-immediate-evidence-list">
      {rows.map(([key, value], index) => (
        <div key={`${key}-${index}`}>
          <strong>{Array.isArray(data) ? `Entry ${key}` : formatLabel(key)}</strong>
          <EvidenceValue value={value} />
        </div>
      ))}
    </div>
  );
}

function normalizeCase(response) {
  const source = getObject(response);
  const caseData = getObject(source.case || source.case_data || source.data);
  const patient = getObject(
    source.patient || caseData.patient,
  );

  const clinicalEvidence = getEvidence(source.clinical_evidence ?? caseData.clinical_evidence);
  const laboratoryEvidence = getEvidence(source.laboratory_evidence ?? caseData.laboratory_evidence);
  const aiEvidence = getEvidence(source.ai_evidence ?? caseData.ai_evidence);
  const reportFields = getEvidence(source.report_fields ?? caseData.report_fields);
  const condition = valueOrDash(
    source.disease || source.condition || caseData.disease || caseData.condition,
  );
  const patientName = valueOrDash(
    source.patient_name || source.patientName || patient.name ||
      [patient.first_name, patient.last_name].filter(Boolean).join(" "),
  );

  return {
    caseId: valueOrDash(
      source.case_id ||
        source.caseId ||
        caseData.case_id ||
        caseData.caseId,
    ),

    patientId: valueOrDash(
      source.patient_id ||
        source.patientId ||
        patient.patient_id ||
        patient.patientId,
    ),

    patientName,

    dob: valueOrDash(
      source.date_of_birth ||
        source.dateOfBirth ||
        patient.date_of_birth ||
        patient.dateOfBirth,
    ),

    sex: valueOrDash(
      source.sex || patient.sex,
    ),

    condition,

    jurisdiction: valueOrDash(
      source.jurisdiction ||
        caseData.jurisdiction,
    ),

    deadline:
      source.deadline ||
      caseData.deadline ||
      null,

    severity: valueOrDash(
      source.severity ??
        caseData.severity,
    ),

    submissionMode: valueOrDash(
      source.submission_mode ||
        source.submissionMode ||
        caseData.submission_mode ||
        caseData.submissionMode,
    ),

    caseStatus: valueOrDash(
      source.case_status ??
        caseData.status,
    ),

    reportabilityDecision: valueOrDash(
      source.reportability ??
        source.reportability_decision ??
        caseData.reportability_decision,
    ),

    evidenceStatus: valueOrDash(
      source.review_status ??
        source.reportability_evidence_status ??
        caseData.reportability_evidence_status,
    ),

    ruleId: valueOrDash(
      source.rule_id ??
        caseData.rule_id,
    ),

    clinicalEvidence,
    laboratoryEvidence,
    aiEvidence,
    reportFields,
    missingInformation: Array.isArray(source.missing_information)
      ? source.missing_information
      : [],
    validation: getObject(source.validation),
    review: getObject(source.review),
    attestation: getObject(source.attestation),

    raw: source,
  };
}

export default function AdminImmediateReview() {
  const navigate = useNavigate();
  const { caseId } = useParams();

  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadCase = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await getAdminQueueCase(caseId);

      setCaseData(normalizeCase(response));
    } catch (err) {
      setError(
        err?.message ||
          "Unable to load the case.",
      );
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  const patientInitials = useMemo(() => {
    if (!caseData?.patientName || caseData.patientName === "—") {
      return "PT";
    }

    return caseData.patientName
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((name) => name[0])
      .join("")
      .toUpperCase();
  }, [caseData]);

  async function handleAuthorizeAndSubmit() {
    try {
      setSubmitting(true);
      setError("");

      const dispatchResponse = await dispatchCase(caseId);
      const submissionResponse = dispatchResponse?.submission
        || dispatchResponse?.data?.submission
        || dispatchResponse?.data
        || dispatchResponse;
      const submissionStatus = String(submissionResponse?.status || "").toUpperCase();
      if (submissionStatus !== "SUBMITTED") {
        throw new Error(submissionResponse?.errors?.join("; ") || "The case was not successfully submitted.");
      }

      const submissionId = submissionResponse?.submission_id
        || submissionResponse?.submissionId
        || dispatchResponse?.submission_id
        || dispatchResponse?.data?.submission_id;
      if (!submissionId) {
        throw new Error("Submission succeeded, but the dispatch response did not include a submission ID.");
      }

      let followupError = "";
      try {
        await ensureSubmissionFollowUp(caseId, submissionId);
      } catch (followupRequestError) {
        followupError = followupRequestError?.message || "PHA follow-up tracking could not be loaded or created.";
      }

      navigate(`/admin/submission-journey/${encodeURIComponent(submissionId)}`, {
        state: { dispatchResponse, followupError },
      });
    } catch (err) {
      setError(
        err?.message ||
          "Unable to authorize and submit the case.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="admin-immediate-review-page">
        <div className="admin-immediate-state">
          Loading immediate review...
        </div>
      </main>
    );
  }

  if (error && !caseData) {
    return (
      <main className="admin-immediate-review-page">
        <button
          type="button"
          className="admin-immediate-back"
          onClick={() => navigate("/admin/queue")}
        >
          <ArrowLeft size={16} />
          Back to Reporting Queue
        </button>

        <div className="admin-immediate-error">
          {error}
        </div>
      </main>
    );
  }

  return (
    <main className="admin-immediate-review-page">
      <div className="admin-immediate-topbar">
        <button
          type="button"
          className="admin-immediate-back"
          onClick={() => navigate("/admin/queue")}
        >
          <ArrowLeft size={16} />
          Reporting Queue
        </button>

        <div className="admin-immediate-breadcrumb">
          Reporting Queue
          <span>›</span>
          Immediate Review
        </div>
      </div>

      <header className="admin-immediate-header">
        <div>
          <div className="admin-immediate-eyebrow">
            ADMINISTRATOR / IMMEDIATE REPORT
          </div>

          <h1>Immediate Review</h1>

          <p>
            Review the case before authorizing immediate
            submission to the public health authority.
          </p>
        </div>

        <div className="admin-immediate-case-id">
          <span>CASE ID</span>
          <strong>{caseData.caseId}</strong>
        </div>
      </header>

      {error && (
        <div className="admin-immediate-alert error">
          {error}
        </div>
      )}

      <section className="admin-immediate-summary">
        <div className="admin-immediate-patient">
          <div className="admin-immediate-avatar">
            {patientInitials}
          </div>

          <div>
            <span className="admin-immediate-label">
              PATIENT
            </span>

            <strong>
              {caseData.patientName}
            </strong>

          </div>
        </div>

        <div className="admin-immediate-summary-item">
          <span>Condition</span>
          <strong>{caseData.condition}</strong>
        </div>

        <div className="admin-immediate-summary-item">
          <span>Jurisdiction</span>
          <strong>{caseData.jurisdiction}</strong>
        </div>

        <div className="admin-immediate-summary-item">
          <span>Severity</span>
          <strong className="severity-urgent">
            {caseData.severity}
          </strong>
        </div>

        <div className="admin-immediate-summary-item">
          <span>Deadline</span>
          <strong>
            <Clock3 size={14} />
            {formatDate(caseData.deadline)}
          </strong>
        </div>
      </section>

      <div className="admin-immediate-grid">
        <div className="admin-immediate-main">
          {[
            {
              number: "01",
              title: "Patient & Case Information",
              subtitle: "Core patient and reporting information.",
            },
            {
              number: "02",
              title: "Clinical Information",
              subtitle: "Evidence supporting the reportable case.",
            },
            {
              number: "03",
              title: "Reportability & Validation",
              subtitle: "Decision and validation evidence generated by SIGNAL.",
            },
            {
              number: "04",
              title: "AI Evidence",
              subtitle: "Decision evidence stored with this case.",
            },
            {
              number: "05",
              title: "Reporting Data",
              subtitle: "Available report fields from the case record.",
            },
            {
              number: "06",
              title: "Missing Information",
              subtitle: caseData.missingInformation.length
                ? "Additional information is required."
                : "No missing information identified.",
              warning: caseData.missingInformation.length > 0,
            },
          ].map(({ number, title, subtitle, warning }) => (
            <section
              className="admin-immediate-section-row"
              key={number}
              aria-label={title}
            >
              <span className={`admin-immediate-section-check${warning ? " is-warning" : ""}`} aria-hidden="true">
                {warning ? "!" : "✓"}
              </span>
              <span className="admin-immediate-section-number">{number}</span>
              <div className="admin-immediate-section-copy">
                <h2>{title}</h2>
                <p>{subtitle}</p>
              </div>
            </section>
          ))}
        </div>

        <aside className="admin-immediate-sidebar">
          <div className="admin-immediate-action-card">
            <div className="admin-immediate-action-icon">
              <FileCheck2 size={21} />
            </div>

            <span className="admin-immediate-label">
              AUTHORIZATION
            </span>

            <h2>
              Authorize Immediate Submission
            </h2>

            <p>
              This action authorizes the case for immediate
              electronic submission to the configured public
              health destination.
            </p>

            <button
              type="button"
              className="authorize-submit-button"
              onClick={handleAuthorizeAndSubmit}
              disabled={submitting}
            >
              <CheckCircle2 size={17} />

              {submitting
                ? "Submitting..."
                : "AUTHORIZE & SUBMIT IMMEDIATELY"}
            </button>

            <button
              type="button"
              className="cancel-review-button"
              onClick={() =>
                navigate("/admin/queue")
              }
              disabled={submitting}
            >
              Return to Queue
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
