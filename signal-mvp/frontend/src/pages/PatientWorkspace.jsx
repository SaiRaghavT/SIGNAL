import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { getCanonicalPatient, listCanonicalPatients } from "../api/canonical.js";
import { getCase, getCaseJourney, listCasesForPatient } from "../api/cases.js";
import { getImmediateNotification, recordImmediateNotification } from "../api/workflow.js";
import { ErrorState } from "../components/ui/Loading.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { useDemoWorkflow } from "../hooks/useDemoWorkflow.js";
import { resetDemoWorkflow } from "../state/demoWorkflow.js";
import "../styles/patient-workspace.css";

const TABS = ["Overview", "Encounters", "Evidence", "Case"];

function readable(value) {
  if (value === null || value === undefined || value === "") return "Not available";
  return String(value);
}

function containsMeaslesCondition(value) {
  if (typeof value === "string") return /\bmeasles\b/i.test(value);
  if (Array.isArray(value)) return value.some(containsMeaslesCondition);
  if (!value || typeof value !== "object") return false;
  return ["display", "code", "text", "name", "disease", "condition"].some((key) =>
    containsMeaslesCondition(value[key]),
  );
}

function requestErrorMessage(error) {
  const message = error?.message;
  return typeof message === "string" && !message.includes("[object Object]")
    ? message
    : "";
}

function dateTimeLabel(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function dateLabel(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function currentReportingUser() {
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const user = JSON.parse(storage.getItem("signal-user") || "null");
      const name = user?.name || user?.email;
      if (typeof name === "string" && name.trim()) return name.trim();
    } catch {
      continue;
    }
  }
  return "";
}

async function loadPatientNavigation(patientId, suppliedNavigation) {
  if (suppliedNavigation?.patientIds?.includes(patientId)) {
    return suppliedNavigation;
  }
  const firstPage = await listCanonicalPatients({
    page: 1,
    page_size: 10,
  });
  return {
    page: firstPage.page,
    pageSize: firstPage.page_size,
    pages: firstPage.pages,
    patientIds: (firstPage.items || []).map((item) => item.patient_id),
  };
}

function PatientFields({ patient, summary }) {
  const address = patient.address || {};
  const contact = [
    address.line,
    address.city,
    address.county,
    address.state,
    address.postal_code,
  ].filter(Boolean).join(", ");

  return (
    <section className="patient-workspace-card">
      <div className="patient-section-heading">
        <div>
          <h2>Patient information</h2>
          <p>Canonical patient context</p>
        </div>
      </div>
      <dl className="workspace-fields">
        <div><dt>First name</dt><dd>{readable(patient.first_name)}</dd></div>
        <div><dt>Last name</dt><dd>{readable(patient.last_name)}</dd></div>
        <div><dt>MRN / Source ID</dt><dd>{readable(patient.source_patient_id)}</dd></div>
        <div><dt>Date of birth</dt><dd>{dateLabel(patient.date_of_birth)}</dd></div>
        <div><dt>Gender</dt><dd>{readable(patient.sex)}</dd></div>
        <div><dt>Contact information</dt><dd>{readable(patient.telecom || patient.phone || patient.email)}</dd></div>
        <div className="workspace-field-wide"><dt>Address</dt><dd>{contact || "Not available"}</dd></div>
        <div><dt>Condition</dt><dd>{readable(summary?.condition)}</dd></div>
        <div><dt>Jurisdiction</dt><dd>{readable(summary?.jurisdiction)}</dd></div>
        <div><dt>Reporting status</dt><dd>{readable(summary?.reportingStatus)}</dd></div>
        <div><dt>Deadline</dt><dd>{dateTimeLabel(summary?.deadline)}</dd></div>
      </dl>
    </section>
  );
}

function EncounterList({ encounters }) {
  if (!encounters.length) {
    return <p className="workspace-empty">No encounters are available for this patient.</p>;
  }
  return (
    <div className="workspace-record-list">
      {encounters.map((encounter) => (
        <article className="workspace-record" key={encounter.encounter_id}>
          <div>
            <h3>{readable(encounter.encounter_type)} encounter</h3>
            <p>{dateTimeLabel(encounter.start_time)}</p>
          </div>
          <dl>
            <div><dt>Facility</dt><dd>{readable(encounter.facility_id)}</dd></div>
            <div><dt>Provider</dt><dd>{readable(encounter.provider_reference)}</dd></div>
            <div><dt>Status</dt><dd>{readable(encounter.status)}</dd></div>
            {encounter.end_time && (
              <div><dt>End time</dt><dd>{dateTimeLabel(encounter.end_time)}</dd></div>
            )}
          </dl>
        </article>
      ))}
    </div>
  );
}

function EvidenceGroup({ title, items, getLabel }) {
  if (!items.length) return null;
  return (
    <section className="workspace-evidence-group">
      <div className="patient-section-heading">
        <h3>{title}</h3>
        <span>{items.length}</span>
      </div>
      <ul>
        {items.map((item, index) => (
          <li key={item.observation_id || item.lab_result_id || item.condition_id || item.document_id || item.id || index}>
            {getLabel(item)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ExistingCase({ caseData, journey, onContinue, demoActive, demoStages }) {
  const stageKey = { VALIDATION: "validation", REVIEW: "review", ATTESTATION: "attestation", NOTIFICATION: "notification", REPORTING: "reporting", SUBMISSION: "submission", PHA_FOLLOW_UP: "followUp" };
  const workflowStages = journey?.journey || [];
  return (
    <section className="patient-workspace-card">
      <div className="patient-section-heading">
        <div>
          <span className="workspace-overline">EXISTING REPORTING CASE</span>
          <h2>{caseData.disease || "Reporting case"}</h2>
        </div>
        <span className="workspace-status">{readable(caseData.status)}</span>
      </div>
      <dl className="workspace-case-fields">
        <div><dt>Case ID</dt><dd className="workspace-mono">{caseData.case_id}</dd></div>
        <div><dt>Disease</dt><dd>{readable(caseData.disease)}</dd></div>
        <div><dt>Jurisdiction</dt><dd>{readable(caseData.jurisdiction)}</dd></div>
        <div><dt>Deadline</dt><dd>{dateTimeLabel(caseData.deadline)}</dd></div>
        <div><dt>Severity</dt><dd>{readable(caseData.severity)}</dd></div>
        <div><dt>Workflow status</dt><dd>{demoActive ? "Demo workflow restarted" : readable(journey?.current_stage)}</dd></div>
      </dl>
      {workflowStages.length > 0 && (
        <ol className="workspace-case-stages">
          {workflowStages.map((stage) => (
            <li key={stage.stage}>
              <span>{stage.stage.replaceAll("_", " ")}</span>
              <strong>{demoActive && stageKey[stage.stage]
                ? (demoStages[stageKey[stage.stage]] === "COMPLETED" ? "Completed in this demo" : "Available in this demo")
                : stage.available ? readable(stage.status || "Available") : "Not available"}</strong>
            </li>
          ))}
        </ol>
      )}
      <button type="button" className="primary" onClick={onContinue}>
        Continue Workflow
      </button>
    </section>
  );
}

function ReportingWorkflow({
  caseData,
  notification,
  manualPackage,
  formDefinition,
  busy,
  error,
  onRecordNotification,
  onPrepareForm,
  onContinue,
  demoActive,
  demoStages,
}) {
  const isTexasMeasles = caseData.jurisdiction === "TX" && (caseData.disease || "").toLowerCase() === "measles";
  const visibleNotification = demoActive && demoStages.notification !== "COMPLETED" ? null : notification;
  const notificationPayload = visibleNotification?.payload || {};
  return (
    <section className="patient-workspace-card workspace-reporting-workflow">
      <div className="patient-section-heading">
        <div>
          <span className="workspace-overline">CASE REPORTING WORKFLOW</span>
          <h2>Continue reporting</h2>
          <p>Actions and statuses are recorded by SIGNAL&apos;s case workflow APIs.</p>
        </div>
      </div>
      {error && <div className="workspace-workflow-error" role="alert">{error}</div>}
      <div className="workspace-reporting-step">
        <div>
          <h3>Immediate notification</h3>
          {visibleNotification ? (
            <p>Recorded as {readable(notification.status)} · {readable(notificationPayload.notification_method)} · {dateTimeLabel(notificationPayload.notification_time)}</p>
          ) : (
            <p>No immediate notification has been recorded for this case.</p>
          )}
        </div>
        {!visibleNotification && isTexasMeasles && (
          <button type="button" className="primary" onClick={onRecordNotification} disabled={busy !== ""}>
            Record Immediate Notification
          </button>
        )}
      </div>
      <div className="workspace-reporting-step">
        <div>
          <h3>Texas Measles reporting form</h3>
          {manualPackage ? (
            <>
              <p>{manualPackage.form_id} · version {manualPackage.form_version} · {manualPackage.status}</p>
              {manualPackage.missing_fields?.length > 0 && <p>Needs review: {manualPackage.missing_fields.join(", ")}</p>}
              {formDefinition && <p>{formDefinition.fields.length} fields provided by the configured form definition.</p>}
              <p>Form rendering is gated by persisted validation, case approval, and attestation. Continue to the case workflow to complete those steps.</p>
            </>
          ) : (
            <p>{isTexasMeasles
              ? visibleNotification
                ? "The notification is recorded. Continue to the Case Workspace to complete validation, review, and attestation before form rendering."
                : "Continue to the Case Workspace after recording immediate notification."
              : "No Texas Measles form is configured for this case."}</p>
          )}
        </div>
        {isTexasMeasles && !manualPackage && (
          <button type="button" onClick={onPrepareForm} disabled={busy !== "" || !visibleNotification}>
            Continue to Case Workspace
          </button>
        )}
      </div>
      <button type="button" className="primary workspace-continue-case" onClick={onContinue}>
        Continue to Case Workspace
      </button>
    </section>
  );
}

export default function PatientWorkspace() {
  const { patientId = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [refreshKey, setRefreshKey] = useState(0);
  const [context, setContext] = useState(null);
  const [summary, setSummary] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [notification, setNotification] = useState(null);
  const [manualPackage, setManualPackage] = useState(null);
  const [formDefinition, setFormDefinition] = useState(null);
  const [workflowBusy, setWorkflowBusy] = useState("");
  const [workflowError, setWorkflowError] = useState("");
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [notificationTime, setNotificationTime] = useState("");
  const [notificationMethod, setNotificationMethod] = useState("PHONE");
  const [notificationNotes, setNotificationNotes] = useState("");
  const [notificationConfirmed, setNotificationConfirmed] = useState(false);
  const [reportingUser, setReportingUser] = useState(currentReportingUser);
  const [patientNavigation, setPatientNavigation] = useState(null);
  const [navigationError, setNavigationError] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const demo = useDemoWorkflow(caseData?.case_id || "");

  const load = useCallback(async (isActive = () => true) => {
    if (isActive()) {
      setLoading(true);
      setError("");
    }
    try {
      const [patientContext, patientRows, casesResult, navigationData] = await Promise.all([
        getCanonicalPatient(patientId),
        listCanonicalPatients({ search: patientId, page: 1, page_size: 100 }),
        listCasesForPatient(patientId),
        loadPatientNavigation(
          patientId,
          location.state?.patientNavigation,
        ),
      ]);
      const patient = patientContext.patient || {};
      const patientSummary = (patientRows.items || []).find(
        (item) => item.patient_id === patientId,
      ) || null;
      const patientCase = (casesResult.items || [])[0] || null;

      const caseDetails = patientCase
        ? await Promise.all([
            getCase(patientCase.case_id),
            getCaseJourney(patientCase.case_id),
            getImmediateNotification(patientCase.case_id),
          ])
        : [null, null, null];

      if (!isActive()) return;
      setContext(patientContext);
      setSummary({
        condition: patientSummary?.condition,
        jurisdiction:
          patientSummary?.deadline?.jurisdiction ||
          caseDetails[0]?.jurisdiction,
        deadline:
          patientSummary?.deadline?.deadline ||
          caseDetails[0]?.deadline,
        urgency:
          patientSummary?.deadline?.urgency ||
          caseDetails[0]?.severity,
        reportingStatus:
          caseDetails[0]?.status,
      });
      setCaseData(caseDetails[0]);
      setJourney(caseDetails[1]);
      setNotification(caseDetails[2]);
      setPatientNavigation(navigationData);
    } catch (requestError) {
      if (isActive()) {
        setError(requestErrorMessage(requestError));
      }
    } finally {
      if (isActive()) setLoading(false);
    }
  }, [location.state, patientId]);

  useEffect(() => {
    setWorkflowError("");
    setNotificationOpen(false);
    setNotification(null);
    setManualPackage(null);
    setFormDefinition(null);
  }, [patientId]);

  useEffect(() => {
    let active = true;
    load(() => active);
    return () => { active = false; };
  }, [load, refreshKey]);

  const patient = context?.patient || {};
  const encounters = context?.encounters || [];
  const conditions = context?.conditions || [];
  const observations = context?.observations || [];
  const labs = context?.lab_results || [];
  const documents = context?.clinical_documents || [];
  const fullName = [patient.first_name, patient.last_name].filter(Boolean).join(" ") || "Patient";
  const patientIds = patientNavigation?.patientIds || [];
  const patientIndex = patientIds.indexOf(patientId);
  const previousPatientId = patientIndex > 0 ? patientIds[patientIndex - 1] : null;
  const nextPatientId = patientIndex >= 0 ? patientIds[patientIndex + 1] || null : null;

  async function movePatient(direction) {
    setNavigationError("");
    const withinPageId = direction < 0 ? previousPatientId : nextPatientId;
    if (withinPageId) {
      navigate(`/patients/${encodeURIComponent(withinPageId)}`, {
        state: { patientNavigation },
      });
      return;
    }

    const targetPage = (patientNavigation?.page || 1) + direction;
    if (
      !patientNavigation ||
      targetPage < 1 ||
      targetPage > patientNavigation.pages
    ) return;

    try {
      const result = await listCanonicalPatients({
        page: targetPage,
        page_size: patientNavigation.pageSize,
        search: patientNavigation.search,
        facility: patientNavigation.facility,
      });
      const targetPatients = result.items || [];
      const targetId = direction > 0
        ? targetPatients[0]?.patient_id
        : targetPatients[targetPatients.length - 1]?.patient_id;
      if (!targetId) return;
      navigate(`/patients/${encodeURIComponent(targetId)}`, {
        state: {
          patientNavigation: {
            page: result.page,
            pageSize: result.page_size,
            pages: result.pages,
            search: patientNavigation.search,
            facility: patientNavigation.facility,
            patientIds: targetPatients.map((item) => item.patient_id),
          },
        },
      });
    } catch (requestError) {
      setNavigationError(
        requestErrorMessage(requestError) || "Unable to load the adjacent patient.",
      );
    }
  }

  const evidenceGroups = useMemo(() => [
    {
      title: "Clinical evidence",
      items: conditions,
      label: (item) => item.code?.display || item.code?.code || "Condition",
    },
    {
      title: "Laboratory evidence",
      items: labs,
      label: (item) => {
        const result = item.observations?.map(
          (row) => row.value?.text || row.value?.numeric || row.value?.code,
        ).filter(Boolean).join(", ");
        return `${item.test?.display || item.test?.code || "Lab result"} · ${item.conclusion || result || item.report_status || "Result not available"}`;
      },
    },
    {
      title: "Observation evidence",
      items: observations,
      label: (item) => `${item.code?.display || item.code?.code || "Observation"} · ${item.value?.text || item.value?.numeric || "Value not available"}`,
    },
    {
      title: "Document evidence",
      items: documents,
      label: (item) => `${item.title || item.document_type || "Clinical document"} · ${item.document_status || "Status not available"}`,
    },
  ], [conditions, documents, labs, observations]);
  const showMeaslesVisualization = containsMeaslesCondition([
    summary?.condition,
    caseData?.disease,
    conditions.map((condition) => condition.code),
  ]);

  async function recordNotification(event) {
    event.preventDefault();
    if (!caseData) return;
    setWorkflowBusy("notification");
    setWorkflowError("");
    try {
      const notificationDate = new Date(notificationTime);
      if (Number.isNaN(notificationDate.getTime())) {
        throw new Error("Enter a valid notification date and time.");
      }
      const result = await recordImmediateNotification(caseData.case_id, {
        notification_time: notificationDate.toISOString(),
        reporting_user: reportingUser.trim(),
        notification_method: notificationMethod,
        status: "COMPLETED",
        notes: notificationNotes.trim() || undefined,
      });
      setNotification(result);
      demo.complete("notification");
      setNotificationOpen(false);
      setNotificationConfirmed(false);
      setJourney(await getCaseJourney(caseData.case_id));
    } catch (requestError) {
      setWorkflowError(requestErrorMessage(requestError) || "Unable to record the immediate notification.");
    } finally {
      setWorkflowBusy("");
    }
  }

  function continueToCaseWorkspace() {
    const selectedCaseId = caseData?.case_id;
    if (!selectedCaseId) {
      setWorkflowError("This patient does not have a persisted case to open.");
      return;
    }
    navigate(`/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(selectedCaseId)}`);
  }

  function refreshPatientWorkflow() {
    if (caseData?.case_id) resetDemoWorkflow(caseData.case_id);
    setNotification(null);
    setManualPackage(null);
    setFormDefinition(null);
    setWorkflowError("");
    setNotificationOpen(false);
    setNotificationTime("");
    setNotificationNotes("");
    setNotificationConfirmed(false);
    setRefreshKey((value) => value + 1);
  }

  async function prepareReportingForm() {
    if (!caseData?.case_id) return;
    continueToCaseWorkspace();
  }

  if (loading) {
    return (
      <section className="patient-workspace">
        <SignalLoading
          title={refreshKey > 0 ? "Refreshing Patient Workflow" : "Loading Patient"}
          message={refreshKey > 0 ? "Reloading patient and case data for this demo session." : "Retrieving demographics, encounters, evidence, and active cases."}
        />
      </section>
    );
  }

  if (error) {
    return (
      <section className="patient-workspace">
        <div className="patient-workspace-back"><Link to="/patients">← Back to Patients</Link></div>
        <ErrorState message={`Unable to load patient information. ${error}`} />
        <button type="button" className="primary" onClick={() => setRefreshKey((value) => value + 1)}>
          Retry
        </button>
      </section>
    );
  }

  return (
    <section className="patient-workspace">
      <div className="workspace-header-top">
        <Link className="patient-workspace-back" to="/patients">← Back to Patients</Link>
        <div className="workspace-patient-navigation">
          <button
            type="button"
            onClick={() => movePatient(-1)}
            disabled={
              !previousPatientId &&
              (!patientNavigation || patientNavigation.page <= 1)
            }
          >
            Previous Patient
          </button>
          <button
            type="button"
            onClick={() => movePatient(1)}
            disabled={
              !nextPatientId &&
              (!patientNavigation || patientNavigation.page >= patientNavigation.pages)
            }
          >
            Next Patient
          </button>
        </div>
        {navigationError && <div className="workspace-navigation-error" role="alert">{navigationError}</div>}
      </div>

      <PageHeader
        title={fullName}
        subtitle={`MRN: ${readable(patient.source_patient_id)}  ·  DOB: ${dateLabel(patient.date_of_birth)}`}
      >
        <button type="button" onClick={refreshPatientWorkflow}>Refresh</button>
      </PageHeader>

      {notificationOpen && caseData && (
        <div className="workspace-notification-overlay">
          <section className="workspace-notification-dialog" role="dialog" aria-modal="true" aria-labelledby="notification-dialog-title">
            <div className="patient-section-heading">
              <div>
                <span className="workspace-overline">TEXAS MEASLES</span>
                <h2 id="notification-dialog-title">Record immediate notification</h2>
                <p>This records a notification that has already been made; it does not contact the health authority.</p>
              </div>
            </div>
            <form onSubmit={recordNotification}>
              <label>
                Reporting user
                <input value={reportingUser} onChange={(event) => setReportingUser(event.target.value)} required maxLength={255} />
              </label>
              <label>
                Notification time
                <input type="datetime-local" value={notificationTime} onChange={(event) => setNotificationTime(event.target.value)} required />
              </label>
              <label>
                Notification method
                <select value={notificationMethod} onChange={(event) => setNotificationMethod(event.target.value)} required>
                  <option value="PHONE">Phone</option>
                  <option value="FAX">Fax</option>
                  <option value="SECURE_EMAIL">Secure email</option>
                  <option value="FORM">Form</option>
                </select>
              </label>
              <label>
                Notes (optional)
                <textarea value={notificationNotes} onChange={(event) => setNotificationNotes(event.target.value)} />
              </label>
              <label className="workspace-notification-confirm">
                <input type="checkbox" checked={notificationConfirmed} onChange={(event) => setNotificationConfirmed(event.target.checked)} required />
                I confirm this immediate notification was completed using the method above.
              </label>
              {workflowError && <div className="workspace-workflow-error" role="alert">{workflowError}</div>}
              <div className="workspace-notification-actions">
                <button type="button" onClick={() => setNotificationOpen(false)} disabled={workflowBusy !== ""}>Cancel</button>
                <button type="submit" className="primary" disabled={workflowBusy !== "" || !notificationConfirmed}>
                  {workflowBusy === "notification" ? "Recording…" : "Record notification"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      <nav className="workspace-tabs" aria-label="Patient workspace sections">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={activeTab === tab ? "workspace-tab is-active" : "workspace-tab"}
            aria-current={activeTab === tab ? "page" : undefined}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "Overview" && (
        <div className="workspace-tab-content">
          <div className="patient-workspace-grid">
            <PatientFields patient={patient} summary={summary} />
            <section className="patient-workspace-card">
              <div className="patient-section-heading"><div><h2>Reporting case</h2><p>Persisted case information from SIGNAL</p></div></div>
              {caseData ? <>
                <dl className="workspace-record-fields">
                  <div><dt>Disease</dt><dd>{readable(caseData.disease)}</dd></div>
                  <div><dt>Jurisdiction</dt><dd>{readable(caseData.jurisdiction)}</dd></div>
                  <div><dt>Case status</dt><dd>{readable(caseData.status)}</dd></div>
                </dl>
                <button type="button" className="primary" onClick={continueToCaseWorkspace}>Continue to Case Workspace</button>
              </> : <p className="workspace-empty">No persisted case was returned for this patient.</p>}
            </section>
          </div>
          {showMeaslesVisualization && (
            <section className="patient-workspace-card clinical-visualization-card">
              <div className="patient-section-heading">
                <div>
                  <span className="clinical-visualization-eyebrow">CLINICAL VISUALIZATION</span>
                  <h2>Clinical Visualization</h2>
                  <p>Documented clinical context</p>
                </div>
                <span className="clinical-visualization-badge">Measles</span>
              </div>
              <div className="clinical-visualization-media">
                <img
                  src="/images/measles-anatomy.png"
                  alt="Clinical visualization for measles"
                  className="clinical-visualization-image"
                />
              </div>
              <p className="clinical-visualization-disclaimer">
                Visualization provides contextual reference for documented clinical information. It does not represent an independent diagnosis or reportability determination.
              </p>
            </section>
          )}
          {caseData && (
            <ReportingWorkflow
              caseData={caseData}
              notification={notification}
              manualPackage={manualPackage}
              formDefinition={formDefinition}
              busy={workflowBusy}
              error={workflowError}
              demoActive={demo.active}
              demoStages={demo.stages}
              onRecordNotification={() => {
                setWorkflowError("");
                setNotificationTime("");
                setReportingUser(currentReportingUser());
                setNotificationOpen(true);
              }}
              onPrepareForm={prepareReportingForm}
              onContinue={continueToCaseWorkspace}
            />
          )}
          <section className="patient-workspace-card">
            <div className="patient-section-heading">
              <div><h2>Current conditions</h2><p>Conditions returned by the canonical patient endpoint</p></div>
            </div>
            {conditions.length ? (
              <ul className="workspace-condition-list">
                {conditions.map((condition, index) => (
                  <li key={condition.condition_id || index}>
                    {condition.code?.display || condition.code?.code || "Condition"}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="workspace-empty">No condition records are available. The patient condition summary comes from the backend patient-list response.</p>
            )}
          </section>
          <section className="patient-workspace-card">
            <div className="patient-section-heading">
              <div><h2>Recent encounters</h2><p>Encounter data from the canonical patient record</p></div>
              <button type="button" onClick={() => setActiveTab("Encounters")}>View all</button>
            </div>
            <EncounterList encounters={encounters.slice(0, 3)} />
          </section>
        </div>
      )}

      {activeTab === "Encounters" && (
        <section className="patient-workspace-card workspace-tab-content">
          <div className="patient-section-heading">
            <div><h2>Encounters</h2><p>Available encounters for this patient</p></div>
          </div>
          <EncounterList encounters={encounters} />
        </section>
      )}

      {activeTab === "Evidence" && (
        <section id="patient-workspace-evidence" className="patient-workspace-card workspace-tab-content">
          <div className="patient-section-heading">
            <div><h2>Evidence</h2><p>Clinical, laboratory, observation, and document information returned for this patient</p></div>
          </div>
          {evidenceGroups.some((group) => group.items.length) ? (
            <div className="workspace-evidence-list">
              {evidenceGroups.map((group) => (
                <EvidenceGroup key={group.title} {...group} getLabel={group.label} />
              ))}
            </div>
          ) : (
            <p className="workspace-empty">No evidence available</p>
          )}
        </section>
      )}

      {activeTab === "Case" && (
        <div className="workspace-tab-content">
          {caseData ? (
            <>
              <ExistingCase
                caseData={caseData}
                journey={journey}
                onContinue={continueToCaseWorkspace}
                demoActive={demo.active}
                demoStages={demo.stages}
              />
              <ReportingWorkflow
                caseData={caseData}
                notification={notification}
                manualPackage={manualPackage}
                formDefinition={formDefinition}
                busy={workflowBusy}
                error={workflowError}
                demoActive={demo.active}
                demoStages={demo.stages}
                onRecordNotification={() => {
                  setWorkflowError("");
                  setNotificationTime("");
                  setReportingUser(currentReportingUser());
                  setNotificationOpen(true);
                }}
                onPrepareForm={prepareReportingForm}
                onContinue={continueToCaseWorkspace}
              />
            </>
          ) : (
            <section className="patient-workspace-card">
              <div className="patient-section-heading">
                <div><h2>No reporting case has been created yet.</h2></div>
              </div>
              <p className="workspace-empty">No persisted reporting case is available to continue from this patient workspace.</p>
            </section>
          )}
        </div>
      )}
    </section>
  );
}
