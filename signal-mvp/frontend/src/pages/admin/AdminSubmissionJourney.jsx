import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { listFollowUps } from "../../api/followups.js";
import { getSubmissionAcknowledgement } from "../../api/submissions.js";
import { getAdminQueueCase, getAdminSubmission } from "../../services/adminService.js";
import "../../styles/AdminSubmissionJourney.css";

const text = (value, fallback = "Not available") => value === undefined || value === null || String(value).trim() === "" ? fallback : String(value);
const statusCode = (value) => String(value || "").trim().toUpperCase();
const isFailed = (value) => /FAILED|ERROR|REJECTED|REJECT|INVALID/i.test(String(value || ""));

function formatTimestamp(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
}

function isAcknowledgementComplete(acknowledgement) {
  const state = statusCode(acknowledgement?.status);
  return ["ACKNOWLEDGED", "RECEIVED", "SUCCESS", "COMPLETED", "ACCEPTED"].includes(state);
}

function OverviewField({ label, value }) {
  return <div className="asj-overview-field"><span>{label}</span><strong title={value ? String(value) : undefined}>{text(value)}</strong></div>;
}

function JourneyStage({ number, title, state }) {
  const marker = state === "complete" ? "✓" : state === "failed" ? "!" : state === "current" ? "•" : "•";
  const label = state === "complete" ? "Completed" : state === "failed" ? "Failed" : state === "current" ? "Current" : "Pending";
  return <article className={`asj-stage ${state}`}>
    <span className="asj-stage-number" aria-hidden="true">{number}</span>
    <h3>{title}</h3>
    <span className="asj-stage-state" aria-label={label}>{marker}</span>
  </article>;
}

function InformationField({ label, value, format = "text" }) {
  const display = format === "timestamp" ? formatTimestamp(value) : format === "date" ? formatDate(value) : text(value);
  return <div className="asj-info-field"><dt>{label}</dt><dd>{display}</dd></div>;
}

function responseValue(acknowledgement, keys) {
  const response = acknowledgement?.response;
  for (const key of keys) {
    if (acknowledgement?.[key] !== undefined && acknowledgement?.[key] !== null && acknowledgement[key] !== "") return acknowledgement[key];
    if (response && typeof response === "object" && response[key] !== undefined && response[key] !== null && response[key] !== "") return response[key];
  }
  return null;
}

export default function AdminSubmissionJourney() {
  const { submissionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [submission, setSubmission] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [acknowledgement, setAcknowledgement] = useState(null);
  const [followup, setFollowup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const record = await getAdminSubmission(submissionId);
        const caseId = record?.case_id || record?.case?.case_id;
        const [caseResult, acknowledgementResult, followupResult] = await Promise.allSettled([
          caseId ? getAdminQueueCase(caseId) : Promise.resolve(null),
          getSubmissionAcknowledgement(submissionId),
          listFollowUps({ search: submissionId, page_size: 100 }),
        ]);
        if (!active) return;
        setSubmission(record);
        setCaseData(caseResult.status === "fulfilled" ? caseResult.value?.data || caseResult.value : null);
        setAcknowledgement(acknowledgementResult.status === "fulfilled" ? acknowledgementResult.value?.data || acknowledgementResult.value : record?.acknowledgement || null);
        const followups = followupResult.status === "fulfilled" ? followupResult.value?.items || [] : [];
        const matchingFollowups = followups
          .filter((item) => item.submission_id === submissionId)
          .sort((left, right) => Date.parse(right.updated_at || right.created_at || 0) - Date.parse(left.updated_at || left.created_at || 0));
        setFollowup(matchingFollowups[0] || null);
        if (caseResult.status === "rejected") setError(caseResult.reason?.message || "Case details could not be loaded.");
        else if (followupResult.status === "rejected") setError(followupResult.reason?.message || "Follow-up information could not be loaded.");
      } catch (requestError) {
        if (active) setError(requestError?.message || "Submission information could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [submissionId]);

  const status = statusCode(submission?.status);
  const destination = submission?.destination;
  const warnings = Array.isArray(submission?.warnings) ? submission.warnings : [];
  const simulated = /MOCK_PHA|SIMULAT/i.test(String(destination || "")) || warnings.some((warning) => /MOCK_PHA|SIMULAT/i.test(String(warning)));
  const patient = submission?.patient || caseData?.patient || {};
  const patientName = patient.name || [patient.first_name, patient.last_name].filter(Boolean).join(" ");
  const caseId = submission?.case_id || caseData?.case_id;
  const condition = caseData?.condition || caseData?.clinical_evidence?.diagnosis || submission?.disease;
  const jurisdictionCode = caseData?.jurisdiction || submission?.jurisdiction;
  const jurisdiction = statusCode(jurisdictionCode) === "TX" ? "Texas" : jurisdictionCode;
  const reviewStatus = statusCode(caseData?.review_status);
  const attestationStatus = statusCode(caseData?.attestation_status);
  const adminReviewed = ["APPROVE", "APPROVED"].includes(reviewStatus) && attestationStatus === "ATTESTED";
  const acknowledgementComplete = isAcknowledgementComplete(acknowledgement);
  const submissionFailed = isFailed(status);
  const submissionComplete = ["SUBMITTED", "ACKNOWLEDGED"].includes(status);
  const followupStatus = statusCode(followup?.status);
  const followupComplete = ["CLOSED", "COMPLETED"].includes(followupStatus);
  const followupFailed = isFailed(followupStatus);
  const followupState = followupFailed ? "failed" : followupComplete ? "complete" : followup ? "current" : acknowledgementComplete ? "current" : "pending";
  const caseState = caseData && caseId ? "complete" : "pending";
  const adminState = caseData && isFailed(reviewStatus) ? "failed" : adminReviewed ? "complete" : caseData && reviewStatus ? "current" : "pending";
  const formState = submissionFailed ? "failed" : submissionComplete ? "complete" : submission ? "current" : "pending";
  const transmissionState = submissionFailed ? "failed" : simulated ? "current" : submissionComplete ? "complete" : submission ? "current" : "pending";
  const responseState = acknowledgementComplete ? "complete" : acknowledgement && isFailed(acknowledgement.status) ? "failed" : submissionComplete ? "current" : "pending";
  const acknowledgementState = responseState;
  const stages = [
    { title: "CASE READY", state: caseState },
    { title: "ADMIN REVIEW", state: adminState },
    { title: "FORM SUBMITTED", state: formState },
    { title: "PHA SENT", state: transmissionState },
    { title: "PHA RESPONSE", state: responseState },
    { title: "ACKNOWLEDGEMENT", state: acknowledgementState },
    { title: "FOLLOW-UP", state: followupState },
  ];

  if (loading) return <main className="admin-submission-journey"><div className="asj-state">Loading submission journey…</div></main>;
  if (!submission) return <main className="admin-submission-journey"><div className="asj-error" role="alert">{error || "Submission not found."}</div><Link className="asj-secondary-button" to="/admin/submissions">Admin Submissions</Link></main>;

  const responseCode = responseValue(acknowledgement, ["response_code", "code"]);
  const responseMessage = responseValue(acknowledgement, ["response_message", "message"]);
  const acknowledgementLabel = acknowledgementComplete ? text(acknowledgement?.status) : acknowledgement && isFailed(acknowledgement.status) ? text(acknowledgement.status) : "AWAITING ACKNOWLEDGEMENT";
  const nextStepMessage = acknowledgementComplete
    ? `PHA acknowledgement status: ${text(acknowledgement.status)}. The persisted follow-up state is ${text(followup?.status)}.`
    : "PHA acknowledgement is pending. Once an acknowledgement is received, SIGNAL will update the submission and follow-up status.";
  const followupError = location.state?.followupError;

  return <main className="admin-submission-journey">
    <header className="asj-header">
      <div><span>ADMINISTRATOR / SUBMISSION</span><h1>Submission Acknowledgement</h1><p>Case successfully submitted from SIGNAL</p></div>
      <Link to="/admin/submissions" className="asj-header-link">Admin Submissions</Link>
    </header>

    {error && <div className="asj-inline-error" role="alert">{error}</div>}
    {followupError && !followup && <div className="asj-inline-error" role="status">{followupError}</div>}

    <section className="asj-card asj-overview" aria-label="Submission overview">
      <header className="asj-section-header"><span>SUBMISSION OVERVIEW</span><strong className={`asj-status-badge ${submissionFailed ? "failed" : "complete"}`}>{text(submission?.status)}</strong></header>
      <div className="asj-overview-grid">
        <OverviewField label="Submission ID" value={submission?.submission_id || submissionId} />
        <OverviewField label="Status" value={submission?.status} />
        <OverviewField label="Submission Mode" value={submission?.submission_mode} />
        <OverviewField label="Destination" value={destination} />
        <OverviewField label="Case ID" value={caseId} />
        <OverviewField label="Patient" value={patientName} />
        <OverviewField label="Condition" value={condition} />
        <OverviewField label="Jurisdiction" value={jurisdiction} />
      </div>
    </section>

    {simulated && <div className="asj-simulation-notice" role="status"><strong>SIMULATED TRANSMISSION</strong><span>Demo environment: no real PHA transmission has occurred.</span></div>}

    <section className="asj-card asj-journey-card" aria-labelledby="asj-journey-title">
      <header className="asj-section-header"><div><span>SUBMISSION STATUS</span><h2 id="asj-journey-title">Submission Journey</h2></div></header>
      <div className="asj-journey-track">
        {stages.map((item, index) => <div className={`asj-stage-slot ${item.state}`} key={item.title}>
          <JourneyStage number={index + 1} {...item} />
        </div>)}
      </div>
    </section>

    <section className="asj-status-cards" aria-label="Workflow status">
      <article><span>SUBMISSION</span><strong className={submissionFailed ? "failed" : "complete"}>{text(submission?.status)}</strong></article>
      <article><span>TRANSMISSION</span><strong className={simulated ? "info" : submissionComplete ? "complete" : "pending"}>{simulated ? "SIMULATED" : submissionComplete ? "SENT" : "PENDING"}</strong></article>
      <article><span>ACKNOWLEDGEMENT</span><strong className={acknowledgementComplete ? "complete" : "pending"}>{acknowledgementLabel}</strong></article>
      <article><span>FOLLOW-UP</span><strong className={followupFailed ? "failed" : followupComplete ? "complete" : followup ? "current" : "pending"}>{text(followup?.status, "OPEN")}</strong></article>
    </section>

    <section className="asj-detail-grid">
      <article className="asj-card asj-detail-card" id="asj-transmission-information">
        <header className="asj-section-header"><span>TRANSMISSION INFORMATION</span></header>
        <dl>
          <InformationField label="Destination" value={destination} />
          <InformationField label="ECR ID" value={submission?.ecr_id} />
          <InformationField label="Submission ID" value={submission?.submission_id || submissionId} />
          <InformationField label="Submitted At" value={submission?.created_at} format="timestamp" />
          <InformationField label="Transmission Status" value={simulated ? "SIMULATED" : submissionComplete ? "SENT" : submission?.status} />
        </dl>
        {simulated && <p className="asj-warning">Demo environment: no real PHA transmission has occurred.</p>}
      </article>

      <article className="asj-card asj-detail-card">
        <header className="asj-section-header"><span>PHA ACKNOWLEDGEMENT</span><strong className={`asj-status-badge ${acknowledgementComplete ? "complete" : "pending"}`}>{acknowledgementLabel}</strong></header>
        <dl>
          <InformationField label="Acknowledgement Status" value={acknowledgement?.status} />
          <InformationField label="Acknowledgement / Reference ID" value={acknowledgement?.acknowledgement_id || submission?.acknowledgement_id} />
          <InformationField label="Received At" value={acknowledgement?.received_at} format="timestamp" />
          {(acknowledgement || responseCode) && <InformationField label="Response Code" value={responseCode} />}
          {(acknowledgement || responseMessage) && <InformationField label="Response Message" value={responseMessage} />}
        </dl>
      </article>

      <article className="asj-card asj-detail-card asj-followup-card">
        <header className="asj-section-header"><span>PHA FOLLOW-UP</span><strong className={`asj-status-badge ${followupFailed ? "failed" : followupComplete ? "complete" : followup ? "current" : "pending"}`}>{text(followup?.status, "OPEN")}</strong></header>
        {followup ? <dl>
          <InformationField label="Status" value={followup.status} />
          <InformationField label="Action" value={followup.action} />
          <InformationField label="Next Action" value={followup.next_action} />
          <InformationField label="Due Date" value={followup.due_date} format="date" />
          <InformationField label="Created At" value={followup.created_at} format="timestamp" />
          <InformationField label="Updated At" value={followup.updated_at} format="timestamp" />
          <InformationField label="Notes" value={followup.notes} />
        </dl> : <p className="asj-empty-followup">No persisted follow-up record is available for this submission.</p>}
      </article>
    </section>

    <section className="asj-next-step">
      <div><span>NEXT STEP</span><p>{nextStepMessage}</p></div>
      <div className="asj-next-actions">
        <button type="button" className="asj-primary-button" onClick={() => navigate("/admin/submissions")}>VIEW SUBMISSION</button>
        <button type="button" className="asj-secondary-button" onClick={() => navigate("/admin/queue")}>RETURN TO QUEUE</button>
      </div>
    </section>
  </main>;
}
