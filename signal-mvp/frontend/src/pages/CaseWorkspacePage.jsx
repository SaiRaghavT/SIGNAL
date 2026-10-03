import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getCase, getCaseJourney, updateCaseReportFields } from "../api/cases.js";
import { acknowledge, followUp, getFormDefinition, prepareManualReport, renderForm, submitEcr, trackSubmission, validateAttestation } from "../api/workflow.js";
import { apiBaseUrl } from "../api/client.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { Loading, ErrorState } from "../components/ui/Loading.jsx";
import { StatusBadge } from "../components/ui/StatusBadge.jsx";
import "../styles/case-workspace.css";
import "../styles/case-report-fields.css";

const stages = ["DATA_INGESTION", "DETECTION", "CANDIDATE", "REPORTABILITY", "CASE", "VALIDATION", "REPORTING", "SUBMISSION", "PHA_FOLLOW_UP"];
const stageLabels = { DATA_INGESTION: "Data ingestion", DETECTION: "Detection", CANDIDATE: "Candidate", REPORTABILITY: "Reportability", CASE: "Case", VALIDATION: "Validation", REPORTING: "Reporting", SUBMISSION: "Submission", PHA_FOLLOW_UP: "PHA follow-up" };
const pretty = (value) => JSON.stringify(value, null, 2);

function currentReviewer() {
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const user = JSON.parse(storage.getItem("signal-user") || "null");
      if (user) return { id: user.email || user.name || "reporting_user", name: user.name || "Reporting Staff" };
    } catch { /* Use the service's configured reporting role if no session is present. */ }
  }
  return { id: "reporting_user", name: "Reporting Staff" };
}

function readable(value) {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "object") return pretty(value);
  return String(value);
}

export function CaseWorkspacePage() {
  const { caseId = "" } = useParams();
  const location = useLocation();
  const workflowResult = location.state?.workflowResult;
  const [data, setData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [reportFields, setReportFields] = useState({});
  const [formDefinition, setFormDefinition] = useState(null);
  const [providerFields, setProviderFields] = useState({});
  const [facilityFields, setFacilityFields] = useState({});
  const [manualPackage, setManualPackage] = useState(null);
  const [lastAction, setLastAction] = useState(workflowResult || null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const reload = useCallback(async () => {
    const [caseData, journeyData] = await Promise.all([getCase(caseId), getCaseJourney(caseId)]);
    setData(caseData);
    setJourney(journeyData);
    setReportFields(caseData.report_fields || {});
    setProviderFields(caseData.provider || {});
    setFacilityFields(caseData.facility || {});
  }, [caseId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([getCase(caseId), getCaseJourney(caseId)])
      .then(([caseData, journeyData]) => {
        if (!active) return;
        setData(caseData);
        setJourney(journeyData);
        setReportFields(caseData.report_fields || {});
        setProviderFields(caseData.provider || {});
        setFacilityFields(caseData.facility || {});
      })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [caseId, refreshKey]);

  const journeyByStage = useMemo(() => new Map((journey?.journey || []).map((item) => [item.stage, item])), [journey]);
  const validation = journeyByStage.get("VALIDATION")?.data;
  const latestSubmission = journeyByStage.get("SUBMISSION")?.data?.submissions?.slice(-1)[0];

  async function perform(name, operation, shouldReload = true) {
    setBusy(name);
    setError("");
    try {
      const result = await operation();
      setLastAction(result);
      if (shouldReload) await reload();
      return result;
    } catch (requestError) {
      setError(requestError.message);
      return null;
    } finally {
      setBusy("");
    }
  }

  async function saveReportFields() {
    await perform("save", () => updateCaseReportFields(caseId, {
      report_fields: reportFields,
      provider: providerFields,
      facility: facilityFields,
      reviewer_id: currentReviewer().id,
    }));
  }

  async function prepareReport() {
    const result = await perform("prepare", () => prepareManualReport({ case_id: caseId, reporting_method: "FORM" }), false);
    if (result) {
      setManualPackage(result);
      try { setFormDefinition(await getFormDefinition(result.form_id)); }
      catch (requestError) { setError(requestError.message); }
    }
  }

  async function generateReport() {
    const refreshedPackage = await perform("prepare", () => prepareManualReport({ case_id: caseId, reporting_method: "FORM" }), false);
    if (!refreshedPackage) return;
    setManualPackage(refreshedPackage);
    try { setFormDefinition(await getFormDefinition(refreshedPackage.form_id)); }
    catch (requestError) { setError(requestError.message); return; }
    const result = await perform("render", () => renderForm({ case_id: caseId, form_id: refreshedPackage.form_id, form_version: refreshedPackage.form_version, report_data: refreshedPackage.report_data }), false);
    if (result) setManualPackage((current) => ({ ...current, rendered: result }));
  }

  async function attest() {
    const reviewer = currentReviewer();
    await perform("review", () => validateAttestation({
      case_reference: caseId,
      reviewer_id: reviewer.id,
      reviewer_role: "REPORTING_STAFF",
      attestation_status: "ATTESTED",
      comments: "Reviewed in SIGNAL case workspace.",
    }));
  }

  if (loading) return <section><Loading /></section>;
  if (error && !data) return <section><ErrorState message={error} /><button className="primary" onClick={() => setRefreshKey((value) => value + 1)}>Retry</button></section>;
  if (!data) return null;

  const submissionId = latestSubmission?.submission_id;
  const validationValid = validation?.valid;

  return (
    <section className="case-workspace">
      <PageHeader title="Reportable case" subtitle={`${data.disease || "Disease not available"} · ${data.jurisdiction || "Jurisdiction not available"}`}>
        <StatusBadge value={data.status} />
      </PageHeader>

      {error && <div className="error-state" role="alert"><span>{error}</span><button onClick={() => setError("")}>Dismiss</button></div>}

      <section className="case-journey panel">
        <div className="case-section-title"><div><h2>Workflow journey</h2><p>Stages and status returned by the case journey API.</p></div><button onClick={() => setRefreshKey((value) => value + 1)}>Refresh journey</button></div>
        <ol>{stages.map((stage) => {
          const item = journeyByStage.get(stage);
          const complete = Boolean(item?.available && item?.status && !["PENDING", "NEEDS_COMPLETION", "INVALID"].includes(item.status));
          const current = journey?.current_stage === stage;
          return <li className={`${complete ? "complete" : "pending"} ${current ? "current" : ""}`} key={stage}><span className="journey-step-dot">{complete ? "✓" : "·"}</span><span>{stageLabels[stage]}</span><small>{item?.available ? item.status || "Recorded" : "Not recorded"}</small></li>;
        })}</ol>
        {journeyByStage.get("DATA_INGESTION")?.limitations?.map((item) => <p className="case-limitation" key={item}>{item}</p>)}
      </section>

      <div className="case-workspace-grid">
        <div className="case-workspace-main">
          <section className="panel">
            <div className="case-section-title"><div><h2>Review summary</h2><p>Persisted case, evidence, jurisdiction, and decisions.</p></div></div>
            <div className="case-review-grid">
              <div><span>Patient</span><strong>{[data.patient?.first_name, data.patient?.last_name].filter(Boolean).join(" ") || data.patient?.name || "Not available"}</strong></div>
              <div><span>Patient ID</span><strong>{data.patient?.patient_id || "Not available"}</strong></div>
              <div><span>DOB</span><strong>{data.patient?.date_of_birth || "Not available"}</strong></div>
              <div><span>Disease</span><strong>{data.disease || "Not available"}</strong></div>
              <div><span>Jurisdiction</span><strong>{data.jurisdiction || "Not available"} · {data.jurisdiction_status}</strong></div>
              <div><span>Reportability</span><strong>{data.final_decision || data.reportability_decision}</strong></div>
              <div><span>Rule</span><strong>{data.rule_id || "Not available"}</strong></div>
              <div><span>Case</span><strong>{data.case_id}</strong></div>
            </div>
            <div className="case-evidence-grid">
              <EvidenceBlock title="Clinical evidence" value={data.clinical_evidence} />
              <EvidenceBlock title="Laboratory evidence" value={data.laboratory_evidence} />
              <EvidenceBlock title="Provider and facility" value={{ provider: data.provider, facility: data.facility }} />
            </div>
            {!!data.warnings?.length && <ul className="case-warning-list">{data.warnings.map((warning, index) => <li key={index}>{typeof warning === "string" ? warning : readable(warning)}</li>)}</ul>}
          </section>

          <section className="panel">
            <div className="case-section-title"><div><h2>Texas measles reporting form</h2><p>Fields are persisted by the case API and updated through backend validation.</p></div><button onClick={prepareReport} disabled={busy !== ""}>{busy === "prepare" ? "Preparing…" : "Prepare form"}</button></div>
            {formDefinition ? <div className="case-report-fields-grid">
              {formDefinition.fields.map((field) => (
                <label className="case-report-field" key={field.field}>
                  <span>{field.field.replaceAll(".", " · ")}{field.required ? <b>Required</b> : null}</span>
                  <input value={reportFields[field.field] ?? ""} onChange={(event) => {
                    const previous = reportFields[field.field];
                    const value = typeof previous === "boolean" ? event.target.value === "true" : typeof previous === "number" && event.target.value !== "" ? Number(event.target.value) : event.target.value;
                    setReportFields((current) => ({ ...current, [field.field]: value }));
                  }} placeholder="Not available" />
                  <small>Source: {field.source || "Not specified"}</small>
                </label>
              ))}
              <h3 className="case-report-subheading">Provider and facility details</h3>
              {["name", "phone", "address"].map((key) => <label className="case-report-field" key={`provider.${key}`}><span>Provider · {key}</span><input value={providerFields[key] ?? ""} onChange={(event) => setProviderFields((current) => ({ ...current, [key]: event.target.value }))} placeholder="Not available" /></label>)}
              <label className="case-report-field"><span>Facility · name</span><input value={facilityFields.name ?? ""} onChange={(event) => setFacilityFields((current) => ({ ...current, name: event.target.value }))} placeholder="Not available" /></label>
            </div> : <div className="patients-state"><span>Prepare the case form to load the backend form fields.</span></div>}
            <div className="button-row"><button className="primary" onClick={saveReportFields} disabled={busy !== ""}>{busy === "save" ? "Saving…" : "Save fields and validate"}</button></div>
            {validation && <div className={`case-validation ${validationValid ? "valid" : "incomplete"}`}>
              <strong>{validationValid ? "Backend validation passed" : "Backend validation needs completion"}</strong>
              <ul>{[...(validation.errors || []), ...(validation.completion_required || []), ...(validation.warnings || [])].map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
              {!validation.errors?.length && !validation.completion_required?.length && !validation.warnings?.length && <p>No backend validation issues were returned.</p>}
            </div>}
            {manualPackage && <div className="case-form-result"><strong>{manualPackage.form_id || "Reporting form"} · {manualPackage.form_version || "Version not returned"}</strong><p>Status: {manualPackage.status}</p>
              {!!manualPackage.missing_fields?.length && <p>Missing: {manualPackage.missing_fields.join(", ")}</p>}
              {!!manualPackage.warnings?.length && <ul>{manualPackage.warnings.map((item, index) => <li key={index}>{item}</li>)}</ul>}
              {manualPackage.rendered?.retrieval_url && <a href={`${apiBaseUrl}${manualPackage.rendered.retrieval_url}`} target="_blank" rel="noreferrer">Open rendered reporting form (PDF)</a>}
            </div>}
          </section>

          <section className="panel">
            <div className="case-section-title"><div><h2>Report and submission</h2><p>Preparation, form rendering, attestation, and submission are handled by existing backend services.</p></div></div>
            <div className="case-workflow-actions">
              <button onClick={generateReport} disabled={busy !== ""}>{busy === "render" || busy === "prepare" ? "Working…" : "Generate reporting form"}</button>
              <button className="primary" onClick={attest} disabled={busy !== "" || data.final_decision !== "REPORT"}>{busy === "review" ? "Reviewing…" : "Review and attest"}</button>
              <button className="primary" onClick={() => perform("submit", () => submitEcr(caseId))} disabled={busy !== "" || data.status !== "REPORT"}>{busy === "submit" ? "Submitting…" : "Submit eCR"}</button>
            </div>
            {latestSubmission && <div className="case-submission-state"><strong>Submission: {latestSubmission.status}</strong><span>ID: {latestSubmission.submission_id}</span><span>Destination: {latestSubmission.destination}</span>{latestSubmission.warnings?.map((item, index) => <small key={index}>{item}</small>)}</div>}
            {submissionId && <div className="case-workflow-actions">
              <button onClick={() => perform("track", () => trackSubmission(submissionId))} disabled={busy !== ""}>Track submission</button>
              <button onClick={() => perform("acknowledge", () => acknowledge(submissionId))} disabled={busy !== ""}>Process acknowledgement</button>
            </div>}
            {lastAction && <details className="case-action-result"><summary>Latest backend response</summary><pre className="result">{pretty(lastAction)}</pre></details>}
          </section>

          <section className="panel">
            <div className="case-section-title"><div><h2>PHA follow-up</h2><p>Follow-up actions and acknowledgement integrations are simulated by the existing backend.</p></div></div>
            <div className="case-workflow-actions">
              {["REQUEST_INFORMATION", "INVESTIGATION", "OUTCOME_UPDATE", "CLOSE"].map((action) => <button key={action} onClick={() => perform(`followup-${action}`, () => followUp({ case_id: caseId, action }))} disabled={busy !== "" || !submissionId}>{action.replaceAll("_", " ")}</button>)}
            </div>
            <FollowupSummary journey={journeyByStage.get("PHA_FOLLOW_UP")} />
          </section>
        </div>

        <aside className="case-workspace-rail">
          <section className="panel"><h2>Workflow status</h2><StatusBadge value={data.status} /><p>{data.reportability_evidence_status || "Reportability evidence status not available"}</p><small>Current journey stage: {stageLabels[journey?.current_stage] || journey?.current_stage || "Not returned"}</small></section>
          <section className="panel"><h2>Case identifiers</h2><dl><dt>Case ID</dt><dd>{data.case_id}</dd><dt>Candidate ID</dt><dd>{data.candidate_id}</dd><dt>Created</dt><dd>{new Date(data.created_at).toLocaleString()}</dd><dt>Updated</dt><dd>{new Date(data.updated_at).toLocaleString()}</dd></dl></section>
          <Link to="/cases">← All cases</Link>
        </aside>
      </div>
    </section>
  );
}

function EvidenceBlock({ title, value }) {
  return <details className="case-evidence-block"><summary>{title}</summary><pre>{pretty(value ?? {})}</pre></details>;
}

function FollowupSummary({ journey }) {
  const followups = journey?.data?.follow_ups || [];
  const submissions = journey?.data?.submission_statuses || [];
  return <div className="case-followup-summary">
    <p>Status: {journey?.available ? journey.status || "Recorded" : "No follow-up recorded"}</p>
    {submissions.map((item) => <div key={item.submission_id}>Submission {item.submission_id}: {item.status}{item.acknowledgement_warnings?.length ? ` · ${item.acknowledgement_warnings.join("; ")}` : ""}</div>)}
    {followups.map((item) => <div key={item.followup_id}>{item.action} · {item.status} · {item.created_at ? new Date(item.created_at).toLocaleString() : "Timestamp unavailable"}</div>)}
    {journey?.limitations?.map((item) => <small key={item}>{item}</small>)}
  </div>;
}
