import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { readReportingPreview, writeReportingPreview } from "../utils/reportingPreviewStorage.js";
import {
  getCase,
  getFormDefinition,
  renderForm,
  renderUrl,
  downloadRenderUrl,
} from "../api/signal.js";
import "../styles/reporting-form.css";

const FORM_ID = "TX_MEASLES_OUTBREAK_CRF_2025";
const FORM_VERSION = "2025-05-07";
const PAGE_SIZE = 5;
const REPORTING_MISSING_INFO_FIELDS = [
  "reporting.investigated_by",
  "reporting.investigating_agency",
  "reporting.investigating_agency_email",
  "reporting.investigating_agency_phone",
  "reporting.investigation_start_date",
];
const pendingFormRenders = new Map();
const responseData = (response) => response?.data ?? response;
const toList = (value) => Array.isArray(value) ? value : value == null ? [] : [value];
const isFilled = (value) => value !== null && value !== undefined && value !== "";
const hasRequiredValue = (value) => isFilled(value) && String(value).trim() !== "";
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
  return [patient?.first_name, patient?.last_name].filter(Boolean).join(" ") || patient?.name || "Patient";
}

export default function ReportingFormPage() {
  const { patientId: routePatientId = "", caseId = "" } = useParams();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [formDefinition, setFormDefinition] = useState(null);
  const [renderResult, setRenderResult] = useState(null);
  const [fieldValues, setFieldValues] = useState({});
  const [savedFieldValues, setSavedFieldValues] = useState({});
  const [visiblePage, setVisiblePage] = useState(0);
  const [loading, setLoading] = useState(true);
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
  const missingFields = REPORTING_MISSING_INFO_FIELDS.filter((field) => !hasRequiredValue(savedFieldValues[field]));
  const missingMessages = [];
  const pageCount = Math.ceil(missingFields.length / PAGE_SIZE);
  const visibleFields = missingFields.slice(visiblePage * PAGE_SIZE, (visiblePage + 1) * PAGE_SIZE);
  const renderId = renderResult?.render_id;
  const pdfUrl = renderId ? renderUrl(renderId) : "";
  const downloadUrl = renderId ? downloadRenderUrl(renderId) : "";
  async function loadBackendData() {
    const [caseResponse, formResponse] = await Promise.all([
      getCase(caseId),
      getFormDefinition(FORM_ID),
    ]);
    const data = responseData(caseResponse);
    const definition = responseData(formResponse);
    setCaseData(data);
    setFormDefinition(definition);
    const localPreview = readReportingPreview(caseId);
    const initialValues = Object.fromEntries(toList(definition?.fields).map((field) => [
      field.field,
      REPORTING_MISSING_INFO_FIELDS.includes(field.field)
        ? localPreview[field.field] ?? ""
        : initialFieldValue(data, field),
    ]));
    setFieldValues(initialValues);
    setSavedFieldValues(initialValues);
    return { data, definition, initialValues };
  }

  async function generateForm(isRegeneration = false, force = false, fieldOverrides = fieldValues) {
    if (!caseId || (working && !force)) return null;
    setWorking(true);
    setOperation(isRegeneration ? "regenerate" : "generate");
    setError("");
    setRenderResult(null);
    try {
      const transientValues = Object.fromEntries(
        REPORTING_MISSING_INFO_FIELDS.map((field) => [field, fieldOverrides[field] || ""])
      );
      const rendered = responseData(await renderFormOnce(caseId, FORM_ID, FORM_VERSION, transientValues));
      if (!rendered?.render_id || (!rendered?.demo_mode && !rendered?.report_id)) throw new Error("The backend did not return the generated PDF identifier.");
      setRenderResult(rendered);
      return rendered;
    } catch (requestError) {
      setError(`Unable to generate the Texas Measles Reporting Form. ${errorText(requestError)}`);
      return null;
    } finally {
      setWorking(false);
      setOperation("");
    }
  }

  useEffect(() => {
    let active = true;
    async function initialize() {
      setLoading(true);
      setError("");
      let loaded = false;
      let pageData;
      try {
        pageData = await loadBackendData();
        const casePatientId = pageData.data?.patient?.patient_id || pageData.data?.patient?.id || pageData.data?.patient_id;
        if (routePatientId && casePatientId && String(routePatientId) !== String(casePatientId)) {
          throw new Error("The case does not belong to the patient in this route.");
        }
        loaded = true;
      } catch (requestError) {
        if (active) setError(errorText(requestError));
      } finally {
        if (active) setLoading(false);
      }
      if (active && loaded) await generateForm(false, false, pageData.initialValues);
    }
    initialize();
    return () => { active = false; };
  // Initial case load is tied to the route IDs; the generated PDF is always backend-served.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, routePatientId]);

  async function saveMissingInformation() {
    if (working || !visibleFields.length) return;
    let saved = false;
    let transientValues = null;
    setWorking(true);
    setOperation("save");
    setError("");
    setMessage("");
    try {
      const savedFields = Object.fromEntries(visibleFields
        .filter((field) => isFilled(fieldValues[field]) && String(fieldValues[field]).trim())
        .map((field) => [field, fieldValues[field]]));
      if (!Object.keys(savedFields).length) {
        setError("Enter at least one missing value before saving.");
        return;
      }
      transientValues = { ...fieldValues, ...savedFields };
      const temporaryFields = Object.fromEntries(
        REPORTING_MISSING_INFO_FIELDS.map((field) => [field, transientValues[field] ?? ""])
      );
      writeReportingPreview(caseId, temporaryFields);
      setFieldValues(transientValues);
      setSavedFieldValues(transientValues);
      setVisiblePage(0);
      saved = true;
    } catch (requestError) {
      setError(`Unable to save missing information. ${errorText(requestError)}`);
    } finally {
      setWorking(false);
      setOperation("");
    }
    if (saved) {
      const updated = await generateForm(true, true, transientValues || fieldValues);
      setMessage(updated
        ? "Your entries are saved in this browser session only and reset when the frontend starts again."
        : "");
    }
  }

  if (loading) return <section className="reporting-form-page"><SignalLoading title="Loading Patient Reporting Form" message="Loading the official form and case fields from SIGNAL." /></section>;

  if (!caseData) return <section className="reporting-form-page"><div className="reporting-form-error" role="alert"><h2>Unable to load patient reporting data.</h2><p>{error || "The requested case could not be loaded."}</p><button type="button" className="button" onClick={() => navigate(patientPath)}>Back to Patient</button></div></section>;

  return <section className="reporting-form-page">
    <header className="reporting-form-header">
      <div>
        <button type="button" className="reporting-form-back" onClick={() => navigate(patientPath)}>← Back</button>
        <span className="reporting-form-eyebrow">SIGNAL · PATIENT WORKSPACE</span>
        <h1>Patient Reporting Form</h1>
        <p>Texas Measles Reporting Form · {patientName(patient)}</p>
      </div>
    </header>

    {working && <SignalLoading
      title={operation === "save" ? "Saving temporary entries" : operation === "regenerate" ? "Updating the form preview" : "Generating Texas Measles Reporting Form"}
      message={operation === "save" ? "Saving these values in this browser session only." : "SIGNAL is updating the temporary form preview."}
    />}
    {error && <div className="reporting-form-message is-error" role="alert"><strong>Reporting form error</strong><span>{error.replace(/^Unable to generate the Texas Measles Reporting Form\.\s*/, "")}</span>{error.startsWith("Unable to generate") && <button type="button" className="button" disabled={working} onClick={() => generateForm()}>Retry</button>}</div>}
    {message && <div className="reporting-form-message is-success" role="status">{message}</div>}

    <div className="reporting-form-columns">
      <section className="reporting-form-pdf-card" aria-label="Official Texas Measles Reporting Form">
        <header className="reporting-form-card-header"><div><span>BACKEND-GENERATED PDF</span><h2>Texas Measles Reporting Form</h2><p>{renderResult?.form_id || FORM_ID} · Version {renderResult?.form_version || FORM_VERSION}</p></div>{renderResult && <span className="reporting-form-rendered-badge">Generated</span>}</header>
        {renderResult?.render_id ? <div className="reporting-form-pdf-frame"><iframe src={pdfUrl} title="Backend-generated Texas Measles Reporting Form" className="reporting-form-pdf-viewer" /></div> : <div className="reporting-form-pdf-empty"><strong>Form preview unavailable</strong><span>Retry to request the official PDF from the backend.</span></div>}
        {renderResult?.render_id && <div className="reporting-form-actions"><a className="button" href={pdfUrl} target="_blank" rel="noreferrer">Open PDF</a><a className="button" href={downloadUrl}>Download PDF</a></div>}
      </section>

      <aside className="reporting-form-missing-card" aria-labelledby="missing-info-heading">
        <header><span>MISSING INFORMATION</span><h2 id="missing-info-heading">Complete Required Fields</h2><p>Enter missing values here. Saving refreshes the PDF from the backend.</p></header>
        <div className="reporting-form-missing-count"><strong>{missingFields.length + missingMessages.length}</strong><span>items remaining</span></div>
        {visibleFields.length ? <div className="reporting-form-missing-fields">
          {visibleFields.map((field) => {
            const metadata = definitions.find((item) => item?.field === field);
            return <label className="reporting-form-field" key={field}><span>{fieldLabel(field, definitions)} <b aria-hidden="true">*</b></span><FieldEditor field={field} definition={metadata} value={fieldValues[field] ?? initialFieldValue(caseData, metadata || { field })} onChange={(value) => setFieldValues((current) => ({ ...current, [field]: value }))} /></label>;
          })}
          {pageCount > 1 && <div className="reporting-form-pager"><span>Showing {visiblePage * PAGE_SIZE + 1}–{Math.min((visiblePage + 1) * PAGE_SIZE, missingFields.length)} of {missingFields.length}</span><button type="button" className="button" onClick={() => setVisiblePage((page) => (page + 1) % pageCount)}>Next 5</button></div>}
          <button type="button" className="button button-primary reporting-form-save" disabled={working} onClick={saveMissingInformation}>Save &amp; Update Form</button>
        </div> : <div className="reporting-form-no-missing">No required fields are missing.</div>}
        {missingMessages.length > 0 && <div className="reporting-form-requirements"><strong>Other requirements</strong><ul>{missingMessages.map((item) => <li key={item}>{item}</li>)}</ul></div>}
        <button
          type="button"
          className="button reporting-form-continue-review"
          disabled={working || missingFields.length > 0 || missingMessages.length > 0}
          onClick={() => navigate(caseWorkspacePath)}
        >
          Continue to Review
        </button>
      </aside>
    </div>
  </section>;
}
