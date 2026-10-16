import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { useDemoWorkflow } from "../hooks/useDemoWorkflow.js";
import { getCase, getJourney } from "../api/signal.js";
import "../styles/CaseCompletion.css";

const array = (value) => Array.isArray(value) ? value : [];
const text = (value) => value === null || value === undefined || value === "" ? "Not recorded" : String(value);
const findStage = (journey, name) => array(journey?.journey).find((item) => item.stage === name) || null;
const latest = (values) => values.length ? values[values.length - 1] : null;
const patientName = (patient) => [patient?.first_name, patient?.last_name].filter(Boolean).join(" ") || patient?.name || "Patient name not returned";
const readable = (value) => String(value || "").replaceAll("_", " ");

const WORKFLOW_STAGES = [
  ["DATA_INGESTION", "Data Ingestion"], ["DETECTION", "Detection"],
  ["REPORTABILITY", "Reportability"], ["CASE", "Case"], ["VALIDATION", "Validation"],
  ["REPORTING", "Reporting"], ["SUBMISSION", "Submission"],
];

function deriveStatus(stages, submission, journeyAvailable) {
  if (!journeyAvailable) return { label: "STATUS NOT FULLY DETERMINED", tone: "unknown", reason: "The case journey could not be loaded." };
  if (!stages.REPORTABILITY || !stages.CASE || !stages.VALIDATION || !stages.REPORTING || !stages.SUBMISSION) {
    return { label: "STATUS NOT FULLY DETERMINED", tone: "unknown", reason: "One or more required workflow stages were not returned." };
  }
  const validation = stages.VALIDATION.status;
  const submissionStatus = String(submission?.status || "").toUpperCase();
  if (["INVALID", "NEEDS_COMPLETION", "FAILED"].includes(validation) || /REJECT|FAIL|ERROR/.test(submissionStatus) || array(submission?.errors).length > 0) {
    return { label: "ACTION REQUIRED", tone: "attention", reason: "A workflow stage or submission reports an issue that needs attention." };
  }
  const requiredCompleted = ["REPORTABILITY", "CASE", "VALIDATION", "REPORTING", "SUBMISSION"]
    .every((name) => stages[name]?.status === "COMPLETED");
  if (requiredCompleted) {
    return { label: "REPORTING WORKFLOW COMPLETE", tone: "complete", reason: "The backend journey records reporting and submission as complete. This does not assert a separate case-resolution state." };
  }
  const hasOperationalProgress = ["REPORTABILITY", "CASE", "VALIDATION", "REPORTING", "SUBMISSION"]
    .some((name) => stages[name]?.available || stages[name]?.status === "COMPLETED" || stages[name]?.status === "CURRENT");
  if (hasOperationalProgress) return { label: "WORKFLOW IN PROGRESS", tone: "progress", reason: "At least one required operational stage is still pending or current." };
  return { label: "STATUS NOT FULLY DETERMINED", tone: "unknown", reason: "The returned workflow data is insufficient to determine completion." };
}

function displayTime(value) {
  if (!value) return "Timestamp not returned";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function StatusPill({ children, tone = "unknown" }) {
  return <span className={`completion-status-pill ${tone}`}>{text(children)}</span>;
}

function Field({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return <div className="completion-field"><dt>{label}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>;
}

export default function CaseCompletion() {
  const { patientId: routePatientId, caseId = "" } = useParams();
  const navigate = useNavigate();
  const demo = useDemoWorkflow(caseId);
  const [caseData, setCaseData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [loading, setLoading] = useState(true);
  const [caseError, setCaseError] = useState("");
  const [journeyError, setJourneyError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setCaseError(""); setJourneyError("");
    const [caseResult, journeyResult] = await Promise.allSettled([getCase(caseId), getJourney(caseId)]);
    if (caseResult.status === "fulfilled") setCaseData(caseResult.value?.data || caseResult.value);
    else { setCaseData(null); setCaseError(caseResult.reason?.message || "Unable to load case completion information."); }
    if (journeyResult.status === "fulfilled") setJourney(journeyResult.value?.data || journeyResult.value);
    else { setJourney(null); setJourneyError(journeyResult.reason?.message || "Workflow journey information is currently unavailable."); }
    setLoading(false);
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const stages = useMemo(() => {
    const result = Object.fromEntries(WORKFLOW_STAGES.map(([name]) => [name, findStage(journey, name)]));
    if (!demo.active) return result;
    const sessionKeys = { VALIDATION: "validation", REPORTING: "reporting", SUBMISSION: "submission" };
    for (const [name, key] of Object.entries(sessionKeys)) {
      if (!result[name]) continue;
      result[name] = { ...result[name], status: demo.stages[key] === "COMPLETED" ? "COMPLETED" : "PENDING", available: true };
    }
    return result;
  }, [demo.active, demo.stages, journey]);
  const submissionList = array(stages.SUBMISSION?.data?.submissions);
  const persistedSubmission = latest(submissionList) || caseData?.submission || null;
  const submission = demo.active && demo.stages.submission !== "COMPLETED" ? null : persistedSubmission;
  const auditEvents = array(journey?.supporting_audit_events);
  const finalStatus = deriveStatus(stages, submission, Boolean(journey));
  const destination = submission?.destination;
  const simulated = destination === "MOCK_PHA";
  const submissionStatus = submission?.status || stages.SUBMISSION?.status || "Not recorded";
  const patient = caseData?.patient || {};
  const patientId = routePatientId || patient.patient_id || caseData?.patient_id || "";
  const patientPath = patientId ? `/patients/${encodeURIComponent(patientId)}` : "";
  const caseWorkspacePath = patientId
    ? `${patientPath}/case/${encodeURIComponent(caseId)}`
    : `/cases/${encodeURIComponent(caseId)}`;
  const reportingFormPath = `${caseWorkspacePath}/reporting-form`;
  const submissionPath = `${caseWorkspacePath}/submission`;
  const eventList = auditEvents.slice().reverse().slice(0, 20);

  const next = (() => {
    if (finalStatus.tone === "complete") return { label: "No further workflow action recorded", button: "Return to Cases", path: "/cases" };
    if (/REJECT|FAIL|ERROR/i.test(submissionStatus)) return { label: "Review submission and retry if available", button: "Return to Submission", path: submissionPath };
    if (["INVALID", "NEEDS_COMPLETION", "FAILED"].includes(stages.VALIDATION?.status)) return { label: "Resolve case validation items", button: "View Case Workspace", path: caseWorkspacePath };
    if (stages.REPORTING?.status !== "COMPLETED") return { label: "Continue reporting preparation", button: "Return to Reporting Form", path: reportingFormPath };
    if (!submission) return { label: "Continue the submission workflow", button: "Return to Submission", path: submissionPath };
    return { label: "Review the case workspace", button: "View Case Workspace", path: caseWorkspacePath };
  })();

  if (loading) return <section className="case-completion-page"><SignalLoading title="Preparing Final Status" message="Gathering workflow and reporting outcomes." /></section>;
  if (!caseData) return <section className="case-completion-page"><div className="completion-load-error" role="alert"><strong>Unable to load case completion information.</strong><span>{caseError || "Case data is unavailable."}</span><div><button onClick={load}>Retry</button><button onClick={() => navigate(patientId ? `/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(caseId)}` : `/cases/${encodeURIComponent(caseId)}`)}>Back to Case Workspace</button></div></div></section>;

  const jurisdiction = caseData.jurisdiction;
  const disease = caseData.disease;

  return <section className="case-completion-page">
    <header className="completion-header">
      <div>
        <button className="completion-back" onClick={() => navigate(submissionPath)}>← Back to Submission</button>
        <nav className="completion-breadcrumb" aria-label="Workflow"><span>Case Workspace</span><i>›</i><span>Reporting Form</span><i>›</i><span>Submission</span><i>›</i><b>Completion</b></nav>
        <span className="completion-eyebrow">PUBLIC HEALTH CASE OPERATIONS</span>
        <h2>Case Completion &amp; Audit</h2>
        <p>Final workflow status, reporting outcome, and available audit information for this case.</p>
      </div>
      <div className="completion-jurisdiction"><span>{text(jurisdiction)}</span><strong>{text(disease)}</strong><small>Case ID · {String(caseData.case_id || caseId).slice(0, 12)}…</small></div>
    </header>

    {simulated && <div className="completion-simulation"><strong>SIMULATION ENVIRONMENT</strong><span>This case used the SIGNAL mock public-health destination ({destination}). No real Texas DSHS transmission occurred.</span></div>}
    {journeyError && <div className="completion-journey-warning" role="status"><strong>Workflow journey information is currently unavailable.</strong><span>{journeyError} The available case information is still shown below.</span></div>}

    <div className="completion-context">
      <div><span>Patient</span><strong>{patientName(patient)}</strong></div><div><span>MRN</span><strong>{text(patient.source_patient_id || patient.patient_id)}</strong></div><div><span>DOB</span><strong>{text(patient.date_of_birth)}</strong></div><div><span>Case</span><strong>{caseData.case_id || caseId}</strong></div><div><span>Disease</span><strong>{text(disease)}</strong></div><div><span>Jurisdiction</span><strong>{text(jurisdiction)}</strong></div>
    </div>

    <div className="completion-summary">
      <article><span>FINAL WORKFLOW STATUS</span><strong className={`final-status-text ${finalStatus.tone}`}>{finalStatus.label}</strong><small>Derived from workflow stages</small></article>
      <article><span>REPORTABILITY</span><strong>{text(caseData.reportability_decision)}</strong><small>Rule: {text(caseData.rule_id)}</small></article>
      <article><span>REPORTING STATUS</span><strong>{text(submissionStatus)}</strong><small>{submission?.submission_id || "Submission ID not recorded"}</small></article>
    </div>

    <main className="completion-grid">
      <div className="completion-primary">
        <article className="completion-card">
          <header className="completion-card-header"><div><span className="completion-index">01</span><div><h3>Final Workflow Status</h3><p>Current end-to-end status from backend-recorded workflow stages.</p></div></div></header>
          <div className={`completion-status-hero ${finalStatus.tone}`}><span>FINAL WORKFLOW STATUS</span><strong>{finalStatus.label}</strong><p>{finalStatus.reason}</p><small>Case status remains separate: {text(caseData.status)}</small></div>
          <div className="completion-timeline">{WORKFLOW_STAGES.map(([name, label]) => {
            const item = stages[name];
            const state = item?.status || (item?.available === false ? "NOT_AVAILABLE" : "NOT_RECORDED");
            const note = item?.agent || item?.source || item?.limitations?.[0] || item?.error || "No additional stage detail returned.";
            return <div className={`completion-timeline-item ${String(state).toLowerCase()}`} key={name}><span className="completion-timeline-mark">{item?.status === "COMPLETED" ? "✓" : item?.status === "CURRENT" ? "●" : "·"}</span><div><strong>{label}</strong><StatusPill tone={String(state).toLowerCase()}>{readable(state)}</StatusPill><p>{note}</p></div></div>;
          })}<div className={`completion-timeline-item ${finalStatus.tone}`}><span className="completion-timeline-mark">●</span><div><strong>Completion</strong><StatusPill tone={finalStatus.tone}>{finalStatus.label}</StatusPill><p>Final status view; no separate case-resolution stage is exposed by the backend.</p></div></div></div>
        </article>

        <article className="completion-card">
          <header className="completion-card-header"><div><span className="completion-index">02</span><div><h3>Reporting Outcome</h3><p>Submission and acknowledgement details returned by the case journey.</p></div></div></header>
          {submission ? <dl className="completion-fields">
            <Field label="Disease" value={disease} /><Field label="Jurisdiction" value={jurisdiction} /><Field label="Reportability Decision" value={caseData.reportability_decision} /><Field label="Reporting Rule" value={caseData.rule_id} /><Field label="Destination" value={submission.destination} /><Field label="Submission Status" value={submission.status} /><Field label="ECR ID" value={submission.ecr_id} /><Field label="Submission ID" value={submission.submission_id} /><Field label="Acknowledgement Status" value={submission.acknowledgement_status || (/ACKNOWLEDGED/i.test(submission.status || "") ? "ACKNOWLEDGED" : undefined)} /><Field label="Created" value={submission.created_at} /><Field label="Updated" value={submission.updated_at} />
          </dl> : <p className="completion-empty">No submission record is available in the journey or case response.</p>}
          {array(submission?.warnings).length > 0 && <div className="completion-response-list"><strong>Backend warnings</strong><ul>{array(submission.warnings).map((warning, index) => <li key={`warning-${index}`}>{warning}</li>)}</ul></div>}
          {array(submission?.errors).length > 0 && <div className="completion-response-list errors"><strong>Backend errors</strong><ul>{array(submission.errors).map((entry, index) => <li key={`error-${index}`}>{typeof entry === "string" ? entry : JSON.stringify(entry)}</li>)}</ul></div>}
          {simulated && array(submission?.warnings).length === 0 && <p className="completion-simulation-note">The destination is simulated; no real PHA response or transmission is established by this record.</p>}
        </article>
      </div>

      <aside className="completion-aside">
        <article className="completion-side-card"><span>CASE SUMMARY</span><div><label>Patient</label><strong>{patientName(patient)}</strong></div><div><label>Disease</label><strong>{text(disease)}</strong></div><div><label>Jurisdiction</label><strong>{text(jurisdiction)}</strong></div><div><label>Case status</label><strong>{text(caseData.status)}</strong></div><div><label>Reportability</label><strong>{text(caseData.reportability_decision)}</strong></div><div><label>Reporting rule</label><strong>{text(caseData.rule_id)}</strong></div><div><label>Submission</label><strong>{text(submissionStatus)}</strong></div></article>

        <article className="completion-card audit-card">
          <header className="completion-card-header"><div><span className="completion-index">03</span><div><h3>Audit Information</h3><p>Events returned in supporting journey data.</p></div></div></header>
          {auditEvents.length ? <><div className="completion-audit-list">{eventList.map((event, index) => <details className="completion-audit-event" key={`${event.event_type || "event"}-${event.event_timestamp || event.created_at || index}`}>
            <summary><span><strong>{text(event.event_type)}</strong><small>{displayTime(event.event_timestamp || event.created_at)}</small></span><StatusPill tone={String(event.status || "").toLowerCase()}>{event.status || event.actor_type || "Event"}</StatusPill></summary>
            <dl><Field label="Actor" value={event.actor_id || event.actor_type} /><Field label="Source" value={event.source_agent} /><Field label="Entity" value={event.entity_type ? `${event.entity_type} · ${event.entity_id || ""}` : undefined} /><Field label="Description" value={event.description} /></dl>
            {(event.metadata || event.new_value) && <pre>{JSON.stringify({ ...(event.metadata ? { metadata: event.metadata } : {}), ...(event.new_value ? { new_value: event.new_value } : {}) }, null, 2)}</pre>}
          </details>)}</div>{auditEvents.length > eventList.length && <small className="completion-audit-count">Showing latest {eventList.length} of {auditEvents.length} journey audit events.</small>}</> : <div className="completion-audit-empty"><strong>Audit history</strong><p>{journey ? "No audit events were returned for this case in the journey response. The backend exposes audit event creation, but no separate audit-history retrieval endpoint." : "Audit history is recorded by SIGNAL, but the current backend does not expose a read endpoint for audit history."}</p><small>Audit Event Service · recording capability available</small></div>}
        </article>

        <article className="completion-side-card completion-next-card"><span>WHAT HAPPENS NEXT</span><label>Current</label><strong>{finalStatus.tone === "complete" ? "Case workflow complete" : next.label}</strong><label>Next</label><strong>{next.label}</strong><p>Workflow completion and case resolution are distinct; no resolution state is asserted here.</p><button onClick={() => navigate(next.path)}>{next.button}</button></article>
        <button className="completion-return" onClick={() => navigate("/cases")}>Return to Cases</button>
        <button className="completion-return secondary" onClick={() => navigate(caseWorkspacePath)}>View Case Workspace</button>
        {patientPath && <button className="completion-return secondary" onClick={() => navigate(patientPath)}>Back to Patient</button>}
      </aside>
    </main>
  </section>;
}
