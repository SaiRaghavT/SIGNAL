import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, CircleAlert, FileCheck2, Send, ShieldCheck } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import {
  dispatchCase,
  getAdminQueueCase,
} from "../../services/adminService.js";
import "../../styles/AdminCaseReview.css";
import { cleanPatientName } from "../../utils/patientNames.js";

function firstDefined(...values) {
  return values.find(
    (value) => value !== undefined && value !== null && value !== ""
  );
}

function formatValue(value, fallback = "—") {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  return String(value);
}

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function normalizeCaseResponse(response) {
  const raw =
    response?.data ??
    response?.case ??
    response?.item ??
    response ??
    {};

  const patient =
    raw.patient ??
    raw.patient_data ??
    raw.canonical_patient ??
    {};

  const clinical =
    raw.clinical ??
    raw.clinical_data ??
    raw.clinical_evidence ??
    {};

  const reportability =
    raw.reportability ??
    raw.reportability_result ??
    raw.reportability_decision ??
    {};

  const validation =
    raw.validation ??
    raw.validation_result ??
    raw.validation_summary ??
    {};

  const caseData = {
    ...raw,
    patient,
    clinical,
    reportability,
    validation,
  };

  return caseData;
}

function getSubmissionMode(caseData) {
  const mode = String(
    firstDefined(
      caseData?.submission_mode,
      caseData?.mode,
      caseData?.submission?.submission_mode
    ) || ""
  ).toUpperCase();

  if (mode === "IMMEDIATE") return "IMMEDIATE";
  if (mode === "INDIVIDUAL") return "INDIVIDUAL";

  return mode;
}

function getValidationStatus(caseData) {
  const validation = caseData?.validation || {};

  const explicitStatus = firstDefined(
    validation.status,
    validation.result,
    validation.validation_status,
    caseData?.validation_status
  );

  if (explicitStatus) {
    return String(explicitStatus);
  }

  const valid = firstDefined(
    validation.valid,
    validation.is_valid,
    caseData?.is_valid
  );

  if (valid === true) return "VALID";
  if (valid === false) return "INVALID";

  return "REVIEW REQUIRED";
}

function getValidationItems(caseData) {
  const validation = caseData?.validation || {};

  const items = firstDefined(
    validation.items,
    validation.checks,
    validation.rules,
    validation.errors,
    caseData?.validation_items
  );

  if (Array.isArray(items)) {
    return items;
  }

  return [];
}

function InfoField({ label, value, wide = false }) {
  return (
    <div className={`admin-review-field ${wide ? "admin-review-field-wide" : ""}`}>
      <div className="admin-review-label">{label}</div>
      <div className="admin-review-value">{formatValue(value)}</div>
    </div>
  );
}

function Section({ icon: Icon, title, children }) {
  return (
    <section className="admin-review-section">
      <div className="admin-review-section-header">
        <div className="admin-review-section-title">
          {Icon ? <Icon size={17} /> : null}
          <span>{title}</span>
        </div>
      </div>

      <div className="admin-review-section-body">{children}</div>
    </section>
  );
}

export default function AdminCaseReview() {
  const navigate = useNavigate();
  const { caseId } = useParams();

  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [authorized, setAuthorized] = useState(false);

  const loadCase = useCallback(async () => {
    if (!caseId) {
      setError("No case ID was provided.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await getAdminQueueCase(caseId);
      const normalized = normalizeCaseResponse(response);

      setCaseData(normalized);
    } catch (err) {
      setError(
        err?.message ||
          err?.detail ||
          "Unable to load the case review."
      );
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  const submissionMode = useMemo(
    () => getSubmissionMode(caseData),
    [caseData]
  );

  const validationStatus = useMemo(
    () => getValidationStatus(caseData),
    [caseData]
  );

  const validationItems = useMemo(
    () => getValidationItems(caseData),
    [caseData]
  );

  const patient = caseData?.patient || {};
  const clinical = caseData?.clinical || {};
  const reportability = caseData?.reportability || {};

  const patientName = cleanPatientName(firstDefined(
    caseData?.patient_name,
    patient?.name,
    [patient?.first_name, patient?.last_name].filter(Boolean).join(" ")
  ));

  const patientId = firstDefined(
    caseData?.patient_id,
    patient?.patient_id,
    patient?.id
  );

  const condition = firstDefined(
    caseData?.condition,
    caseData?.disease,
    caseData?.condition_name,
    caseData?.disease_name,
    reportability?.condition
  );

  const jurisdiction = firstDefined(
    caseData?.jurisdiction,
    caseData?.jurisdiction_name,
    reportability?.jurisdiction
  );

  const deadline = firstDefined(
    caseData?.deadline,
    caseData?.reporting_deadline,
    caseData?.due_date
  );

  const caseStatus = firstDefined(
    caseData?.status,
    caseData?.case_status
  );

  const priority = firstDefined(
    caseData?.priority,
    caseData?.priority_level
  );

  const caseNumber = firstDefined(
    caseData?.case_id,
    caseData?.id,
    caseId
  );

  const dob = firstDefined(
    patient?.date_of_birth,
    patient?.dob,
    caseData?.date_of_birth,
    caseData?.dob
  );

  const sex = firstDefined(
    patient?.sex,
    patient?.gender,
    caseData?.sex,
    caseData?.gender
  );

  const mrn = firstDefined(
    patient?.mrn,
    patient?.medical_record_number,
    caseData?.mrn
  );

  const encounterId = firstDefined(
    caseData?.encounter_id,
    clinical?.encounter_id
  );

  const onsetDate = firstDefined(
    clinical?.onset_date,
    clinical?.illness_onset_date,
    caseData?.onset_date,
    caseData?.illness_onset_date
  );

  const rashOnsetDate = firstDefined(
    clinical?.rash_onset_date,
    caseData?.rash_onset_date
  );

  const labResult = firstDefined(
    clinical?.lab_result,
    clinical?.laboratory_result,
    caseData?.lab_result
  );

  const labTest = firstDefined(
    clinical?.lab_test,
    clinical?.laboratory_test,
    caseData?.lab_test
  );

  const reportabilityDecision = firstDefined(
    reportability?.decision,
    reportability?.result,
    reportability?.status,
    caseData?.reportability_decision
  );

  const reportabilityReason = firstDefined(
    reportability?.reason,
    reportability?.rationale,
    reportability?.explanation,
    caseData?.reportability_reason
  );

  const authorizationLabel =
    submissionMode === "IMMEDIATE"
      ? "Authorize & Submit Immediately"
      : "Authorize & Submit Case";

  const handleAuthorize = async () => {
    if (!caseId || submitting) return;

    try {
      setSubmitting(true);
      setError("");
      setSuccess("");

      const response = await dispatchCase(caseId);
      const submission = response?.submission || response?.data?.submission || response?.data || response;
      if (String(submission?.status || "").toUpperCase() !== "SUBMITTED") {
        throw new Error(submission?.errors?.join("; ") || "The case was not successfully submitted.");
      }
      const submissionId = submission?.submission_id || submission?.submissionId;
      if (!submissionId) throw new Error("Submission succeeded, but the dispatch response did not include a submission ID.");

      setAuthorized(true);

      const message =
        response?.message ||
        response?.detail ||
        "Case authorized and submitted successfully.";

      setSuccess(message);
      navigate(`/admin/submission-journey/${encodeURIComponent(submissionId)}`);
    } catch (err) {
      setError(
        err?.message ||
          err?.detail ||
          "Unable to authorize and submit this case."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-review-page">
        <div className="admin-review-loading">
          <div className="admin-review-spinner" />
          <div>
            <strong>Loading case review</strong>
            <p>Retrieving the reporting package...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error && !caseData) {
    return (
      <div className="admin-review-page">
        <div className="admin-review-topbar">
          <button
            type="button"
            className="admin-review-back"
            onClick={() => navigate("/admin/queue")}
          >
            <ArrowLeft size={16} />
            Back to Reporting Queue
          </button>
        </div>

        <div className="admin-review-error">
          <CircleAlert size={22} />
          <div>
            <strong>Unable to load case</strong>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!caseData) {
    return null;
  }

  return (
    <div className="admin-review-page">
      <div className="admin-review-topbar">
        <button
          type="button"
          className="admin-review-back"
          onClick={() => navigate("/admin/queue")}
        >
          <ArrowLeft size={16} />
          Back to Reporting Queue
        </button>

        <div className="admin-review-breadcrumb">
          Reporting Queue <span>/</span> Review &amp; Authorize
        </div>
      </div>

      <div className="admin-review-heading">
        <div>
          <div className="admin-review-eyebrow">
            {submissionMode === "IMMEDIATE"
              ? "IMMEDIATE REPORT"
              : "INDIVIDUAL REPORT"}
          </div>

          <h1>Review &amp; Authorize</h1>

          <p>
            Review the reporting package and authorize submission to the
            appropriate public health authority.
          </p>
        </div>

        <div className="admin-review-case-badge">
          <span>CASE ID</span>
          <strong>{formatValue(caseNumber)}</strong>
        </div>
      </div>

      {success ? (
        <div className="admin-review-success">
          <CheckCircle2 size={20} />
          <div>
            <strong>Submission successful</strong>
            <p>{success}</p>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="admin-review-error">
          <CircleAlert size={20} />
          <div>
            <strong>Submission error</strong>
            <p>{error}</p>
          </div>
        </div>
      ) : null}

      <div className="admin-review-status-row">
        <div className="admin-review-status-card">
          <span>Submission Mode</span>
          <strong>{formatValue(submissionMode)}</strong>
        </div>

        <div className="admin-review-status-card">
          <span>Status</span>
          <strong>{formatValue(caseStatus)}</strong>
        </div>

        <div className="admin-review-status-card">
          <span>Priority</span>
          <strong>{formatValue(priority)}</strong>
        </div>

        <div className="admin-review-status-card">
          <span>Deadline</span>
          <strong>{formatDate(deadline)}</strong>
        </div>
      </div>

      <Section icon={FileCheck2} title="Patient & Case Information">
        <div className="admin-review-grid">
          <InfoField label="Patient Name" value={patientName} />
          <InfoField label="Patient ID" value={patientId} />
          <InfoField label="Date of Birth" value={formatDate(dob)} />
          <InfoField label="Sex / Gender" value={sex} />
          <InfoField label="MRN" value={mrn} />
          <InfoField label="Encounter ID" value={encounterId} />
          <InfoField label="Condition" value={condition} />
          <InfoField label="Jurisdiction" value={jurisdiction} />
        </div>
      </Section>

      <Section icon={ShieldCheck} title="Clinical & Laboratory Information">
        <div className="admin-review-grid">
          <InfoField label="Illness Onset" value={formatDate(onsetDate)} />
          <InfoField label="Rash Onset" value={formatDate(rashOnsetDate)} />
          <InfoField label="Laboratory Test" value={labTest} />
          <InfoField label="Laboratory Result" value={labResult} />
        </div>

        {clinical?.symptoms ? (
          <div className="admin-review-detail-box">
            <div className="admin-review-label">Symptoms</div>
            <div className="admin-review-detail-text">
              {formatValue(clinical.symptoms)}
            </div>
          </div>
        ) : null}

        {clinical?.evidence ? (
          <div className="admin-review-detail-box">
            <div className="admin-review-label">Clinical Evidence</div>
            <div className="admin-review-detail-text">
              {typeof clinical.evidence === "object"
                ? JSON.stringify(clinical.evidence, null, 2)
                : formatValue(clinical.evidence)}
            </div>
          </div>
        ) : null}
      </Section>

      <Section icon={ShieldCheck} title="Reportability & Validation">
        <div className="admin-review-grid">
          <InfoField
            label="Reportability Decision"
            value={reportabilityDecision}
          />

          <InfoField
            label="Jurisdiction"
            value={jurisdiction}
          />

          <InfoField
            label="Validation Status"
            value={validationStatus}
          />

          <InfoField
            label="Reporting Deadline"
            value={formatDate(deadline)}
          />
        </div>

        {reportabilityReason ? (
          <div className="admin-review-detail-box">
            <div className="admin-review-label">Reportability Rationale</div>
            <div className="admin-review-detail-text">
              {formatValue(reportabilityReason)}
            </div>
          </div>
        ) : null}

        {validationItems.length > 0 ? (
          <div className="admin-review-validation-list">
            {validationItems.map((item, index) => {
              const itemText =
                typeof item === "string"
                  ? item
                  : firstDefined(
                      item?.message,
                      item?.description,
                      item?.name,
                      item?.rule,
                      JSON.stringify(item)
                    );

              const passed =
                item?.passed === true ||
                item?.valid === true ||
                item?.status === "PASS" ||
                item?.status === "VALID";

              return (
                <div
                  className={`admin-review-validation-item ${
                    passed ? "is-valid" : ""
                  }`}
                  key={`${index}-${itemText}`}
                >
                  {passed ? (
                    <CheckCircle2 size={16} />
                  ) : (
                    <CircleAlert size={16} />
                  )}

                  <span>{formatValue(itemText)}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div
            className={`admin-review-validation-banner ${
              validationStatus === "VALID" ? "is-valid" : ""
            }`}
          >
            {validationStatus === "VALID" ? (
              <CheckCircle2 size={18} />
            ) : (
              <CircleAlert size={18} />
            )}

            <div>
              <strong>{validationStatus}</strong>
              <p>
                {validationStatus === "VALID"
                  ? "The reporting package has passed the available validation checks."
                  : "Review the reporting package before authorization."}
              </p>
            </div>
          </div>
        )}
      </Section>

      <Section icon={ShieldCheck} title="Authorization">
        <div className="admin-review-authorization">
          <div className="admin-review-authorization-icon">
            <ShieldCheck size={24} />
          </div>

          <div className="admin-review-authorization-copy">
            <strong>Administrator Authorization Required</strong>
            <p>
              You are authorizing this completed reporting package for
              submission to the configured public health reporting endpoint.
            </p>

            <div className="admin-review-authorization-meta">
              <span>
                Mode: <strong>{formatValue(submissionMode)}</strong>
              </span>

              <span>
                Case: <strong>{formatValue(caseNumber)}</strong>
              </span>

              <span>
                Jurisdiction: <strong>{formatValue(jurisdiction)}</strong>
              </span>
            </div>
          </div>
        </div>
      </Section>

      <div className="admin-review-actions">
        <button
          type="button"
          className="admin-review-cancel"
          onClick={() => navigate("/admin/queue")}
          disabled={submitting}
        >
          Return to Queue
        </button>

        <button
          type="button"
          className="admin-review-submit"
          onClick={handleAuthorize}
          disabled={submitting || authorized}
        >
          {submitting ? (
            <>
              <span className="admin-review-button-spinner" />
              Submitting...
            </>
          ) : authorized ? (
            <>
              <CheckCircle2 size={17} />
              Submitted
            </>
          ) : (
            <>
              <Send size={17} />
              {authorizationLabel}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
