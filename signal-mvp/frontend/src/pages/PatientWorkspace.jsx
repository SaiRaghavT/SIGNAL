import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getCanonicalPatient } from "../api/canonical.js";
import { listCasesForPatient } from "../api/cases.js";
import { detectCandidates, processCandidate } from "../api/detection.js";
import { auditEvent, listAuditEvents } from "../api/workflow.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { Loading, ErrorState } from "../components/ui/Loading.jsx";
import "../styles/patient-workspace.css";

function dateLabel(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function hasMeaslesEvidence(context) {
  const conditions = context?.conditions || [];
  const labs = context?.lab_results || [];
  return conditions.some((item) => /measles/i.test(item.code?.display || item.code?.code || ""))
    || labs.some((item) => /measles/i.test(`${item.test?.display || ""} ${item.test?.code || ""}`));
}

function userIdentity() {
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const user = JSON.parse(storage.getItem("signal-user") || "null");
      if (user) return { id: user.email || user.name || "reporting_user", name: user.name || user.email || "Reporting User" };
    } catch { /* Ignore invalid local session data. */ }
  }
  return { id: "reporting_user", name: "Reporting User" };
}

export default function PatientWorkspace() {
  const { patientId = "" } = useParams();
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);
  const [context, setContext] = useState(null);
  const [existingCases, setExistingCases] = useState([]);
  const [callEvents, setCallEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detection, setDetection] = useState(null);
  const [detectionBusy, setDetectionBusy] = useState(false);
  const [operationBusy, setOperationBusy] = useState(false);
  const [operationError, setOperationError] = useState("");
  const [callConfirmed, setCallConfirmed] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      getCanonicalPatient(patientId),
      listCasesForPatient(patientId),
      listAuditEvents("PATIENT", patientId),
    ])
      .then(([patientContext, casesResult, events]) => {
        if (!active) return;
        setContext(patientContext);
        setExistingCases(casesResult.items || []);
        setCallEvents(events.filter((event) => event.event_type === "IMMEDIATE_CALL_RECORDED"));
      })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [patientId, refreshKey]);

  const patient = context?.patient || {};
  const measlesEvidence = useMemo(() => hasMeaslesEvidence(context) || Boolean(detection?.candidates?.some((item) => item.disease_id?.toLowerCase() === "measles")), [context, detection]);
  const completedCall = callEvents.find((event) => event.status === "COMPLETED" || event.status === "SUCCESS");
  const retry = () => setRefreshKey((value) => value + 1);

  async function recordImmediateCall() {
    setOperationError("");
    setOperationBusy(true);
    try {
      const actor = userIdentity();
      await auditEvent({
        entity_type: "PATIENT",
        entity_id: patientId,
        event_type: "IMMEDIATE_CALL_RECORDED",
        actor_type: "USER",
        actor_id: actor.id,
        source_agent: "SIGNAL UI",
        status: "COMPLETED",
        description: "User recorded completion of the immediate phone notification.",
        new_value: { disease: "measles", notification_method: "PHONE", confirmed_by_user: true },
        metadata: { disease: "measles", notification_method: "PHONE" },
      });
      const events = await listAuditEvents("PATIENT", patientId);
      setCallEvents(events.filter((event) => event.event_type === "IMMEDIATE_CALL_RECORDED"));
      setCallConfirmed(false);
    } catch (requestError) {
      setOperationError(requestError.message);
    } finally {
      setOperationBusy(false);
    }
  }

  async function runDetection() {
    setOperationError("");
    setDetectionBusy(true);
    try {
      const result = await detectCandidates(patientId);
      setDetection(result);
    } catch (requestError) {
      setOperationError(requestError.message);
    } finally {
      setDetectionBusy(false);
    }
  }

  async function openCandidateWorkflow(candidate) {
    const candidateDisease = candidate.disease_id || "measles";
    const evidence = candidate.evidence || [];
    const sourceIds = new Set(evidence.map((item) => item.source_id).filter(Boolean).map(String));
    const matchingCondition = (context.conditions || []).find((item) => sourceIds.has(String(item.condition_id)) || sourceIds.has(String(item.source_condition_id)));
    const matchingLabs = (context.lab_results || []).filter((item) => sourceIds.has(String(item.lab_result_id)) || sourceIds.has(String(item.source_lab_result_id)));
    setOperationError("");
    setOperationBusy(true);
    try {
      const result = await processCandidate({
        candidate_id: patientId,
        patient_id: patientId,
        disease: candidateDisease,
        patient_state: patient.address?.state || null,
        patient_county: patient.address?.county || null,
        clinical_evidence: matchingCondition || {},
        laboratory_evidence: matchingLabs,
        ai_evidence: {},
      });
      const caseId = result.case?.case_id;
      if (!caseId) throw new Error("The workflow response did not include a case ID.");
      navigate(`/cases/${encodeURIComponent(caseId)}`, { state: { workflowResult: result } });
    } catch (requestError) {
      setOperationError(requestError.message);
    } finally {
      setOperationBusy(false);
    }
  }

  if (loading) return <section className="patient-workspace"><Loading /></section>;
  if (error) return <section className="patient-workspace"><ErrorState message={error} /><button className="primary" onClick={retry}>Retry</button></section>;

  const fullName = [patient.first_name, patient.last_name].filter(Boolean).join(" ") || "Patient";
  const sections = [
    ["Conditions", context.conditions || [], (row) => row.code?.display || row.code?.code || "Condition"],
    ["Observations", context.observations || [], (row) => `${row.code?.display || row.code?.code || "Observation"}: ${row.value?.text ?? row.value?.numeric ?? "Not available"}`],
    ["Encounters", context.encounters || [], (row) => `${row.encounter_type || "Encounter"} · ${row.facility_id || "Facility not available"} · ${dateLabel(row.start_time)}`],
    ["Laboratory results", context.lab_results || [], (row) => `${row.test?.display || row.test?.code || "Lab result"} · ${row.conclusion || row.report_status || "Result not available"}`],
    ["Clinical documents", context.clinical_documents || [], (row) => `${row.title || row.document_type || "Clinical document"} · ${row.document_status || "Status not available"}`],
  ];

  return (
    <section className="patient-workspace">
      <PageHeader title={fullName} subtitle="Patient workspace · clinical information and reporting workflow">
        <button className="patients-refresh" onClick={retry}>Refresh</button>
      </PageHeader>

      {existingCases.length > 0 && (
        <div className="patient-existing-case">
          <div><strong>Existing reporting case</strong><span>{existingCases[0].disease || "Disease not available"} · {existingCases[0].status}</span></div>
          <button className="primary" onClick={() => navigate(`/cases/${existingCases[0].case_id}`)}>Continue workflow</button>
        </div>
      )}

      <div className="patient-workspace-grid">
        <section className="patient-workspace-card patient-overview">
          <div className="patient-section-heading"><h2>Patient overview</h2><span>Canonical patient record</span></div>
          <dl>
            <div><dt>First name</dt><dd>{patient.first_name || "Not available"}</dd></div>
            <div><dt>Last name</dt><dd>{patient.last_name || "Not available"}</dd></div>
            <div><dt>Date of birth</dt><dd>{dateLabel(patient.date_of_birth)}</dd></div>
            <div><dt>Sex</dt><dd>{patient.sex || "Not available"}</dd></div>
            <div><dt>Patient ID</dt><dd className="patient-id-value">{patient.patient_id}</dd></div>
            <div><dt>Source patient ID</dt><dd>{patient.source_patient_id || "Not available"}</dd></div>
            <div><dt>Address</dt><dd>{[patient.address?.line, patient.address?.city, patient.address?.county, patient.address?.state, patient.address?.postal_code].filter(Boolean).join(", ") || "Not available"}</dd></div>
          </dl>
        </section>

        <section className="patient-workspace-card patient-call-card">
          <div className="patient-call-label">IMMEDIATE CALL</div>
          {measlesEvidence ? (
            <>
              <h2>Suspected measles evidence</h2>
              <p>Measles appears in the patient&apos;s recorded clinical or laboratory data. Follow the immediate notification process for suspected measles.</p>
              <div className={`patient-call-status ${completedCall ? "is-complete" : "is-pending"}`}>Immediate notification: {completedCall ? "Completed" : "Pending"}</div>
              {completedCall && <small>Recorded {completedCall.event_timestamp ? new Date(completedCall.event_timestamp).toLocaleString() : "Timestamp not available"} by {completedCall.actor_id}</small>}
              {!completedCall && (
                <div className="patient-call-confirm">
                  <label><input type="checkbox" checked={callConfirmed} onChange={(event) => setCallConfirmed(event.target.checked)} /> I confirm the immediate phone notification has been made.</label>
                  <button className="primary" disabled={!callConfirmed || operationBusy} onClick={recordImmediateCall}>{operationBusy ? "Recording…" : "Record notification"}</button>
                </div>
              )}
              <small>This records your confirmation in the audit ledger. SIGNAL does not place a phone call or provide authority contact details.</small>
            </>
          ) : (
            <><h2>No measles evidence identified</h2><p>The canonical patient record has no condition or laboratory display indicating measles.</p></>
          )}
        </section>
      </div>

      {operationError && <div className="patients-state patients-error" role="alert"><span>{operationError}</span><button onClick={() => setOperationError("")}>Dismiss</button></div>}

      <section className="patient-workspace-card patient-clinical-section">
        <div className="patient-section-heading"><h2>Clinical information</h2><span>Loaded from canonical patient context</span></div>
        <div className="patient-clinical-grid">
          {sections.map(([title, rows, label]) => (
            <article className="patient-clinical-card" key={title}>
              <h3>{title}<span>{rows.length}</span></h3>
              {rows.length ? <ul>{rows.map((row, index) => <li key={row.encounter_id || row.condition_id || row.observation_id || row.lab_result_id || row.document_id || index}>{label(row)}</li>)}</ul> : <p>No {title.toLowerCase()} returned by the backend.</p>}
            </article>
          ))}
        </div>
      </section>

      <section className="patient-workspace-card patient-provider-card">
        <div className="patient-section-heading"><h2>Provider and facility</h2><span>Canonical data available</span></div>
        <div className="patient-provider-grid">
          <div><strong>Facility</strong><span>{(context.encounters || []).map((item) => item.facility_id).filter(Boolean).filter((value, index, all) => all.indexOf(value) === index).join(", ") || "Facility details not available in the current canonical model."}</span></div>
          <div><strong>Provider</strong><span>{(context.lab_results || []).map((item) => item.performer_reference).filter(Boolean).join(", ") || (context.clinical_documents || []).map((item) => item.author_reference).filter(Boolean).join(", ") || "Provider details not available in the current canonical model."}</span></div>
        </div>
      </section>

      <section className="patient-workspace-card patient-detection-card">
        <div className="patient-section-heading"><div><h2>Detection and candidate</h2><p>Run the existing backend detector against this patient&apos;s canonical information.</p></div>
          <button className="primary" disabled={detectionBusy || operationBusy} onClick={runDetection}>{detectionBusy ? "Detecting…" : "Run detection"}</button>
        </div>
        {detection ? (
          <>
            <div className="patient-detection-summary">{detection.candidate_count} potential candidate(s) · {detection.signal_count} signal(s)</div>
            {detection.candidates?.length ? detection.candidates.map((candidate, index) => (
              <article className="patient-candidate" key={`${candidate.disease_id}-${candidate.encounter_id || index}`}>
                <div><strong>{candidate.disease_id || "Disease not identified"}</strong><span>{candidate.status} · {candidate.supporting_signal_count} supporting signal(s)</span></div>
                <ul>{(candidate.evidence || []).map((item, evidenceIndex) => <li key={`${item.source_id || "evidence"}-${evidenceIndex}`}>{item.source_type || "Evidence"}: {item.display || item.code || item.source_id || "Details unavailable"}</li>)}</ul>
                <button className="primary" disabled={operationBusy} onClick={() => openCandidateWorkflow(candidate)}>{operationBusy ? "Processing…" : "Run reportability workflow"}</button>
              </article>
            )) : <div className="patients-state"><strong>No candidates detected</strong><span>The backend found no candidate signals for this patient.</span></div>}
          </>
        ) : <p className="patient-muted-copy">Detection has not been run in this workspace.</p>}
      </section>

      <div className="patient-workspace-footer"><Link to="/patients">← Back to patients</Link></div>
    </section>
  );
}
