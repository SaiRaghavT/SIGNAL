import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { useDemoWorkflow } from "../hooks/useDemoWorkflow.js";
import { listFollowUps } from "../api/followups.js";
import { getSubmissionAcknowledgement } from "../api/submissions.js";
import { getCase, getJourney, processFollowup } from "../api/signal.js";
import { cleanPatientName } from "../utils/patientNames.js";
import "../styles/follow-up-workspace.css";

const items = (value) => Array.isArray(value) ? value : [];
const valueText = (value) => value === null || value === undefined || value === "" ? "Not available" : typeof value === "object" ? JSON.stringify(value) : String(value);
const stage = (journey, name) => items(journey?.journey).find((item) => item.stage === name) || null;
const followupRecords = (journey) => items(stage(journey, "PHA_FOLLOW_UP")?.data?.follow_ups);
const latest = (records) => records.length ? records[records.length - 1] : null;
const patientName = (patient) => cleanPatientName([patient?.first_name, patient?.last_name].filter(Boolean).join(" ") || patient?.name) || "Patient name not returned";

const ACTIONS = [
  ["REQUEST_INFORMATION", "Request Additional Information", "Record a request for additional case information."],
  ["INVESTIGATION", "Investigation Follow-up", "Record an investigation follow-up action."],
  ["OUTCOME_UPDATE", "Document Outcome", "Record an outcome or status update."],
  ["CLOSE", "Close Follow-up Activity", "Close this follow-up record. This does not resolve the case."],
];

function statusClass(status) {
  if (/CLOSED|ACKNOWLEDGED|COMPLETED|SUBMITTED/i.test(status || "")) return "complete";
  if (/REJECT|FAIL|ERROR/i.test(status || "")) return "error";
  if (/PENDING|CURRENT|NOT_STARTED/i.test(status || "")) return "pending";
  return "unknown";
}

function DataPoint({ label, children }) {
  return <div className="fu-data-point"><span>{label}</span><strong>{valueText(children)}</strong></div>;
}

function FlowNode({ title, state, details, note }) {
  const displayValue = (label, value) => {
    if (value === null || value === undefined || value === "") return "Not available";
    if (/time|created|received|updated|due date/i.test(label)) {
      const date = new Date(value);
      if (!Number.isNaN(date.getTime())) return date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    }
    return valueText(value);
  };
  return <article className={`fu-submission-step ${state}`}>
    <span className="fu-journey-marker" aria-hidden="true">{state === "complete" ? "✓" : state === "failed" ? "!" : state === "current" ? "◷" : "•"}</span>
    <strong className="fu-journey-title">{title}</strong>
    <small className="fu-journey-state">{state === "complete" ? "Complete" : state === "failed" ? "Failed" : state === "current" ? "Current" : "Pending"}</small>
    <dl>{details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={value === null || value === undefined ? undefined : String(value)}>{displayValue(label, value)}</dd></div>)}</dl>
    {note && <small className="fu-journey-note">{note}</small>}
  </article>;
}

function ApiResult({ result }) {
  if (!result) return null;
  const fields = [
    ["Status", result.status], ["Action", result.action], ["Follow-up ID", result.followup_id],
    ["Submission ID", result.submission_id], ["Next action", result.next_action], ["Due date", result.due_date], ["Notes", result.notes],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  return <article className="fu-result-card" aria-live="polite">
    <div className="fu-result-title"><span>FOLLOW-UP PROCESSED</span><b className={`fu-status ${statusClass(result.status)}`}>{valueText(result.status)}</b></div>
    <dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{valueText(value)}</dd></div>)}</dl>
    {items(result.warnings).map((warning, index) => <p className="fu-warning" key={`w-${index}`}>{warning}</p>)}
    {items(result.errors).map((error, index) => <p className="fu-error-detail" key={`e-${index}`}>{error}</p>)}
  </article>;
}

export default function FollowUpWorkspace() {
  const { patientId: routePatientId, caseId = "" } = useParams();
  const navigate = useNavigate();
  const demo = useDemoWorkflow(caseId);
  const [caseData, setCaseData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [persistedFollowups, setPersistedFollowups] = useState([]);
  const [acknowledgement, setAcknowledgement] = useState(null);
  const [action, setAction] = useState("INVESTIGATION");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [processingAction, setProcessingAction] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [caseResponse, journeyResponse, followupResponse] = await Promise.all([
        getCase(caseId),
        getJourney(caseId),
        listFollowUps({ search: caseId, page_size: 100 }).catch(() => null),
      ]);
      const journeyData = journeyResponse?.data || journeyResponse;
      const submissionRows = items(stage(journeyData, "SUBMISSION")?.data?.submissions);
      const latestSubmission = submissionRows[submissionRows.length - 1] || null;
      const matchingFollowups = items(followupResponse?.items)
        .filter((record) => record.case_id === caseId)
        .sort((left, right) => Date.parse(left.created_at || 0) - Date.parse(right.created_at || 0));
      const acknowledgementData = latestSubmission?.submission_id
        ? await getSubmissionAcknowledgement(latestSubmission.submission_id).catch(() => null)
        : null;
      setCaseData(caseResponse?.data || caseResponse);
      setJourney(journeyData);
      setPersistedFollowups(matchingFollowups);
      setAcknowledgement(acknowledgementData?.data || acknowledgementData);
    } catch (err) {
      setError(err?.message || err?.response?.data?.detail || "Unable to load case follow-up workspace.");
    } finally { setLoading(false); }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const patient = caseData?.patient || {};
  const patientId = routePatientId || patient.patient_id || caseData?.patient_id || "";
  const caseWorkspacePath = patientId
    ? `/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(caseId)}`
    : `/cases/${encodeURIComponent(caseId)}`;
  const followups = useMemo(() => {
    if (demo.active && demo.stages.followUp !== "COMPLETED") return [];
    return followupRecords(journey);
  }, [demo.active, demo.stages.followUp, journey]);
  const currentFollowup = latest(followups);
  const persistedCurrentFollowup = persistedFollowups[persistedFollowups.length - 1] || currentFollowup;
  const followupStage = stage(journey, "PHA_FOLLOW_UP");
  const submissionStage = stage(journey, "SUBMISSION");
  const submissions = items(submissionStage?.data?.submissions);
  const submission = latest(submissions);
  const visibleSubmission = demo.active && demo.stages.submission !== "COMPLETED" ? null : submission;
  const submissionStatus = visibleSubmission?.status || "No submission recorded";
  const destination = visibleSubmission?.destination;
  const acknowledged = /ACKNOWLEDGED/i.test(acknowledgement?.status || submissionStatus);
  const followupStatus = demo.active && demo.stages.followUp !== "COMPLETED"
    ? "NOT STARTED IN THIS DEMO"
    : currentFollowup?.status || (visibleSubmission ? "FOLLOW-UP NOT PROCESSED" : "REPORTING NOT RECORDED");
  const followupSimulated = items(currentFollowup?.warnings).some((warning) => /simulat/i.test(warning))
    || items(stage(journey, "PHA_FOLLOW_UP")?.limitations).some((limitation) => /simulat/i.test(limitation));
  const submissionSimulated = destination === "MOCK_PHA" || items(submission?.warnings).some((warning) => /simulat|MOCK_PHA/i.test(warning));
  const recordsByEvent = items(journey?.supporting_audit_events).filter((event) => event?.metadata?.workflow_stage === "PHA_FOLLOW_UP");
  const actionDescription = ACTIONS.find(([code]) => code === action)?.[2] || "";
  const nextAction = currentFollowup?.status === "CLOSED" ? "Case Resolution (managed by configured workflow)" : currentFollowup ? "Document follow-up outcome" : "PHA Follow-up";
  const canViewCompletion = demo.active
    ? demo.stages.followUp === "COMPLETED"
    : Boolean(result) || followupStage?.status === "COMPLETED";

  const caseStage = stage(journey, "CASE");
  const reviewStage = stage(journey, "REVIEW");
  const attestationStage = stage(journey, "ATTESTATION");
  const reviewData = reviewStage?.data || {};
  const caseReady = Boolean(caseData?.case_id && caseStage?.available);
  const reviewAuthorized = /^(APPROVE|APPROVED)$/i.test(reviewStage?.status || "")
    && /^ATTESTED$/i.test(attestationStage?.status || "");
  const submissionFailed = /FAIL|ERROR|REJECT/i.test(submission?.status || "");
  const submissionSent = Boolean(submission) && !submissionFailed && /SUBMITTED|ACKNOWLEDGED/i.test(submission.status || "");
  const acknowledgementRecorded = Boolean(acknowledgement)
    || /ACKNOWLEDGED/i.test(submission?.status || "");
  const followupCurrentStatus = String(persistedCurrentFollowup?.status || "").toUpperCase();
  const followupFailed = /FAIL|ERROR|REJECT/i.test(followupCurrentStatus);
  const followupComplete = /CLOSED|COMPLETED/i.test(followupCurrentStatus);
  const reviewActor = reviewData.reviewer_name || reviewData.reviewer_id || reviewData.actor_id;
  const journeyNodes = [
    {
      title: "Case Ready", state: caseReady ? "complete" : "current",
      details: [["Case ID", caseData?.case_id || caseId], ["Patient", patientName(patient)], ["Condition", caseData?.disease], ["Status", caseData?.status]],
    },
    {
      title: "Admin Review",
      state: /REJECT|REQUEST_INFORMATION/i.test(reviewStage?.status || "") ? "failed" : reviewAuthorized ? "complete" : reviewStage?.available ? "current" : "pending",
      details: [["Authorization", `${valueText(reviewStage?.status)} / ${valueText(attestationStage?.status)}`], ["Administrator", reviewActor], ["Review time", reviewStage?.occurred_at]],
    },
    {
      title: "Submission Created",
      state: submissionFailed ? "failed" : submission ? "complete" : reviewAuthorized ? "current" : "pending",
      details: [["Submission ID", submission?.submission_id], ["Status", submission?.status], ["Created", submission?.created_at]],
    },
    {
      title: submissionSimulated ? "PHA Transmission" : "Sent to PHA",
      state: submissionFailed ? "failed" : submissionSent ? "complete" : submission ? "current" : "pending",
      details: [["Destination", destination], ["Transmission", submission?.status], ["Sent time", submission?.sent_at || submission?.transmitted_at]],
      note: submissionSimulated ? "Simulated transmission. No external PHA delivery is confirmed." : undefined,
    },
    {
      title: submissionSimulated ? "PHA Processing" : "PHA Receives",
      state: submissionFailed ? "failed" : acknowledgementRecorded && !submissionSimulated ? "complete" : submissionSent ? "current" : "pending",
      details: [["Destination", destination], ["Receipt / processing", submissionSimulated ? "Not confirmed (simulated)" : acknowledgement?.status]],
      note: submissionSimulated ? "PHA receipt is not confirmed by the mock destination." : undefined,
    },
    {
      title: "Acknowledgement",
      state: submissionFailed ? "failed" : acknowledgementRecorded ? "complete" : submissionSent ? "current" : "pending",
      details: [["Status", acknowledgement?.status || (acknowledgementRecorded ? submission?.status : null)], ["Received", acknowledgement?.received_at], ["Reference ID", acknowledgement?.acknowledgement_id], ["Response", acknowledgement?.response]],
    },
    {
      title: "Follow-up",
      state: followupFailed ? "failed" : followupComplete ? "complete" : persistedCurrentFollowup ? "current" : acknowledgementRecorded ? "current" : "pending",
      details: [["Status", persistedCurrentFollowup?.status], ["Next action", persistedCurrentFollowup?.next_action], ["Due date", persistedCurrentFollowup?.due_date], ["Last updated", persistedCurrentFollowup?.updated_at]],
    },
  ];

  async function process() {
    if (!action || working) return;
    if (action === "CLOSE" && !window.confirm("Close this follow-up activity? This action does not resolve or close the case.")) return;
    setWorking(true); setProcessingAction(true); setError(""); setMessage(""); setResult(null);
    try {
      const response = await processFollowup(caseId, action, notes, submission?.submission_id);
      const responseData = response?.data || response;
      setResult(responseData);
      if (!items(responseData.errors).length && !/FAIL|ERROR|REJECT/i.test(responseData.status || "")) {
        demo.complete("followUp");
      }
      setMessage("Follow-up response received from the Public Health Follow-up Agent.");
      setNotes("");
      const [journeyResponse, followupResponse] = await Promise.all([
        getJourney(caseId),
        listFollowUps({ search: caseId, page_size: 100 }).catch(() => null),
      ]);
      setJourney(journeyResponse?.data || journeyResponse);
      setPersistedFollowups(items(followupResponse?.items)
        .filter((record) => record.case_id === caseId)
        .sort((left, right) => Date.parse(left.created_at || 0) - Date.parse(right.created_at || 0)));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Follow-up could not be processed.");
    } finally { setWorking(false); setProcessingAction(false); }
  }

  if (loading) return <section className="follow-up-page"><SignalLoading title="Loading Follow-up" message="Retrieving public-health follow-up information." /></section>;
  if (!caseData) return <section className="follow-up-page"><div className="fu-alert error" role="alert"><strong>Follow-up workspace unavailable</strong><span>{error || "The case could not be loaded."}</span><button onClick={load}>Retry</button></div></section>;

  return <section className="follow-up-page">
    <header className="fu-header">
      <div>
        <button className="fu-back-link" onClick={() => navigate(`${caseWorkspacePath}/submission`)}>← Back to Submission</button>
        <nav className="fu-breadcrumb" aria-label="Workflow"><span>Case Workspace</span><i>›</i><span>Reporting Form</span><i>›</i><span>Submission</span><i>›</i><b>Follow-up</b></nav>
        <span className="fu-eyebrow">PUBLIC HEALTH CASE OPERATIONS</span>
        <h2>PHA Follow Up</h2>
        <p>Coordinate the next public-health action for this reported case.</p>
      </div>
      <div className="fu-header-badges"><span>{valueText(caseData.jurisdiction)}</span><strong>{valueText(caseData.disease)}</strong>{acknowledged && <small>Acknowledged</small>}</div>
    </header>

    {processingAction && <SignalLoading title="Processing Follow-up" message="Recording the selected public-health follow-up action." />}
    {(followupSimulated || submissionSimulated) && <div className="fu-simulation"><strong>SIMULATION ENVIRONMENT</strong>{submissionSimulated && <span>Submission destination: {valueText(destination)}. No real public-health transmission occurred.</span>}{followupSimulated && <span>The backend indicates public-health follow-up is simulated; no real PHA action was performed.</span>}</div>}
    {(error || message) && <div className={`fu-alert ${error ? "error" : "success"}`} role={error ? "alert" : "status"}><span>{error || message}</span></div>}

    <div className="fu-context">
      <DataPoint label="Patient">{patientName(patient)}</DataPoint><DataPoint label="MRN">{patient.source_patient_id || patient.patient_id}</DataPoint><DataPoint label="DOB">{patient.date_of_birth}</DataPoint><DataPoint label="Case">{caseData.case_id || caseId}</DataPoint><DataPoint label="Disease">{caseData.disease}</DataPoint><DataPoint label="Jurisdiction">{caseData.jurisdiction}</DataPoint>
    </div>

    <section className="fu-submission-journey" aria-labelledby="fu-submission-journey-title">
      <header><div><span>PHA FOLLOW UP</span><h3 id="fu-submission-journey-title">Submission Journey</h3><p>Track how this reporting case moves from SIGNAL to the Public Health Authority and how the acknowledgement is returned to SIGNAL.</p></div></header>
      <div className="fu-submission-track">
        {journeyNodes.map((node) => <FlowNode key={node.title} {...node} />)}
      </div>
    </section>

    <div className="fu-summary">
      <article><span>PUBLIC HEALTH JURISDICTION</span><strong>{valueText(caseData.jurisdiction)}</strong><small>Case jurisdiction</small></article>
      <article><span>REPORTABLE CONDITION</span><strong>{valueText(caseData.disease)}</strong><small>Rule: {valueText(caseData.rule_id)}</small></article>
      <article><span>REPORTING STATUS</span><strong className={`fu-status-text ${statusClass(submissionStatus)}`}>{acknowledged ? "Acknowledged" : valueText(submissionStatus)}</strong><small>Submission and follow-up are separate</small></article>
      <article><span>NEXT ACTION</span><strong>{nextAction}</strong><small>{currentFollowup ? valueText(currentFollowup.status) : "No follow-up record yet"}</small></article>
    </div>

    <main className="fu-grid">
      <div className="fu-primary">
        <article className="fu-card">
          <header className="fu-card-header"><div><span className="fu-index">01</span><div><h3>Public Health Follow-up</h3><p>The case has progressed through reporting. Select the next operational action.</p></div></div><small>Public Health Follow-up Agent</small></header>
          <div className="fu-reporting-distinction"><div><span>REPORTING</span><strong>{acknowledged ? "Acknowledged" : valueText(submissionStatus)}</strong></div><i>→</i><div><span>PUBLIC HEALTH FOLLOW-UP</span><strong>{valueText(followupStatus)}</strong></div></div>
          <p className="fu-agent-copy">Follow-up actions are recorded by the configured backend service. They do not confirm external PHA contact unless the backend explicitly reports it.</p>
        </article>

        <article className="fu-card fu-action-card">
          <header className="fu-card-header"><div><span className="fu-index">02</span><div><h3>Follow-up Action</h3><p>Choose a supported action and document the context.</p></div></div><span className={`fu-status ${working ? "pending" : "ready"}`}>{working ? "Processing" : "Ready"}</span></header>
          <div className="fu-form">
            <label className="fu-label">Action
              <select value={action} onChange={(event) => setAction(event.target.value)} disabled={working}>
                {ACTIONS.map(([code, label]) => <option value={code} key={code}>{label}</option>)}
              </select>
              <small>{actionDescription}</small>
            </label>
            <label className="fu-label">Follow-up Notes <span className="optional">Optional</span>
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} disabled={working} maxLength={4000} placeholder="Document the public-health action, communication, request, or outcome." />
            </label>
            {action === "CLOSE" && <p className="fu-close-note">This closes the follow-up record only. The backend does not provide a separate case-resolution action.</p>}
            <button className="fu-primary-action" disabled={working} onClick={process}>{working ? "Processing follow-up…" : "Process Follow-up"}</button>
          </div>
        </article>

        {result && <ApiResult result={result} />}
        {canViewCompletion && <article className="fu-result-card fu-completion-cta"><div><strong>Follow-up processed successfully.</strong><p>Review the final workflow status and audit information for this case.</p></div><button onClick={() => navigate(`${caseWorkspacePath}/completion`)}>View Final Case Status</button></article>}

        <article className="fu-card fu-lifecycle-card">
          <header className="fu-card-header"><div><span className="fu-index">03</span><div><h3>Case and Reporting Status</h3><p>States reconstructed from the case journey and saved follow-up entries.</p></div></div></header>
          <div className="fu-lifecycle">
            {[
              ["Case Created", stage(journey, "CASE")?.status || "Not recorded"],
              ["Reportability", stage(journey, "REPORTABILITY")?.status || "Not recorded"],
              ["Validation", stage(journey, "VALIDATION")?.status || "Not recorded"],
              ["Reporting", stage(journey, "REPORTING")?.status || "Not recorded"],
              ["Submission", submission?.status || "Not recorded"],
              ["Acknowledgement", acknowledged ? "ACKNOWLEDGED" : "Not recorded"],
              ["PHA Follow-up", currentFollowup?.status || stage(journey, "PHA_FOLLOW_UP")?.status || "PENDING"],
              ["Case Resolution", "No separate resolution state"],
            ].map(([label, state], index) => <div className={`fu-lifecycle-item ${statusClass(state)}`} key={label}><span>{index + 1}</span><strong>{label}</strong><small>{valueText(state)}</small></div>)}
          </div>
          <p className="fu-resolution-note">No dedicated case-resolution endpoint is available. A closed follow-up activity is not represented as a resolved case.</p>
        </article>

        <article className="fu-card fu-activity-card">
          <header className="fu-card-header"><div><span className="fu-index">04</span><div><h3>Follow-up Activity</h3><p>Records returned in the case journey. No separate history endpoint is available.</p></div></div></header>
          {followups.length ? <div className="fu-activity-list">{followups.slice().reverse().map((record, index) => <div className="fu-activity-item" key={record.followup_id || `${record.action}-${record.created_at || index}`}><span className={`fu-activity-dot ${statusClass(record.status)}`} /><div><strong>{valueText(record.action)} · {valueText(record.status)}</strong><p>{record.notes || "No notes recorded."}</p><small>{valueText(record.created_at)}{record.followup_id ? ` · ${record.followup_id}` : ""}</small></div></div>)}</div> : <p className="fu-empty-activity">No follow-up activity is recorded in the case journey.</p>}
          {recordsByEvent.length > followups.length && <small className="fu-activity-note">The journey also contains {recordsByEvent.length} follow-up event(s); only persisted follow-up records are listed above.</small>}
        </article>
      </div>

      <aside className="fu-aside">
        <article className="fu-side-card"><span>FOLLOW-UP STATUS</span><strong className={`fu-status-text ${statusClass(followupStatus)}`}>{valueText(followupStatus)}</strong><p>{currentFollowup ? `Latest backend action: ${valueText(currentFollowup.action)}` : "No follow-up action has been processed yet."}</p><small>Agent: Public Health Follow-up Agent</small></article>
        <article className="fu-side-card"><span>CASE SUMMARY</span><div><label>Patient</label><strong>{patientName(patient)}</strong></div><div><label>Disease</label><strong>{valueText(caseData.disease)}</strong></div><div><label>Jurisdiction</label><strong>{valueText(caseData.jurisdiction)}</strong></div><div><label>Case status</label><strong>{valueText(caseData.status)}</strong></div><div><label>Reportability</label><strong>{valueText(caseData.final_decision || caseData.reportability_decision)}</strong></div><div><label>Reporting rule</label><strong>{valueText(caseData.rule_id)}</strong></div><div><label>Submission status</label><strong>{valueText(submissionStatus)}</strong></div><div><label>Destination</label><strong>{valueText(destination)}</strong></div></article>
        <article className="fu-side-card fu-next-card"><span>WHAT HAPPENS NEXT</span><div><label>Current</label><strong>{currentFollowup?.status === "CLOSED" ? "Follow-up Completed" : "PHA Follow-up"}</strong></div><div><label>Next</label><strong>{currentFollowup?.status === "CLOSED" ? "Case resolution (not exposed by this service)" : currentFollowup ? "Document follow-up outcome" : "Process a supported follow-up action"}</strong></div><p>Submission acknowledgement confirms the reporting workflow state; it does not mean the case is resolved.</p></article>
        <button className="fu-return" onClick={() => navigate(`${caseWorkspacePath}/submission`)}>← Back to Submission</button>
        <button className="fu-return secondary" onClick={() => navigate(caseWorkspacePath)}>Back to Case Workspace</button>
      </aside>
    </main>
  </section>;
}
