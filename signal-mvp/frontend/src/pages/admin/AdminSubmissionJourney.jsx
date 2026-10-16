
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FileCheck2,
  HeartPulse,
  XCircle,
  UserRound,
} from "lucide-react";
import { SignalLoading } from "../../components/ui/SignalLoading.jsx";
import "../../styles/AdminSubmissionJourney.css";
import { cleanPatientName } from "../../utils/patientNames.js";
import {
  getAdminSubmission,
  getAdminQueueCase,
  getAdminSubmissions,
  simulateAdminDemoSubmission,
} from "../../services/adminService.js";

const STAGES = [
  {
    id: "ADMIN",
    label: "AUTHORIZE",
    subtitle: "SIGNAL Admin · Confirm authorization to process clinical data",
  },
  {
    id: "PREPARE",
    label: "PREPARE",
    subtitle: "SIGNAL · Detect potential cases, duplicates, and missed candidates",
  },
  {
    id: "VALIDATE",
    label: "VALIDATE",
    subtitle: "SIGNAL + rules · Check reportability, conflicting evidence, required data, and jurisdiction",
  },
  {
    id: "EICR",
    label: "GENERATE",
    subtitle: "eICR service · Populate and validate the reporting form",
  },
  {
    id: "AIMS_OUTBOUND",
    label: "TRANSPORT",
    subtitle: "APHL AIMS (simulated) · Send through the configured exchange; handle delivery failures safely",
  },
  {
    id: "SIGNAL_RECEIVE",
    label: "RECEIVE",
    subtitle: "AIMS / SIGNAL (simulated) · Track acknowledgements and responses",
  },
  {
    id: "PHA_REVIEW",
    label: "PHA REVIEW",
    subtitle: "Public health agency · Track review status",
  },
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

  if (directName) return cleanPatientName(directName);

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

  return cleanPatientName([firstName, lastName].filter(Boolean).join(" ")) || "—";
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

  const [resolved, setResolved] = useState(() => ({
    submission: location.state?.submission ?? null,
    caseData: location.state?.caseData ?? null,
  }));
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadSubmission() {
      setLoading(true);
      setLoadError("");

      try {
        // Older Admin builds used DEMO-{case_id} as a local reference without
        // creating a submission. Complete that authorized PHA handoff here.
        if (routeSubmissionId?.startsWith("DEMO-")) {
          const caseId = routeSubmissionId.slice("DEMO-".length);
          const response = await simulateAdminDemoSubmission(caseId);
          if (String(response?.status ?? "").toUpperCase() !== "SUBMITTED" || !response?.submission_id) {
            throw new Error("The local PHA submission was not recorded.");
          }
          const caseData = await getAdminQueueCase(caseId);
          if (!cancelled) {
            navigate(`/admin/submission-journey/${encodeURIComponent(response.submission_id)}`, {
              replace: true,
              state: { submission: response, caseData },
            });
          }
          return;
        }

        if (location.state?.submission && location.state?.caseData) {
          if (!cancelled) {
            setResolved({
              submission: location.state.submission,
              caseData: location.state.caseData,
            });
          }
          return;
        }

        const result = await getAdminSubmissions();
        const submission = (result.items ?? []).find(
          (item) => item.submission_id === routeSubmissionId
        );
        if (!submission) throw new Error("No saved submission matches this reference.");

        let caseData;
        try {
          caseData = await getAdminQueueCase(submission.case_id);
        } catch {
          // Saved submissions can outlive queue records. Keep View usable from
          // the Submissions page by building the case summary from its row.
          caseData = {
            ...submission,
            case_id: submission.case_id,
            patient: submission.patient ?? {
              name: submission.patient_name,
              patient_id: submission.patient_id,
            },
            condition: submission.condition ?? submission.disease,
            jurisdiction: submission.jurisdiction,
            rule_id: submission.rule_id,
          };
        }
        if (!cancelled) setResolved({ submission, caseData });
      } catch (error) {
        if (!cancelled) setLoadError(error?.message || "Unable to load the saved submission.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSubmission();
    return () => { cancelled = true; };
  }, [location.state, navigate, routeSubmissionId]);

  useEffect(() => {
    if (!routeSubmissionId || routeSubmissionId.startsWith("DEMO-")) return undefined;

    let cancelled = false;
    let refreshing = false;

    const refreshSubmission = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const latest = await getAdminSubmission(routeSubmissionId);
        if (!cancelled) {
          setResolved((current) => ({ ...current, submission: latest }));
        }
      } catch {
        // Keep the last loaded submission visible if a refresh is temporarily unavailable.
      } finally {
        refreshing = false;
      }
    };

    refreshSubmission();
    const intervalId = window.setInterval(refreshSubmission, 5000);
    window.addEventListener("focus", refreshSubmission);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", refreshSubmission);
    };
  }, [routeSubmissionId]);

  const submission = resolved.submission;
  const caseData = resolved.caseData;

  if (loading) {
    return (
      <div className="admin-journey-page">
        <SignalLoading title="Loading Submission" message="Retrieving the saved submission from SIGNAL." />
      </div>
    );
  }

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
          <h2>Submission not found</h2>
          <p>{loadError || "This reference has no saved submission record."}</p>
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

  const conditionValue =
    getField(submission, "condition") ??
    getField(caseData, "condition", "disease_name", "disease") ??
    "—";
  const condition = conditionValue && typeof conditionValue === "object"
    ? getField(conditionValue, "display", "name", "text", "label") ?? display(conditionValue)
    : conditionValue;

  const jurisdiction =
    getField(submission, "jurisdiction") ??
    getField(caseData, "jurisdiction", "state") ??
    "—";

  const actualSubmissionId =
    getField(submission, "submissionId", "submission_id") ??
    routeSubmissionId ??
    "—";

  const submittedAt =
    getField(submission, "submittedAt", "submitted_at", "created_at") ?? "—";

  const reportingMode =
    getField(submission, "mode", "reportingMode", "reporting_mode", "submission_mode") ??
    "—";

  const reportingRule =
    getField(caseData, "rule_id", "reportingRule", "reporting_rule") ?? "—";

  const deadline =
    getField(caseData, "deadline", "reportingDeadline",
      "reporting_deadline") ?? "—";

  const healthDepartment = getField(caseData, "healthDepartment", "health_department")
    ?? (jurisdiction === "TX" ? "DSHS" : "Public Health Authority");
  const submissionStatus = String(submission.status ?? "").toUpperCase();
  const destination = getField(submission, "destination") ?? "MOCK_PHA";
  const acknowledgement = submission.acknowledgement ?? {};
  const phaDecision = submission.latest_pha_decision ?? {};
  const phaDecisionValue = String(phaDecision.decision ?? "").toUpperCase();
  const isAccepted = phaDecisionValue === "ACCEPTED";
  const isRejected = phaDecisionValue === "REJECTED";
  const isAcknowledged = submissionStatus === "ACKNOWLEDGED"
    || String(acknowledgement.status ?? "").toUpperCase() === "ACKNOWLEDGED";
  const reviewComplete = isAcknowledged || isAccepted || isRejected;
  const journeyStatus = isRejected ? "REJECTED" : isAccepted ? "ACCEPTED" : submissionStatus;
  const currentStageIndex = reviewComplete ? STAGES.length : STAGES.length - 1;
  const progressStageIndex = Math.min(currentStageIndex, STAGES.length - 1);

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
          <strong>{display(actualSubmissionId)}</strong>
          <small>{display(destination)} submission</small>
        </div>

        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>PATIENT</span>
            <UserRound size={17} />
          </div>
          <strong>{display(patientName)}</strong>
          <small>{display(patientId)}</small>
        </div>

        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>CONDITION</span>
            <HeartPulse size={17} />
          </div>
          <strong>{display(condition)}</strong>
          <small>Case {display(actualCaseId)}</small>
        </div>

        <div className="journey-kpi">
          <div className="journey-kpi-heading">
            <span>SUBMISSION STATUS</span>
            <Clock3 size={17} />
          </div>
          <strong>{formatLabel(journeyStatus)}</strong>
          <small>{isRejected ? "PHA rejected this report" : isAccepted ? "PHA accepted this report" : isAcknowledged ? "PHA acknowledgement received" : "Awaiting PHA acknowledgement"}</small>
        </div>
      </div>

      <section className="journey-person-card">
        <div className="journey-person-heading">
          <UserRound size={18} />
          <div>
            <span className="journey-section-label">PATIENT DETAILS</span>
            <h2>{display(patientName)}</h2>
          </div>
        </div>

        <div className="journey-person-fields">
          <div>
            <span>Patient ID</span>
            <strong>{display(patientId)}</strong>
          </div>
          <div>
            <span>Case ID</span>
            <strong>{display(actualCaseId)}</strong>
          </div>
          <div>
            <span>Condition</span>
            <strong>{display(condition)}</strong>
          </div>
          <div>
            <span>Jurisdiction</span>
            <strong>{display(jurisdiction)}</strong>
          </div>
        </div>
      </section>

      <section className="journey-status-card">
        <div>
          <h2>Reporting Workflow</h2>
          <p>
            {isRejected
              ? "PHA rejected this report; the review stage is complete."
              : isAccepted
              ? "PHA accepted this report; the review stage is complete."
              : isAcknowledged
                ? "PHA acknowledgement received; all timeline stages are complete."
              : "The report is in the PHA queue; awaiting its acknowledgement."}
          </p>
        </div>

      </section>

      <section className="journey-section">
        <SectionHeading>Submission Timeline</SectionHeading>

        <div className="journey-track-wrapper">
          <div
            className={`journey-track ${isAcknowledged ? "" : "is-simulated"}`}
            style={{
              "--journey-progress": `${
                (progressStageIndex / STAGES.length) * 100
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
                    index === STAGES.length - 1 && isRejected ? "failed" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  key={stage.id}
                >
                  <div className="journey-stage-circle">
                    {index === STAGES.length - 1 && isRejected
                      ? <XCircle size={18} />
                      : completed ? <CheckCircle2 size={14} /> : index + 1}
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
          <Detail label="Submission Status" value={formatLabel(journeyStatus)} />
          {phaDecision.decision && (
            <Detail label="PHA Review Decision" value={`${formatLabel(phaDecision.decision)}${submission.pha_decision_count > 1 ? ` (${submission.pha_decision_count} recorded)` : ""}`} />
          )}
          {phaDecision.reviewer && <Detail label="PHA Reviewer" value={phaDecision.reviewer} />}
          {phaDecision.created_at && <Detail label="Decision Recorded At" value={formatDateTime(phaDecision.created_at)} />}
          <Detail label="PHA Acknowledgement" value={isAcknowledged ? "Received" : "Pending"} />
          {acknowledgement.acknowledgement_id && (
            <Detail label="Acknowledgement ID" value={acknowledgement.acknowledgement_id} />
          )}
          {acknowledgement.received_at && (
            <Detail label="Received At" value={formatDateTime(acknowledgement.received_at)} />
          )}
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
              <span>{isAcknowledged ? "PHA acknowledgement: received" : "PHA acknowledgement: pending"}</span>
            </div>
            <div>
              <CalendarClock size={14} />
              <span>Follow-up: pending</span>
            </div>
          </div>
        </div>

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
