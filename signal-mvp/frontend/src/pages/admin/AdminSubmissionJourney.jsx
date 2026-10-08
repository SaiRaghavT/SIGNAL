import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { listFollowUps } from "../../api/followups.js";
import { getSubmissionAcknowledgement } from "../../api/submissions.js";
import { getAdminQueueCase, getAdminSubmission } from "../../services/adminService.js";
import { getOpenClinicalInformationRequest, CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT } from "../../utils/clinicalInformationRequests.js";
import "../../styles/AdminSubmissionJourney.css";

const text = (value, fallback = "Not available") => value === undefined || value === null || String(value).trim() === "" ? fallback : String(value);
const statusCode = (value) => String(value || "").trim().toUpperCase();
const isFailed = (value) => /FAILED|ERROR|REJECTED|REJECT|INVALID/i.test(String(value || ""));

function formatTimestamp(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function isAcknowledgementComplete(acknowledgement) {
  const state = statusCode(acknowledgement?.status);
  return ["ACKNOWLEDGED", "RECEIVED", "SUCCESS", "COMPLETED", "ACCEPTED"].includes(state);
}

function OverviewField({ label, value }) {
  return <div className="asj-overview-field"><span>{label}</span><strong title={value ? String(value) : undefined}>{text(value)}</strong></div>;
}

function JourneyStage({ number, title, subtitle, state }) {
  const marker = state === "complete" ? "\u2713" : state === "failed" ? "!" : "\u2022";
  const label = state === "complete" ? "Completed" : state === "failed" ? "Failed" : state === "current" ? "Current" : "Pending";
  return <article className={`asj-stage ${state}`}>
    <span className="asj-stage-number" aria-hidden="true">{number}</span>
    <h3>{title}</h3>
    {subtitle && <small className="asj-stage-subtitle">{subtitle}</small>}
    <span className="asj-stage-state" aria-label={label}>{marker}</span>
  </article>;
}

function JourneyTrack({ stages, className = "" }) {
  return <div className={`asj-journey-track ${className}`}>
    {stages.map((item, index) => <div className={`asj-stage-slot ${item.state}`} key={`${item.title}-${index}`}>
      <JourneyStage number={index + 1} {...item} />
    </div>)}
  </div>;
}
export default function AdminSubmissionJourney() {
  const { submissionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [submission, setSubmission] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [acknowledgement, setAcknowledgement] = useState(null);
  const [followup, setFollowup] = useState(null);
  const [informationRequest, setInformationRequest] = useState(null);
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
  useEffect(() => {
    const refreshInformationRequest = () => setInformationRequest(caseId ? getOpenClinicalInformationRequest(caseId) : null);
    refreshInformationRequest();
    window.addEventListener(CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT, refreshInformationRequest);
    window.addEventListener("storage", refreshInformationRequest);
    return () => {
      window.removeEventListener(CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT, refreshInformationRequest);
      window.removeEventListener("storage", refreshInformationRequest);
    };
  }, [caseId]);

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
  const adminState = submissionComplete || adminReviewed ? "complete" : caseData && isFailed(reviewStatus) ? "failed" : caseData && reviewStatus ? "current" : "pending";
  const signalState = submissionFailed ? "failed" : submissionComplete ? "complete" : submission ? "current" : "pending";
  const eicrState = submissionFailed ? "failed" : submission?.ecr_id ? "complete" : "pending";
  const transmissionState = submissionFailed ? "failed" : simulated && submissionComplete ? "current" : submissionComplete ? "complete" : submission ? "current" : "pending";
  const responseState = acknowledgementComplete ? "complete" : acknowledgement && isFailed(acknowledgement.status) ? "failed" : submissionComplete && !simulated ? "current" : "pending";
  const acknowledgementState = acknowledgementComplete ? "complete" : acknowledgement && isFailed(acknowledgement.status) ? "failed" : "pending";
  const phaProgressState = acknowledgementComplete ? "complete" : acknowledgement && isFailed(acknowledgement.status) ? "failed" : submissionComplete && !simulated ? "current" : "pending";
  const stages = [
    { title: "ADMIN", state: adminState },
    { title: "SIGNAL", state: signalState },
    { title: "eICR", state: eicrState },
    { title: "APHL AIMS", state: transmissionState },
    { title: "TEXAS DSHS", state: phaProgressState },
    { title: "NEDSS", state: phaProgressState },
    { title: "PHA PROCESS", state: phaProgressState },
    { title: "RESPONSE", state: responseState },
    { title: "APHL AIMS", state: acknowledgementState },
    { title: "SIGNAL", state: acknowledgementState },
    { title: "FOLLOW-UP", state: followupState },
  ];
  if (loading) return <main className="admin-submission-journey"><div className="asj-state">Loading submission journey…</div></main>;
  if (!submission) return <main className="admin-submission-journey"><div className="asj-error" role="alert">{error || "Submission not found."}</div><Link className="asj-secondary-button" to="/admin/submissions">Admin Submissions</Link></main>;

  const acknowledgementLabel = acknowledgementComplete ? "ACKNOWLEDGED" : acknowledgement && isFailed(acknowledgement.status) ? text(acknowledgement.status) : "PENDING";
  const transmissionLabel = submissionFailed ? "FAILED" : simulated ? "SIMULATED" : submissionComplete ? "SENT" : "PENDING";
  const followupLabel = text(followup?.status, "PENDING");
  const currentStatusMessage = informationRequest
    ? "Additional information has been requested. Administrator action is required."
    : acknowledgementComplete
      ? "PHA acknowledgement received. SIGNAL has received the PHA response."
      : acknowledgement && isFailed(acknowledgement.status)
        ? `PHA acknowledgement status: ${text(acknowledgement.status)}.`
        : "PHA acknowledgement is pending. SIGNAL is awaiting the PHA response.";
  const followupError = location.state?.followupError;

  return <main className="admin-submission-journey">
    <header className="asj-header">
      <div>
        <span>ADMINISTRATOR / SUBMISSION</span>
        <h1>Submission Acknowledgement</h1>
        <p>Case successfully submitted from SIGNAL.</p>
        <p className="asj-context-line">{[patientName, condition, jurisdiction].filter(Boolean).join(" \u00b7 ")}</p>
      </div>
      <Link to="/admin/submissions" className="asj-header-link">Admin Submissions</Link>
    </header>

    <section className="asj-status-cards" aria-label="Submission status summary">
      <article><span>SUBMISSION</span><strong className={submissionFailed ? "failed" : submissionComplete ? "complete" : "pending"}>{text(submission?.status, "PENDING")}</strong></article>
      <article><span>TRANSMISSION</span><strong className={submissionFailed ? "failed" : simulated ? "info" : submissionComplete ? "complete" : "pending"}>{transmissionLabel}</strong></article>
      <article><span>ACKNOWLEDGEMENT</span><strong className={acknowledgementComplete ? "complete" : acknowledgement && isFailed(acknowledgement.status) ? "failed" : "pending"}>{acknowledgementLabel}</strong></article>
      <article><span>FOLLOW-UP</span><strong className={followupFailed ? "failed" : followupComplete ? "complete" : followup ? "current" : "pending"}>{followupLabel}</strong></article>
    </section>

    {error && <div className="asj-inline-error" role="alert">{error}</div>}
    {followupError && !followup && <div className="asj-inline-error" role="status">{followupError}</div>}

    <section className="asj-card asj-journey-card" aria-labelledby="asj-journey-title">
      <header className="asj-section-header">
        <div><h2 id="asj-journey-title">SUBMISSION JOURNEY</h2><p className="asj-journey-subtitle">How the reporting package moves from SIGNAL to the Public Health Authority and how the response returns to SIGNAL.</p></div>
      </header>
      <JourneyTrack stages={stages} className="asj-main-track" />
    </section>

    {simulated && <div className="asj-simulation-notice" role="status"><strong>SIMULATED PHA FLOW</strong><span>Demo environment &mdash; no real PHA transmission has occurred.</span></div>}

    {informationRequest && <section className="asj-card asj-information-card" aria-label="Information request">
      <div><span className="asj-card-eyebrow">INFORMATION REQUESTED</span><h2>Additional information is required before processing can continue.</h2>
        {informationRequest.message && <p>{informationRequest.message}</p>}
        <strong className="asj-action-required">ADMIN ACTION REQUIRED</strong>
      </div>
      {caseId && <Link className="asj-primary-button" to={`/cases/${encodeURIComponent(caseId)}`}>PROVIDE INFORMATION</Link>}
    </section>}

    <section className="asj-card asj-current-status" aria-label="Current status">
      <span className="asj-card-eyebrow">CURRENT STATUS</span>
      <p>{currentStatusMessage}</p>
    </section>

    <section className="asj-card asj-submission-details" id="submission-details" aria-label="Submission details">
      <OverviewField label="Submission ID" value={submission?.submission_id || submissionId} />
      <OverviewField label="Status" value={submission?.status} />
      <OverviewField label="Destination" value={destination} />
      <OverviewField label="Submitted" value={formatTimestamp(submission?.created_at)} />
    </section>

    <section className="asj-next-step">
      <div className="asj-next-actions">
        <button type="button" className="asj-primary-button" onClick={() => document.getElementById("submission-details")?.scrollIntoView({ behavior: "smooth", block: "center" })}>VIEW SUBMISSION</button>
        <button type="button" className="asj-secondary-button" onClick={() => navigate("/admin/queue")}>RETURN TO QUEUE</button>
      </div>
    </section>
  </main>;
}
