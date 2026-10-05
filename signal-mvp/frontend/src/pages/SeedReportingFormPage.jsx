import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Download, FileText, RotateCcw, Save } from "lucide-react";
import { getFormDefinition } from "../api/workflow.js";
import { downloadRenderUrl, renderSeedPatientForm, renderUrl } from "../api/signal.js";
import { signalApi } from "../services/backendApi.js";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/reporting-form.css";
import "../styles/seed-reporting-form.css";

const FORM_ID = "TX_MEASLES_OUTBREAK_CRF_2025";
const CHOICE_OPTIONS = {
  "patient.sex": ["male", "female", "unknown"],
  "patient.country_of_residence": ["USA", "Other", "Unknown"],
  "patient.hispanic": ["yes", "no", "unknown"],
  "clinical.hospitalized": ["inpatient", "outpatient", "ER only", "urgent care", "unknown"],
  "clinical.icu_admission": ["yes", "no", "unknown"],
  "clinical.confirmation_method": ["Lab Confirmed", "Epi-Linked"],
  "clinical.rash": ["yes", "no", "unknown"],
  "clinical.fever": ["yes", "no", "unknown"],
  "clinical.cough": ["yes", "no", "unknown"],
  "clinical.coryza": ["yes", "no", "unknown"],
  "clinical.conjunctivitis": ["yes", "no", "unknown"],
  "clinical.koplik_spots": ["yes", "no", "unknown"],
};
const RACE_OPTIONS = [
  "White",
  "Black or African American",
  "Asian",
  "American Indian or Alaska Native",
  "Native Hawaiian or Other Pacific Islander",
  "Other",
  "Unknown",
];
const SECTION_LABELS = {
  patient: "Patient and Case",
  reporting: "Reporting and Investigation",
  clinical: "Clinical and Hospitalization",
  rash_fever: "Rash and Fever",
  laboratory: "Laboratory",
};

function responseData(response) {
  return response?.data || response;
}

function fieldLabel(field) {
  return field.split(".").at(-1).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function inputType(source) {
  if (source.includes("date")) return "date";
  if (source.endsWith("email")) return "email";
  if (source.endsWith("phone")) return "tel";
  return "text";
}

function normalizeInputValue(source, value) {
  if (value === null || value === undefined || Array.isArray(value)) return "";
  const text = String(value);
  return source.includes("date") ? text.slice(0, 10) : text;
}

function sourcePrefill(patient) {
  const values = { ...(patient.report_data || {}) };
  if (["US", "U.S.", "United States", "United States of America"].includes(values["patient.country_of_residence"])) {
    values["patient.country_of_residence"] = "USA";
  }
  return values;
}

function hasDraftValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function FormField({ field, value, onChange }) {
  const source = field.source;
  const id = `seed-form-${source.replaceAll(".", "-")}`;
  const choices = CHOICE_OPTIONS[source];

  if (source === "patient.race") {
    const selected = Array.isArray(value) ? value : value ? [value] : [];
    return <fieldset className="seed-form-field seed-form-race-field">
      <legend>{fieldLabel(field.field)}{field.required && <span className="seed-form-required">Required</span>}</legend>
      <div className="seed-form-checkboxes">{RACE_OPTIONS.map((race) => <label key={race}><input type="checkbox" checked={selected.includes(race)} onChange={() => onChange(source, selected.includes(race) ? selected.filter((item) => item !== race) : [...selected, race])}/>{race}</label>)}</div>
      <small>Source: {source}</small>
    </fieldset>;
  }

  return <label className="seed-form-field" htmlFor={id}>
    <span>{fieldLabel(field.field)}{field.required && <span className="seed-form-required">Required</span>}</span>
    {choices ? <select id={id} value={value ?? ""} onChange={(event) => onChange(source, event.target.value)}>
      <option value="">Select value</option>{choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
    </select> : <input id={id} type={inputType(source)} value={normalizeInputValue(source, value)} onChange={(event) => onChange(source, event.target.value)}/>}
    <small>Source: {source}</small>
  </label>;
}

export default function SeedReportingFormPage() {
  const { id: patientId } = useParams();
  const navigate = useNavigate();
  const [patient, setPatient] = useState(null);
  const [definition, setDefinition] = useState(null);
  const [values, setValues] = useState({});
  const [editedSources, setEditedSources] = useState([]);
  const [renderResult, setRenderResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pdfNeedsRefresh, setPdfNeedsRefresh] = useState(false);
  const draftKey = `signal-measles-form-${patientId}`;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      signalApi.getSeedFhirCandidates(),
      getFormDefinition(FORM_ID),
    ]).then(([candidateResponse, formResponse]) => {
      if (!active) return;
      const candidateData = responseData(candidateResponse);
      const candidate = candidateData.items?.find((item) => item.id === patientId);
      if (!candidate) throw new Error("The patient was not found in the FHIR seed dataset.");
      const form = responseData(formResponse);
      let savedDraft = {};
      try {
        savedDraft = JSON.parse(localStorage.getItem(draftKey) || "{}");
      } catch {
        localStorage.removeItem(draftKey);
      }
      const sourceValues = sourcePrefill(candidate);
      const isVersionedDraft = savedDraft?.version === 1 && savedDraft.values && typeof savedDraft.values === "object";
      const draftValues = isVersionedDraft
        ? savedDraft.values
        : Object.fromEntries(Object.entries(savedDraft || {}).filter(([key, value]) => !["version", "values", "editedSources"].includes(key) && hasDraftValue(value)));
      const draftSources = isVersionedDraft
        ? savedDraft.editedSources || []
        : Object.keys(draftValues);
      setPatient(candidate);
      setDefinition(form);
      setValues({ ...sourceValues, ...draftValues });
      setEditedSources(draftSources);
      localStorage.setItem(draftKey, JSON.stringify({ version: 1, values: draftValues, editedSources: draftSources }));
    }).catch((requestError) => {
      if (active) setError(requestError?.message || "Unable to load the Texas Measles form.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [draftKey, patientId]);

  const fields = definition?.fields || [];
  const sections = fields.reduce((groups, field) => {
    const section = field.field.split(".")[0];
    groups[section] ||= [];
    groups[section].push(field);
    return groups;
  }, {});
  const previewUrl = renderResult?.render_id ? renderUrl(renderResult.render_id) : "";
  const pdfDownloadUrl = renderResult?.render_id ? downloadRenderUrl(renderResult.render_id) : "";

  function updateField(source, value) {
    const next = { ...values, [source]: value };
    const nextEditedSources = [...new Set([...editedSources, source])];
    setValues(next);
    setEditedSources(nextEditedSources);
    localStorage.setItem(draftKey, JSON.stringify({ version: 1, values: next, editedSources: nextEditedSources }));
    setPdfNeedsRefresh(Boolean(renderResult));
    setMessage("Draft saved in this browser.");
  }

  function resetDraft() {
    const sourceValues = patient ? sourcePrefill(patient) : {};
    setValues(sourceValues);
    setEditedSources([]);
    localStorage.removeItem(draftKey);
    setPdfNeedsRefresh(Boolean(renderResult));
    setMessage("FHIR-sourced values restored.");
  }

  async function generatePdf() {
    if (!patient || !definition || working) return;
    setWorking(true);
    setError("");
    setMessage("");
    try {
      const reportData = { ...sourcePrefill(patient), ...values };
      const fullName = String(reportData["patient.name"] || patient.patient || "").trim();
      if (fullName) {
        const nameParts = fullName.split(/\s+/);
        reportData["patient.first_name"] = nameParts.shift() || "";
        reportData["patient.last_name"] = nameParts.join(" ");
      }
      const result = responseData(await renderSeedPatientForm(patient.id, {
        form_id: definition.form_id,
        form_version: definition.form_version,
        report_data: reportData,
      }));
      if (!result?.render_id) throw new Error("The backend did not return a PDF render ID.");
      setRenderResult(result);
      setPdfNeedsRefresh(false);
      setMessage("The official Texas form was generated from this FHIR record and your saved edits.");
    } catch (requestError) {
      setError(requestError?.message || "Unable to generate the Texas Measles PDF.");
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <section className="reporting-form-page"><SignalLoading title="Loading Texas Measles Form" message="Loading the official form definition and selected FHIR patient."/></section>;
  if (!patient || !definition) return <section className="reporting-form-page"><div className="reporting-form-error" role="alert"><h2>Unable to load Texas Measles Form</h2><p>{error || "The patient or form definition was not found."}</p><button type="button" className="button" onClick={() => navigate(`/candidates/${encodeURIComponent(patientId)}`)}>Back to Patient</button></div></section>;

  return <section className="reporting-form-page seed-reporting-form">
    <header className="reporting-form-header">
      <div><button type="button" className="reporting-form-back" onClick={() => navigate(`/candidates/${encodeURIComponent(patient.id)}`)}><ArrowLeft size={14}/> Back to Patient</button><span className="reporting-form-eyebrow">TEXAS PUBLIC HEALTH REPORTING · {definition.form_version}</span><h1>Texas Measles Outbreak Case Report Form</h1><p>Review FHIR-sourced values, make manual corrections, and generate the official PDF.</p></div>
      <div className="reporting-form-context-badges"><span>{patient.patient}</span><span>{patient.jurisdiction}</span><span>{patient.source_file}</span></div>
    </header>
    {(error || message) && <div className={`reporting-form-message ${error ? "is-error" : "is-success"}`} role={error ? "alert" : "status"}>{error || message}</div>}
    <div className="seed-form-layout">
      <section className="seed-form-editor">
        <header className="seed-form-editor-header"><div><span>FORM FIELDS</span><h2>Review and edit values</h2><p>Only values present in FHIR are prefilled; other fields remain blank for manual completion.</p></div><button type="button" className="button seed-reset-button" onClick={resetDraft}><RotateCcw size={14}/> Restore FHIR values</button></header>
        <div className="seed-form-sections">{Object.entries(sections).map(([section, sectionFields]) => <fieldset className="seed-form-section" key={section}>
          <legend>{SECTION_LABELS[section] || fieldLabel(section)}</legend>
          <div className="seed-form-field-grid">{sectionFields.map((field) => <FormField key={field.field} field={field} value={values[field.source]} onChange={updateField}/>)}</div>
        </fieldset>)}</div>
        <div className="seed-form-editor-footer"><span><Save size={14}/> Manual edits are saved in this browser.</span><button type="button" className="button button-primary" onClick={generatePdf} disabled={working}>{working ? "Generating PDF…" : renderResult ? "Update PDF" : "Generate PDF"}</button></div>
      </section>
      <section className="reporting-form-pdf-card seed-form-pdf-card">
        <header className="reporting-form-card-header"><div><span>OFFICIAL PDF PREVIEW</span><h2>{renderResult ? "Generated Texas Form" : "Texas Measles Form"}</h2><p>{renderResult ? `Render ID: ${renderResult.render_id}` : "Generate the PDF to preview and download the filled form."}</p></div>{renderResult && <span className="reporting-form-rendered-badge">PDF generated</span>}</header>
        {pdfNeedsRefresh && <div className="reporting-form-message">Manual edits are saved but not in the current PDF. Select Update PDF to refresh the preview.</div>}
        {previewUrl ? <div className="reporting-form-pdf-frame"><iframe src={previewUrl} title="Official Texas Measles Case Report Form" className="reporting-form-pdf-viewer"/></div> : <div className="reporting-form-pdf-empty"><FileText size={24}/><strong>No generated PDF yet</strong><span>Generate the form to see the official Texas template here.</span></div>}
        {previewUrl && <div className="reporting-form-actions"><a className="button" href={previewUrl} target="_blank" rel="noreferrer">Open PDF</a><a className="button" href={pdfDownloadUrl}><Download size={14}/> Download PDF</a></div>}
        {renderResult && !pdfNeedsRefresh && <div className="seed-form-next-step"><div><strong>Form ready for review</strong><span>Continue to clinical review and validation.</span></div><Link className="button button-primary" to={`/candidates/${encodeURIComponent(patient.id)}/review`}>Continue to Review &amp; Validation <ArrowRight size={15}/></Link></div>}
        {renderResult && pdfNeedsRefresh && <div className="seed-form-next-step is-pending" role="status"><div><strong>Update the PDF to continue</strong><span>Manual edits are not included in the current PDF.</span></div></div>}
        {renderResult?.missing_fields?.length > 0 && <details className="reporting-form-technical"><summary>{renderResult.missing_fields.length} PDF fields remain blank</summary><ul>{renderResult.missing_fields.slice(0, 30).map((field) => <li key={field}>{field}</li>)}</ul></details>}
        {renderResult?.warnings?.length > 0 && <div className="reporting-form-notices"><div><strong>PDF rendering notes</strong><ul>{renderResult.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul></div></div>}
      </section>
    </div>
  </section>;
}
