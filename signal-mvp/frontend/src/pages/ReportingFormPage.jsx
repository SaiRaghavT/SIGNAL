import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { cleanPatientName } from "../utils/patientNames.js";
import {
  getCase,
  getFormDefinitionForCase,
  renderForm,
  updateCaseReport,
  renderUrl,
  downloadRenderUrl,
} from "../api/signal.js";
import "../styles/reporting-form.css";

const PAGE_SIZE = 5;
const pendingFormRenders = new Map();
const responseData = (response) => response?.data ?? response;
const toList = (value) => Array.isArray(value) ? value : value == null ? [] : [value];
const isFilled = (value) => value !== null && value !== undefined &&
  (typeof value !== "string" || value.trim() !== "");
const isRecord = (value) => value && typeof value === "object" && !Array.isArray(value);

function errorText(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (detail) return JSON.stringify(detail);
  return error?.message || "Request failed.";
}

function renderFormOnce(caseId, formId, formVersion, fieldValues = {}) {
  const transientKey = JSON.stringify(fieldValues);
  const key = `${caseId}:${formId}:${formVersion || ""}:${transientKey}`;
  const pending = pendingFormRenders.get(key);
  if (pending) return pending;

  const request = renderForm(caseId, formId, formVersion, fieldValues).finally(() => {
    if (pendingFormRenders.get(key) === request) pendingFormRenders.delete(key);
  });
  pendingFormRenders.set(key, request);
  return request;
}

function pathValue(data, path) {
  if (!path) return undefined;
  const aliases = { clinical: "clinical_evidence", laboratory: "laboratory_evidence", rash_fever: "clinical_evidence" };
  const parts = path.split(".");
  let value = data;
  parts.forEach((part, index) => {
    if (index === 0 && aliases[part]) value = value?.[aliases[part]];
    else value = value?.[part];
  });
  return value;
}

function initialFieldValue(caseData, definition) {
  const field = definition?.field;
  if (!field) return "";
  const reportFields = caseData?.report_fields || {};
  if (isFilled(reportFields[field])) return reportFields[field];
  const source = definition.source || field;
  let value = pathValue(caseData, source);
  if (field === "patient.case_name" && !isFilled(value)) {
    value = [caseData?.patient?.first_name, caseData?.patient?.last_name].filter(Boolean).join(" ");
  }
  if (field === "patient.current_address" && isRecord(value)) {
    value = value.line || value.address_line || value.street || "";
  }
  if (field === "patient.zip" && !isFilled(value)) value = caseData?.patient?.postal_code;
  if (field.startsWith("provider.")) value = caseData?.provider?.[field.slice(9)] ?? value;
  if (field.startsWith("facility.")) value = caseData?.facility?.[field.slice(9)] ?? value;
  if (isRecord(value)) value = value.value ?? value.display ?? value.text ?? value.line ?? "";
  return value ?? "";
}

function fieldLabel(field, definitions) {
  const metadata = toList(definitions).find((item) => item?.field === field);
  if (metadata?.label) return metadata.label;
  const [section, ...nameParts] = field.split(".");
  const sectionNames = { patient: "Patient", reporting: "Reporting", clinical: "Clinical", rash_fever: "Rash / Fever", laboratory: "Laboratory", provider: "Provider", facility: "Facility" };
  const name = nameParts.join(" ").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  return `${sectionNames[section] || section.replaceAll("_", " ")} ${name}`.trim();
}

function FieldEditor({ field, definition, value, onChange }) {
  const leaf = field.split(".").at(-1).toLowerCase();
  const declaredType = String(definition?.type || definition?.input_type || "").toLowerCase();
  const options = toList(definition?.options);
  const select = (choices) => <select value={value ?? ""} onChange={(event) => onChange(event.target.value)}>
    <option value="">Select an answer</option>
    {choices.map((item) => {
      const option = isRecord(item) ? item : { value: item, label: item };
      return <option key={String(option.value)} value={option.value}>{option.label ?? option.value}</option>;
    })}
  </select>;
  if (options.length) return select(options);
  if (["boolean", "bool"].includes(declaredType) || ["hospitalized", "icu_admission", "rash", "fever", "cough", "coryza", "conjunctivitis", "koplik_spots", "hispanic"].includes(leaf)) {
    return select([{ value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "unknown", label: "Unknown" }]);
  }
  if (leaf === "sex" || leaf === "gender") return select(["female", "male", "other", "unknown"]);
  if (leaf === "race") return select(["American Indian or Alaska Native", "Asian", "Black or African American", "Native Hawaiian or Other Pacific Islander", "White", "Other", "Unknown"]);
  const type = declaredType || (/date/.test(leaf) ? "date" : /email/.test(leaf) ? "email" : /phone|telephone/.test(leaf) ? "tel" : /temperature|duration/.test(leaf) ? "number" : "text");
  if (["textarea", "address", "notes"].includes(type) || ["current_address", "address", "rash_location"].includes(leaf)) {
    return <textarea rows={3} value={value ?? ""} onChange={(event) => onChange(event.target.value)} />;
  }
  const valueText = value == null ? "" : String(value);
  return <input type={type} value={type === "date" ? valueText.slice(0, 10) : valueText} onChange={(event) => onChange(event.target.value)} />;
}

function patientName(patient) {
  return cleanPatientName([patient?.first_name, patient?.last_name].filter(Boolean).join(" ") || patient?.name) || "Patient";
}

export default function ReportingFormPage() {
  const { patientId: routePatientId = "", caseId = "" } = useParams();
  const navigate = useNavigate();
  const activeRouteKey = `${routePatientId}:${caseId}`;
  const activeRouteKeyRef = useRef(activeRouteKey);
  activeRouteKeyRef.current = activeRouteKey;
  const [caseData, setCaseData] = useState(null);
  const [formDefinition, setFormDefinition] = useState(null);
  const [renderResult, setRenderResult] = useState(null);
  const [fieldValues, setFieldValues] = useState({});
  const [savedFieldValues, setSavedFieldValues] = useState({});
  const [visiblePage, setVisiblePage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadedRouteKey, setLoadedRouteKey] = useState("");
  const [working, setWorking] = useState(false);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const patient = caseData?.patient || {};
  const actualPatientId = routePatientId || patient.patient_id || patient.id || caseData?.patient_id || "";
  const patientPath = actualPatientId ? `/patients/${encodeURIComponent(actualPatientId)}` : "/patients";
  const caseWorkspacePath = actualPatientId
    ? `/patients/${encodeURIComponent(actualPatientId)}/case/${encodeURIComponent(caseId)}`
    : `/cases/${encodeURIComponent(caseId)}`;
  const definitions = toList(formDefinition?.fields);
  // These staff entry fields remain editable even after values are saved.
  const staffEntryFields = toList(formDefinition?.staff_entry_fields);
  const savedStaffFieldCount = staffEntryFields.filter((field) => isFilled(savedFieldValues[field])).length;
  const changedStaffFields = staffEntryFields.filter(
    (field) => String(fieldValues[field] ?? "") !== String(savedFieldValues[field] ?? ""),
  );
  const allStaffFieldsSaved = staffEntryFields.length > 0 &&
    savedStaffFieldCount === staffEntryFields.length && changedStaffFields.length === 0;
  const missingMessages = [
    ...staffEntryFields
      .filter((field) => !isFilled(fieldValues[field]))
      .map((field) => `${fieldLabel(field, definitions)} is required.`),
    ...changedStaffFields
      .map((field) => `${fieldLabel(field, definitions)} must be saved before continuing.`),
  ];
  const pageCount = Math.ceil(staffEntryFields.length / PAGE_SIZE);
  const visibleFields = staffEntryFields.slice(visiblePage * PAGE_SIZE, (visiblePage + 1) * PAGE_SIZE);
  const renderId = renderResult?.render_id;
  const pdfUrl = renderId ? renderUrl(renderId) : "";
  const downloadUrl = renderId ? downloadRenderUrl(renderId) : "";
  async function loadBackendData() {
    const caseResponse = await getCase(caseId);
    let data = responseData(caseResponse);
    const formResponse = await getFormDefinitionForCase(caseId);
    const definition = responseData(formResponse);
    const initialValues = Object.fromEntries(toList(definition?.fields).map((field) => [
      field.field,
      initialFieldValue(data, field),
    ]));
    return { data, definition, initialValues };
  }

  async function generateForm(isRegeneration = false, force = false, fieldValues = {}, definition = formDefinition, isCurrent = () => true) {
    if (!caseId || (working && !force)) return null;
    if (!definition?.form_id) {
      setError("No reporting form is configured for this case.");
      return null;
    }
    setWorking(true);
    setOperation(isRegeneration ? "regenerate" : "generate");
    setError("");
    setRenderResult(null);
    try {
      const rendered = responseData(await renderFormOnce(caseId, definition.form_id, definition.form_version, fieldValues));
      if (!rendered?.render_id || (!rendered?.demo_mode && !rendered?.report_id)) throw new Error("The backend did not return the generated PDF identifier.");
      if (!isCurrent()) return null;
      setRenderResult(rendered);
      return rendered;
    } catch (requestError) {
      if (isCurrent()) setError(`Unable to generate ${definition?.name || "the reporting form"}. ${errorText(requestError)}`);
      return null;
    } finally {
      if (isCurrent()) {
        setWorking(false);
        setOperation("");
      }
    }
  }

  useEffect(() => {
    let active = true;
    async function initialize() {
      setLoading(true);
      setLoadedRouteKey("");
      setError("");
      setCaseData(null);
      setFormDefinition(null);
      setRenderResult(null);
      setFieldValues({});
      setSavedFieldValues({});
      setVisiblePage(0);
      setWorking(false);
      setOperation("");
      setMessage("");
      let loaded = false;
      let pageData;
      try {
        pageData = await loadBackendData();
        const casePatientId = pageData.data?.patient?.patient_id || pageData.data?.patient?.id || pageData.data?.patient_id;
        if (routePatientId && casePatientId && String(routePatientId) !== String(casePatientId)) {
          throw new Error("The case does not belong to the patient in this route.");
        }
        if (active) {
          setCaseData(pageData.data);
          setFormDefinition(pageData.definition);
          setFieldValues(pageData.initialValues);
          setSavedFieldValues(pageData.initialValues);
          setVisiblePage(0);
        }
        loaded = true;
      } catch (requestError) {
        if (active) setError(errorText(requestError));
      } finally {
        if (active) {
          setLoadedRouteKey(activeRouteKey);
          setLoading(false);
        }
      }
      if (active && loaded) {
        await generateForm(false, false, {}, pageData.definition, () => active);
      }
    }
    initialize();
    return () => { active = false; };
  // Initial case load is tied to the route IDs; the generated PDF is always backend-served.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, routePatientId]);

  async function saveMissingInformation() {
    if (working || !changedStaffFields.length) return;
    const savingRouteKey = activeRouteKey;
    const isSameRoute = () => activeRouteKeyRef.current === savingRouteKey;
    let saved = false;
    let persistedFieldValues = null;
    setWorking(true);
    setOperation("save");
    setError("");
    setMessage("");
    try {
      const savedFields = Object.fromEntries(changedStaffFields
        .map((field) => [field, fieldValues[field]]));
      await updateCaseReport(caseId, { report_fields: savedFields });
      const refreshedCase = responseData(await getCase(caseId));
      const unverifiedFields = Object.entries(savedFields).filter(
        ([field, value]) => String(refreshedCase?.report_fields?.[field] ?? "") !== String(value),
      );
      if (unverifiedFields.length) {
        throw new Error(`SIGNAL did not return the saved reporting values: ${unverifiedFields.map(([field]) => field).join(", ")}`);
      }

      if (!isSameRoute()) return;
      setCaseData(refreshedCase);
      persistedFieldValues = {
        ...fieldValues,
        ...Object.fromEntries(staffEntryFields.map((field) => [
          field,
          refreshedCase?.report_fields?.[field] ?? "",
        ])),
      };
      setFieldValues(persistedFieldValues);
      setSavedFieldValues(persistedFieldValues);
      setVisiblePage(0);
      saved = true;
    } catch (requestError) {
      if (isSameRoute()) setError(`Unable to save missing information. ${errorText(requestError)}`);
    } finally {
      if (isSameRoute()) {
        setWorking(false);
        setOperation("");
      }
    }
    if (saved) {
      const updated = await generateForm(true, true, {}, formDefinition, isSameRoute);
      if (isSameRoute()) setMessage(updated
        ? "Your entries are saved to the case and verified from SIGNAL."
        : "");
    }
  }

  if (loading || loadedRouteKey !== activeRouteKey) return <section className="reporting-form-page"><SignalLoading title="Loading Patient Reporting Form" message="Loading the official form and case fields from SIGNAL." /></section>;

  if (!caseData) return <section className="reporting-form-page"><div className="reporting-form-error" role="alert"><h2>Unable to load patient reporting data.</h2><p>{error || "The requested case could not be loaded."}</p><button type="button" className="button" onClick={() => navigate(patientPath)}>Back to Patient</button></div></section>;

  return <section className="reporting-form-page">
    <header className="reporting-form-header">
      <div>
        <button type="button" className="reporting-form-back" onClick={() => navigate(patientPath)}>← Back</button>
        <span className="reporting-form-eyebrow">SIGNAL · PATIENT WORKSPACE</span>
        <h1>Patient Reporting Form</h1>
        <p>{formDefinition?.name || "Reporting Form"} · {patientName(patient)}</p>
      </div>
    </header>

    {working && operation === "save" && <SignalLoading
      title="Saving reporting values"
      message="Saving values to the case and verifying them from SIGNAL."
    />}
    {error && <div className="reporting-form-message is-error" role="alert"><strong>Reporting form error</strong><span>{error}</span>{error.startsWith("Unable to generate") && <button type="button" className="button" disabled={working} onClick={() => generateForm()}>Retry</button>}</div>}
    {message && <div className="reporting-form-message is-success" role="status">{message}</div>}

    <div className="reporting-form-columns">
      <section className="reporting-form-pdf-card" aria-label={formDefinition?.name || "Reporting Form"}>
        <header className="reporting-form-card-header"><div><span>BACKEND-GENERATED PDF</span><h2>{formDefinition?.name || "Reporting Form"}</h2><p>{renderResult?.form_id || formDefinition?.form_id} · Version {renderResult?.form_version || formDefinition?.form_version}</p></div>{renderResult && <span className="reporting-form-rendered-badge">Generated</span>}</header>
        {renderResult?.render_id ? <div className="reporting-form-pdf-frame"><iframe src={pdfUrl} title={`Backend-generated ${formDefinition?.name || "Reporting Form"}`} className="reporting-form-pdf-viewer" /></div> : working && (operation === "generate" || operation === "regenerate") ? <div className="reporting-form-pdf-empty is-loading" role="status" aria-live="polite"><RefreshCw className="reporting-form-preview-spinner" size={20} aria-hidden="true" /><div><strong>{operation === "regenerate" ? "Updating form preview" : "Loading form preview"}</strong><span>SIGNAL is preparing the reporting form PDF.</span></div></div> : <div className="reporting-form-pdf-empty"><strong>Form preview unavailable</strong><span>Retry to request the configured PDF from the backend.</span></div>}
        {renderResult?.render_id && <div className="reporting-form-actions"><a className="button" href={pdfUrl} target="_blank" rel="noreferrer">Open PDF</a><a className="button" href={downloadUrl}>Download PDF</a></div>}
      </section>

      <aside className="reporting-form-missing-card" aria-labelledby="missing-info-heading">
        <header><span>REQUIRED REPORTING INFORMATION</span><h2 id="missing-info-heading">Investigation Details</h2><p>Complete these required reporting fields before continuing. Patient and clinical details are populated from the case; investigation details are entered here.</p></header>
        <div className="reporting-form-missing-count"><strong>{savedStaffFieldCount}/{staffEntryFields.length}</strong><span>required fields saved</span></div>
        {allStaffFieldsSaved && <p className="reporting-form-saved-summary" role="status">All required fields are saved for this patient. You can review or edit them below.</p>}
        {visibleFields.length ? <div className="reporting-form-missing-fields">
          {visibleFields.map((field) => {
            const metadata = definitions.find((item) => item?.field === field);
            return <label className="reporting-form-field" key={field}><span>{fieldLabel(field, definitions)} <small>Required</small></span><FieldEditor field={field} definition={metadata} value={fieldValues[field] ?? ""} onChange={(value) => setFieldValues((current) => ({ ...current, [field]: value }))} /></label>;
          })}
          {pageCount > 1 && <div className="reporting-form-pager"><span>Showing {visiblePage * PAGE_SIZE + 1}–{Math.min((visiblePage + 1) * PAGE_SIZE, staffEntryFields.length)} of {staffEntryFields.length}</span><button type="button" className="button" onClick={() => setVisiblePage((page) => (page + 1) % pageCount)}>Next 5</button></div>}
          <button type="button" className="button button-primary reporting-form-save" disabled={working || !changedStaffFields.length} onClick={saveMissingInformation}>Save Required Fields &amp; Update Form</button>
        </div> : <div className="reporting-form-no-missing">No additional staff fields are configured for this form.</div>}
        {missingMessages.length > 0 && <div className="reporting-form-requirements"><strong>Required fields remaining</strong><ul>{missingMessages.map((item) => <li key={item}>{item}</li>)}</ul></div>}
        <button
          type="button"
          className="button reporting-form-continue-review"
          disabled={working || missingMessages.length > 0}
          onClick={() => navigate(caseWorkspacePath)}
        >
          Continue to Review
        </button>
      </aside>
    </div>
  </section>;
}
