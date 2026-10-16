
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FileCheck2,
  FileText,
  HeartPulse,
  MapPin,
  Send,
  UserRound,
} from "lucide-react";
import "../../styles/AdminSubmissionJourney.css";

const STAGES = [
  { id: "ADMIN", label: "AUTHORIZE", subtitle: "SIGNAL Admin" },
  { id: "PREPARE", label: "PREPARE", subtitle: "SIGNAL" },
  { id: "EICR", label: "GENERATE", subtitle: "eICR" },
  { id: "AIMS_OUTBOUND", label: "TRANSPORT", subtitle: "APHL AIMS" },
  { id: "DSHS", label: "RECEIVE", subtitle: "Texas DSHS" },
  { id: "NEDSS", label: "PROCESS", subtitle: "NEDSS" },
  { id: "PHA_REVIEW", label: "PHA REVIEW", subtitle: "Public Health" },
  { id: "RESPONSE", label: "RESPONSE", subtitle: "RR" },
  { id: "AIMS_RETURN", label: "RETURN", subtitle: "APHL AIMS" },
  { id: "SIGNAL_RECEIVE", label: "RECEIVE", subtitle: "SIGNAL" },
  { id: "FOLLOW_UP", label: "FOLLOW-UP", subtitle: "SIGNAL" },
];

function getField(object, ...keys) {
  for (const key of keys) {
    const value = object?.[key];

    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return null;
}

function getPatientName(data) {
  const patient =
    data?.patient ??
    data?.patientDetails ??
    data?.patient_details ??
    {};

  const directName = getField(
    data,
    "patientName",
    "patient_name",
    "full_name",
    "patient_full_name"
  );

  if (directName) return directName;

  const nestedName = getField(
    patient,
    "full_name",
    "patient_name",
    "name",
    "display"
  );

  if (nestedName) return nestedName;

  const firstName =
    getField(patient, "first_name") ??
    getField(data, "first_name", "patient_first_name");

  const lastName =
    getField(patient, "last_name") ??
    getField(data, "last_name", "patient_last_name");

  return [firstName, lastName].filter(Boolean).join(" ") || "—";
}

function display(value) {
  if (value === null || value === undefined || value === "") return "—";

  if (typeof value === "boolean") return value ? "Yes" : "No";

  if (Array.isArray(value)) {
    return value.length ? value.map(display).join(", ") : "—";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function formatDateTime(value) {
  if (!value || value === "—") return "—";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString();
}

function formatLabel(value) {
  return String(value ?? "—")
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function PanelRow({ label, value }) {
  return (
    <div className="journey-panel-row">
      <span>{label}</span>
      <strong>{display(value)}</strong>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{display(value)}</strong>
    </div>
  );
}

function SectionHeading({ children }) {
  return (
    <div className="journey-section-heading">
      <h2>{children}</h2>
    </div>
  );
}

export default function AdminSubmissionJourney() {
  const location = useLocation();
  const navigate = useNavigate();
  const { submissionId: routeSubmissionId } = useParams();

  const submission = location.state?.submission;
  const caseData = location.state?.caseData;

  if (!submission || !caseData) {
    return (
      <div className="admin-journey-page">
        <header className="admin-journey-header">
          <button
            type="button"
            className="journey-back-button"
            onClick={() => navigate("/admin/queue")}
          >
            <ArrowLeft size={15} />
            Back to Queue
          </button>

          <div className="journey-title-row">
            <div>
              <h1>Submission Journey</h1>
              <p>Submission reference: {routeSubmissionId}</p>
            </div>
          </div>
        </header>

        <section className="journey-alert-card">
          <h2>Submission data unavailable</h2>
          <p>
            Open Immediate Reporting Review from the existing case list
            and use Authorize &amp; Submit to pass the selected patient
            and case data to this page.
          </p>
        </section>
      </div>
    );
  }

  const patient = caseData.patient ??
    caseData.patientDetails ??
    caseData.patient_details ??
    {};

  const patientName = getPatientName({
    ...caseData,
    patientName: getField(
      submission,
      "patientName",
      "patient_name"
    ) ?? getField(
      caseData,
      "patientName",
      "patient_name"
    ),
  });

  const patientId =
    getField(submission, "patientId", "patient_id") ??
    getField(caseData, "patientId", "patient_id") ??
    getField(patient, "id", "patient_id") ??
    "—";

  const actualCaseId =
    getField(submission, "caseId", "case_id") ??
    getField(caseData, "caseId", "case_id") ??
    "—";

  const condition =
    getField(submission, "condition") ??
    getField(caseData, "condition", "disease_name", "disease") ??
    "—";

  const jurisdiction =
    getField(submission, "jurisdiction") ??
    getField(caseData, "jurisdiction", "state") ??
    "—";

  const actualSubmissionId =
    getField(submission, "submissionId", "submission_id") ??
    routeSubmissionId ??
    "—";

  const submittedAt =
    getField(submission, "submittedAt", "submitted_at") ?? "—";

  const reportingMode =
    getField(submission, "mode", "reportingMode", "reporting_mode") ??
    "—";

  const reportingRule =
    getField(caseData, "reportingRule", "reporting_rule") ?? "—";

  const deadline =
    getField(caseData, "deadline", "reportingDeadline",
      "reporting_deadline") ?? "—";

  const healthDepartment =
    getField(caseData, "healthDepartment", "health_department") ?? "—";

  // This is a simulated transport stage, not a real external transmission.
  const currentStageIndex = 3;

  const handleBack = () => navigate("/admin/queue");

  return (
    <div className="admin-journey-page">
      <header className="admin-journey-header">
        <button
          type="button"
          className="journey-back-button"
          onClick={handleBack}
        >
          <ArrowLeft size={15} />
          Back to Queue
        </button>

        <div className="journey-title-row">
          <div>
            <span className="journey-section-label">
              SIGNAL / ADMINISTRATOR
            </span>
            <h1>Submission Journey</h1>
            <p>
              Track the workflow for the selected reporting case.
            </p>
          </div>
        </div>
      </header>

      <div className="journey-kpis">
        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>SUBMISSION ID</span>
            <FileCheck2 size={17} />
          </div>
          <strong>{actualSubmissionId}</strong>
          <small>Local demo reference</small>
        </div>

        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>PATIENT</span>
            <UserRound size={17} />
          </div>
          <strong>{patientName}</strong>
          <small>{patientId}</small>
        </div>

        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>CONDITION</span>
            <HeartPulse size={17} />
          </div>
          <strong>{condition}</strong>
          <small>Case {actualCaseId}</small>
        </div>

        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>SUBMISSION STATUS</span>
            <Clock3 size={17} />
          </div>
          <strong>IN PROGRESS</strong>
          <small>No external receipt confirmed</small>
        </div>
      </div>

      <section className="journey-person-card">
        <div className="journey-person-heading">
          <UserRound size={18} />
          <div>
            <span className="journey-section-label">PATIENT DETAILS</span>
            <h2>{patientName}</h2>
          </div>
        </div>

        <div className="journey-person-fields">
          <div>
            <span>Patient ID</span>
            <strong>{patientId}</strong>
          </div>
          <div>
            <span>Case ID</span>
            <strong>{actualCaseId}</strong>
          </div>
          <div>
            <span>Condition</span>
            <strong>{condition}</strong>
          </div>
          <div>
            <span>Jurisdiction</span>
            <strong>{jurisdiction}</strong>
          </div>
        </div>
      </section>

      <section className="journey-status-card">
        <div>
          <h2>Reporting Workflow</h2>
          <p>
            Current demonstration stage: APHL AIMS transport.
          </p>
        </div>

      </section>

      <section className="journey-section">
        <SectionHeading>Submission Timeline</SectionHeading>

        <div className="journey-track-wrapper">
          <div
            className="journey-track is-simulated"
            style={{
              "--journey-progress": `${
                (currentStageIndex / (STAGES.length - 1)) * 100
              }%`,
            }}
          >
            {STAGES.map((stage, index) => {
              const completed = index < currentStageIndex;
              const current = index === currentStageIndex;

              return (
                <div
                  className={[
                    "journey-stage",
                    completed ? "completed" : "",
                    current ? "current" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  key={stage.id}
                >
                  <div className="journey-stage-circle">
                    {completed ? <CheckCircle2 size={14} /> : index + 1}
                  </div>
                  <div className="journey-stage-label">{stage.label}</div>
                  <div className="journey-stage-subtitle">
                    {stage.subtitle}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <p className="journey-simulation-note">
          SIMULATED WORKFLOW · No external system has been contacted.
        </p>
      </section>

      <div className="journey-grid">
        <section className="journey-panel">
          <SectionHeading>Submission Details</SectionHeading>

          <PanelRow label="Submission ID" value={actualSubmissionId} />
          <PanelRow label="Case ID" value={actualCaseId} />
          <PanelRow label="Patient" value={patientName} />
          <PanelRow label="Patient ID" value={patientId} />
          <PanelRow label="Condition" value={condition} />
          <PanelRow label="Jurisdiction" value={jurisdiction} />
          <PanelRow label="Reporting Mode" value={formatLabel(reportingMode)} />
          <PanelRow label="Submitted At" value={formatDateTime(submittedAt)} />
          <PanelRow label="Reporting Rule" value={reportingRule} />
          <PanelRow label="Deadline" value={formatDateTime(deadline)} />
        </section>

        <section className="journey-panel">
          <SectionHeading>Clinical Evidence</SectionHeading>

          <div className="journey-details-grid">
            {Object.entries(
              getField(caseData, "clinicalEvidence", "clinical_evidence") ?? {}
            ).map(([key, value]) => (
              <Detail key={key} label={formatLabel(key)} value={display(value)} />
            ))}

            {Object.entries(
              getField(caseData, "laboratoryEvidence", "laboratory_evidence") ?? {}
            ).map(([key, value]) => (
              <Detail key={`lab-${key}`} label={formatLabel(key)} value={display(value)} />
            ))}

            {Object.keys(
              getField(caseData, "clinicalEvidence", "clinical_evidence") ?? {}
            ).length === 0 &&
              Object.keys(
                getField(caseData, "laboratoryEvidence", "laboratory_evidence") ?? {}
              ).length === 0 && (
                <Detail label="Evidence" value="No evidence fields supplied" />
              )}
          </div>
        </section>
      </div>

      <section className="journey-response-card">
        <h2>Destination &amp; Acknowledgement</h2>
        <p>
          Destination details are shown for the selected case. These
          values do not confirm successful delivery.
        </p>

        <div className="journey-response-content">
          <Detail label="Jurisdiction" value={jurisdiction} />
          <Detail label="Health Department" value={healthDepartment} />
          <Detail label="Transport Status" value="Simulated" />
          <Detail label="External Acknowledgement" value="Not received" />
        </div>
      </section>

      <section className="journey-information-card">
        <div className="journey-information-copy">
          <h2>Next Action</h2>
          <p>
            Check the reporting status through your connected workflow
            before treating this case as externally acknowledged.
          </p>

          <div className="journey-requested-list">
            <div>
              <Clock3 size={14} />
              <span>External acknowledgement: not verified</span>
            </div>
            <div>
              <CalendarClock size={14} />
              <span>Follow-up: pending</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="journey-primary-button"
          onClick={handleBack}
        >
          <ArrowLeft size={14} />
          Back to Queue
        </button>
      </section>

      <section className="journey-followup-card">
        <div>
          <h2>Follow-up Tracking</h2>
          <p>
            Follow-up has not been executed by this static demonstration.
          </p>
        </div>

        <div className="journey-followup-status">
          <span className="followup-dot warning" />
          Pending
        </div>
      </section>
    </div>
  );
}
