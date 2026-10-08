import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CalendarClock, FileCheck2, HeartPulse, MapPin, UserRound } from "lucide-react";
import { getAdminQueueCase, getAdminSubmission } from "../../services/adminService.js";
import "../../styles/AdminSubmissionJourney.css";

const STAGES = [
  { key: "ADMIN", label: "ADMIN", subtitle: "Authorize" },
  { key: "SIGNAL", label: "SIGNAL", subtitle: "Prepare" },
  { key: "EICR", label: "eICR", subtitle: "Generate" },
  { key: "AIMS_OUTBOUND", label: "APHL AIMS", subtitle: "Transport" },
  { key: "TX_DSHS", label: "TEXAS DSHS", subtitle: "Receive" },
  { key: "NEDSS", label: "NEDSS", subtitle: "Process" },
  { key: "PHA_PROCESSING", label: "PHA PROCESS", subtitle: "Review" },
  { key: "RESPONSE", label: "RESPONSE", subtitle: "RR" },
  { key: "AIMS_INBOUND", label: "APHL AIMS", subtitle: "Return" },
  { key: "SIGNAL_RESPONSE", label: "SIGNAL", subtitle: "Receive" },
  { key: "FOLLOW_UP", label: "FOLLOW-UP", subtitle: "Track" },
];

function firstValue(...values) {
  return values.find(
    (value) =>
      value !== null &&
      value !== undefined &&
      value !== "" &&
      value !== "null"
  );
}

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function normalizeStatus(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[\s-]+/g, "_");
}

function getTransportValue(submission) {
  return submission?.channel;
}

function getDestination(submission) {
  return submission?.destination;
}

function getSubmissionMode(submission) {
  return submission?.submission_mode;
}

function getPatientName(submission) {
  const patient = submission?.patient || submission?.case?.patient || {};

  const fullName = firstValue(
    patient?.name,
    patient?.full_name,
    submission?.patient_name,
    submission?.case?.patient_name
  );

  if (fullName && typeof fullName === "object") {
    const displayName = firstValue(fullName.text, fullName.display, fullName.name);
    const nameParts = [fullName.given, fullName.family].filter(Boolean).join(" ");
    if (displayName || nameParts) return displayName || nameParts;
  } else if (fullName) {
    return fullName;
  }

  const firstName = firstValue(
    patient?.first_name,
    patient?.given_name,
    submission?.first_name,
    submission?.given_name,
    submission?.case?.first_name
  );

  const lastName = firstValue(
    patient?.last_name,
    patient?.family_name,
    submission?.last_name,
    submission?.family_name,
    submission?.case?.last_name
  );

  const combined = [firstName, lastName].filter(Boolean).join(" ");

  return combined || "—";
}

function getCondition(submission) {
  return submission?.disease;
}

function getPatientField(submission, caseData, ...keys) {
  const casePatient = caseData?.patient || {};
  const submissionPatient = submission?.patient || submission?.case?.patient || {};
  for (const key of keys) {
    const value = firstValue(
      casePatient?.[key],
      submissionPatient?.[key],
      caseData?.[key],
      submission?.[key]
    );
    if (value !== undefined) return displayValue(value);
  }
  return "—";
}

function conditionLabel(value) {
  if (Array.isArray(value)) return value.map(conditionLabel).find((label) => label !== "—") || "—";
  if (value && typeof value === "object") {
    for (const key of ["display", "name", "condition_name", "disease_name", "text", "label", "title", "description", "condition", "disease", "concept", "coding", "code"]) {
      const label = conditionLabel(value[key]);
      if (label !== "—") return label;
    }
    return "—";
  }
  if (typeof value === "number") return value === 14189004 ? "Measles" : "—";
  if (typeof value !== "string" || !value.trim()) return "—";

  const candidate = value.trim();
  const code = candidate.match(/(?:^|[|/])(\d{5,})\s*$/)?.[1];
  if (code) return code === "14189004" ? "Measles" : "—";
  if (/^\d+$/.test(candidate) || /(?:snomed|^https?:\/\/)/i.test(candidate)) return "—";
  return candidate.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDeadline(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return conditionLabel(value);
}

function getCaseId(submission) {
  return submission?.case_id;
}

function getEicrId(submission) {
  return submission?.ecr_id;
}

function getResponsePayload(submission) {
  return submission?.acknowledgement || null;
}

function getErrorMessage(submission) {
  return firstValue(
    Array.isArray(submission?.errors) && submission.errors.length ? submission.errors.join("; ") : null,
  );
}

function getCurrentStage(submission) {
  const rawStatus = normalizeStatus(
    firstValue(
      submission?.status,
      submission?.submission_status,
      submission?.state,
      submission?.acknowledgement?.status
    )
  );
  const acknowledgementStatus = normalizeStatus(submission?.acknowledgement?.status);

  if (acknowledgementStatus.includes("INFORMATION_REQUESTED") || acknowledgementStatus.includes("INFO_REQUEST")) return "FOLLOW_UP";
  if (submission?.acknowledgement || acknowledgementStatus.includes("ACKNOWLEDGED")) return "RESPONSE";

  if (
    rawStatus.includes("FAILED") ||
    rawStatus.includes("ERROR") ||
    rawStatus.includes("REJECTED")
  ) {
    return submission?.ecr_id ? "EICR" : "SIGNAL";
  }

  if (
    rawStatus.includes("ACKNOWLEDGED") ||
    rawStatus.includes("ACKNOWLEDGEMENT")
  ) {
    return "RESPONSE";
  }

  if (
    rawStatus.includes("RESPONSE") ||
    rawStatus.includes("RR_RECEIVED") ||
    rawStatus.includes("REPORTABILITY")
  ) {
    return "RESPONSE";
  }

  if (
    rawStatus.includes("FOLLOW") ||
    rawStatus.includes("INFORMATION_REQUESTED") ||
    rawStatus.includes("INFO_REQUEST")
  ) {
    return "FOLLOW_UP";
  }

  if (/DELIVERED|SENT|SUBMITTED/.test(rawStatus)) return "AIMS_OUTBOUND";

  if (
    rawStatus.includes("VALIDATED") ||
    rawStatus.includes("EICR_GENERATED") ||
    rawStatus.includes("PREPARED")
  ) {
    return "EICR";
  }

  if (submission?.ecr_id) return "EICR";
  return "SIGNAL";
}

function getStageState(stageKey, currentStage, submission) {
  const currentIndex = STAGES.findIndex(
    (stage) => stage.key === currentStage
  );

  const stageIndex = STAGES.findIndex(
    (stage) => stage.key === stageKey
  );

  const rawStatus = normalizeStatus(
    firstValue(
      submission?.status,
      submission?.submission_status,
      submission?.state,
      submission?.acknowledgement?.status
    )
  );

  const isFailure =
    rawStatus.includes("FAILED") ||
    rawStatus.includes("ERROR") ||
    rawStatus.includes("REJECTED");

  if (isFailure && stageKey === currentStage) {
    return "failed";
  }

  if (stageIndex < currentIndex) {
    return "completed";
  }

  if (stageIndex === currentIndex) {
    return "current";
  }

  return "pending";
}

function getCurrentStageLabel(stageKey) {
  return (
    STAGES.find((stage) => stage.key === stageKey)?.label || "SIGNAL"
  );
}

function getStatusLabel(submission, currentStage) {
  const rawStatus = firstValue(
    submission?.status,
    submission?.submission_status,
    submission?.state
  );

  if (!rawStatus) {
    return getCurrentStageLabel(currentStage);
  }

  return String(rawStatus)
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function isInformationRequested(submission) {
  const status = normalizeStatus(
    firstValue(
      submission?.acknowledgement?.status
    )
  );

  return (
    status.includes("INFORMATION_REQUESTED") ||
    status.includes("INFO_REQUEST")
  );
}

export default function AdminSubmissionJourney() {
  const { submissionId } = useParams();
  const navigate = useNavigate();

  const [submission, setSubmission] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadSubmission() {
      try {
        setLoading(true);
        setError("");

        const result = await getAdminSubmission(submissionId);

        if (!active) return;

        const record = result?.data ?? result;
        setSubmission(record);
        setCaseData(null);
        if (record?.case_id) {
          try {
            const caseResult = await getAdminQueueCase(record.case_id);
            if (active) setCaseData(caseResult?.data ?? caseResult);
          } catch {
            // Deadline details are optional; keep the real submission visible if case details fail.
          }
        }
      } catch (err) {
        if (!active) return;

        setError(
          err?.response?.data?.detail ||
            err?.message ||
            "Unable to load submission."
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    if (submissionId) {
      loadSubmission();
    }

    return () => {
      active = false;
    };
  }, [submissionId]);

  const currentStage = useMemo(
    () => getCurrentStage(submission || {}),
    [submission]
  );

  const informationRequested = useMemo(
    () => isInformationRequested(submission || {}),
    [submission]
  );

  const requestedInformation = Array.isArray(submission?.acknowledgement?.requested_fields)
    ? submission.acknowledgement.requested_fields
    : [];

  const patientDetails = {
    ...(submission || {}),
    ...(caseData || {}),
    patient: caseData?.patient || submission?.patient || submission?.case?.patient,
  };
  const condition = getCondition(submission || {});
  const caseId = getCaseId(submission || null);
  const destination = getDestination(submission || {});
  const submissionMode = getSubmissionMode(submission || {});
  const transport = getTransportValue(submission || {});
  const transportIsSimulated = /mock|simulat/i.test(String(transport || ""))
    || /mock|simulat/i.test(String(destination || ""))
    || (submission?.warnings || []).some((warning) => /mock|simulat/i.test(String(warning)));
  const eicrId = getEicrId(submission || {});
  const responsePayload = getResponsePayload(submission || {});
  const errorMessage = getErrorMessage(submission || {});
  const responseFailed = Boolean(responsePayload)
    && /FAILED|FAILURE|ERROR|REJECTED/.test(normalizeStatus(responsePayload?.status));

  const submittedAt = firstValue(
    submission?.submitted_at,
    submission?.created_at,
    submission?.timestamp
  );

  const responseReceivedAt = submission?.acknowledgement?.received_at;

  const currentStatus = getStatusLabel(
    submission || {},
    currentStage
  );
  const jurisdictionValue = displayValue(caseData?.jurisdiction || submission?.jurisdiction || destination);
  const caseConditionValue = conditionLabel(caseData?.condition);
  const conditionValue = caseConditionValue !== "—" ? caseConditionValue : conditionLabel(condition);
  const reportabilityValue = displayValue(caseData?.reportability);
  const deadlineValue = formatDeadline(caseData?.deadline ?? caseData?.reporting_deadline);
  const kpis = [
    { label: "REPORTING JURISDICTION", value: jurisdictionValue, subtitle: "State health authority", Icon: MapPin },
    { label: "REPORTING CONDITION", value: conditionValue, subtitle: reportabilityValue !== "—" ? `Reportability: ${reportabilityValue}` : "Reportability status unavailable", Icon: HeartPulse },
    { label: "REPORTING DEADLINE", value: deadlineValue, subtitle: "Reporting deadline", Icon: CalendarClock },
    { label: "SUBMISSION STATUS", value: displayValue(submission?.status), subtitle: "Current submission state", Icon: FileCheck2 },
  ];

  const handleProvideInformation = () => {
    if (caseId) {
      navigate(`/admin/queue/${caseId}`);
      return;
    }

    navigate("/admin/queue");
  };

  if (loading) {
    return (
      <div className="admin-journey-page">
        <div className="admin-journey-loading">
          Loading submission...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="admin-journey-page">
        <div className="admin-journey-header">
          <button
            type="button"
            className="journey-back-button"
            onClick={() => navigate("/admin/queue")}
          >
            {"\u2190 Back to Reporting Queue"}
          </button>
          <h1>Submission Journey</h1>
        </div>

        <div className="journey-error-card">
          <span className="journey-section-label">ERROR</span>
          <h2>Unable to load submission</h2>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!submission) {
    return (
      <div className="admin-journey-page">
        <div className="admin-journey-header">
          <button
            type="button"
            className="journey-back-button"
            onClick={() => navigate("/admin/queue")}
          >
            {"\u2190 Back to Reporting Queue"}
          </button>
          <h1>Submission Journey</h1>
        </div>

        <div className="journey-empty-card">
          <span className="journey-section-label">SUBMISSION</span>
          <h2>Submission not found</h2>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-journey-page">
      <header className="admin-journey-header">
        <button
          type="button"
          className="journey-back-button"
          onClick={() => navigate("/admin/queue")}
        >
          {"\u2190 Back to Reporting Queue"}
        </button>

        <div className="journey-title-row">
          <div>
            <span className="journey-section-label">
              ADMIN SUBMISSION
            </span>

            <h1>Submission Journey</h1>

            <p>
              Track the electronic case report from administrative
              authorization through public health processing.
            </p>
          </div>

        </div>
      </header>

      <section className="journey-kpis" aria-label="Submission summary">
        {kpis.map(({ label, value, subtitle, Icon }) => (
          <article className="journey-kpi" key={label}>
            <div className="journey-kpi-heading">
              <span>{label}</span>
              <Icon size={16} aria-hidden="true" />
            </div>
            <strong title={value}>{value}</strong>
            <small>{subtitle}</small>
          </article>
        ))}
      </section>
      <section className="journey-person-card" aria-labelledby="journey-person-title">
        <div className="journey-person-heading">
          <UserRound size={18} aria-hidden="true" />
          <div>
            <span className="journey-section-label">PATIENT &amp; CASE INFORMATION</span>
            <h2 id="journey-person-title">Core patient and reporting information.</h2>
          </div>
        </div>
        <div className="journey-person-fields">
          <div><span>Patient Name</span><strong>{getPatientName(patientDetails)}</strong></div>
          <div><span>Date of Birth</span><strong>{getPatientField(submission, caseData, "date_of_birth", "dateOfBirth", "dob")}</strong></div>
          <div><span>Sex</span><strong>{getPatientField(submission, caseData, "sex")}</strong></div>
          <div><span>Condition</span><strong>{conditionValue}</strong></div>
          <div><span>Jurisdiction</span><strong>{jurisdictionValue}</strong></div>
          <div><span>Submission Mode</span><strong>{displayValue(caseData?.submission_mode || submissionMode)}</strong></div>
        </div>
      </section>
      <section className="journey-section">
        <div className="journey-section-heading">
          <span className="journey-section-label">
            TRANSMISSION JOURNEY
          </span>
          <h2>Public Health Data Path</h2>
        </div>

        <div className="journey-track-wrapper">
          <div
            className={`journey-track ${currentStage === "AIMS_OUTBOUND" && transportIsSimulated ? "is-simulated" : ""}`}
            style={{ "--journey-progress": `${Math.max(0, STAGES.findIndex((stage) => stage.key === currentStage) - 1) / STAGES.length * 100}%` }}
          >
            {STAGES.map((stage) => {
              const state = getStageState(
                stage.key,
                currentStage,
                submission
              );

              return (
                <React.Fragment key={stage.key}>
                  <div className={`journey-stage ${state}`}>
                    <div className="journey-stage-circle" aria-label={state}>
                      {state === "completed" ? "✓" : ""}
                    </div>

                    <div className="journey-stage-label">
                      {stage.label}
                    </div>

                    <div className="journey-stage-subtitle">
                      {stage.subtitle}
                    </div>
                  </div>

                </React.Fragment>
              );
            })}
          </div>
        </div>
      </section>

      {transportIsSimulated && (
        <div className="journey-simulation-note" role="status">
          SIMULATED — no real PHA transmission or receipt is recorded.
        </div>
      )}

      <section className="journey-grid">
        <div className="journey-panel">
          <span className="journey-section-label">
            CURRENT STATUS
          </span>

          <h2>{getCurrentStageLabel(currentStage)}</h2>
          <p>{transportIsSimulated ? "Simulated submission to the configured transport. Downstream delivery is not confirmed." : currentStage === "AIMS_OUTBOUND" ? "Backend submission is recorded; destination receipt is not confirmed." : currentStage === "FOLLOW_UP" ? "The response requests follow-up." : currentStage === "RESPONSE" ? "A backend acknowledgement is recorded." : "Submission progress is shown from available backend status."}</p>

          <div className="journey-panel-row">
            <span>Status</span>
            <strong>{currentStatus}</strong>
          </div>

          <div className="journey-panel-row">
            <span>Destination</span>
            <strong>{destination || "—"}</strong>
          </div>

          <div className="journey-panel-row">
            <span>Channel / transport</span>
            <strong>{transport ? `${transport}${transportIsSimulated ? " (simulated)" : ""}` : "—"}</strong>
          </div>

          <div className="journey-panel-row">
            <span>Submitted</span>
            <strong>{formatDate(submittedAt)}</strong>
          </div>
        </div>

        <div className="journey-panel">
          <span className="journey-section-label">
            TRANSMISSION DETAILS
          </span>

          <div className="journey-details-grid">
            <div>
              <span>Submission ID</span>
              <strong>{submissionId || "—"}</strong>
            </div>

            <div>
              <span>Case ID</span>
              <strong>{caseId || "—"}</strong>
            </div>

            <div>
              <span>eICR ID</span>
              <strong>{eicrId || "—"}</strong>
            </div>

            <div>
              <span>Destination</span>
              <strong>{destination || "—"}</strong>
            </div>

            <div>
              <span>Channel / transport</span>
              <strong>{transport ? `${transport}${transportIsSimulated ? " (simulated)" : ""}` : "—"}</strong>
            </div>

            <div>
              <span>Submitted At</span>
              <strong>{formatDate(submittedAt)}</strong>
            </div>

            <div>
              <span>Response Received</span>
              <strong>{formatDate(responseReceivedAt)}</strong>
            </div>
          </div>
        </div>
      </section>

      {errorMessage && (
        <section className="journey-alert-card error">
          <span className="journey-section-label">SUBMISSION ERROR</span>
          <h2>Transmission requires attention</h2>
          <p>{errorMessage}</p>
        </section>
      )}

      <section className="journey-response-card">
        <div>
          <span className="journey-section-label">
            RESPONSE / RR
          </span>

          <h2>{informationRequested ? "INFORMATION REQUESTED" : errorMessage || responseFailed ? "FAILURE" : responsePayload ? "RESPONSE RECEIVED" : "AWAITING REPORTABILITY RESPONSE"}</h2>

          <p>
            {informationRequested ? "Public health requires additional information before processing can be completed." : errorMessage || (responseFailed && responsePayload?.errors?.join("; ")) ? errorMessage || responsePayload?.errors?.join("; ") : responsePayload ? "Backend acknowledgement details are available for this submission." : "The submission is recorded and SIGNAL is waiting for a response. No acknowledgement has been recorded by the backend."}
          </p>
        </div>

        {responsePayload && (
          <div className="journey-response-content">
            <div>
              <span>Acknowledgement status</span>
              <strong>{responsePayload?.status || "—"}</strong>
            </div>

            <div>
              <span>Acknowledgement ID</span>
              <strong>{responsePayload?.acknowledgement_id || "—"}</strong>
            </div>

            <div>
              <span>Received</span>
              <strong>{formatDate(responsePayload?.received_at)}</strong>
            </div>

            <div>
              <span>Errors</span>
              <strong>{Array.isArray(responsePayload?.errors) && responsePayload.errors.length ? responsePayload.errors.join("; ") : "—"}</strong>
            </div>
          </div>
        )}
      </section>

      {informationRequested && (
        <section className="journey-information-card">
          <div className="journey-information-copy">
            <span className="journey-section-label">
              INFORMATION REQUESTED
            </span>

            <h2>Additional information is required</h2>

            <p>
              Public health requires additional information before
              processing can be completed.
            </p>

            {requestedInformation.length > 0 && (
              <div className="journey-requested-list">
                {requestedInformation.map((item, index) => {
                  const label =
                    typeof item === "string"
                      ? item
                      : firstValue(
                          item?.label,
                          item?.field,
                          item?.name,
                          item?.description
                        );

                  if (!label) return null;

                  return (
                    <div key={`${label}-${index}`}>
                      <span>•</span>
                      <span>{label}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <button
            type="button"
            className="journey-primary-button"
            onClick={handleProvideInformation}
          >
            Provide Information
          </button>
        </section>
      )}

      <section className="journey-followup-card">
        <div>
          <span className="journey-section-label">FOLLOW-UP</span>
          <h2>Submission Follow-up</h2>
        </div>

        <div className="journey-followup-status">
          <span
            className={`followup-dot ${
              informationRequested
                ? "warning"
              : responsePayload && !responseFailed
              ? "success"
              : responseFailed
              ? "warning"
                : "pending"
            }`}
          />

          <span>
            {informationRequested
              ? "Information Requested"
              : responseFailed
              ? "Response indicates failure"
              : responsePayload
              ? "Response Received"
              : "Awaiting Public Health Response"}
          </span>
        </div>
      </section>
    </div>
  );
}
