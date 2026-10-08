import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { getCase, getJourney, getCaseReview, getCaseAttestation, submitEcr, trackSubmission, processAcknowledgement, retrySubmission } from "../api/signal.js";
import "../styles/submission-workspace.css";

const list = (value) => Array.isArray(value) ? value : [];
const display = (value) => value === null || value === undefined || value === "" ? "Not recorded" : String(value);
const getStage = (journey, name) => list(journey?.journey).find((item) => item.stage === name);
const tone = (value) => /REJECT|FAIL|ERROR/i.test(value || "") ? "bad" : /ACKNOWLEDG|COMPLETE|SUBMITTED|APPROV|ATTEST|READY/i.test(value || "") ? "good" : /PENDING|CURRENT|PROCESS|NEEDS|INVALID/i.test(value || "") ? "wait" : "unknown";
const latestSubmission = (journey) => list(getStage(journey, "SUBMISSION")?.data?.submissions).at(-1) || null;
const patientLabel = (patient) => [patient?.first_name, patient?.last_name].filter(Boolean).join(" ") || patient?.name || "Patient name not returned";

function Detail({ label, value }) { return <div className="submission-detail"><span>{label}</span><strong>{display(value)}</strong></div>; }
function ResponseItems({ title, items }) {
  if (!list(items).length) return null;
  return <div className="submission-response-items"><strong>{title}</strong><ul>{items.map((item, index) => <li key={`${index}-${String(item)}`}>{typeof item === "string" ? item : JSON.stringify(item)}</li>)}</ul></div>;
}

export default function SubmissionWorkspace() {
  const { patientId: routePatientId, caseId = "" } = useParams();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [review, setReview] = useState(null);
  const [attestation, setAttestation] = useState(null);
  const [submission, setSubmission] = useState(null);
  const [tracking, setTracking] = useState(null);
  const [acknowledgement, setAcknowledgement] = useState(null);
  const [retryResult, setRetryResult] = useState(null);
  const [retryReason, setRetryReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [caseResponse, journeyResponse, reviewResponse, attestationResponse] = await Promise.all([
        getCase(caseId), getJourney(caseId), getCaseReview(caseId).catch(() => null), getCaseAttestation(caseId).catch(() => null),
      ]);
      const data = caseResponse?.data || caseResponse;
      const journeyData = journeyResponse?.data || journeyResponse;
      setCaseData(data);
      setJourney(journeyData);
      setReview(reviewResponse?.data || reviewResponse);
      setAttestation(attestationResponse?.data || attestationResponse);
      setSubmission(latestSubmission(journeyData));
      setTracking(null);
      setAcknowledgement(null);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Unable to load case and workflow status.");
    } finally { setLoading(false); }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const stages = useMemo(() => ({
    reportability: getStage(journey, "REPORTABILITY"),
    validation: getStage(journey, "VALIDATION"),
    review: getStage(journey, "REVIEW"),
    attestation: getStage(journey, "ATTESTATION"),
    reporting: getStage(journey, "REPORTING"),
    submission: getStage(journey, "SUBMISSION"),
  }), [journey]);
  const patient = caseData?.patient || {};
  const patientId = routePatientId || patient.patient_id || caseData?.patient_id || "";
  const caseWorkspacePath = patientId
    ? `/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(caseId)}`
    : `/cases/${encodeURIComponent(caseId)}`;
  const patientPath = patientId ? `/patients/${encodeURIComponent(patientId)}` : "/patients";
  const patientName = patientLabel(patient);
  const destination = submission?.destination || "Not configured in workflow data";
  const status = acknowledgement?.status || tracking?.status || submission?.status || (stages.submission?.status === "PENDING" ? "Not submitted" : stages.submission?.status);
  const warnings = submission?.warnings || [];
  const simulated = destination === "MOCK_PHA" || list(stages.submission?.limitations).some((item) => /simulated|MOCK_PHA/i.test(item)) || list(warnings).some((item) => /simulat|MOCK_PHA/i.test(String(item)));
  const ackStatus = acknowledgement?.status || tracking?.acknowledgement_status || submission?.acknowledgement_status || (/ACKNOWLEDGED/i.test(submission?.status || "") ? "ACKNOWLEDGED" : "No acknowledgement recorded");
  const accepted = /ACKNOWLEDGED|ACCEPTED/i.test(ackStatus);
  const rejected = /REJECT/i.test(ackStatus) || /REJECT/i.test(status || "");
  const readiness = [
    ["Case available", Boolean(caseData), caseData ? caseData.status : "Not available"],
    ["Reportability decision", Boolean(caseData?.reportability_decision || stages.reportability?.available), caseData?.reportability_decision || stages.reportability?.status],
    ["Reporting package", stages.reporting?.status === "COMPLETED", stages.reporting?.status || "No generated report recorded"],
    ["Validation, review and attestation", stages.validation?.status === "COMPLETED" && review?.status === "APPROVE" && attestation?.status === "ATTESTED",
      `${stages.validation?.status || "Validation not recorded"} · ${review?.status || "Review not recorded"} · ${attestation?.status || "Attestation not recorded"}`],
  ];
  const canSubmit = readiness.every((item) => item[1]) && stages.validation?.status === "COMPLETED";

  async function act(label, action, onSuccess) {
    setWorking(true); setOperation(label); setError(""); setMessage("");
    try {
      const response = await action();
      const result = response?.data || response;
      onSuccess(result);
      setMessage(`${label} response received from SIGNAL.`);
      const journeyResponse = await getJourney(caseId);
      const data = journeyResponse?.data || journeyResponse;
      setJourney(data);
      setSubmission(result?.submission_id ? result : latestSubmission(data) || submission);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || `Unable to ${label.toLowerCase()}.`);
    } finally { setWorking(false); setOperation(""); }
  }

  function submit() {
    const action = submission?.submission_id ? "Submit another electronic case report" : "Submit the electronic case report";
    if (!window.confirm(`${action} for ${patientName}, ${display(caseData.disease)}, ${display(caseData.jurisdiction)}? Destination: ${destination}.`)) return;
    act("Submission", () => submitEcr(caseId), (result) => {
      setSubmission(result);
    });
  }
  function track() {
    if (!submission?.submission_id) return;
    act("Tracking", () => trackSubmission(submission.submission_id), setTracking);
  }
  function acknowledge() {
    if (!submission?.submission_id) return;
    act("Acknowledgement", () => processAcknowledgement(submission.submission_id), (result) => {
      setAcknowledgement(result);
    });
  }
  function retry() {
    if (!submission?.submission_id || !retryReason.trim()) return;
    act("Retry", () => retrySubmission(submission.submission_id, retryReason.trim()), setRetryResult);
  }

  if (loading) return <section className="submission-page"><SignalLoading title="Preparing Submission" message="Preparing the case for electronic reporting." /></section>;
  if (!caseData) return <section className="submission-page"><div className="submission-message error" role="alert">{error || "The case could not be loaded."}<button onClick={load}>Retry</button></div></section>;

  return <section className="submission-page">
    <header className="submission-header">
      <div className="submission-heading">
        <button className="submission-back" onClick={() => navigate(`${caseWorkspacePath}/reporting-form`)}>← Back to Reporting Form</button>
        <div className="submission-steps"><span>Case Workspace</span><i>›</i><span>Reporting Form</span><i>›</i><b>Submission</b></div>
        <span className="submission-kicker">SUBMISSION WORKSPACE</span>
        <h2>Texas Measles Electronic Reporting</h2>
        <p>Review submission readiness, submit through the configured electronic reporting channel, and track destination acknowledgement.</p>
      </div>
      <div className="submission-jurisdiction"><span>{display(caseData.jurisdiction)}</span><strong>{display(caseData.disease)}</strong><small>Case · {String(caseData.case_id || caseId).slice(0, 12)}…</small></div>
    </header>

    {working && <SignalLoading
      title={operation === "Tracking" ? "Checking Submission" : operation === "Acknowledgement" ? "Processing Response" : operation === "Retry" ? "Retrying Submission" : "Preparing Submission"}
      message={operation === "Tracking" ? "Retrieving the current submission status." : operation === "Acknowledgement" ? "Processing the public-health acknowledgement." : operation === "Retry" ? "Retrying the submission through its configured destination." : "Preparing the case for electronic reporting."}
    />}

    {simulated && <div className="simulation-banner"><strong>SIMULATION ENVIRONMENT</strong><span>This submission is handled by SIGNAL’s mock public-health destination. No real Texas DSHS transmission has occurred.</span></div>}
    {(error || message) && <div className={`submission-message ${error ? "error" : "success"}`} role={error ? "alert" : "status"}>{error || message}</div>}

    <div className="submission-context">
      <Detail label="Patient" value={patientName} /><Detail label="MRN" value={patient.source_patient_id || patient.patient_id} /><Detail label="DOB" value={patient.date_of_birth} /><Detail label="Case" value={caseData.case_id || caseId} /><Detail label="Disease" value={caseData.disease} /><Detail label="Jurisdiction" value={caseData.jurisdiction} />
    </div>

    <div className="submission-kpis">
      <div><span>REPORTING JURISDICTION</span><strong>{display(caseData.jurisdiction)}</strong><small>Configured for this case</small></div>
      <div><span>REPORTABLE CONDITION</span><strong>{display(caseData.disease)}</strong><small>Rule: {display(caseData.rule_id)}</small></div>
      <div><span>SUBMISSION STATUS</span><strong className={`status-text ${tone(status)}`}>{display(status)}</strong><small>{submission?.submission_id || "No submission ID recorded"}</small></div>
      <div><span>REPORTING CHANNEL</span><strong>{display(submission?.channel)}</strong><small>{display(destination)}</small></div>
    </div>

    <main className="submission-grid">
      <div className="submission-primary-column">
        <article className="submission-card-main readiness-card-main">
          <div className="submission-card-title"><div><span className="submission-number">01</span><div><h3>Submission Readiness</h3><p>{canSubmit ? "The required workflow stages are recorded." : "Complete the items below before submission."}</p></div></div><span className={`readiness-badge ${canSubmit ? "good" : "wait"}`}>{canSubmit ? "Ready" : "Action required"}</span></div>
          <div className="readiness-steps">{readiness.map(([title, ready, note]) => <div className={`readiness-step ${ready ? "complete" : "pending"}`} key={title}><span>{ready ? "✓" : "!"}</span><div><strong>{title}</strong><small>{display(note)}</small></div></div>)}</div>
          {!canSubmit && <p className="submission-block-note">The eCR service enforces approved review, current attestation, and a generated report. Resolve missing workflow steps in the Case Workspace or Reporting Form.</p>}
          <div className="submission-destination"><div className="destination-icon">eCR</div><div><strong>Electronic Submission</strong><p>Handled by eCR Submission Agent · Destination: {destination}</p></div></div>
          <button className="submit-button" disabled={working || !canSubmit} onClick={submit}>{working ? "Submitting…" : submission?.submission_id ? "Submit Again" : "Submit eCR"}</button>
        </article>

        {submission && <article className="submission-card-main">
          <div className="submission-card-title"><div><span className="submission-number">02</span><div><h3>Submission Package</h3><p>Persisted submission details returned by the backend.</p></div></div></div>
          <dl className="submission-result-grid"><div><dt>Submission ID</dt><dd>{display(submission.submission_id)}</dd></div><div><dt>Status</dt><dd>{display(submission.status)}</dd></div><div><dt>Channel</dt><dd>{display(submission.channel)}</dd></div><div><dt>Destination</dt><dd>{display(submission.destination)}</dd></div><div><dt>ECR ID</dt><dd>{display(submission.ecr_id)}</dd></div><div><dt>Submitted At</dt><dd>{display(submission.created_at)}</dd></div><div><dt>Acknowledgement</dt><dd>{display(ackStatus)}</dd></div></dl>
          <ResponseItems title="Warnings" items={submission.warnings} /><ResponseItems title="Errors" items={submission.errors} />
          <div className="submission-controls"><button disabled={working} onClick={track}>{working ? "Working…" : "Track Submission"}</button><button disabled={working} onClick={acknowledge}>{working ? "Working…" : "Process Acknowledgement"}</button></div>
        </article>}

        <article className="submission-card-main"><div className="submission-card-title"><div><span className="submission-number">03</span><div><h3>Submission Lifecycle</h3><p>Lifecycle status is based on persisted journey state and returned service responses.</p></div></div></div>
          <div className="lifecycle">{[["Ready", canSubmit ? "READY" : "BLOCKED"], ["Submitted", submission?.status || "PENDING"], ["Tracking", tracking?.status || (submission ? "PENDING" : "PENDING")], ["Acknowledgement", ackStatus], ["Complete", accepted ? "ACKNOWLEDGED" : "PENDING"]].map(([label, value], index) => <div className={`lifecycle-step ${tone(value)}`} key={label}><span>{index + 1}</span><strong>{label}</strong><small>{display(value)}</small></div>)}</div>
          <p className="submission-agent-note">eCR Submission Agent · Submission Tracking Agent · Acknowledgement Agent</p>
          {tracking && <><dl className="submission-result-grid"><div><dt>Tracking status</dt><dd>{display(tracking.status)}</dd></div><div><dt>Destination</dt><dd>{display(tracking.destination)}</dd></div></dl><ResponseItems title="Tracking warnings" items={tracking.warnings} /><ResponseItems title="Tracking errors" items={tracking.errors} /></>}
          {acknowledgement && <><dl className="submission-result-grid"><div><dt>Acknowledgement status</dt><dd>{display(acknowledgement.status)}</dd></div><div><dt>Acknowledgement ID</dt><dd>{display(acknowledgement.acknowledgement_id)}</dd></div><div><dt>PHA case ID</dt><dd>{display(acknowledgement.pha_case_id)}</dd></div></dl><ResponseItems title="Acknowledgement warnings" items={acknowledgement.warnings} /><ResponseItems title="Acknowledgement errors" items={acknowledgement.errors} /></>}
          {rejected && <div id="retry-submission" className="retry-panel"><label>Retry reason<textarea value={retryReason} maxLength={1000} onChange={(event) => setRetryReason(event.target.value)} /></label><button disabled={working || !retryReason.trim()} onClick={retry}>{working ? "Retrying…" : "Retry Submission"}</button>{retryResult && <p>{display(retryResult.status)} · New submission: {display(retryResult.new_submission_id)}</p>}</div>}
          {accepted && <p className="acknowledged-note">✓ Acknowledgement status returned by backend: {display(ackStatus)}{simulated ? ". This is a simulated response and does not confirm external PHA delivery." : "."}</p>}
        </article>
      </div>

      <aside className="submission-sidebar">
        <article className="side-card"><span>REPORTING ROUTE</span>{/* Immediate reporting card temporarily disabled.
          <div className="route-info"><strong>Immediate notification</strong><p>Phone notification to the appropriate public-health authority. This remains separate from eCR.</p></div>
        */}<div className="route-info"><strong>Electronic reporting</strong><p>eCR / eICR → {display(destination)}</p></div><div className="route-info"><strong>Manual / fallback</strong><p>Use when required by jurisdiction or onboarding status. Follow local procedure.</p></div></article>
        <article className="side-card"><span>CASE SUMMARY</span><div className="side-row"><label>Patient</label><strong>{patientName}</strong></div><div className="side-row"><label>Reportability</label><strong>{display(caseData.final_decision || caseData.reportability_decision)}</strong></div><div className="side-row"><label>Case status</label><strong>{display(caseData.status)}</strong></div><div className="side-row"><label>Rule</label><strong>{display(caseData.rule_id)}</strong></div><div className="side-row"><label>Case ID</label><strong>{caseData.case_id || caseId}</strong></div></article>
        <article className="side-card next-card"><span>WHAT HAPPENS NEXT</span><strong>{submission ? accepted ? "Review the completed reporting workflow" : rejected ? "Review the returned rejection and retry if appropriate" : "Track delivery and process the acknowledgement" : canSubmit ? "Confirm the patient and destination, then submit the eCR" : "Complete review, attestation, and report preparation"}</strong><p>Only backend-confirmed workflow information is shown here.</p>{submission?.submission_id && <button className="next-action" disabled={working} onClick={accepted ? () => navigate(`${caseWorkspacePath}/completion`) : rejected ? () => document.getElementById("retry-submission")?.scrollIntoView({ behavior: "smooth", block: "center" }) : tracking ? acknowledge : track}>{accepted ? "View Final Status" : rejected ? "Go to Retry Submission" : tracking ? "Process Acknowledgement" : "Track Submission"}</button>}</article>
        <button className="return-button" onClick={() => navigate(patientPath)}>← Back to Patient</button>
      </aside>
    </main>
  </section>;
}
