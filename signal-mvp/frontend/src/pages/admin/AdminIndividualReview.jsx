import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Clock3, FileCheck2, UserRound } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import {
  dispatchCase,
  getAdminQueueCase,
} from "../../services/adminService.js";
import { ensureSubmissionFollowUp } from "../../api/followups.js";
import { upsertClinicalInformationRequest } from "../../utils/clinicalInformationRequests.js";
import { demoPatientName } from "../../utils/adminDemoPatientNames.js";
import { cleanPatientName } from "../../utils/patientNames.js";
import "../../styles/AdminIndividualReview.css";

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
      <details className="admin-individual-nested">
        <summary>{value.length} {value.length === 1 ? "entry" : "entries"}</summary>
        <div className="admin-individual-nested-content">
          {value.map((entry, index) => (
            <div className="admin-individual-nested-item" key={index}>
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
      <details className="admin-individual-nested">
        <summary>{entries.length} {entries.length === 1 ? "field" : "fields"}</summary>
        <div className="admin-individual-nested-content">
          {entries.map(([key, nested]) => (
            <div className="admin-individual-nested-item" key={key}>
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
    <div className="admin-individual-evidence-list">
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
  const reportFieldObject = getObject(source.report_fields ?? caseData.report_fields);
  const prefixedFields = (prefix) => Object.fromEntries(
    Object.entries(reportFieldObject)
      .filter(([key]) => key.startsWith(prefix))
      .map(([key, value]) => [key.slice(prefix.length), value]),
  );
  const provider = getObject(
    source.provider ?? caseData.provider ?? reportFieldObject.provider ??
    getObject(source.reporting).provider ?? prefixedFields("provider."),
  );
  const facility = getObject(
    source.facility ?? caseData.facility ?? reportFieldObject.facility ??
    getObject(source.reporting).facility ?? prefixedFields("facility."),
  );
  const missingInformation = Array.isArray(source.missing_information)
    ? source.missing_information
    : [];
  const condition = valueOrDash(
    source.disease || source.condition || caseData.disease || caseData.condition,
  );
  const patientName = valueOrDash(cleanPatientName(
    source.patient_name || source.patientName || patient.name ||
      [patient.first_name, patient.last_name].filter(Boolean).join(" "),
  ));

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

    patientName: patientName === "—" ? demoPatientName(source.case_id || source.caseId || caseData.case_id || caseData.caseId, condition) || patientName : patientName,

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
    provider,
    facility,
    destination: valueOrDash(source.destination ?? source.destination_name ?? caseData.destination ?? caseData.destination_name),
    reviewStatus: valueOrDash(source.review_status ?? caseData.review_status),
    attestationStatus: valueOrDash(source.attestation_status ?? caseData.attestation_status),
    validationState: valueOrDash(
      source.validation_state ?? source.validation_status ??
      (missingInformation.length ? "NEEDS_COMPLETION" : source.queue_status),
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
    missingInformation,
    validationReady: source.validation_valid !== false
      && source.validation?.valid !== false
      && ![source.validation_state, source.validation_status, source.validation?.status]
        .some((status) => ["INVALID", "FAILED", "BLOCKED"].includes(String(status || "").toUpperCase()))
      && missingInformation.length === 0
      && Boolean(source.report_id ?? caseData.report_id),
    reportId: source.report_id ?? caseData.report_id ?? null,

    raw: source,
  };
}

export default function AdminIndividualReview() {
  const navigate = useNavigate();
  const { caseId } = useParams();

  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showInformationRequest, setShowInformationRequest] = useState(false);
  const [informationRequestSent, setInformationRequestSent] = useState(false);

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

  const authorizationReady = Boolean(
    caseData &&
    caseData.missingInformation.length === 0 &&
    caseData.validationReady &&
    String(caseData.reviewStatus).toUpperCase() === "APPROVE" &&
    String(caseData.attestationStatus).toUpperCase() === "ATTESTED"
  );

  function handleSendInformationRequest() {
    if (!caseData?.missingInformation.length) return;
    const message = "Please complete the missing required information for this case and resubmit it for administrative review.";
    try {
      upsertClinicalInformationRequest({
        caseId,
        patientId: caseData.raw?.patient?.patient_id || (caseData.patientId === "—" ? null : caseData.patientId),
        patientName: caseData.patientName === "—" ? null : caseData.patientName,
        missingFields: caseData.missingInformation,
        message,
        requestedAt: new Date().toISOString(),
      });
      setShowInformationRequest(false);
      setInformationRequestSent(true);
      setError("");
    } catch (requestError) {
      setError(requestError?.message || "Unable to send the information request.");
    }
  }

  async function handleAuthorizeAndSubmit() {
    if (!authorizationReady) {
      setError("This case must have valid reporting information, an approved review, and a completed attestation before submission.");
      return;
    }
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
      <main className="admin-individual-review-page">
        <div className="admin-individual-state">
          Loading individual review...
        </div>
      </main>
    );
  }

  if (error && !caseData) {
    return (
      <main className="admin-individual-review-page">
        <button
          type="button"
          className="admin-individual-back"
          onClick={() => navigate("/admin/queue")}
        >
          <ArrowLeft size={16} />
          Back to Reporting Queue
        </button>

        <div className="admin-individual-error">
          {error}
        </div>
      </main>
    );
  }

  return (
    <main className="admin-individual-review-page">
      <div className="admin-individual-topbar">
        <button
          type="button"
          className="admin-individual-back"
          onClick={() => navigate("/admin/queue")}
        >
          <ArrowLeft size={16} />
          Reporting Queue
        </button>

        <div className="admin-individual-breadcrumb">
          Reporting Queue
          <span>›</span>
          Individual Review
        </div>
      </div>

      <header className="admin-individual-header">
        <div>
          <div className="admin-individual-eyebrow">
            ADMINISTRATOR / INDIVIDUAL REPORT
          </div>

          <h1>Individual Review</h1>

          <p>
            Review and authorize this individual case for submission.
          </p>
        </div>

        <div className="admin-individual-case-id">
          <span>CASE ID</span>
          <strong>{caseData.caseId}</strong>
        </div>
      </header>

      {error && (
        <div className="admin-individual-alert error">
          {error}
        </div>
      )}

      <section className="admin-individual-summary">
        <div className="admin-individual-patient">
          <div className="admin-individual-avatar">
            {patientInitials}
          </div>

          <div>
            <span className="admin-individual-label">
              PATIENT
            </span>

            <strong>
              {caseData.patientName}
            </strong>

            <small>
              Patient ID: {caseData.patientId}
            </small>
          </div>
        </div>

        <div className="admin-individual-summary-item">
          <span>Condition</span>
          <strong>{caseData.condition}</strong>
        </div>

        <div className="admin-individual-summary-item">
          <span>Jurisdiction</span>
          <strong>{caseData.jurisdiction}</strong>
        </div>

        <div className="admin-individual-summary-item">
          <span>Severity</span>
          <strong className="severity-urgent">
            {caseData.severity}
          </strong>
        </div>

        <div className="admin-individual-summary-item">
          <span>Deadline</span>
          <strong>
            <Clock3 size={14} />
            {formatDate(caseData.deadline)}
          </strong>
        </div>
      </section>

      <div className="admin-individual-grid">
        <div className="admin-individual-main">
          <section className="admin-individual-card">
            <div className="admin-individual-card-header">
              <div>
                <span className="admin-individual-section-number">
                  01
                </span>
                <div>
                  <h2>Patient & Case Information</h2>
                  <p>
                    Core patient and reporting information.
                  </p>
                </div>
              </div>

              <UserRound size={19} />
            </div>

              <div className="admin-individual-fields">
              <div>
                <span>Patient Name</span>
                <strong>{caseData.patientName}</strong>
              </div>

              <div>
                <span>Date of Birth</span>
                <strong>{caseData.dob}</strong>
              </div>

              <div>
                <span>Sex</span>
                <strong>{caseData.sex}</strong>
              </div>

              <div>
                <span>Condition</span>
                <strong>{caseData.condition}</strong>
              </div>

              <div>
                <span>Jurisdiction</span>
                <strong>{caseData.jurisdiction}</strong>
              </div>

              <div>
                <span>Submission Mode</span>
                <strong>
                  {caseData.submissionMode}
                </strong>
              </div>
              {Object.entries(caseData.provider).map(([key, value]) => (
                <div key={`provider-${key}`}><span>Provider {formatLabel(key)}</span><strong>{formatEvidenceValue(value)}</strong></div>
              ))}
              {Object.entries(caseData.facility).map(([key, value]) => (
                <div key={`facility-${key}`}><span>Facility {formatLabel(key)}</span><strong>{formatEvidenceValue(value)}</strong></div>
              ))}
            </div>
          </section>

          <section className="admin-individual-card">
            <div className="admin-individual-card-header">
              <div>
                <span className="admin-individual-section-number">
                  02
                </span>
                <div>
                  <h2>Clinical Information</h2>
                  <p>
                    Evidence supporting the reportable case.
                  </p>
                </div>
              </div>
            </div>

            <div className="admin-individual-evidence-grid">
              <div className="admin-individual-evidence-box">
                <span>Clinical Evidence</span>
                <EvidenceRows data={caseData.clinicalEvidence} />
              </div>

              <div className="admin-individual-evidence-box">
                <span>Laboratory Evidence</span>
                <EvidenceRows data={caseData.laboratoryEvidence} />
              </div>
            </div>

            <div className="admin-individual-fields">
              {[
                ["Illness Onset Date", caseData.clinicalEvidence.illness_onset_date ?? caseData.clinicalEvidence.onset_date],
                ["Rash Onset Date", caseData.clinicalEvidence.rash_onset_date],
                ["Hospitalized", caseData.clinicalEvidence.hospitalized],
                ["Admission Date", caseData.clinicalEvidence.admission_date],
                ["Discharge Date", caseData.clinicalEvidence.discharge_date],
                ["Diagnosis Date", caseData.clinicalEvidence.diagnosis_date],
              ].map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{formatEvidenceValue(value)}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-individual-card">
            <div className="admin-individual-card-header">
              <div>
                <span className="admin-individual-section-number">
                  03
                </span>
                <div>
                  <h2>Reportability & Validation</h2>
                  <p>
                    Decision and validation evidence generated
                    by SIGNAL.
                  </p>
                </div>
              </div>

              <FileCheck2 size={19} />
            </div>

            <div className="admin-individual-fields admin-individual-decision-fields">
              <div>
                <span>Reportability Decision</span>
                <strong className={`admin-individual-value-${statusTone(caseData.reportabilityDecision)}`}>
                  {caseData.reportabilityDecision}
                </strong>
              </div>

              <div>
                <span>Evidence Status</span>
                <strong className={`admin-individual-value-${statusTone(caseData.evidenceStatus)}`}>
                  {caseData.evidenceStatus}
                </strong>
              </div>

              <div>
                <span>Rule ID</span>
                <strong className="admin-individual-value-rule">{caseData.ruleId}</strong>
              </div>

              <div>
                <span>Case Status</span>
                <strong className={`admin-individual-value-${statusTone(caseData.caseStatus)}`}>
                  {caseData.caseStatus}
                </strong>
              </div>
              <div><span>Review Status</span><strong className={`admin-individual-value-${statusTone(caseData.reviewStatus)}`}>{caseData.reviewStatus}</strong></div>
              <div><span>Attestation Status</span><strong className={`admin-individual-value-${statusTone(caseData.attestationStatus)}`}>{caseData.attestationStatus}</strong></div>
              <div><span>Validation State</span><strong className={`admin-individual-value-${statusTone(caseData.validationState)}`}>{caseData.validationState}</strong></div>
            </div>

            <div className="admin-individual-validation">
              <div className="validation-icon">
                <CheckCircle2 size={17} />
              </div>

              <div>
                <strong>Case status: {caseData.caseStatus}</strong>
                <span>Deadline: {formatDate(caseData.deadline)}</span>
              </div>
            </div>
          </section>

          <section className="admin-individual-card">
            <div className="admin-individual-card-header">
              <div>
                <span className="admin-individual-section-number">04</span>
                <div>
                  <h2>AI Evidence</h2>
                  <p>Decision evidence stored with this case.</p>
                </div>
              </div>
            </div>
            <EvidenceRows
              data={caseData.aiEvidence}
              emptyMessage="No AI evidence available."
            />
          </section>

          <section className="admin-individual-card">
            <div className="admin-individual-card-header">
              <div>
                <span className="admin-individual-section-number">05</span>
                <div>
                  <h2>Reporting Data</h2>
                  <p>Available report fields from the case record.</p>
                </div>
              </div>
            </div>
            <EvidenceRows data={caseData.reportFields} />
          </section>
        </div>

        <aside className="admin-individual-sidebar">
          <section className="admin-individual-card" aria-live="polite">
            <div className="admin-individual-card-header">
              <div>
                <span className="admin-individual-section-number">06</span>
                <div>
                  <h2 className="admin-individual-missing-heading">
                    Missing Information
                    <span className="admin-individual-missing-count">
                      ({caseData.missingInformation.length})
                    </span>
                  </h2>
                </div>
              </div>
            </div>
            {caseData.missingInformation.length ? (
              <div className="admin-individual-alert error">
                <ul>
                  {caseData.missingInformation.map((item, index) => (
                    <li key={`${item}-${index}`}>{formatEvidenceValue(item)}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="admin-individual-alert success">
                No missing information identified
              </div>
            )}
            {caseData.missingInformation.length > 0 && (
              <button
                type="button"
                className="admin-individual-request-button"
                onClick={() => {
                  setInformationRequestSent(false);
                  setShowInformationRequest(true);
                }}
              >
                REQUEST INFORMATION FROM CLINICAL STAFF
              </button>
            )}
            {informationRequestSent && (
              <div className="admin-individual-alert success" role="status">
                Information request sent to Clinical Staff.
              </div>
            )}
          </section>

          <div className="admin-individual-action-card">
            <div className="admin-individual-action-icon">
              <FileCheck2 size={21} />
            </div>

            <span className="admin-individual-label">
              AUTHORIZATION
            </span>

            <h2>
              Authorize Individual Submission
            </h2>

            <p>
              This action authorizes this individual case for electronic submission.
            </p>

            <div className="admin-individual-action-details">
              <div>
                <span>Destination</span>
                <strong>{caseData.destination}</strong>
              </div>

              <div>
                <span>Mode</span>
                <strong>
                  {caseData.submissionMode}
                </strong>
              </div>

              <div>
                <span>Case</span>
                <strong>
                  {caseData.caseId}
                </strong>
              </div>
              <div><span>Patient</span><strong>{caseData.patientName}</strong></div>
              <div><span>Readiness</span><strong>{caseData.validationState}</strong></div>
            </div>

            <button
              type="button"
              className="authorize-submit-button"
              onClick={handleAuthorizeAndSubmit}
              disabled={submitting || !authorizationReady}
            >
              <CheckCircle2 size={17} />

              {submitting
                ? "Submitting..."
                : "AUTHORIZE & SUBMIT CASE"}
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
      {showInformationRequest && (
        <div className="admin-individual-modal-backdrop" role="presentation">
          <section
            className="admin-individual-request-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-individual-request-title"
          >
            <h2 id="admin-individual-request-title">Request Missing Information</h2>
            <p>The following information is required before this case can be submitted.</p>
            <ul className="admin-individual-request-fields">
              {caseData.missingInformation.map((field, index) => (
                <li key={`${field}-${index}`}>{formatEvidenceValue(field)}</li>
              ))}
            </ul>
            <p>Please complete the missing required information for this case and resubmit it for administrative review.</p>
            <div className="admin-individual-request-actions">
              <button type="button" onClick={() => setShowInformationRequest(false)}>CANCEL</button>
              <button type="button" onClick={handleSendInformationRequest}>SEND REQUEST</button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

