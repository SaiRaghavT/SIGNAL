import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { useDemoWorkflow } from "../hooks/useDemoWorkflow.js";
import {
  getCase,
  getJourney,
  updateCaseReport,
  attestation,
  persistAttestation,
  getCaseValidation,
  getCaseAttestation,
  getCaseReview,
  reviewCase,
  getImmediateNotification,
  recordImmediateNotification,
  validateCase,
  calculateDeadline,
  evaluateDeadlineEscalation,
} from "../api/signal.js";
import "../styles/case-workspace.css";
import "../styles/case-report-fields.css";
import "../styles/case-data-completion.css";
import "../styles/case-evidence.css";

const WORKFLOW_STEPS = [
  { key: "reportability", label: "Reportability" },
  { key: "case", label: "Case" },
  { key: "validation", label: "Validation" },
  { key: "review", label: "Human Review" },
  { key: "attestation", label: "Attestation" },
  { key: "notification", label: "Immediate Notification" },
  { key: "reporting", label: "Reporting" },
];

function normalizeStatus(value) {
  return String(value || "").toUpperCase();
}

function validEventTime(value) {
  return typeof value === "string" && value.includes("T") && Number.isFinite(Date.parse(value)) ? value : null;
}

function caseEventTime(data) {
  const clinical = data?.clinical_evidence || {};
  const candidateSignals = Array.isArray(clinical.candidate_signals) ? clinical.candidate_signals : [];
  const labEvidence = Array.isArray(data?.laboratory_evidence) ? data.laboratory_evidence : [];
  const candidates = [
    clinical.illness_onset_datetime,
    clinical.onset_datetime,
    clinical.event_time,
    clinical.detected_at,
    ...candidateSignals.flatMap((signal) => [signal?.detected_at, signal?.evidence?.effective_time, signal?.evidence?.issued_time]),
    ...labEvidence.flatMap((item) => [item?.effective_time, item?.issued_time, item?.evidence?.effective_time, item?.evidence?.issued_time, ...(item?.observations || []).map((observation) => observation?.effective_time)]),
    data?.created_at,
  ];
  return candidates.map(validEventTime).find(Boolean) || null;
}

function deadlineDateLabel(value) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Not available";
  return new Date(value).toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" });
}

function getJourneyStage(journey, key) {
  if (!journey) return null;

  const stages = Array.isArray(journey)
    ? journey
    : journey?.stages ||
      journey?.journey ||
      journey?.items ||
      [];

  return stages.find(
    (stage) =>
      normalizeStatus(stage?.stage || stage?.name || stage?.key) ===
      normalizeStatus(key)
  );
}

const MISSING_FIELD_GROUPS = [
  { key: "patient", label: "PATIENT" },
  { key: "reporting", label: "REPORTING" },
  { key: "clinical", label: "CLINICAL" },
  { key: "rash_fever", label: "RASH / FEVER" },
  { key: "laboratory", label: "LABORATORY" },
  { key: "provider", label: "PROVIDER" },
  { key: "facility", label: "FACILITY" },
];

const MISSING_FIELD_LABELS = {
  "patient.case_name": "Patient name",
  "patient.parent_guardian_name": "Parent or guardian name",
  "patient.current_address": "Current address",
  "patient.date_of_birth": "Date of birth",
  "patient.country_of_residence": "Country of residence",
  "patient.hispanic": "Hispanic or Latino",
  "patient.zip": "ZIP code",
  "reporting.reported_by": "Reported by",
  "reporting.earliest_date_reported": "Earliest date reported",
  "clinical.icu_admission": "ICU admission",
  "clinical.admission_date": "Admission date",
  "clinical.discharge_date": "Discharge date",
  "clinical.hospital": "Hospital or facility",
  "clinical.illness_onset_date": "Illness onset date",
  "clinical.diagnosis_date": "Diagnosis date",
  "rash_fever.rash_onset_date": "Rash onset date",
  "rash_fever.rash_duration": "Rash duration",
  "rash_fever.rash_location": "Rash location",
  "rash_fever.fever_onset_date": "Fever onset date",
  "rash_fever.highest_temperature": "Highest temperature",
  "rash_fever.koplik_spots": "Koplik spots",
  "provider.name": "Provider name",
  "provider.phone": "Provider phone",
  "provider.address": "Provider address",
  "facility.name": "Facility name",
};

const CASE_VALUE_PATHS = {
  "patient.case_name": "patient.name",
  "patient.parent_guardian_name": "patient.parent_guardian_name",
  "patient.current_address": "patient.address",
  "patient.city": "patient.city",
  "patient.county": "patient.county",
  "patient.zip": "patient.zip",
  "patient.phone": "patient.phone",
  "patient.date_of_birth": "patient.date_of_birth",
  "patient.sex": "patient.sex",
  "patient.country_of_residence": "patient.country_of_residence",
  "patient.hispanic": "patient.hispanic",
  "patient.race": "patient.race",
  "clinical.hospitalized": "clinical_evidence.hospitalized",
  "clinical.icu_admission": "clinical_evidence.icu_admission",
  "clinical.admission_date": "clinical_evidence.admission_date",
  "clinical.discharge_date": "clinical_evidence.discharge_date",
  "clinical.hospital": "facility.name",
  "clinical.illness_onset_date": "clinical_evidence.onset_date",
  "clinical.confirmation_method": "clinical_evidence.confirmation_method",
  "clinical.diagnosis": "disease",
  "clinical.diagnosis_date": "clinical_evidence.diagnosis_date",
  "rash_fever.rash": "clinical_evidence.rash",
  "rash_fever.rash_onset_date": "clinical_evidence.rash_onset_date",
  "rash_fever.rash_duration": "clinical_evidence.rash_duration",
  "rash_fever.rash_location": "clinical_evidence.rash_location",
  "rash_fever.fever": "clinical_evidence.fever",
  "rash_fever.fever_onset_date": "clinical_evidence.fever_onset_date",
  "rash_fever.highest_temperature": "clinical_evidence.highest_temperature",
  "rash_fever.cough": "clinical_evidence.cough",
  "rash_fever.coryza": "clinical_evidence.coryza",
  "rash_fever.conjunctivitis": "clinical_evidence.conjunctivitis",
  "rash_fever.koplik_spots": "clinical_evidence.koplik_spots",
};

function getObjectPath(source, path) {
  return path.split(".").reduce((value, key) => value?.[key], source);
}

function missingFieldLabel(field) {
  return MISSING_FIELD_LABELS[field] || field.split(".").at(-1).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function missingFieldControl(field, value, onChange) {
  const normalized = String(value ?? "").toLowerCase();
  const yesNoFields = new Set(["hospitalized", "icu_admission", "rash", "fever", "cough", "coryza", "conjunctivitis", "koplik_spots", "hispanic"]);
  if (yesNoFields.has(field.split(".").at(-1))) {
    const selected = ["true", "1", "y", "yes"].includes(normalized)
      ? "yes"
      : ["false", "0", "n", "no"].includes(normalized)
        ? "no"
        : normalized === "unknown"
          ? "unknown"
          : "";
    return <select value={selected} onChange={(event) => onChange(event.target.value)}><option value="">Select an answer</option><option value="yes">Yes</option><option value="no">No</option><option value="unknown">Unknown</option></select>;
  }
  if (field.endsWith(".date_of_birth") || field.endsWith("_date")) {
    const dateValue = typeof value === "string" ? value.slice(0, 10) : "";
    return <input type="date" value={dateValue} onChange={(event) => onChange(event.target.value)} />;
  }
  if (field.endsWith(".phone")) return <input type="tel" value={value ?? ""} onChange={(event) => onChange(event.target.value)} />;
  if (field.endsWith(".highest_temperature") || field.endsWith(".rash_duration")) return <input type="number" step="any" value={value ?? ""} onChange={(event) => onChange(event.target.value)} />;
  if (normalized.length > 90 || field.endsWith(".address")) return <textarea rows="3" value={value ?? ""} onChange={(event) => onChange(event.target.value)} />;
  return <input type="text" value={value ?? ""} onChange={(event) => onChange(event.target.value)} />;
}

export default function CaseWorkspace() {
  const { patientId: routePatientId, caseId } = useParams();
  const navigate = useNavigate();
  const demo = useDemoWorkflow(caseId);

  const [caseData, setCaseData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [validationRecord, setValidationRecord] = useState(null);
  const [reviewRecord, setReviewRecord] = useState(null);
  const [attestationRecord, setAttestationRecord] = useState(null);
  const [notificationRecord, setNotificationRecord] = useState(null);
  const [deadlineCalculation, setDeadlineCalculation] = useState(null);
  const [deadlineEscalation, setDeadlineEscalation] = useState(null);
  const [deadlineState, setDeadlineState] = useState("NOT CALCULATED");
  const [deadlineError, setDeadlineError] = useState("");
  const [deadlineLoading, setDeadlineLoading] = useState(false);

  const [reportFields, setReportFields] = useState({});
  const [provider, setProvider] = useState({});
  const [facility, setFacility] = useState({});

  const [missingOpen, setMissingOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);

  const [working, setWorking] = useState(false);
  const [operation, setOperation] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadWorkspace();
  }, [caseId]);

  async function loadWorkspace({ showLoading = true } = {}) {
    try {
      if (showLoading) setLoading(true);
      setError("");

      const [caseResponse, journeyResponse, validationResponse, reviewResponse, attestationResponse, notificationResponse] = await Promise.all([
        getCase(caseId),
        getJourney(caseId),
        getCaseValidation(caseId),
        getCaseReview(caseId),
        getCaseAttestation(caseId),
        getImmediateNotification(caseId),
      ]);

      const data = caseResponse?.data || caseResponse;
      const journeyData = journeyResponse?.data || journeyResponse;

      setCaseData(data);
      setJourney(journeyData);
      setValidationRecord(validationResponse?.data || validationResponse);
      setReviewRecord(reviewResponse?.data || reviewResponse);
      setAttestationRecord(attestationResponse?.data || attestationResponse);
      setNotificationRecord(notificationResponse?.data || notificationResponse);
      const escalations = Array.isArray(journeyData?.deadline_escalations) ? journeyData.deadline_escalations : [];
      setDeadlineEscalation(escalations.at(-1) || null);
      setDeadlineState(data?.deadline ? "DEADLINE CALCULATED" : caseEventTime(data) ? "NOT CALCULATED" : "DEADLINE UNAVAILABLE");

      setReportFields(data?.report_fields || {});
      setProvider(data?.provider || {});
      setFacility(data?.facility || {});

    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to load case workspace."
      );
      return false;
    } finally {
      if (showLoading) setLoading(false);
    }
    return true;
  }

  const patient = caseData?.patient || {};
  const patientId = routePatientId || patient.patient_id || caseData?.patient_id || "";
  const patientPath = patientId ? `/patients/${encodeURIComponent(patientId)}` : "/patients";
  const casePath = patientId
    ? `${patientPath}/case/${encodeURIComponent(caseId)}`
    : `/cases/${encodeURIComponent(caseId)}`;

  const missingFields = useMemo(() => [...new Set([
    ...(caseData?.missing_report_fields || []),
    ...(caseData?.required_missing_fields || []),
    ...(validationRecord?.missing_fields || []),
    ...(validationRecord?.completion_required || []),
  ].filter((field) => typeof field === "string" && field.trim()))], [caseData, validationRecord]);
  const groupedMissingFields = useMemo(() => {
    const groups = MISSING_FIELD_GROUPS.map((group) => ({ ...group, fields: [] }));
    for (const field of missingFields) {
      const groupKey = field.split(".")[0];
      const group = groups.find((item) => item.key === groupKey) || groups.find((item) => item.key === "clinical");
      group.fields.push(field);
    }
    return groups.filter((group) => group.fields.length);
  }, [missingFields]);

  function getMissingFieldValue(field) {
    if (field.startsWith("provider.")) return provider[field.slice("provider.".length)] ?? "";
    if (field.startsWith("facility.")) return facility[field.slice("facility.".length)] ?? "";
    return reportFields[field] ?? getObjectPath(caseData, CASE_VALUE_PATHS[field] || "") ?? "";
  }

  function setMissingFieldValue(field, value) {
    if (field.startsWith("provider.")) {
      const key = field.slice("provider.".length);
      setProvider((current) => ({ ...current, [key]: value }));
    } else if (field.startsWith("facility.")) {
      const key = field.slice("facility.".length);
      setFacility((current) => ({ ...current, [key]: value }));
    } else {
      setReportFields((current) => ({ ...current, [field]: value }));
    }
  }

  const reportabilityDecision = normalizeStatus(caseData?.reportability_decision);
  const finalDecision = normalizeStatus(caseData?.final_decision);
  const jurisdictionResolved = normalizeStatus(caseData?.jurisdiction_status) === "RESOLVED";
  const reportabilityPending = reportabilityDecision === "PROCEED_TO_RULES";
  const isReportable = reportabilityDecision === "REPORT";
  const backendValidationReady = isReportable && validationRecord?.valid === true && validationRecord?.ready_for_review === true;
  const validationReady = demo.active
    ? demo.stages.validation === "COMPLETED" && backendValidationReady
    : backendValidationReady;
  const validationState = reportabilityPending
    ? "PENDING REPORTABILITY"
    : !isReportable
      ? "PENDING REPORTABILITY"
      : validationReady
        ? "READY"
        : "NEEDS COMPLETION";
  const reviewApproved = demo.active
    ? demo.stages.review === "COMPLETED"
    : normalizeStatus(reviewRecord?.status) === "APPROVE";
  const humanReviewReady = validationReady;
  const attested = demo.active
    ? demo.stages.attestation === "COMPLETED"
    : normalizeStatus(attestationRecord?.status) === "ATTESTED";
  const attestationReady = humanReviewReady && reviewApproved && finalDecision === "REPORT" && jurisdictionResolved;
  const notificationComplete = demo.active
    ? demo.stages.notification === "COMPLETED"
    : normalizeStatus(notificationRecord?.status) === "COMPLETED";
  const reportingReady = attested && notificationComplete;
  const deadlineValue = deadlineCalculation?.deadline || caseData?.deadline || null;
  const escalationStatus = deadlineEscalation?.status || null;

  async function handleCalculateDeadline() {
    const eventTime = caseEventTime(caseData);
    if (!eventTime) {
      setDeadlineState("DEADLINE UNAVAILABLE");
      setDeadlineError("No valid event timestamp is available in the case or workflow data.");
      return;
    }
    if (deadlineLoading || !caseData?.disease || !caseData?.jurisdiction) return;
    let calculationCompleted = false;
    try {
      setDeadlineLoading(true);
      setDeadlineState("CALCULATING");
      setDeadlineError("");
      const calculation = await calculateDeadline({
        event_time: eventTime,
        disease: caseData.disease,
        jurisdiction: caseData.jurisdiction,
        // caseData.rule_id is the reportability decision rule (for example,
        // MEASLES-003). Deadline rules are selected separately by disease
        // and jurisdiction from the deadline catalog.
        case_id: caseId,
      });
      if (!calculation?.deadline || !Number.isFinite(Date.parse(calculation.deadline))) {
        throw new Error("Deadline Agent response did not contain a valid deadline.");
      }
      setDeadlineCalculation(calculation);
      calculationCompleted = true;
      const escalation = await evaluateDeadlineEscalation({
        case_id: caseId,
        deadline: calculation.deadline,
        warning_window_minutes: 60,
        jurisdiction: caseData.jurisdiction,
        rule_id: calculation.rule_id || caseData.rule_id || undefined,
      });
      setDeadlineEscalation(escalation);
      setDeadlineState("DEADLINE CALCULATED");
      await loadWorkspace({ showLoading: false });
    } catch (err) {
      setDeadlineState(calculationCompleted ? "DEADLINE CALCULATED" : "ERROR");
      setDeadlineError(calculationCompleted
        ? `Deadline calculated, but escalation status could not be evaluated: ${err?.message || "Backend error."}`
        : err?.message || "Reporting deadline could not be calculated.");
    } finally {
      setDeadlineLoading(false);
    }
  }

  async function saveCase() {
    try {
      setWorking(true);
      setError("");
      setMessage("");

      await updateCaseReport(caseId, {
        report_fields: (() => {
          const fields = { ...reportFields };
          if (Object.hasOwn(fields, "reported_by")) {
            fields["reporting.reported_by"] ??= fields.reported_by;
            delete fields.reported_by;
          }
          return fields;
        })(),
        provider,
        facility,
        reviewer_id: "reporting_user",
      });

      const refreshed = await loadWorkspace({ showLoading: false });
      if (!refreshed) return false;
      setMessage("Information saved successfully.");
      return true;
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to save case information."
      );
      return false;
    } finally {
      setWorking(false);
    }
  }

  async function runValidation() {
    try {
      setWorking(true);
      setOperation("validation");
      setError("");
      setMessage("");
      const response = await validateCase(caseId);
      const result = response?.data || response;
      if (result?.valid === true && result?.ready_for_review === true) demo.complete("validation");
      await loadWorkspace({ showLoading: false });
      setMessage("Backend validation completed. Review the returned status and required fields.");
    } catch (err) {
      setError(err?.response?.data?.detail?.message || err?.response?.data?.detail || err?.message || "Unable to validate case.");
      await loadWorkspace({ showLoading: false });
    } finally {
      setWorking(false);
      setOperation("");
    }
  }

  async function handleReview() {
    if (!validationReady) {
      setMissingOpen(true);
      return;
    }

    try {
      setWorking(true);
      setOperation("review");
      setError("");
      const response = await reviewCase(caseId, {
        reviewer_id: "reporting_user",
        reviewer_role: "REPORTING_STAFF",
        decision: "APPROVE",
        comments: "Case reviewed and approved for reporting.",
      });
      if (normalizeStatus((response?.data || response)?.status) === "APPROVE") demo.complete("review");
      setReviewRecord(response?.data || response);
      await loadWorkspace({ showLoading: false });
      setMessage("Human review approval saved.");
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Unable to save human review.");
    } finally {
      setWorking(false);
      setOperation("");
    }
  }

  async function handleAttestation() {
      if (!attestationReady) {
      return;
    }

    try {
      setWorking(true);
      setOperation("attestation");
      setError("");
      setMessage("");

      const response = await attestation({
        case_reference: caseId,
        reviewer_id: "reporting_user",
        reviewer_role: "REPORTING_STAFF",
        attestation_status: "ATTESTED",
        comments: "Case reviewed and approved for reporting.",
      });

      const data = response?.data || response;

      if (data?.authorized !== true || data?.attestation_status !== "ATTESTED") {
        setMessage(data?.message || "Backend did not authorize attestation.");
        return;
      }
      const savedResponse = await persistAttestation(caseId, {
        reviewer_id: "reporting_user",
        reviewer_role: "REPORTING_STAFF",
        attestation_status: "ATTESTED",
        comments: "Case reviewed and approved for reporting.",
      });
      const savedAttestation = savedResponse?.data || savedResponse;
      if (normalizeStatus(savedAttestation?.status || savedAttestation?.attestation_status) !== "ATTESTED") {
        throw new Error("The backend did not confirm that the case was attested.");
      }
      demo.complete("attestation");
      await loadWorkspace({ showLoading: false });

      setMessage(
        "Case attested successfully. Immediate notification is now required."
      );
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to attest case."
      );
    } finally {
      setWorking(false);
      setOperation("");
    }
  }

  async function handlePrepareNotification() {
    try {
      setWorking(true);
      setOperation("notification");
      setError("");
      setMessage("");

      if (!attested) return;
      const response = await recordImmediateNotification(caseId, {
        notification_time: new Date().toISOString(),
        reporting_user: "SIGNAL Reporting User",
        notification_method: "PHONE",
        status: "COMPLETED",
        notes: "Phone notification recorded.",
      });
      demo.complete("notification");
      setNotificationRecord(response?.data || response);
      await loadWorkspace({ showLoading: false });
      setNotificationOpen(false);

      setMessage(
        "Immediate notification recorded. The case can now proceed to the Texas reporting form."
      );
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to prepare immediate notification."
      );
    } finally {
      setWorking(false);
      setOperation("");
    }
  }

  function goToReportingForm() {
    navigate(`${casePath}/reporting-form`);
  }

  function updateReportField(key, value) {
    setReportFields((previous) => ({
      ...previous,
      [key]: value,
    }));
  }

  if (loading) {
    return (
      <div className="case-workspace-page">
        <SignalLoading title="Loading Case" message="Retrieving case details, reportability, validation, and workflow status." />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="case-workspace-page">
        <div className="case-error-card">
          <h2>Case unavailable</h2>
          <p>{error || "The requested case was not found."}</p>
          <button onClick={() => navigate(routePatientId ? `/patients/${encodeURIComponent(routePatientId)}` : "/cases")}>
            {routePatientId ? "Back to Patient" : "Back to Cases"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="case-workspace-page">
      <header className="case-header">
        <div>
          <button
            className="case-back"
            onClick={() => navigate(patientPath)}
          >
            ← {patientId ? "Patient" : "Cases"}
          </button>

          <div className="case-kicker">CASE WORKSPACE</div>

          <h1>
            {patient.first_name || ""}{" "}
            {patient.last_name || ""}
          </h1>

          <p>
            Review, validate and authorize this reportable measles
            case before public-health reporting.
          </p>
        </div>

        <div className="case-header-right">
          <span className="case-status">
            {caseData.status || "NEEDS_REVIEW"}
          </span>

          <span className="case-jurisdiction">
            {caseData.jurisdiction || "TX"}
          </span>
        </div>
      </header>

      {(error || message) && (
        <div
          className={`case-message ${
            error ? "error" : "success"
          }`}
        >
          {error || message}
        </div>
      )}

      {working && operation && <SignalLoading
        title={operation === "validation" ? "Validating Case" : operation === "review" ? "Recording Human Review" : operation === "attestation" ? "Recording Attestation" : "Recording Immediate Notification"}
        message={operation === "validation" ? "Checking required reporting information and submission readiness." : operation === "review" ? "Saving the case review decision." : operation === "attestation" ? "Requesting and recording the reporting attestation." : "Recording the case notification details."}
      />}

      <main className="case-layout">
        <section className="case-main">
          <div className="patient-context">
            <div>
              <span>MRN</span>
              <strong>
                {patient.source_patient_id ||
                  patient.patient_id ||
                  "Not available"}
              </strong>
            </div>

            <div>
              <span>DOB</span>
              <strong>
                {patient.date_of_birth || "Not available"}
              </strong>
            </div>

            <div>
              <span>DISEASE</span>
              <strong>{caseData.disease}</strong>
            </div>

            <div>
              <span>RULE</span>
              <strong>{caseData.rule_id || "Not available"}</strong>
            </div>

            <div>
              <span>CASE ID</span>
              <strong className="case-id">
                {caseData.case_id}
              </strong>
            </div>
          </div>

          <section className="workflow-card">
            <div className="workflow-header">
              <div>
                <span className="card-kicker">CASE JOURNEY</span>
                <h2>Reporting Workflow</h2>
              </div>
            </div>

            <div className="workflow-stepper">
              {WORKFLOW_STEPS.map((step, index) => {
                let complete = false;
                let active = false;

                if (step.key === "reportability") {
                  complete = isReportable;
                }

                if (step.key === "case") {
                  complete = Boolean(caseData.case_id);
                }

                if (step.key === "validation") {
                  complete = validationReady;
                  active = !complete;
                }

                if (step.key === "review") {
                  complete = reviewApproved;
                  active =
                    validationReady && !reviewApproved;
                }

                if (step.key === "attestation") {
                  complete = attested;
                  active =
                    reviewApproved && !attested;
                }

                if (step.key === "notification") {
                  complete = notificationComplete;
                  active =
                    attested && !notificationComplete;
                }

                if (step.key === "reporting") {
                  complete = reportingReady;
                  active = notificationComplete;
                }

                return (
                  <React.Fragment key={step.key}>
                    <div
                      className={`workflow-item ${
                        complete ? "complete" : ""
                      } ${active ? "active" : ""}`}
                    >
                      <div className="workflow-circle">
                        {complete ? "✓" : index + 1}
                      </div>

                      <span>{step.label}</span>
                    </div>

                    {index < WORKFLOW_STEPS.length - 1 && (
                      <div
                        className={`workflow-line ${
                          complete ? "complete" : ""
                        }`}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </section>

          <section className="summary-grid">
            <div className="summary-card">
              <span>REPORTABILITY</span>
              <strong className={isReportable ? "green" : "warning"}>
                {reportabilityPending ? "Reportability Decision Pending" : caseData.reportability_decision || "Not available"}
              </strong>
              <small>
                Rule: {caseData.rule_id || "Not available"}
              </small>
            </div>

            <div className="summary-card">
              <span>JURISDICTION</span>
              <strong>
                {caseData.jurisdiction || "Not available"}
              </strong>
              <small>
                {caseData.jurisdiction_status ||
                  "Not available"}
              </small>
            </div>

            <div className="summary-card">
              <span>CASE STATUS</span>
              <strong>{caseData.status}</strong>
              <small>
                Updated{" "}
                {caseData.updated_at
                  ? new Date(
                      caseData.updated_at
                    ).toLocaleString()
                  : "Not available"}
              </small>
            </div>
          </section>

          <section className="case-card deadline-card">
            <div className="card-header">
              <div>
                <span className="card-kicker">CALCULATED BY SIGNAL</span>
                <h2>Reporting Deadline</h2>
              </div>
              <span className={`review-state ${deadlineState === "DEADLINE CALCULATED" ? "approved" : ""}`}>
                {deadlineLoading ? "CALCULATING" : deadlineState}
              </span>
            </div>
            <div className="deadline-content">
              {deadlineValue ? (
                <dl className="deadline-details">
                  <div><dt>Deadline</dt><dd>{deadlineDateLabel(deadlineValue)}</dd></div>
                  {(deadlineCalculation?.event_time || caseEventTime(caseData)) && <div><dt>Event time</dt><dd>{deadlineDateLabel(deadlineCalculation?.event_time || caseEventTime(caseData))}</dd></div>}
                  <div><dt>Rule</dt><dd>{deadlineCalculation?.rule_id || caseData.rule_id || "Not available"}</dd></div>
                  <div><dt>Disease</dt><dd>{deadlineCalculation?.disease || caseData.disease || "Not available"}</dd></div>
                  <div><dt>Jurisdiction</dt><dd>{deadlineCalculation?.jurisdiction || caseData.jurisdiction || "Not available"}</dd></div>
                  <div><dt>Status</dt><dd className={`deadline-status ${escalationStatus === "OVERDUE" ? "overdue" : escalationStatus === "UPCOMING" ? "warning" : "normal"}`}>
                    {escalationStatus === "OVERDUE" ? "Overdue" : escalationStatus === "UPCOMING" ? "Warning" : escalationStatus === "WITHIN_WINDOW" ? "Normal" : deadlineCalculation?.urgency || caseData.severity || "Not evaluated"}
                  </dd></div>
                  {(deadlineEscalation?.minutes_remaining ?? deadlineCalculation?.minutes_remaining) !== undefined && <div><dt>Time remaining</dt><dd>{deadlineEscalation?.minutes_remaining ?? deadlineCalculation?.minutes_remaining} minutes</dd></div>}
                  {deadlineEscalation?.message && <div className="deadline-message"><dt>Agent message</dt><dd>{deadlineEscalation.message}</dd></div>}
                </dl>
              ) : (
                <p className="deadline-empty">{deadlineState === "DEADLINE UNAVAILABLE" ? "Deadline cannot be calculated yet" : "Not calculated"}</p>
              )}
              {deadlineError && <p className="deadline-error">{deadlineCalculation?.deadline ? "Deadline escalation could not be completed." : "Reporting deadline could not be calculated."}<span>{deadlineError}</span></p>}
              <button className="outline-button" disabled={deadlineLoading || !caseEventTime(caseData) || !caseData.disease || !caseData.jurisdiction} onClick={handleCalculateDeadline}>
                {deadlineLoading ? "Calculating…" : "Calculate Deadline"}
              </button>
              <details className="deadline-technical">
                <summary>Technical Details</summary>
                <pre>{JSON.stringify({ calculation_response: deadlineCalculation, escalation_response: deadlineEscalation, persisted_case_deadline: caseData.deadline || null, persisted_severity: caseData.severity || null }, null, 2)}</pre>
              </details>
            </div>
          </section>

          <section className="case-card">
            <div className="card-header">
              <div>
                <span className="card-kicker">
                  SMART FIELD POPULATION
                </span>
                <h2>Reporting Data</h2>
              </div>

              <button
                className="small-button"
                disabled={working}
                onClick={saveCase}
              >
                Save
              </button>
            </div>

            <div className="field-grid">
              <label>
                <span>Facility Name</span>
                <input
                  value={facility.name || ""}
                  onChange={(e) =>
                    setFacility({
                      ...facility,
                      name: e.target.value,
                    })
                  }
                  placeholder="Facility name"
                />
              </label>

              <label>
                <span>Provider Name</span>
                <input
                  value={provider.name || ""}
                  onChange={(e) =>
                    setProvider({
                      ...provider,
                      name: e.target.value,
                    })
                  }
                  placeholder="Provider name"
                />
              </label>

              <label>
                <span>Provider Phone</span>
                <input
                  value={provider.phone || ""}
                  onChange={(e) =>
                    setProvider({
                      ...provider,
                      phone: e.target.value,
                    })
                  }
                  placeholder="Provider phone"
                />
              </label>

              <label>
                <span>Reported By</span>
                <input
                  value={reportFields["reporting.reported_by"] || reportFields.reported_by || ""}
                  onChange={(e) =>
                    updateReportField(
                      "reporting.reported_by",
                      e.target.value
                    )
                  }
                  placeholder="Reporting staff"
                />
              </label>
            </div>
          </section>

          <section className="case-card validation-card">
            <div className="card-header">
              <div>
                <span className="card-kicker">VALIDATION</span>
                <h2>Case Validation</h2>
              </div>

              <span
                className={`validation-badge ${
                  validationReady ? "valid" : "invalid"
                }`}
              >
                {validationState}
              </span>
              <button className="small-button" disabled={working || !isReportable} onClick={runValidation}>
                {working ? "Working..." : "Validate Case Again"}
              </button>
            </div>

            <div className="validation-content">
              {validationReady ? (
                <div className="validation-success">
                  <div className="validation-icon">✓</div>
                  <div>
                    <strong>
                      Required reporting information is complete.
                    </strong>
                    <p>
                      The case can proceed to human review.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="validation-warning">
                  <div className="validation-icon">!</div>
                  <div>
                    <strong>{reportabilityPending || !isReportable
                      ? "Reportability decision is not finalized."
                      : missingFields.length
                        ? `${missingFields.length} required item${missingFields.length === 1 ? "" : "s"} need attention.`
                        : "Backend validation has not marked this case ready."}</strong>
                    <p>{reportabilityPending || !isReportable
                      ? "Validation and review stay locked until the case is classified as reportable."
                      : missingFields.length
                        ? "Complete the backend-reported information, save it, then validate the case again."
                        : "Check the backend validation result and resolve its issues before human review."}</p>
                  </div>

                  <button
                    className="outline-button"
                    onClick={() => setMissingOpen(true)}
                  >
                    {missingFields.length ? "View Missing Information" : "View Validation Details"}
                  </button>
                </div>
              )}
            </div>
          </section>

          <section className="case-card">
            <div className="card-header">
              <div>
                <span className="card-kicker">
                  HUMAN REVIEW
                </span>
                <h2>Review Decision</h2>
              </div>

              <span
                className={`review-state ${
                  reviewApproved ? "approved" : ""
                }`}
              >
                {reviewApproved ? "APPROVED" : "PENDING"}
              </span>
            </div>

            <p className="review-description">
              A reporting user must review the assembled case before
              attestation.
            </p>

            <button
              className="primary-action"
              disabled={!validationReady || working || reviewApproved}
              onClick={handleReview}
            >
              {reviewApproved
                ? "Human Review Approved"
                : "Approve Human Review"}
            </button>
          </section>

          <section className="case-card">
            <div className="card-header">
              <div>
                <span className="card-kicker">
                  ATTESTATION
                </span>
                <h2>Authorize Reporting</h2>
              </div>

              <span
                className={`review-state ${
                  attested ? "approved" : ""
                }`}
              >
                {attested ? "ATTESTED" : "LOCKED"}
              </span>
            </div>

            <p className="review-description">
              Attestation confirms that the reportable case has been
              reviewed and is authorized for reporting.
            </p>

            <button
              className="primary-action"
              disabled={
                !attestationReady || working || attested
              }
              onClick={handleAttestation}
            >
              {attested
                ? "Case Attested"
                : "Attest Case"}
            </button>
          </section>

          <section className="case-card notification-card">
            <div className="card-header">
              <div>
                <span className="card-kicker">
                  TEXAS REPORTING
                </span>
                <h2>Immediate Notification</h2>
              </div>

              <span
                className={`review-state ${
                  notificationComplete ? "approved" : ""
                }`}
              >
                {notificationComplete
                  ? "RECORDED"
                  : "REQUIRED"}
              </span>
            </div>

            <p className="review-description">
              Suspected measles requires immediate public-health
              notification. Record the notification before continuing
              to the reporting form.
            </p>

            {!attested && !notificationComplete && <p className="review-description">Locked until successful backend attestation.</p>}

            {attested && !notificationComplete && (
              <button
                className="primary-action notification-action"
                disabled={working}
                onClick={() => setNotificationOpen(true)}
              >
                Record Immediate Notification
              </button>
            )}

            {attested && notificationComplete && (
              <button
                className="primary-action"
                onClick={goToReportingForm}
              >
                Continue to Texas Reporting Form →
              </button>
            )}
          </section>
          <details className="case-card technical-state">
            <summary>Technical Case State</summary>
            <dl>
              {[["Status", caseData.status], ["Reportability decision", caseData.reportability_decision], ["Final decision", caseData.final_decision], ["Jurisdiction status", caseData.jurisdiction_status], ["Reportability evidence", caseData.reportability_evidence_status], ["Validation", validationState]].map(([label, value]) => (
                <div key={label}><dt>{label}</dt><dd>{value || "Not available"}</dd></div>
              ))}
              <div><dt>Missing report fields</dt><dd>{JSON.stringify(caseData.missing_report_fields || [])}</dd></div>
              <div><dt>Required missing fields</dt><dd>{JSON.stringify(caseData.required_missing_fields || [])}</dd></div>
              <div><dt>Backend validation</dt><dd>{JSON.stringify(validationRecord || {})}</dd></div>
            </dl>
          </details>
        </section>

        <aside className="case-sidebar">
          <div className="side-card">
            <span className="side-label">PATIENT</span>

            <h3>
              {patient.first_name || ""}{" "}
              {patient.last_name || ""}
            </h3>

            <div className="side-row">
              <span>MRN</span>
              <strong>
                {patient.source_patient_id ||
                  patient.patient_id ||
                  "—"}
              </strong>
            </div>

            <div className="side-row">
              <span>DOB</span>
              <strong>
                {patient.date_of_birth || "—"}
              </strong>
            </div>

            <div className="side-row">
              <span>Sex</span>
              <strong>{patient.sex || "—"}</strong>
            </div>
          </div>

          <div className="side-card">
            <span className="side-label">CASE</span>

            <div className="side-row">
              <span>Disease</span>
              <strong>{caseData.disease}</strong>
            </div>

            <div className="side-row">
              <span>Jurisdiction</span>
              <strong>{caseData.jurisdiction}</strong>
            </div>

            <div className="side-row">
              <span>Rule</span>
              <strong>{caseData.rule_id || "—"}</strong>
            </div>

          </div>

          <div className="side-card next-card">
            <span className="side-label">NEXT STEP</span>

            {!validationReady && (
              <>
                <strong>Complete missing information</strong>
                <p>
                  Resolve the required reporting fields before
                  review.
                </p>

                <button
                  onClick={() => setMissingOpen(true)}
                >
                  View Missing Information
                </button>
              </>
            )}

            {validationReady && !reviewApproved && (
              <>
                <strong>Human review</strong>
                <p>
                  Review the assembled case and approve it.
                </p>
              </>
            )}

            {reviewApproved && !attested && (
              <>
                <strong>Attestation</strong>
                <p>
                  Authorize the case for reporting.
                </p>
              </>
            )}

            {attested && !notificationComplete && (
              <>
                <strong>Immediate notification</strong>
                <p>
                  Record the Texas measles notification.
                </p>
              </>
            )}

            {notificationComplete && (
              <>
                <strong>Reporting form</strong>
                <p>
                  Continue to the Texas measles reporting form.
                </p>

                <button onClick={goToReportingForm}>
                  Continue →
                </button>
              </>
            )}
          </div>
        </aside>
      </main>

      {missingOpen && (
        <div
          className="drawer-overlay"
          onClick={() => setMissingOpen(false)}
        >
          <aside
            className="missing-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-header">
              <div>
                <span>MISSING INFORMATION</span>
                <h2>Complete Required Fields</h2>
              </div>

              <button
                onClick={() => setMissingOpen(false)}
              >
                ×
              </button>
            </div>

            {missingFields.length === 0 ? (
              <div className="drawer-empty">
                No missing reporting fields were returned by the
                backend.
              </div>
            ) : (
              <div className="missing-list">
                {groupedMissingFields.map((group) => (
                  <section className="missing-field-group" key={group.key}>
                    <h3>{group.label}</h3>
                    {group.fields.map((field) => (
                      <label className="missing-field" key={field}>
                        <span>{missingFieldLabel(field)} <b aria-hidden="true">*</b></span>
                        {missingFieldControl(field, getMissingFieldValue(field), (value) => setMissingFieldValue(field, value))}
                        <small>Required for reporting</small>
                      </label>
                    ))}
                  </section>
                ))}
              </div>
            )}

            {error && <div className="missing-drawer-error" role="alert">{error}</div>}

            <div className="drawer-footer">
              <button
                className="outline-button"
                disabled={working}
                onClick={() => setMissingOpen(false)}
              >
                Close
              </button>

              <button
                className="primary-action"
                disabled={working}
                onClick={async () => {
                  const saved = await saveCase();
                  if (saved) setMissingOpen(false);
                }}
              >
                {working ? "Saving..." : "Save Information"}
              </button>
            </div>
          </aside>
        </div>
      )}

      {notificationOpen && (
        <div
          className="drawer-overlay"
          onClick={() => setNotificationOpen(false)}
        >
          <aside
            className="notification-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-header">
              <div>
                <span>IMMEDIATE NOTIFICATION</span>
                <h2>Record Texas Measles Notification</h2>
              </div>

              <button
                onClick={() => setNotificationOpen(false)}
              >
                ×
              </button>
            </div>

            <div className="notification-warning">
              <strong>Immediate reporting required</strong>
              <p>
                Record the phone notification to the appropriate
                public-health authority before proceeding with the
                reporting package.
              </p>
            </div>

            <div className="notification-detail">
              <label>
                Reporting Method
                <input value="PHONE" readOnly />
              </label>

              <label>
                Reporting User
                <input
                  value="SIGNAL Reporting User"
                  readOnly
                />
              </label>

              <label>
                Case
                <input value={caseId} readOnly />
              </label>
            </div>

            <div className="drawer-footer">
              <button
                className="outline-button"
                onClick={() =>
                  setNotificationOpen(false)
                }
              >
                Cancel
              </button>

              <button
                className="primary-action"
                disabled={working}
                onClick={handlePrepareNotification}
              >
                {working
                  ? "Recording..."
                  : "Record Notification"}
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
