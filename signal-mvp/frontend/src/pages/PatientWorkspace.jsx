import { useEffect, useMemo, useRef, useState } from "react";

import "@google/model-viewer";



import { Link, useNavigate, useParams } from "react-router-dom";



import { getCanonicalPatient } from "../api/canonical.js";






import { detectPatientCandidates as detectCandidates, getCandidate, persistDetectedCandidate, processCandidate } from "../api/detection.js";
import { getCase } from "../api/cases.js";



import {



  auditEvent,



  listAuditEvents,



} from "../api/workflow.js";





import { deletePatientDocument, uploadPatientDocument } from "../api/documents.js";





import "../styles/patient-workspace.css";





/* =========================================================



   Helpers



\========================================================= */





function formatDate(value) {



  if (!value) return "—";





  const date = new Date(value);





  if (Number.isNaN(date.getTime())) return String(value);





  return date.toLocaleDateString();



}





function formatDateTime(value) {



  if (!value) return "—";





  const date = new Date(value);





  if (Number.isNaN(date.getTime())) return String(value);





  return date.toLocaleString();



}





function safeText(value, fallback = "—") {



  if (value === null || value === undefined) return fallback;





  if (



    typeof value === "string" ||



    typeof value === "number" ||



    typeof value === "boolean"



  ) {



    return String(value);



  }





  return fallback;



}





function displayClinicalValue(value, fallback = String.fromCharCode(0x2014)) {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "object") {
    value = value.display ?? value.text ?? value.code ?? value.numeric ?? value.value ?? value.name;
    if (value === null || value === undefined || value === "") return fallback;
  }
  const raw = String(value).trim();
  const labels = { f: "Female", female: "Female", m: "Male", male: "Male", ambulatory: "Ambulatory visit", available: "Available", finished: "Finished", active: "Active", provisional: "Provisional", final: "Final", present: "Present", completed: "Completed", clinical_note: "Clinical Note", clinical_document: "Clinical Document", diagnostic_report: "Diagnostic Report", "http://hl7.org/fhir/sid/icd-10-cm": "ICD-10-CM", "http://loinc.org": "LOINC", "http://snomed.info/sct": "SNOMED CT" };
  return labels[raw.toLowerCase()] || raw;
}

function getPatientName(patient) {



  if (!patient) return "Patient";





  if (patient.name) {



    if (typeof patient.name === "string") return patient.name;





    if (Array.isArray(patient.name)) {



      const first = patient.name[0];





      if (typeof first === "string") return first;





      return [



        first?.given?.join?.(" "),



        first?.family,



      ]



        .filter(Boolean)



        .join(" ");



    }





    return [



      patient.name.given?.join?.(" "),



      patient.name.family,



    ]



      .filter(Boolean)



      .join(" ");



  }





  return [



    patient.first_name,



    patient.last_name,



  ]



    .filter(Boolean)



    .join(" ") || "Patient";



}





function removePatientNameNumbers(value) {
  const rawName =
    value && typeof value === "object"
      ? getPatientName({ name: value })
      : String(value || "");

  return rawName
    .replace(/\d+/g, " ")
    .replace(/[|#,:;]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[\s_-]+|[\s_-]+$/g, "")
    .trim();
}

function getDocuments(context) {



  return (



    context?.clinical_documents ||



    context?.clinicalDocuments ||



    context?.documents ||



    []



  );



}





function isMeaslesCondition(condition) {
  if (!condition || typeof condition !== "object") return false;

  const code = condition.code;
  const codings = [
    ...(Array.isArray(code?.coding) ? code.coding : []),
    code,
  ];
  const displays = [
    condition.display,
    condition.condition_name,
    condition.name,
    code?.display,
    ...codings.map((coding) => coding?.display),
  ];
  const codes = [
    condition.code_value,
    typeof code === "string" || typeof code === "number" ? code : code?.code,
    ...codings.map((coding) => coding?.code),
  ];

  return (
    displays.some((value) => /measles/i.test(String(value || ""))) ||
    codes.some((value) =>
      /^(?:B05(?:\.|$)|14168008$|14189004$|772152006$)/i.test(
        String(value || "").trim()
      )
    )
  );
}


function getConditions(context) {



  return context?.conditions || [];



}





function getLabs(context) {



  return (



    context?.lab_results ||



    context?.labResults ||



    context?.diagnostic_reports ||



    context?.diagnosticReports ||



    []



  );



}





function getEncounters(context) {



  return context?.encounters || [];



}





function getObservations(context) {



  return context?.observations || [];



}





/* =========================================================



   Workflow



\========================================================= */





function PatientHeader({ patient, onRefresh, refreshing }) {

  const patientData =

    patient?.patient ||

    patient?.data ||

    patient ||

    {};



  const firstName =

    patientData.first_name ||

    patientData.firstName ||

    "";



  const lastName =

    patientData.last_name ||

    patientData.lastName ||

    "";



  const name = removePatientNameNumbers(

    patientData.name ||

    patientData.patient_name ||

    [firstName, lastName]

      .filter(Boolean)

      .join(" ") ||

    "Patient"
  ) || "Patient";



  const patientIdentifier =
    patientData.source_patient_id ||
    patientData.patient_id ||
    patientData.id ||
    String.fromCharCode(0x2014);

  const dob =

    patientData.dob ||

    patientData.date_of_birth ||

    patientData.birth_date ||

    patientData.birthDate ||

    null;



  const rawSex =

    patientData.sex ||

    patientData.gender ||

    patientData.administrative_gender ||

    null;



  const sex = displayClinicalValue(rawSex, "");



  const facility =

    patientData.facility_name ||

    patientData.facility?.name ||

    (typeof patientData.facility === "string"

      ? patientData.facility

      : null);



  const city =

    patientData.city ||

    patientData.location?.city ||

    (typeof patientData.location === "string"

      ? patientData.location

      : null) ||

    patientData.address?.city;



  function formatHeaderDate(value) {

    if (!value) return "—";



    const date = new Date(value);



    if (Number.isNaN(date.getTime())) {

      return value;

    }



    return date.toLocaleDateString("en-US", {

      month: "short",

      day: "numeric",

      year: "numeric",

    });

  }



  const initials =

    `${firstName?.[0] || ""}${lastName?.[0] || ""}`

      .toUpperCase() || "P";



  return (

    <header className="patient-header">



      {/* Top navigation */}

      <div className="patient-header-nav">

        <Link to="/patients" className="back-link">

          ← Back to Patients

        </Link>



        <div className="patient-header-actions">

          <button

            type="button"

            className="secondary-button patient-refresh-button"

            onClick={onRefresh}

            disabled={refreshing}

          >

            {refreshing ? (

              <>

                <span className="refresh-spinner" />

                Refreshing...

              </>

            ) : (

              <>

                ↻ Refresh

              </>

            )}

          </button>

        </div>

      </div>



      {/* Main patient identity */}

      <div className="patient-header-main">



        <div className="patient-avatar">

          {initials}

        </div>



        <div className="patient-header-info">



          <div className="page-kicker">

            PATIENT WORKSPACE

          </div>



          <h1>{name}</h1>



          <div className="patient-identity-row">



            <div className="patient-identity-item">

              <span className="patient-identity-label">

                Patient ID

              </span>



              <span className="patient-identity-value">

                {patientIdentifier}

              </span>

            </div>



            <div className="patient-identity-divider" />



            <div className="patient-identity-item">

              <span className="patient-identity-label">

                DOB

              </span>



              <span className="patient-identity-value">

                {formatHeaderDate(dob)}

              </span>

            </div>



            {sex && (

              <>

                <div className="patient-identity-divider" />



                <div className="patient-identity-item">

                  <span className="patient-identity-label">

                    Sex

                  </span>



                  <span className="patient-identity-value">

                    {sex}

                  </span>

                </div>

              </>

            )}



          </div>



          {(city || facility) && (

            <div className="patient-location">

              <span className="location-icon">

                ●

              </span>



              <span>

                {city || "Location unavailable"}



                {facility && (

                  <>

                    <span className="location-separator">

                      ·

                    </span>



                    {facility}

                  </>

                )}

              </span>

            </div>

          )}



        </div>



      </div>



    </header>

  );

}





/* =========================================================



   Detection Progress



\========================================================= */





const DETECTION_STAGES = [



  {



    id: "context",



    title: "Patient context",



    description: "Loading canonical patient records",



  },



  {



    id: "structured",



    title: "Structured detection",



    description:



      "Checking conditions, laboratory results and observations",



  },



  {



    id: "documents",



    title: "Document intelligence",



    description:



      "Processing available clinical documents",



  },



  {



    id: "fusion",



    title: "Patient detection",



    description:



      "Combining supporting detection signals",



  },



];





function DetectionProgress({ activeStage }) {



  return (



    <section className="detection-panel">



      <div className="section-label">



        SIGNAL DETECTION



      </div>





      <h2>Detection in progress</h2>





      <p className="section-description">SIGNAL is reviewing the patient's clinical information and available documentation.</p>





      <div className="detection-stage-list">



        {DETECTION_STAGES.map((stage, index) => {



          const completed = index < activeStage;



          const active = index === activeStage;





          return (



            <div



              className={`detection-stage ${completed



                ? "completed"



                : active



                  ? "active"



                  : "pending"



                }`}



              key={stage.id}



            >



              <div className="detection-stage-icon">



                {completed ? "✓" : active ? "●" : "○"}



              </div>





              <div className="detection-stage-content">



                <div className="detection-stage-title">



                  {stage.title}



                </div>





                <div className="detection-stage-description">



                  {stage.description}



                </div>





                {stage.id === "structured" &&



                  active && (



                    <div className="stage-detail">



                      Conditions · Labs · Observations



                    </div>



                  )}





                {stage.id === "documents" &&



                  active && (



                    <div className="stage-detail">



                      Extracting clinical evidence from



                      available documents



                    </div>



                  )}



              </div>



            </div>



          );



        })}



      </div>





      <div className="detection-running">



        Reviewing clinical information...



      </div>



    </section>



  );



}





/* =========================================================



   Records Summary



\========================================================= */





function PatientAnatomyCard({ patientName = "Patient", conditions = [], documents = [] }) {
  const documentedText = documents
    .map((document) => [document?.title, document?.extracted_text, document?.text, document?.content].filter(Boolean).join(" "))
    .join(" ")
    .toLowerCase();
  const conditionName = getReadableConditionName(conditions) || "Clinical case";
  const findings = [
    { id: "skin", label: "Rash or skin changes", terms: /rash|maculopapular|skin lesion|skin changes/ },
    { id: "eyes", label: "Eye redness or irritation", terms: /conjunctiv|red eyes|eye redness|eye irritation/ },
    { id: "respiratory", label: "Cough or respiratory symptoms", terms: /cough|coryza|nasal congestion|runny nose|shortness of breath|dyspnea/ },
    { id: "fever", label: "Fever", terms: /\bfever\b|febrile|elevated temperature/ },
    { id: "pain", label: "Pain or tenderness", terms: /\bpain\b|tenderness|soreness/ },
    { id: "gastrointestinal", label: "Gastrointestinal symptoms", terms: /nausea|vomiting|diarrhea|abdominal pain/ },
  ].filter((finding) => finding.terms.test(documentedText));

  return (
    <section className="anatomy-card" aria-labelledby="anatomy-card-title">
      <div className="anatomy-card-copy">
        <span className="anatomy-card-kicker">PATIENT CASE · CLINICAL FINDINGS</span>
        <h2 id="anatomy-card-title">{patientName} · {conditionName}</h2>
        <p className="anatomy-card-note">Generic anatomy view for this case. Findings appear when they are documented in the available clinical notes.</p>
        <div className="anatomy-findings" aria-label="Documented findings shown">
          {findings.length ? findings.map((finding) => (
            <div className="anatomy-finding" key={finding.id}>
              <span className="anatomy-finding-dot" aria-hidden="true" />
              <span>{finding.label}</span>
              <span className="anatomy-finding-status">Documented</span>
            </div>
          )) : <p className="anatomy-no-findings">No matching findings were found in the available clinical documents.</p>}
        </div>
      </div>
      <div className="anatomy-figure-wrap" aria-label="3D patient model">
        <span className="anatomy-visual-badge">GENERIC PATIENT MODEL</span>
        <model-viewer
          class="anatomy-figure"
          src="/models/neutral-mannequin.glb"
          alt="Smooth blue, gender-neutral mannequin shown in a fixed front view"
          shadow-intensity="0.65"
          exposure="1.4"
          environment-image="neutral"
          aria-label="Fixed front view of the gender-neutral patient model"
        >
          {findings.some(({ id }) => id === "skin") && <>
            <span slot="hotspot-rash-face" className="anatomy-callout anatomy-callout-left" data-position="-0.055m 1.49m 0.31m" data-normal="0m 0m 1m" role="img" aria-label="Documented facial rash">
              <span className="anatomy-callout-label" aria-hidden="true">Face rash</span>
            </span>
            <span slot="hotspot-rash-trunk" className="anatomy-callout anatomy-callout-left" data-position="0m 1.27m 0.31m" data-normal="0m 0m 1m" role="img" aria-label="Documented upper trunk rash">
              <span className="anatomy-callout-label" aria-hidden="true">Trunk rash</span>
            </span>
          </>}
          {findings.some(({ id }) => id === "eyes") && <>
            <span slot="hotspot-eye-left" className="anatomy-callout anatomy-callout-point" data-position="-0.035m 1.53m 0.31m" data-normal="0m 0m 1m" role="img" aria-label="Documented redness in left eye" />
            <span slot="hotspot-eye-right" className="anatomy-callout anatomy-callout-right anatomy-callout-face" data-position="0.035m 1.53m 0.31m" data-normal="0m 0m 1m" role="img" aria-label="Documented bilateral eye redness">
              <span className="anatomy-callout-label" aria-hidden="true">Eye redness</span>
            </span>
          </>}
          {findings.some(({ id }) => id === "respiratory") && (
            <span slot="hotspot-respiratory" className="anatomy-callout anatomy-callout-right" data-position="0m 1.16m 0.31m" data-normal="0m 0m 1m" role="img" aria-label="Documented cough and coryza, indicated on the chest">
              <span className="anatomy-callout-label" aria-hidden="true">Cough</span>
            </span>
          )}
        </model-viewer>
        <a className="anatomy-view-label" href="https://www.innerscene.com/tools/library/3d-parts/human-base-mesh-with-editable-53-bone-rig-8e7c8ab1" target="_blank" rel="noreferrer">FIXED FRONT VIEW <i aria-hidden="true" /> CC0 MODEL SOURCE</a>
      </div>
    </section>
  );
}

function RecordSummary({
  patient,
  conditions = [],
  labs = [],
  encounters = [],
  observations = [],
  documents = [],
}) {
  const condition = conditions[0];
  const encounter = encounters[0];
  const observation = observations[0];
  const lab = labs[0];
  const document = documents[0];

  const formatRecordDate = (value) => {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <>
    <PatientAnatomyCard
      patientName={getPatientName(patient?.patient || patient?.data || patient)}
      conditions={conditions}
      documents={documents}
    />
    <section className="patient-records-section">
      <div className="patient-records-heading">
        <span className="patient-records-kicker">
          CLINICAL RECORD
        </span>

        <h2>Structured clinical information currently available for this patient.</h2>

      </div>

      <div className="patient-records-grid">

        {/* CONDITION */}
        <article className="patient-record-card">
          <div className="patient-record-card-label">
            CONDITION
          </div>

          {condition ? (
            <>
              <h3>
                {condition?.code?.display || condition?.display || condition?.code?.code || "Condition"}
              </h3>

              <div className="patient-record-meta">
                <span>
                  {displayClinicalValue(condition?.clinical_status || condition?.status)}
                </span>

                <span className="patient-record-dot">
                  ·
                </span>

                <span>
                  {displayClinicalValue(condition?.verification_status)}
                </span>
              </div>

              {condition?.code?.code && (
                <div className="patient-record-code">
                  {displayClinicalValue(condition.code.system)} · {condition.code.code}
                </div>
              )}
            </>
          ) : (
            <div className="patient-record-empty">
              No condition recorded
            </div>
          )}
        </article>

        {/* LAB RESULT */}
        <article className="patient-record-card">
          <div className="patient-record-card-label">
            LAB RESULT
          </div>

          {lab ? (
            <>
              <h3>
                {lab?.test?.display || lab?.test_name || lab?.test?.code || "Laboratory result"}
              </h3>

              {(lab?.conclusion || lab?.result || lab?.value) && (
                <div className="patient-record-result">
                  {displayClinicalValue(lab.conclusion || lab.result || lab.value)}
                </div>
              )}

              <div className="patient-record-meta">
                <span>
                  {displayClinicalValue(lab?.report_status || lab?.status)}
                </span>

                {(lab?.effective_time || lab?.issued_time) && (
                  <>
                    <span className="patient-record-dot">
                      ·
                    </span>

                    <span>
                      {formatRecordDate(
                        lab.effective_time
                      )}
                    </span>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="patient-record-empty">
              No laboratory results
            </div>
          )}
        </article>

        {/* OBSERVATION */}
        <article className="patient-record-card">
          <div className="patient-record-card-label">
            OBSERVATION
          </div>

          {observation ? (
            <>
              <h3>{observation?.code?.display || observation?.display || observation?.code?.code || "Observation"}</h3>

              {(observation?.value?.text || observation?.value?.code || observation?.value?.numeric) && (
                <div className="patient-record-result">{displayClinicalValue(observation?.value)}</div>
              )}

              <div className="patient-record-meta">
                <span>
                  {displayClinicalValue(observation?.status)}
                </span>

                {observation?.effective_time && (
                  <>
                    <span className="patient-record-dot">
                      ·
                    </span>

                    <span>
                      {formatRecordDate(
                        observation.effective_time
                      )}
                    </span>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="patient-record-empty">
              No observations recorded
            </div>
          )}
        </article>

        {/* ENCOUNTER */}
        <article className="patient-record-card">
          <div className="patient-record-card-label">
            ENCOUNTER
          </div>

          {encounter ? (
            <>
              <h3>{displayClinicalValue(encounter?.encounter_type || "Clinical encounter")}</h3>

              <div className="patient-record-meta">
                <span>
                  {displayClinicalValue(encounter?.status)}
                </span>

                {encounter?.start_time && (
                  <>
                    <span className="patient-record-dot">
                      ·
                    </span>

                    <span>
                      {formatRecordDate(
                        encounter.start_time
                      )}
                    </span>
                  </>
                )}
              </div>

              {encounter?.facility_id && (
                <div className="patient-record-code">
                  {encounter.facility_id}
                </div>
              )}
            </>
          ) : (
            <div className="patient-record-empty">
              No encounters recorded
            </div>
          )}
        </article>

        {/* DOCUMENT */}
        <article className="patient-record-card patient-record-card-document">
          <div className="patient-record-card-label">
            CLINICAL DOCUMENT
          </div>

          {document ? (
            <>
              <h3>
                {document?.title ||
                  "Clinical document"}
              </h3>

              <div className="patient-record-meta">
                <span>
                  {document?.document_type ||
                    "Document"}
                </span>

                <span className="patient-record-dot">
                  ·
                </span>

                <span>
                  {displayClinicalValue(document?.document_status)}
                </span>
              </div>

              {document?.document_date && (
                <div className="patient-record-code">
                  {formatRecordDate(
                    document.document_date
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="patient-record-empty">
              No clinical documents
            </div>
          )}
        </article>

      </div>
    </section>
    </>
  );
}





/* =========================================================



   Documents



\========================================================= */





function DocumentsSection({



  documents,



  onAddDocument,



}) {



  return (



    <section className="documents-section">



      <div className="section-heading-row">



        <div>



          <div className="section-label">



            SOURCE DOCUMENTS



          </div>





          <h2>Clinical documents</h2>

          <p className="section-description">Clinical documentation available to support patient review.</p>









        </div>





        <button



          className="secondary-button"



          onClick={onAddDocument}



        >



          + Add Document



        </button>



      </div>





      {documents.length === 0 ? (



        <div className="empty-state compact">



          No clinical documents uploaded.



        </div>



      ) : (



        <div className="document-list">



          {documents.map((document, index) => {



            const title =



              document.title ||



              document.file_name ||



              document.name ||



              `Clinical Document ${index + 1}`;





            const type =



              document.document_type ||



              document.type ||



              "Clinical document";





            return (



              <div



                className="document-row"



                key={



                  document.id ||



                  document.document_id ||



                  index



                }



              >



                <div>



                  <div className="document-title">



                    {safeText(title)}



                  </div>





                  <div className="document-meta">



                    {displayClinicalValue(type, "Clinical document")}



                    {document.created_at &&



                      ` · ${formatDate(



                        document.created_at



                      )}`}



                  </div>



                </div>





                <span className="status-badge">



                  {displayClinicalValue(document.document_status || document.status, "Available")}



                </span>



              </div>



            );



          })}



        </div>



      )}



    </section>



  );



}

function AiDocumentUploadCard({
  documents = [],
  onUpload,
  onRemove,
  removingDocumentId,
  actionError,
  disabled = false,
}) {
  const uploadedDocuments = (Array.isArray(documents) ? documents : []).filter(
    (document) =>
      document?.provenance?.source === "document_upload" ||
      document?.source === "document_upload"
  );

  return (
    <section className="ai-document-upload-card">
      <div className="ai-document-upload-icon" aria-hidden="true">↑</div>
      <div className="ai-document-upload-copy">
        <div className="section-label">AI DETECTION INPUT</div>
        <h2>Upload clinical documents</h2>
        <p>
          Add a clinical note, lab report, or discharge summary. SIGNAL will
          include it the next time you run detection.
        </p>
        <span className="ai-document-upload-meta">
          {uploadedDocuments.length} uploaded document{uploadedDocuments.length === 1 ? "" : "s"}
          <span aria-hidden="true"> · </span>PDF, DOCX, or TXT up to 10 MB
        </span>
        {actionError && <p className="ai-document-action-error" role="alert">{actionError}</p>}
        {uploadedDocuments.length > 0 && (
          <ul className="ai-uploaded-document-list" aria-label="Uploaded documents">
            {uploadedDocuments.map((document) => {
              const id = document.document_id ?? document.id;
              return (
                <li key={id}>
                  <span className="ai-uploaded-document-name" title={document.title || "Uploaded clinical document"}>
                    {document.title || "Uploaded clinical document"}
                  </span>
                  <button
                    type="button"
                    className="ai-uploaded-document-remove"
                    onClick={() => onRemove(document)}
                    disabled={disabled || !id || removingDocumentId === id}
                    aria-label={`Remove ${document.title || "uploaded document"}`}
                  >
                    {removingDocumentId === id ? "Removing…" : "Remove"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <button
        className="secondary-button ai-document-upload-button"
        type="button"
        onClick={onUpload}
        disabled={disabled}
      >
        Upload documents
      </button>
    </section>
  );
}





/* =========================================================



   Patient Detection Result



\========================================================= */





function getCandidateName(candidate) {



  return (



    candidate?.condition ||



    candidate?.disease ||

    candidate?.disease_id ||



    candidate?.condition_name ||



    candidate?.name ||



    "Potential condition"



  );



}





function normalizeText(value) {
  if (value === undefined || value === null) return "";
  return String(value)
    .normalize("NFKC")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function getDisplayValue(value) {
  if (value === undefined || value === null || value === "") return "";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) {
    return value.map(getDisplayValue).filter(Boolean).join(", ");
  }
  const numeric = value.numeric ?? value.value;
  if (numeric !== undefined && numeric !== null && numeric !== "") {
    const unit = value.unit ? " " + getDisplayValue(value.unit) : "";
    return String(numeric) + unit;
  }
  return (
    getDisplayValue(value.display) ||
    getDisplayValue(value.text) ||
    getDisplayValue(value.name) ||
    getDisplayValue(value.code) ||
    getDisplayValue(value.value) ||
    ""
  );
}

function firstEvidenceValue(...values) {
  for (const value of values) {
    const display = getDisplayValue(value);
    if (display.trim()) return display.trim();
  }
  return "";
}

function getEvidenceCategory(signal, categoryHint = "") {
  if (!signal || typeof signal !== "object") return "";

  const nested =
    signal.evidence &&
      typeof signal.evidence === "object" &&
      !Array.isArray(signal.evidence)
      ? signal.evidence
      : {};

  // ---------------------------------------------------------
  // Candidate Detection trigger types are authoritative
  // for categorizing detection evidence.
  // ---------------------------------------------------------

  const triggerType = normalizeText(
    signal.trigger_type || nested.trigger_type
  )
    .replace(/[\s-]+/g, "_")
    .toUpperCase();

  if (
    triggerType === "SUSPECTED_DISORDER" ||
    triggerType === "CONDITION_CODE" ||
    triggerType === "DIAGNOSIS_PROBLEM"
  ) {
    return "condition";
  }

  if (
    triggerType === "LAB_RESULT" ||
    triggerType === "LAB_ORDER" ||
    triggerType === "ALL_RESULTS" ||
    triggerType === "DOCUMENT_LABORATORY"
  ) {
    return "laboratory";
  }

  if (
    triggerType === "DOCUMENT_EVIDENCE" ||
    triggerType === "DOCUMENT_DIAGNOSIS"
  ) {
    return "document";
  }

  // ---------------------------------------------------------
  // Fallback classification for older / non-trigger evidence.
  // ---------------------------------------------------------

  const markers = [
    signal.source,
    signal.source_type,
    signal.evidence_type,
    signal.resource_type,
    signal.type,
    signal.category,
    nested.source,
    nested.source_type,
    nested.evidence_type,
    nested.resource_type,
    nested.type,
    nested.category,
    categoryHint,
  ]
    .filter(Boolean)
    .map((value) =>
      normalizeText(value).replace(/[\s-]+/g, "_")
    );

  if (
    markers.some((value) =>
      /document|clinical_document|clinical_note|note/.test(value)
    )
  ) {
    return "document";
  }

  if (
    markers.some((value) =>
      /laboratory|lab_result|(^|_)lab($|_)|diagnostic|diagnostic_report/.test(
        value
      )
    )
  ) {
    return "laboratory";
  }

  if (
    markers.some((value) =>
      /condition|clinical|diagnosis|diagnostic_condition/.test(value)
    )
  ) {
    return "condition";
  }

  return "";
}

function getDetectionSignalCounts(result) {
  const signals = Array.isArray(result?.signals)
    ? result.signals.filter(
      (signal) => signal && typeof signal === "object"
    )
    : [];

  if (signals.length > 0) {
    const counts = {
      total: result?.signal_count ?? signals.length,
      clinical: 0,
      laboratory: 0,
      document: 0,
    };

    for (const signal of signals) {
      const category = getEvidenceCategory(signal);
      if (category === "condition") counts.clinical += 1;
      if (category === "laboratory") counts.laboratory += 1;
      if (category === "document") counts.document += 1;
    }

    return counts;
  }

  return {
    total: result?.signal_count ?? 0,
    clinical: result?.condition_signal_count ?? 0,
    laboratory: result?.lab_signal_count ?? 0,
    document: result?.document_signal_count ?? 0,
  };
}

function getCategoryHint(key) {
  const normalized = normalizeText(key).replace(/[\s-]+/g, "_");
  if (/document|clinical_note|notes/.test(normalized)) return "document";
  if (/laboratory|lab_result|(^|_)lab($|_)/.test(normalized)) return "laboratory";
  if (/condition|clinical|diagnosis/.test(normalized)) return "condition";
  return "";
}

function collectCandidateEvidence(candidate) {
  const found = [];

  // Candidate Detection is the only source of evidence shown inside
  // CandidateCard. Prefer the primary `signals` array when it exists.
  // `supporting_signals` and `evidence` can contain the same detection
  // signals in alternate/summary form, which would otherwise render the
  // same evidence more than once.
  const sources = [
    candidate?.signals,
    candidate?.supporting_signals,
    candidate?.evidence,
  ];

  const source = sources.find(
    (value) => Array.isArray(value) && value.length > 0
  );

  if (!source) {
    return found;
  }

  for (const signal of source) {
    if (!signal || typeof signal !== "object") {
      continue;
    }

    found.push({
      item: signal,
      categoryHint: "",
    });
  }

  return found;
}

function getCanonicalEvidenceRecords(context, category) {
  const value =
    category === "condition"
      ? getConditions(context)
      : category === "laboratory"
        ? getLabs(context)
        : getDocuments(context);
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function getEvidenceData(item) {
  return item?.evidence && typeof item.evidence === "object" && !Array.isArray(item.evidence)
    ? item.evidence
    : item || {};
}

function getEvidenceSourceId(item) {
  const data = getEvidenceData(item);
  return firstEvidenceValue(
    data.source_id,
    data.condition_id,
    data.lab_result_id,
    data.document_id,
    item?.source_id,
    item?.condition_id,
    item?.lab_result_id,
    item?.document_id
  );
}

function getCanonicalSourceId(item, category) {
  if (!item) return "";
  return firstEvidenceValue(
    item.condition_id,
    item.lab_result_id,
    item.document_id,
    item.source_condition_id,
    item.source_lab_result_id,
    item.source_document_id,
    category === "condition" ? item.id : "",
    category === "laboratory" ? item.id : "",
    category === "document" ? item.id : ""
  );
}

function getEvidenceName(item, data, category) {
  const contextName =
    category === "condition"
      ? item?.code?.display
      : category === "laboratory"
        ? item?.test?.display
        : item?.title;
  const nestedName =
    category === "condition"
      ? data?.code?.display
      : category === "laboratory"
        ? data?.test?.display
        : data?.title;

  if (category === "condition") {
    return firstEvidenceValue(
      contextName,
      nestedName,
      data?.condition_name,
      item?.condition_name,
      data?.display,
      item?.display,
      data?.description,
      item?.description,
      data?.name,
      item?.name,
      data?.label,
      item?.label,
      data?.code_display,
      item?.code_display
    );
  }
  if (category === "laboratory") {
    const observations = data?.observations || item?.observations || [];
    const firstObservation = Array.isArray(observations)
      ? observations.find(Boolean)
      : null;
    return firstEvidenceValue(
      contextName,
      nestedName,
      data?.test_name,
      item?.test_name,
      data?.display,
      item?.display,
      data?.name,
      item?.name,
      data?.description,
      item?.description,
      data?.code?.display,
      item?.code?.display,
      firstObservation?.code?.display,
      firstObservation?.display
    );
  }
  return firstEvidenceValue(
    contextName,
    nestedName,
    data?.document_title,
    item?.document_title,
    data?.name,
    item?.name,
    data?.document_type,
    item?.document_type,
    data?.source_title,
    item?.source_title,
    data?.title,
    item?.title
  );
}

function getLabResult(item, data, raw) {
  const canonicalObservations = item?.observations;
  const evidenceObservations = data?.observations;
  const rawObservations = raw?.observations;
  const observations = [
    ...(Array.isArray(evidenceObservations) ? evidenceObservations : []),
    ...(Array.isArray(rawObservations) ? rawObservations : []),
    ...(Array.isArray(canonicalObservations) ? canonicalObservations : []),
  ];
  const observationValues = observations.map((observation) =>
    getDisplayValue(observation?.value)
  );
  return firstEvidenceValue(
    raw?.result,
    data?.result,
    item?.result,
    raw?.conclusion,
    data?.conclusion,
    item?.conclusion,
    raw?.result_text,
    data?.result_text,
    item?.result_text,
    raw?.interpretation,
    data?.interpretation,
    item?.interpretation,
    raw?.value,
    data?.value,
    item?.value,
    ...observationValues
  );
}

function isDuplicateDocumentSentence(sentence, representedEvidence) {
  const text = normalizeText(sentence);
  if (!text) return true;

  return representedEvidence.some((item) => {
    const name = normalizeText(item.name);
    const description = normalizeText(item.description);
    const result = normalizeText(item.result);
    if (
      item.category === "condition" &&
      name.length > 3 &&
      text.includes(name)
    ) {
      return true;
    }
    if (
      item.category === "laboratory" &&
      name.length > 3 &&
      result &&
      text.includes(name) &&
      text.includes(result)
    ) {
      return true;
    }
    return (
      description.length > 12 &&
      (text === description || text.includes(description))
    );
  });
}

function selectDocumentSentence(text, representedEvidence) {
  const sentences =
    String(text)
      .replace(/\s+/g, " ")
      .match(/[^.!?]+[.!?]?/g)
      ?.map((sentence) => sentence.trim())
      .filter((sentence) => sentence.length >= 20) || [];
  const relevantTerms =
    /\b(patient|clinical|present|symptom|diagnos|assessment|concern|finding|report|history|treatment|examination|impression|onset|result|test|positive|negative|detected)\b/i;
  const candidates = sentences
    .filter((sentence) => !isDuplicateDocumentSentence(sentence, representedEvidence))
    .map((sentence) => ({
      sentence,
      score:
        (relevantTerms.test(sentence) ? 2 : 0) +
        Math.min(sentence.length, 240) / 240,
    }))
    .sort((a, b) => b.score - a.score);
  const excerpt = candidates[0]?.sentence || "";
  if (excerpt.length <= 240) return excerpt;
  const concise = excerpt.slice(0, 237).replace(/\s+\S*$/, "");
  return concise ? concise + "..." : excerpt.slice(0, 237) + "...";
}

function getDocumentExcerpt(document, representedEvidence = []) {
  if (!document || typeof document !== "object") return "";

  const structuredSummary = firstEvidenceValue(
    document.clinical_summary,
    document.summary,
    document.abstract,
    document.description
  );
  const summaryExcerpt = selectDocumentSentence(
    structuredSummary,
    representedEvidence
  );
  if (summaryExcerpt) return summaryExcerpt;

  return selectDocumentSentence(
    firstEvidenceValue(
      document.extracted_text,
      document.extractedText,
      document.text,
      document.content
    ),
    representedEvidence
  );
}

function normalizeCandidateEvidence(candidate, context) {
  const entries = collectCandidateEvidence(candidate);
  const normalized = [];
  const seen = new Set();

  for (const entry of entries) {
    const raw = entry?.item;
    const categoryHint = entry?.categoryHint || "";

    if (!raw || typeof raw !== "object") {
      continue;
    }

    const nested =
      raw.evidence &&
        typeof raw.evidence === "object" &&
        !Array.isArray(raw.evidence)
        ? raw.evidence
        : {};

    const category = getEvidenceCategory(raw, categoryHint);

    if (!category) {
      continue;
    }

    /*
     * The candidate detection response is the source of truth.
     *
     * Do NOT pull additional evidence from canonical patient
     * records here. Canonical documents belong in Source Documents.
     */

    const sourceId =
      raw.source_id ||
      raw.evidence_id ||
      raw.signal_id ||
      nested.source_id ||
      nested.evidence_id ||
      raw.trigger_key ||
      `${category}-${normalized.length}`;

    const identity = normalizeText(sourceId);

    if (seen.has(identity)) {
      continue;
    }

    seen.add(identity);

    if (category === "condition") {
      const name = firstEvidenceValue(
        nested.display,
        nested.name,
        nested.code_display,
        raw.display,
        raw.name,
        raw.condition_name,
        raw.description,
        raw.trigger_type,
        "Condition evidence"
      );

      const description = firstEvidenceValue(
        nested.description,
        raw.description,
        nested.display,
        raw.display
      );

      const status = firstEvidenceValue(
        nested.clinical_status,
        nested.status,
        raw.clinical_status,
        raw.status
      );

      const verification = firstEvidenceValue(
        nested.verification_status,
        nested.verification,
        raw.verification_status,
        raw.verification
      );

      normalized.push({
        category: "condition",
        title: "Condition evidence",
        name,
        description,
        status,
        verification,
        sourceId,
      });

      continue;
    }

    if (category === "laboratory") {
      const name = firstEvidenceValue(
        nested.display,
        nested.test_name,
        nested.name,
        nested.code_display,
        raw.test_name,
        raw.name,
        raw.code_display,
        raw.display,
        raw.description,
        "Laboratory result"
      );

      const result = firstEvidenceValue(
        nested.result,
        nested.value,
        nested.interpretation,
        nested.result_text,
        raw.result,
        raw.value,
        raw.interpretation,
        raw.result_text
      );

      const status = firstEvidenceValue(
        nested.status,
        nested.result_status,
        nested.report_status,
        raw.status,
        raw.result_status,
        raw.report_status
      );

      normalized.push({
        category: "laboratory",
        title: "Laboratory evidence",
        name,
        description: firstEvidenceValue(
          nested.description,
          raw.description,
          name
        ),
        result,
        status,
        sourceId,
      });

      continue;
    }

    if (category === "document") {
      const name = firstEvidenceValue(
        nested.title,
        nested.document_title,
        nested.name,
        raw.document_title,
        raw.title,
        raw.name,
        raw.description,
        "Clinical document"
      );

      const description = firstEvidenceValue(
        nested.excerpt,
        nested.evidence_text,
        nested.text,
        nested.description,
        raw.evidence_text,
        raw.excerpt,
        raw.description
      );

      normalized.push({
        category: "document",
        title: "Document evidence",
        name,
        description,
        sourceId,
      });
    }
  }

  return normalized.filter(
    (item) =>
      item &&
      (
        item.name ||
        item.description ||
        item.result
      )
  );
}

function getCandidateSignalEntries(candidate) {
  const sources = [candidate?.signals, candidate?.supporting_signals, candidate?.evidence];
  const source = sources.find((value) => Array.isArray(value) && value.length > 0);
  return Array.isArray(source) ? source.filter((signal) => signal && typeof signal === "object") : [];
}

function getCandidateDisplaySignals(candidate) {
  const entries = getCandidateSignalEntries(candidate);
  const documentEntries = entries.filter(
    (signal) => getEvidenceCategory(signal) === "document"
  );
  const clinicalEntries = entries.filter(
    (signal) => getEvidenceCategory(signal) !== "document"
  );
  const entriesToDisplay = clinicalEntries.length > 0 ? clinicalEntries : entries;
  const seen = new Set();

  const visibleSignals = entriesToDisplay.filter((signal) => {
    const category = getEvidenceCategory(signal);
    if (category !== "laboratory") return true;

    const code = getSignalValue(signal, "evidence.code", "test_code", "code");
    const title = getSignalTitle(signal, category).toLowerCase();
    const evidenceText = getSignalValue(signal, "evidence.evidence_text", "evidence_text").toLowerCase();
    const text = `${title} ${evidenceText}`;
    // A coded lab result and an NLP mention of the same result are one
    // clinical finding for the summary. Keep unrelated assays separate.
    const identity = /measles/.test(text) && /\b(rna|pcr|nucleic acid|naa)\b/.test(text)
      ? "measles-rna-pcr"
      : code
        ? `code:${String(code).toLowerCase()}`
        : `text:${title.replace(/\b(positive|detected|result|test|laboratory)\b/g, " ").replace(/[^a-z0-9]+/g, " ").trim()}`;
    const key = `${category}:${identity}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  if (clinicalEntries.length === 0 || documentEntries.length === 0) {
    return visibleSignals;
  }

  const supportingDocumentEvidence = documentEntries.map((signal) => ({
    title: getSignalTitle(signal, "document"),
    text: getSignalValue(
      signal,
      "evidence.evidence_text",
      "evidence.concept",
      "evidence.text",
      "evidence_text",
      "text",
      "description"
    ),
    sourceId: getSignalValue(signal, "evidence.source_id", "source_id"),
  }));
  const conditionIndex = visibleSignals.findIndex(
    (signal) => getEvidenceCategory(signal) === "condition"
  );
  const attachmentIndex = conditionIndex >= 0 ? conditionIndex : 0;

  return visibleSignals.map((signal, index) =>
    index === attachmentIndex
      ? { ...signal, supporting_document_evidence: supportingDocumentEvidence }
      : signal
  );
}

function getSignalValue(signal, ...keys) {
  const evidence = signal?.evidence && typeof signal.evidence === "object" && !Array.isArray(signal.evidence)
    ? signal.evidence
    : {};

  for (const key of keys) {
    const value = key.includes(".")
      ? key.split(".").reduce((current, part) => current?.[part], signal)
      : signal?.[key] ?? evidence?.[key];
    if (value !== null && value !== undefined && value !== "") {
      if (typeof value === "object") {
        return value.display ?? value.text ?? value.code ?? value.value ?? value.name ?? "";
      }
      return value;
    }
  }
  return "";
}

function getSignalTitle(signal, category) {
  if (category === "condition") {
    return getSignalValue(
      signal,
      "evidence.display",
      "evidence.name",
      "evidence.code_display",
      "evidence.concept",
      "condition_name",
      "display",
      "name",
      "trigger_concept_key",
      "trigger_key"
    ) || "Condition signal";
  }

  if (category === "laboratory") {
    return getSignalValue(
      signal,
      "evidence.display",
      "evidence.test_name",
      "evidence.name",
      "evidence.concept",
      "test_name",
      "display",
      "name",
      "observation_code_display"
    ) || "Laboratory signal";
  }

  return getSignalValue(
    signal,
    "title",
    "document_title",
    "evidence.title",
    "evidence.document_title",
    "evidence.source_title",
    "source_title",
    "evidence.file_name",
    "file_name",
    "name",
    "document_type"
  ) || "Clinical document";
}

function getSignalCategoryLabel(category) {
  if (category === "condition") return "Clinical Signal";
  if (category === "laboratory") return "Laboratory Signal";
  return "Document Signal";
}

function getSignalPrimaryValue(signal, category) {
  if (category === "laboratory") {
    const result = getSignalValue(
      signal,
      "result",
      "observation_value",
      "value",
      "interpretation",
      "report_status",
      "evidence.result",
      "evidence.value",
      "evidence.evidence_text"
    );

    const evidenceText = getSignalValue(signal, "evidence.evidence_text", "evidence_text");
    const textualResult = String(evidenceText).match(
      /\b(?:not detected|non[- ]?reactive|positive|detected|reactive|negative)\b/i
    )?.[0];

    if (textualResult && result === evidenceText) {
      return textualResult.toUpperCase();
    }

    return result;
  }

  if (category === "document") {
    return getSignalValue(
      signal,
      "text",
      "evidence_text",
      "evidence.text",
      "evidence.excerpt",
      "description"
    );
  }

  return getSignalValue(
    signal,
    "evidence.display",
    "evidence.description",
      "evidence.concept",
      "evidence.evidence_text",
    "description",
    "display",
    "name"
  );
}

function getSignalDetails(signal, category) {
  const evidence = signal?.evidence && typeof signal.evidence === "object" && !Array.isArray(signal.evidence)
    ? signal.evidence
    : {};

  const rows = [
    ["Source ID", signal?.source_id ?? evidence?.source_id],
    ["Trigger", signal?.trigger_type ?? signal?.trigger_key],
    ["Trigger Concept", signal?.trigger_concept_key ?? signal?.trigger_concept],
    ["Encounter", signal?.encounter_id],
    ["Code", evidence?.code ?? signal?.code],
    ["Code System", evidence?.code_system ?? signal?.code_system],
    ["Observation ID", signal?.observation_id],
    ["Observation Value", signal?.observation_value],
    ["Document ID", signal?.document_id ?? evidence?.document_id],
    ["Document name", signal?.source_title ?? evidence?.source_title ?? signal?.document_title ?? evidence?.document_title],
    ["Document Type", signal?.document_type ?? evidence?.document_type],
    ["Document Date", signal?.document_date ?? evidence?.document_date],
    ["Document Status", signal?.document_status ?? evidence?.document_status],
    ["Evidence Role", signal?.evidence_role ?? evidence?.evidence_role],
    ["Confidence", getConfidenceLabel(signal?.confidence)],
    ["Detected At", signal?.detected_at],
  ];

  return rows.filter(([, value]) => value !== null && value !== undefined && value !== "");
}

function getSignalMoreDetails(signal) {
  const evidence = signal?.evidence && typeof signal.evidence === "object" && !Array.isArray(signal.evidence)
    ? signal.evidence
    : {};

  const rows = [
    ["Trigger ID", signal?.trigger_id],
    ["Trigger Concept Keys", signal?.trigger_concept_keys],
    ["Trigger Keys", signal?.trigger_keys],
    ["Trigger Types", signal?.trigger_types],
    ["Disease ID", signal?.disease_id],
    ["Source Type", signal?.source_type ?? evidence?.source_type],
    ["RCTC Group", evidence?.rctc_group],
    ["RCTC Group ID", evidence?.rctc_group_id],
    ["Value Sets", evidence?.value_sets],
    ["Value Set IDs", evidence?.value_set_ids],
    ["Value Set URLs", evidence?.value_set_urls],
  ];

  return rows.filter(([, value]) => value !== null && value !== undefined && value !== "");
}

function getReadableConditionName(value) {
  if (value === null || value === undefined || value === "") return "";

  if (Array.isArray(value)) {
    for (const item of value) {
      const readable = getReadableConditionName(item);
      if (readable) return readable;
    }
    return "";
  }

  if (typeof value === "object") {
    for (const key of [
      "display",
      "condition_name",
      "disease_name",
      "name",
      "text",
      "title",
      "description",
      "coding",
    ]) {
      const readable = getReadableConditionName(value[key]);
      if (readable) return readable;
    }
    return "";
  }

  const text = String(value).trim();
  if (
    !text ||
    /https?:\/\//i.test(text) ||
    text.includes("|") ||
    /^\d{5,}$/.test(text) ||
    /^[A-Z]\d{2}(?:\.\d+)?$/i.test(text)
  ) {
    return "";
  }

  return text;
}

function getCandidateConditionName(candidate) {
  const candidateFields = [
    candidate?.condition_name,
    candidate?.disease_name,
    candidate?.condition_display,
    candidate?.disease_display,
    candidate?.condition,
    candidate?.disease,
    candidate?.name,
    candidate?.display,
    candidate?.disease_id,
  ];

  for (const field of candidateFields) {
    const readable = getReadableConditionName(field);
    if (readable) return readable;
  }

  const signals = getCandidateSignalEntries(candidate).sort((a, b) => {
    const diagnosisPattern = /diagnos|suspected_disorder|condition/i;
    return Number(diagnosisPattern.test(b?.trigger_type || "")) -
      Number(diagnosisPattern.test(a?.trigger_type || ""));
  });
  for (const signal of signals) {
    const evidence = signal?.evidence;
    const signalFields = [
      signal?.condition_name,
      signal?.disease_name,
      signal?.display,
      signal?.name,
      evidence?.condition_name,
      evidence?.disease_name,
      evidence?.display,
      evidence?.name,
      evidence?.concept?.display,
      evidence?.description,
      signal?.description,
    ];

    for (const field of signalFields) {
      const readable = getReadableConditionName(field);
      if (readable) return readable;
    }
  }

  return "Potential condition";
}

function formatSignalDetail(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    return value?.display ?? value?.text ?? value?.code ?? JSON.stringify(value);
  }
  return String(value);
}

function getConfidenceLabel(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string" && /^(high|medium|low)$/i.test(value.trim())) {
    return value.trim()[0].toUpperCase() + value.trim().slice(1).toLowerCase();
  }

  const text = String(value).trim();
  const parsed = Number.parseFloat(text);
  if (!Number.isFinite(parsed)) return safeText(value);

  const normalized = text.includes("%") || parsed > 1 ? parsed / 100 : parsed;
  if (normalized >= 0.8) return "High";
  if (normalized >= 0.5) return "Medium";
  return "Low";
}

function DetectionSignal({ signal, category }) {
  const [expanded, setExpanded] = useState(false);
  const title = getSignalTitle(signal, category);
  const primaryValue = getSignalPrimaryValue(signal, category);
  const details = getSignalDetails(signal, category);
  const moreDetails = getSignalMoreDetails(signal);
  const supportingDocumentEvidence = Array.isArray(signal?.supporting_document_evidence)
    ? signal.supporting_document_evidence.filter((item) => item?.text || item?.title)
    : [];

  const icon =
    category === "condition" ? "✦" : category === "laboratory" ? "⌁" : "▤";

  return (
    <article className={`signal-accordion signal-accordion-${category}`}>
      <button
        type="button"
        className="signal-accordion-trigger"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <span className="signal-accordion-icon" aria-hidden="true">
          {icon}
        </span>
        <span className="signal-accordion-heading">
          <span className="signal-accordion-type">
            {getSignalCategoryLabel(category)}
          </span>
          <strong>{title}</strong>
        </span>
        <span className={`signal-accordion-chevron ${expanded ? "open" : ""}`} aria-hidden="true">
          ↓
        </span>
      </button>

      {expanded && (
        <div className="signal-accordion-body">
          {primaryValue && (
            <div className="signal-evidence-callout">
              <span>
                {category === "laboratory"
                  ? "Result"
                  : category === "document"
                    ? "Evidence"
                    : "Evidence"}
              </span>
              <strong>{formatSignalDetail(primaryValue)}</strong>
            </div>
          )}

          {supportingDocumentEvidence.length > 0 && (
            <div className="signal-evidence-callout">
              <span>Supporting document evidence</span>
              {supportingDocumentEvidence.map((item, index) => (
                <p key={item.sourceId || `${item.title}-${index}`}>
                  <strong>{item.title || "Clinical document"}</strong>
                  {item.text ? ` — ${item.text}` : ""}
                </p>
              ))}
            </div>
          )}

          {details.length > 0 && (
            <div className="signal-detail-grid">
              {details.map(([label, value]) => (
                <div className="signal-detail" key={label}>
                  <span>{label}</span>
                  <strong
                    className={label === "Confidence" ? `detection-confidence-${String(value).toLowerCase()}` : undefined}
                  >
                    {formatSignalDetail(value)}
                  </strong>
                </div>
              ))}
            </div>
          )}

          {moreDetails.length > 0 && (
            <details className="signal-more-details">
              <summary>More detection details</summary>
              <div className="signal-detail-grid signal-detail-grid-secondary">
                {moreDetails.map(([label, value]) => (
                  <div className="signal-detail" key={label}>
                    <span>{label}</span>
                    <strong>{formatSignalDetail(value)}</strong>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </article>
  );
}

function CandidateDetails({ candidate, signalCount }) {
  const signalSources = [...new Set(
    getCandidateSignalEntries(candidate)
      .map((signal) => {
        const category = getEvidenceCategory(signal);
        if (category === "condition") return "Clinical record";
        if (category === "laboratory") return "Laboratory result";
        if (category === "document") return "Clinical document";
        return "";
      })
      .filter(Boolean)
  )];
  const detectedAt = candidate?.detected_at
    ? new Date(candidate.detected_at)
    : null;
  const detectedLabel = detectedAt && !Number.isNaN(detectedAt.getTime())
    ? detectedAt.toLocaleString(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit",
      })
    : "Not available";
  const statusLabel = String(candidate?.status || "POTENTIAL").toUpperCase() === "POTENTIAL"
    ? "Potential · review needed"
    : displayClinicalValue(candidate?.status);
  const readableDetails = [
    ["Review status", statusLabel],
    ["Disease", getCandidateConditionName(candidate)],
    ["Evidence found", signalSources.length ? signalSources.join(" · ") : "Clinical evidence"],
    ["Distinct supporting findings", signalCount],
    ["Confidence", getConfidenceLabel(candidate?.confidence ?? candidate?.score)],
    ["Detected", detectedLabel],
  ];
  const technicalDetails = [
    ["Patient detection ID", candidate?.candidate_id ?? candidate?.id],
    ["Disease ID", candidate?.disease_id],
    ["Encounter", candidate?.encounter_id ?? candidate?.encounter?.id],
    ["Trigger Type", candidate?.trigger_type ?? candidate?.trigger_types],
    ["Trigger Concept", candidate?.trigger_concept_key ?? candidate?.trigger_concept_keys],
    ["Detected At", candidate?.detected_at],
    ["Evidence Sources", candidate?.evidence_source_types],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");

  return (
    <section className="detection-candidate-details">
      <div className="detection-section-heading">
        <div>
          <span className="detection-eyebrow">PATIENT DETAILS</span>
          <h3>{getCandidateConditionName(candidate)} review</h3>
        </div>
        <span className="detection-section-note">AI detection summary</span>
      </div>

      <div className="detection-details-table">
        {readableDetails.map(([label, value]) => (
          <div className="detection-details-row" key={label}>
            <span>{label}</span>
            <strong
              className={label === "Confidence" ? `detection-confidence-${String(value).toLowerCase()}` : undefined}
            >
              {formatSignalDetail(value)}
            </strong>
          </div>
        ))}
      </div>
      {technicalDetails.length > 0 && (
        <details className="candidate-technical-details">
          <summary>Technical identifiers and source metadata</summary>
          <div className="detection-details-table detection-details-table-technical">
            {technicalDetails.map(([label, value]) => (
              <div className="detection-details-row" key={label}>
                <span>{label}</span>
                <strong>{formatSignalDetail(value)}</strong>
              </div>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

function DetectionCandidate({ candidate, onContinue, onRunAgain }) {
  const rawSignals = getCandidateDisplaySignals(candidate);
  const grouped = { condition: [], laboratory: [], document: [] };

  rawSignals.forEach((signal) => {
    const category = getEvidenceCategory(signal);
    if (grouped[category]) grouped[category].push(signal);
  });

  const signalCount = rawSignals.length;
  const hasClinicalSignals = grouped.condition.length > 0 || grouped.laboratory.length > 0;
  const confidence = candidate?.confidence ?? candidate?.score;
  const name = getCandidateConditionName(candidate).replaceAll("_", " ");
  const confidenceValue = getConfidenceLabel(confidence);

  return (
    <div className="enterprise-detection-result">
      <section className="detection-result-hero">
        <div className="detection-result-hero-topline">
          <div className="detection-result-kicker">
            <span className="detection-live-dot" />
            SIGNAL DETECTION · COMPLETED
          </div>
          <button
            type="button"
            className="detection-run-again"
            onClick={onRunAgain}
          >
            Run again
          </button>
        </div>

        <div className="detection-result-hero-main">
          <div>
            <span className="detection-result-overline">Potential reportable condition</span>
            <h2>{safeText(name).toUpperCase()}</h2>
            <div className="detection-status-pill">
              <span className="detection-status-dot" />
              Potential · Review Required
            </div>
          </div>

          <div className="detection-hero-metrics">
            <div>
              <span>Confidence</span>
              <strong className={`detection-confidence-${confidenceValue.toLowerCase()}`}>
                {confidenceValue}
              </strong>
            </div>
            <div>
              <span>Supporting signals</span>
              <strong>{signalCount}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="detection-support-section">
        <div className="detection-section-heading">
          <div>
            <span className="detection-eyebrow">
              {hasClinicalSignals ? "CLINICAL SIGNALS" : "SUPPORTING SIGNALS"}
            </span>
            <h3>What SIGNAL found</h3>
          </div>
          <span className="detection-section-note">
            {signalCount} {hasClinicalSignals ? "clinical " : "supporting "}signal{signalCount === 1 ? "" : "s"}
          </span>
        </div>

        <div className="signal-accordion-list">
          {["condition", "laboratory", "document"].map((category) =>
            grouped[category].length > 0 ? (
              grouped[category].map((signal, index) => (
                <DetectionSignal
                  key={
                    signal?.signal_id ||
                    signal?.source_id ||
                    `${category}-${index}`
                  }
                  signal={signal}
                  category={category}
                />
              ))
            ) : null
          )}
        </div>

        {signalCount === 0 && (
          <div className="detection-empty-signals">
            No supporting signals were returned for this patient.
          </div>
        )}
      </section>

      <CandidateDetails candidate={candidate} signalCount={signalCount} />

      <div className="detection-action-bar">
        <div>
          <span className="detection-eyebrow">NEXT STEP</span>
          <strong>Patient review is ready</strong>
          <span>Continue when you are ready to begin reporting.</span>
        </div>
        <button
          type="button"
          className="detection-primary-action"
          onClick={() => onContinue(candidate)}
        >
          Continue to Reporting
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </div>
  );
}

/* =========================================================



   Why Flagged



\========================================================= */






/* =========================================================



   Next Action



\========================================================= */





function EncountersTab({ encounters = [] }) {
  const encounterTypeLabels = {
    I: "Inpatient",
    IMP: "Inpatient",
    INPATIENT: "Inpatient",
    O: "Outpatient",
    AMB: "Ambulatory",
    AMBULATORY: "Ambulatory",
    OUTPATIENT: "Outpatient",
    E: "Emergency",
    EMER: "Emergency",
    EMERGENCY: "Emergency",
    OBS: "Observation",
    OBSENC: "Observation",
    OBSERVATION: "Observation",
    PRENC: "Pre-admission",
    SS: "Short stay",
    V: "Virtual",
    VR: "Virtual",
  };

  if (!Array.isArray(encounters) || encounters.length === 0) {
    return <div className="empty-state">No encounter records are available.</div>;
  }

  return (
    <section className="tab-section encounters-tab">
      <header className="encounters-heading">
        <div>
          <div className="section-label">ENCOUNTERS</div>
          <h2>Patient encounters</h2>
          <p>Visit dates, type, location, and status from the patient record.</p>
        </div>
        <span className="encounters-count">
          {encounters.length} {encounters.length === 1 ? "encounter" : "encounters"}
        </span>
      </header>

      <div className="encounter-list">
        {encounters.map((encounter, index) => {
          const rawType = encounter?.type || encounter?.encounter_type;
          const normalizedType = String(rawType || "").trim().toUpperCase();
          const typeLabel = encounterTypeLabels[normalizedType] ||
            String(rawType || "Encounter")
              .replace(/[_-]+/g, " ")
              .replace(/\b\w/g, (letter) => letter.toUpperCase());
          const facilityName =
            encounter?.facility_name ||
            encounter?.facility?.name ||
            (typeof encounter?.facility === "string" ? encounter.facility : "");
          const facilityId = encounter?.facility_id;
          const providerName =
            encounter?.provider_name || encounter?.provider?.name;
          const startTime =
            encounter?.start_time ||
            encounter?.date ||
            encounter?.start ||
            encounter?.period?.start ||
            encounter?.encounter_date;
          const status = encounter?.status;
          const id = encounter?.encounter_id || encounter?.id || index;

          return (
            <article className="encounter-card" key={id}>
              <time className="encounter-date" dateTime={startTime || undefined}>
                {startTime ? formatDateTime(startTime) : "Date not recorded"}
              </time>

              <div className="encounter-main">
                <strong>{typeLabel}</strong>
                {facilityName ? (
                  <span>Facility: {safeText(facilityName)}</span>
                ) : facilityId ? (
                  <span>Facility ID: {safeText(facilityId)}</span>
                ) : null}
                {providerName && <span>Provider: {safeText(providerName)}</span>}
              </div>

              <span className="status-badge">
                {status
                  ? String(status).replace(/[_-]+/g, " ").toUpperCase()
                  : "STATUS UNAVAILABLE"}
              </span>
            </article>
          );
        })}
      </div>
    </section>
  );
}

/* =========================================================



   Evidence



\========================================================= */





function formatEvidenceMeta(...values) {
  return values
    .map((value) => (value === null || value === undefined ? "" : String(value).trim()))
    .filter(Boolean)
    .join(" · ");
}

function EvidenceTab({
  conditions = [],
  labs = [],
  observations = [],
  documents = [],
  onAddDocument,
}) {
  const groups = [
    {
      key: "conditions",
      title: "Conditions",
      items: conditions,
      getKey: (item) => item?.condition_id || item?.source_condition_id,
      getDate: (item) => item?.onset_time || item?.recorded_time,
      renderItem: (item) =>
        item?.code?.display || item?.display || item?.name || item?.code?.text || "Condition",
      renderMeta: (item) =>
        formatEvidenceMeta(
          item?.clinical_status && `Status: ${displayClinicalValue(item.clinical_status)}`,
          item?.verification_status && `Verification: ${displayClinicalValue(item.verification_status)}`
        ),
    },
    {
      key: "laboratory",
      title: "Laboratory results",
      items: labs,
      getKey: (item) => item?.lab_result_id || item?.source_lab_result_id,
      getDate: (item) => item?.effective_time || item?.issued_time,
      renderItem: (item) =>
        item?.test?.display || item?.test_name || item?.name || item?.display || "Laboratory result",
      renderMeta: (item) => {
        const observationValues = (item?.observations || [])
          .map((observation) => getDisplayValue(observation?.value))
          .filter(Boolean);
        const result = firstEvidenceValue(
          item?.conclusion,
          item?.result,
          item?.value,
          ...observationValues
        );
        return formatEvidenceMeta(
          result && `Result: ${result}`,
          (item?.report_status || item?.status) &&
            `Status: ${displayClinicalValue(item.report_status || item.status)}`
        );
      },
    },
    {
      key: "observations",
      title: "Observations",
      items: observations,
      getKey: (item) => item?.observation_id || item?.source_observation_id,
      getDate: (item) => item?.effective_time,
      renderItem: (item) =>
        item?.code?.display || item?.display || item?.name || item?.code?.text || "Observation",
      renderMeta: (item) =>
        formatEvidenceMeta(
          getDisplayValue(item?.value) && `Value: ${getDisplayValue(item.value)}`,
          item?.status && `Status: ${displayClinicalValue(item.status)}`
        ),
    },
    {
      key: "documents",
      title: "Documents",
      items: documents,
      getKey: (item) => item?.document_id || item?.source_document_id || item?.id,
      getDate: (item) => item?.document_date || item?.created_at,
      renderItem: (item) => item?.title || item?.file_name || item?.name || "Clinical document",
      renderMeta: (item) =>
        formatEvidenceMeta(
          displayClinicalValue(item?.document_type || item?.type, "Clinical document"),
          item?.document_status && `Status: ${displayClinicalValue(item.document_status)}`
        ),
    },
  ].filter((group) => group.items.length > 0);

  return (
    <section className="tab-section evidence-tab">
      <div className="section-heading-row evidence-page-heading">
        <div>
          <div className="section-label">EVIDENCE</div>
          <h2>Patient evidence</h2>
        </div>
        <button className="secondary-button" onClick={onAddDocument}>
          + Add Document
        </button>
      </div>

      {groups.length ? (
        groups.map((group) => <EvidenceGroup key={group.title} groupKey={group.key} {...group} />)
      ) : (
        <p className="evidence-empty">No patient evidence is available.</p>
      )}
    </section>
  );
}

function EvidenceGroup({
  groupKey,
  title,
  items = [],
  getKey,
  getDate,
  renderItem,
  renderMeta,
}) {
  return (
    <section className={`evidence-group evidence-group-${groupKey}`}>
      <header className="evidence-group-heading">
        <h3>{title}</h3>
      </header>

      <div className="evidence-record-list">
          {items.map((item, index) => {
            const date = getDate?.(item);
            const meta = renderMeta?.(item);
            const key = getKey?.(item) || item?.id || index;
            const source = item?.provenance?.source;

            return (
              <article className="evidence-record-row" key={key}>
                <strong>{renderItem(item)}</strong>
                {meta && <span>{meta}</span>}
                {(date || source) && <small>{formatEvidenceMeta(date && formatDateTime(date), source && `Source: ${source}`)}</small>}
              </article>
            );
          })}
      </div>
    </section>
  );
}

function DocumentUploadModal({



  patientId,



  onClose,



  onUploaded,



}) {



  const [file, setFile] = useState(null);



  const [documentType, setDocumentType] =



    useState("Clinical Note");



  const [title, setTitle] = useState("");



  const [busy, setBusy] = useState(false);



  const [error, setError] = useState("");





  async function handleSubmit(event) {



    event.preventDefault();





    if (!file) {



      setError("Please select a document.");



      return;



    }

    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "docx", "txt"].includes(extension)) {
      setError("Unsupported file type. Choose a PDF, DOCX, or TXT file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The file is larger than the 10 MB upload limit.");
      return;
    }





    try {



      setBusy(true);



      setError("");





      await uploadPatientDocument({



        patientId,



        file,



        documentType,



        title:



          title.trim() ||



          file.name,



      });





      onUploaded();



    } catch (err) {



      setError(



        err?.message ||



        "Document upload failed."



      );



    } finally {



      setBusy(false);



    }



  }





  return (



    <div



      className="modal-backdrop"



      onMouseDown={(event) => {



        if (



          event.target === event.currentTarget



        ) {



          onClose();



        }



      }}



    >



      <div className="document-modal">



        <div className="modal-header">



          <div>



            <div className="section-label">



              PATIENT DOCUMENT



            </div>





            <h2>Add Patient Document</h2>



          </div>





          <button



            className="modal-close"



            onClick={onClose}



            type="button"



          >



            ×



          </button>



        </div>





        <p className="section-description">



          Add a clinical document that SIGNAL can



          evaluate during detection.



        </p>





        <form onSubmit={handleSubmit}>



          <label className="field-label">



            Document



          </label>





          <label className="upload-zone">



            <input



              type="file"



              accept=".pdf,.docx,.txt"



              onChange={(event) =>



                setFile(



                  event.target.files?.[0] ||



                  null



                )



              }



            />





            <span className="upload-title">



              {file



                ? file.name



                : "Browse Files"}



            </span>





            <span className="upload-subtitle">



              PDF · DOCX · TXT · max 10 MB



            </span>



          </label>





          <label className="field-label">



            Document type



          </label>





          <select



            className="form-control"



            value={documentType}



            onChange={(event) =>



              setDocumentType(



                event.target.value



              )



            }



          >



            <option>



              Clinical Note



            </option>



            <option>



              Discharge Summary



            </option>



            <option>



              Laboratory Report



            </option>



            <option>



              Referral



            </option>



            <option>



              Other



            </option>



          </select>





          <label className="field-label">



            Title



          </label>





          <input



            className="form-control"



            value={title}



            onChange={(event) =>



              setTitle(event.target.value)



            }



            placeholder="Document title"



          />





          {error && (



            <div className="error-message">



              {error}



            </div>



          )}





          <div className="modal-actions">



            <button



              type="button"



              className="secondary-button"



              onClick={onClose}



              disabled={busy}



            >



              Cancel



            </button>





            <button



              type="submit"



              className="primary-button"



              disabled={busy}



            >



              {busy



                ? "Uploading..."



                : "Add Document"}



            </button>



          </div>



        </form>



      </div>



    </div>



  );



}



export default function PatientWorkspace() {



  const { patientId } = useParams();
  const navigate = useNavigate();

  const [consentCheckPatientId, setConsentCheckPatientId] = useState(null);
  const [consentedPatientId, setConsentedPatientId] = useState(null);
  const [showMeaslesWarning, setShowMeaslesWarning] = useState(false);













  const [context, setContext] =



    useState(null);





  const [auditEvents, setAuditEvents] =



    useState([]);





  const [loading, setLoading] =



    useState(true);





  const [refreshing, setRefreshing] =



    useState(false);





  const [error, setError] =



    useState("");





  const [activeTab, setActiveTab] =



    useState("overview");





  const [detectionState, setDetectionState] =



    useState("idle");





  const [detectionStage, setDetectionStage] =



    useState(0);





  const detectionProgressRef = useRef(null);

  const [detectionResult, setDetectionResult] =



    useState(null);





  const [detectionError, setDetectionError] =



    useState("");





  const [showDocumentModal, setShowDocumentModal] =



    useState(false);

  const [removingDocumentId, setRemovingDocumentId] = useState(null);
  const [documentActionError, setDocumentActionError] = useState("");





  const conditions = useMemo(



    () => getConditions(context),



    [context]



  );





  const hasMeasles = conditions.some(isMeaslesCondition);
  const consentChecked = consentCheckPatientId === patientId;
  const consentAcknowledged = consentedPatientId === patientId;

  useEffect(() => {
    if (!patientId || !hasMeasles || consentAcknowledged) return undefined;

    const timer = window.setTimeout(() => {
      setShowMeaslesWarning(true);
    }, 5000);

    return () => window.clearTimeout(timer);
  }, [patientId, hasMeasles, consentAcknowledged]);

  const labs = useMemo(



    () => getLabs(context),



    [context]



  );





  const encounters = useMemo(



    () => getEncounters(context),



    [context]



  );





  const observations = useMemo(



    () => getObservations(context),



    [context]



  );





  const documents = useMemo(



    () => getDocuments(context),



    [context]



  );





  async function loadWorkspace(showSpinner = true) {



    if (showSpinner) {



      setLoading(true);



    }





    setError("");





    try {



      const [patientContext, events] = await Promise.all([
        getCanonicalPatient(patientId),
        listAuditEvents("PATIENT", patientId),
      ]);

      setContext(patientContext);











      setAuditEvents(events || []);



    } catch (err) {



      setError(



        err?.message ||



        "Unable to load patient workspace."



      );



    } finally {



      setLoading(false);



      setRefreshing(false);



    }



  }

  useEffect(() => {
    if (!patientId) return;

    setDetectionResult(null);
    setDetectionState("idle");
    setDetectionError("");
    loadWorkspace();
  }, [patientId]);

  useEffect(() => {
    setShowMeaslesWarning(false);

    if (!patientId || !hasMeasles) return undefined;

    const warningTimer = window.setTimeout(() => {
      setShowMeaslesWarning(true);
    }, 5000);

    return () => window.clearTimeout(warningTimer);
  }, [patientId, hasMeasles]);

  useEffect(() => {
    if (detectionState === "running") {
      detectionProgressRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [detectionState]);





  function handleRefresh() {



    setRefreshing(true);



    loadWorkspace(false);



  }



  async function handleDetection() {



    if (



      detectionState === "running" ||



      !patientId



    ) {



      return;



    }





    setDetectionState("running");



    setDetectionStage(0);



    setDetectionResult(null);



    setDetectionError("");





    /*



     * Presentation-only stage progression.



     *



     * There is still ONLY ONE backend API request.



     * These stages do not represent real-time backend events.



     */



    let stageTimer;
    const progressAnimation = new Promise((resolve) => {
      let nextStage = 0;
      stageTimer = setInterval(() => {
        nextStage += 1;
        setDetectionStage(nextStage);
        if (nextStage >= 3) {
          clearInterval(stageTimer);
          resolve();
        }
      }, 650);
    });

    try {
      const [result] = await Promise.all([
        detectCandidates(patientId),
        progressAnimation,
      ]);

      clearInterval(stageTimer);
      setDetectionStage(4);
      await new Promise((resolve) => setTimeout(resolve, 650));
      setDetectionResult(result);
      setDetectionState("completed");
    } catch (err) {
      clearInterval(stageTimer);
      setDetectionError(err?.message || "Detection failed.");
      setDetectionState("error");
    }
  }

  async function handleDocumentUploaded() {



    setShowDocumentModal(false);





    /*



     * Detection result is transient.



     * New document means the old result should not



     * remain visible as though it included the document.



     */



    setDetectionResult(null);



    setDetectionState("idle");



    setDetectionStage(0);





    await loadWorkspace(false);



  }

  async function handleRemoveDocument(document) {
    const documentId = document?.document_id ?? document?.id;
    if (!documentId || removingDocumentId) return;

    setRemovingDocumentId(documentId);
    setDocumentActionError("");
    try {
      await deletePatientDocument({ patientId, documentId });
      setDetectionResult(null);
      setDetectionState("idle");
      setDetectionStage(0);
      await loadWorkspace(false);
    } catch (err) {
      setDocumentActionError(err?.message || "Unable to remove the uploaded document.");
    } finally {
      setRemovingDocumentId(null);
    }
  }





  async function handleReviewCandidate(candidate) {
    setDetectionError("");
    try {
      let candidateId = candidate?.candidate_id || candidate?.id;
      let caseId = candidate?.case_id || candidate?.case?.case_id || candidate?.case?.id;

      if (!candidateId && candidate?.disease_id) {
        const persisted = await persistDetectedCandidate(patientId, candidate);
        candidateId = persisted?.candidate_id;
        caseId = persisted?.case_id || caseId;
      }
      if (!candidateId) {
        throw new Error("This patient detection has no record ID. Run detection again before continuing.");
      }

      if (!caseId) {
        const candidateResponse = await getCandidate(candidateId);
        const candidateRecord = candidateResponse?.data || candidateResponse;
        if (String(candidateRecord?.patient_id) !== String(patientId)) {
          throw new Error("This patient record does not match the current workspace.");
        }
        caseId = candidateRecord?.case_id || candidateRecord?.case?.case_id;
      }
      if (!caseId) {
        const processResponse = await processCandidate(candidateId);
        const processed = processResponse?.data || processResponse;
        caseId = processed?.case?.case_id || processed?.case?.id || processed?.case_id;
      }
      if (!caseId) {
        throw new Error("SIGNAL could not create a case for this patient.");
      }

      const caseResponse = await getCase(caseId);
      const caseRecord = caseResponse?.data || caseResponse;
      const casePatientId = caseRecord?.patient?.patient_id || caseRecord?.patient_id;
      if (casePatientId && String(casePatientId) !== String(patientId)) {
        throw new Error("This case does not belong to the current patient.");
      }

      const storedUser = sessionStorage.getItem("signal-user") || localStorage.getItem("signal-user");
      let actorId = "reporting_user";
      if (storedUser) {
        try {
          const user = JSON.parse(storedUser);
          actorId = user?.email || user?.name || actorId;
        } catch {
          // Keep a valid fallback actor if stored session data is malformed.
        }
      }

      try {
        await auditEvent({
          entity_type: "PATIENT",
          entity_id: String(patientId),
          event_type: "CANDIDATE_REVIEW_STARTED",
          actor_type: "USER",
          actor_id: actorId,
          source_agent: "patient_workspace",
          status: "STARTED",
          description: "Reviewer continued a detected candidate to reporting.",
          new_value: { disease: getCandidateConditionName(candidate), case_id: String(caseId) },
          metadata: { patient_id: String(patientId), case_id: String(caseId) },
        });
        const events = await listAuditEvents("PATIENT", patientId);
        setAuditEvents(events || []);
      } catch (auditError) {
        console.warn("Unable to record candidate review event", auditError);
      }

      navigate(`/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(caseId)}/reporting-form`);
    } catch (err) {
      console.error("Unable to continue to reporting", err);
      setDetectionError(err?.message || "Unable to continue to reporting.");
    }
  }
  if (loading) {



    return (



      <main className="patient-workspace-page">



        <div className="workspace-loading">



          Loading patient workspace...



        </div>



      </main>



    );



  }





  if (error) {



    return (



      <main className="patient-workspace-page">



        <div className="workspace-error">



          <h2>Unable to load patient</h2>



          <p>{error}</p>





          <button



            className="primary-button"



            onClick={() =>



              loadWorkspace()



            }



          >



            Try Again



          </button>



        </div>



      </main>



    );



  }





  return (



    <main className="patient-workspace-page">



      <PatientHeader



        patient={context}



        onRefresh={handleRefresh}



        refreshing={refreshing}



      />





      {hasMeasles && showMeaslesWarning && !consentAcknowledged && (
        <div className="measles-consent-backdrop">
          <section
            className="measles-consent-gate"
            role="dialog"
            aria-modal="true"
            aria-labelledby="measles-consent-title"
          >
            <section className="measles-reporting-warning" role="alert">
              <div className="measles-warning-heading">
                <span aria-hidden="true">!</span>
                <div>
                  <p className="section-label">TEXAS MEASLES REPORTING</p>
                  <h2>Suspected measles must be reported immediately</h2>
                </div>
              </div>
              <p>
                Texas requires suspected measles cases to be reported right away.
                Do not wait for laboratory confirmation. Please call the Texas
                DSHS reporting line yourself; SIGNAL will not call the patient
                or place the report for you.
              </p>
              <p className="measles-reporting-number">
                Texas DSHS reporting line: <strong>1-800-705-8868</strong>
              </p>
            </section>
            <h2 id="measles-consent-title">Consent is required to continue</h2>
            <p>
              Confirm that the patient or their authorized representative has
              consented to continue in this workspace.
            </p>
            <label className="measles-consent-check">
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(event) =>
                  setConsentCheckPatientId(
                    event.target.checked ? patientId : null
                  )
                }
              />
              <span>Patient consent to continue has been provided.</span>
            </label>
            <button
              type="button"
              className="primary-button"
              disabled={!consentChecked}
              onClick={() => setConsentedPatientId(patientId)}
            >
              Continue to patient workspace
            </button>
          </section>
        </div>
      )}

      <div
        className="workspace-gated-content"
        inert={hasMeasles && showMeaslesWarning && !consentAcknowledged}
      >
        <div className="workspace-tabs">



          <button



            className={



              activeTab === "overview"



                ? "workspace-tab active"



                : "workspace-tab"



            }



            onClick={() =>



              setActiveTab("overview")



            }



          >



            Overview



          </button>





          <button



            className={



              activeTab === "encounters"



                ? "workspace-tab active"



                : "workspace-tab"



            }



            onClick={() =>



              setActiveTab("encounters")



            }



          >



            Encounters



          </button>





          <button



            className={



              activeTab === "evidence"



                ? "workspace-tab active"



                : "workspace-tab"



            }



            onClick={() =>



              setActiveTab("evidence")



            }



          >



            Evidence



          </button>









        </div>





        {activeTab === "overview" && (



          <div className="workspace-content">

            {detectionState !== "completed" && !showDocumentModal && (
              <AiDocumentUploadCard
                documents={documents}
                onUpload={() => setShowDocumentModal(true)}
                onRemove={handleRemoveDocument}
                removingDocumentId={removingDocumentId}
                actionError={documentActionError}
                disabled={detectionState === "running" || Boolean(removingDocumentId)}
              />
            )}

            {detectionState === "idle" && (



              <section className="detection-start-panel">



                <div className="section-label">



                  SIGNAL DETECTION



                </div>





                <h2>



                  Identify potential reportable conditions



                </h2>





                <p className="section-description">SIGNAL will review the patient's structured clinical records and available documents to identify potential conditions that may require further review.</p>











                <button



                  className="primary-button"



                  onClick={handleDetection}



                >



                  Run Detection



                </button>



              </section>



            )}





            {detectionState === "running" && (



              <div ref={detectionProgressRef}>
                <DetectionProgress



                  activeStage={



                    detectionStage



                  }



                />
              </div>



            )}





            {detectionState === "error" && (



              <section className="detection-error-panel">



                <div className="section-label">



                  DETECTION ERROR



                </div>





                <h2>



                  Detection could not be completed



                </h2>





                <p>



                  {detectionError}



                </p>





                <button



                  className="primary-button"



                  onClick={handleDetection}



                >



                  Run Detection Again



                </button>



              </section>



            )}





            {detectionState === "completed" && detectionResult && (
              <>
                {detectionResult.document_evidence_status === "failed" && (
                  <section className="document-ai-warning" role="status">
                    <strong>AI processing could not be performed</strong>
                    <p>
                      {detectionResult.document_evidence_error ||
                        "Both AI models are unavailable. Your uploaded documents are saved, and structured record detection may still complete."}
                    </p>
                    {detectionResult.diagnostics?.run_id && (
                      <p>
                        Backend log reference: <code>{detectionResult.diagnostics.run_id}</code>
                      </p>
                    )}
                  </section>
                )}
                {Array.isArray(detectionResult?.candidates) && detectionResult.candidates.length > 0 ? (
                  detectionResult.candidates.length === 1 ? (
                    <DetectionCandidate
                      candidate={detectionResult.candidates[0]}
                      onContinue={handleReviewCandidate}
                      onRunAgain={handleDetection}
                    />
                  ) : (
                    <section className="candidate-section">
                      <div className="section-label">SIGNAL DETECTION</div>
                      <h2>Multiple potential reportable conditions identified</h2>
                      <p className="section-description">
                        Review each condition and its supporting evidence before continuing.
                      </p>
                      {detectionResult.candidates.map((candidate, index) => (
                        <div key={candidate?.candidate_id || candidate?.id || index}>
                          <DetectionCandidate
                            candidate={candidate}
                            onContinue={handleReviewCandidate}
                            onRunAgain={handleDetection}
                          />
                        </div>
                      ))}
                    </section>
                  )
                ) : (
                  <section className="no-candidate-panel">
                    <div className="section-label">DETECTION COMPLETE</div>
                    <h2>No potential reportable condition identified</h2>
                    <p>
                      No configured public health reporting trigger matched the available patient evidence.
                      A condition may still need review if its diagnosis or test result is missing from the record.
                    </p>
                  </section>
                )}
              </>
            )}

            {detectionState !== "completed" && (
              <RecordSummary



              patient={context}



              conditions={conditions}



              labs={labs}



              encounters={encounters}

              observations={observations}

              documents={documents}



              />
            )}

            {detectionState !== "completed" && (
              <DocumentsSection



              documents={documents}



              onAddDocument={() =>



                setShowDocumentModal(true)



              }



              />
            )}

          </div>



        )}





        {activeTab === "encounters" && (



          <div className="workspace-content">



            <EncountersTab



              encounters={encounters}



            />



          </div>



        )}





        {activeTab === "evidence" && (



          <div className="workspace-content">



            <EvidenceTab



              conditions={conditions}



              labs={labs}



              observations={observations}



              documents={documents}



              onAddDocument={() =>



                setShowDocumentModal(true)



              }



            />



          </div>



        )}





        {showDocumentModal && (



          <DocumentUploadModal



            patientId={patientId}



            onClose={() =>



              setShowDocumentModal(false)



            }



            onUploaded={



              handleDocumentUploaded



            }



          />



        )}

      </div>







    </main>



  );



}
