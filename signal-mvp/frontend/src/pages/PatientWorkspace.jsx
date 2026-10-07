import { useEffect, useMemo, useRef, useState } from "react";



import { Link, useParams } from "react-router-dom";



import { getCanonicalPatient } from "../api/canonical.js";






import { detectPatientCandidates as detectCandidates } from "../api/detection.js";



import {



  auditEvent,



  listAuditEvents,



} from "../api/workflow.js";





import { uploadPatientDocument } from "../api/documents.js";





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





function getDocuments(context) {



  return (



    context?.clinical_documents ||



    context?.clinicalDocuments ||



    context?.documents ||



    []



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



  const name =

    patientData.name ||

    patientData.patient_name ||

    [firstName, lastName]

      .filter(Boolean)

      .join(" ") ||

    "Patient";



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



    title: "Candidate fusion",



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





function RecordSummary({
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





/* =========================================================



   Candidate Result



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
    signal.evidence && typeof signal.evidence === "object"
      ? signal.evidence
      : {};
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
    signal.trigger_type,
    nested.trigger_type,
    categoryHint,
  ]
    .filter(Boolean)
    .map((value) => normalizeText(value).replace(/[\s-]+/g, "_"));

  if (
    markers.some((value) =>
      /document|clinical_document|clinical_note|note/.test(value)
    )
  ) {
    return "document";
  }
  if (
    markers.some((value) =>
      /laboratory|lab_result|(^|_)lab($|_)|diagnostic|diagnostic_report/.test(value)
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

function getCategoryHint(key) {
  const normalized = normalizeText(key).replace(/[\s-]+/g, "_");
  if (/document|clinical_note|notes/.test(normalized)) return "document";
  if (/laboratory|lab_result|(^|_)lab($|_)/.test(normalized)) return "laboratory";
  if (/condition|clinical|diagnosis/.test(normalized)) return "condition";
  return "";
}

function collectCandidateEvidence(candidate) {
  const found = [];
  const roots = [
    candidate?.signals,
    candidate?.supporting_signals,
    candidate?.evidence,
  ];

  function visit(value, hint = "", depth = 0) {
    if (!value || depth > 8) return;
    if (Array.isArray(value)) {
      value.forEach((item) => visit(item, hint, depth + 1));
      return;
    }
    if (typeof value !== "object") return;

    const hasEvidenceFields = [
      "source",
      "source_type",
      "evidence_type",
      "resource_type",
      "type",
      "category",
      "trigger_type",
      "description",
      "display",
      "test",
      "test_name",
      "condition_name",
      "document_title",
      "source_id",
      "result",
      "conclusion",
      "observations",
    ].some((key) => Object.prototype.hasOwnProperty.call(value, key));

    if (hasEvidenceFields) {
      found.push({ item: value, categoryHint: hint });
      return;
    }

    Object.entries(value).forEach(([key, child]) => {
      visit(child, getCategoryHint(key) || hint, depth + 1);
    });
  }

  roots.forEach((root) => visit(root));
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
  const seenKeys = new Set();
  const seenDocumentIds = new Set();

  for (const { item: raw, categoryHint } of entries) {
    const category = getEvidenceCategory(raw, categoryHint);
    if (!category) continue;

    const data = getEvidenceData(raw);
    const sourceId = getEvidenceSourceId(raw);
    const canonicalRecords = getCanonicalEvidenceRecords(context, category);
    const name = getEvidenceName(raw, data, category);
    const sourceIdKey = normalizeText(sourceId);
    const match = canonicalRecords.find((record) => {
      const recordId = normalizeText(getCanonicalSourceId(record, category));
      if (sourceIdKey && recordId) return sourceIdKey === recordId;

      const recordName = normalizeText(getEvidenceName(record, record, category));
      return Boolean(name && recordName && normalizeText(name) === recordName);
    });
    const canonical = match || {};
    const canonicalId = getCanonicalSourceId(canonical, category);
    const identity = normalizeText(sourceId || canonicalId);
    const enrichedName =
      getEvidenceName(canonical, canonical, category) || name;

    const categoryTitle =
      category === "condition"
        ? "Condition evidence"
        : category === "laboratory"
          ? "Laboratory evidence"
          : "Document evidence";

    if (category === "condition") {
      const description = firstEvidenceValue(
        data?.description,
        raw?.description,
        enrichedName
      );
      const status = firstEvidenceValue(
        data?.clinical_status,
        data?.status,
        raw?.clinical_status,
        raw?.status,
        canonical?.clinical_status
      );
      const verification = firstEvidenceValue(
        data?.verification_status,
        data?.verification,
        raw?.verification_status,
        raw?.verification,
        canonical?.verification_status
      );
      const key = [
        "condition",
        identity,
        normalizeText(enrichedName),
        normalizeText(description),
        normalizeText(status),
        normalizeText(verification),
      ].join("|");
      if (seenKeys.has(key) || (identity && seenKeys.has("condition|id|" + identity))) continue;
      seenKeys.add(key);
      if (identity) seenKeys.add("condition|id|" + identity);
      normalized.push({
        category,
        title: categoryTitle,
        name: enrichedName,
        description,
        status,
        verification,
        sourceId: identity,
      });
      continue;
    }

    if (category === "laboratory") {
      const result = getLabResult(canonical, data, raw);
      const status = firstEvidenceValue(
        data?.report_status,
        data?.result_status,
        data?.status,
        raw?.report_status,
        raw?.result_status,
        raw?.status,
        canonical?.report_status,
        canonical?.result_status,
        canonical?.status
      );
      const key = [
        "laboratory",
        identity,
        normalizeText(enrichedName),
        normalizeText(result),
        normalizeText(status),
      ].join("|");
      if (seenKeys.has(key) || (identity && seenKeys.has("laboratory|id|" + identity))) continue;
      seenKeys.add(key);
      if (identity) seenKeys.add("laboratory|id|" + identity);
      normalized.push({
        category,
        title: categoryTitle,
        name: enrichedName,
        description: firstEvidenceValue(
          data?.description,
          raw?.description,
          enrichedName
        ),
        result,
        status,
        sourceId: identity,
      });
      continue;
    }

    const documentId = identity;
    if (documentId && seenDocumentIds.has(documentId)) continue;
    const documentSource = {
      ...canonical,
      ...data,
      title:
        canonical?.title ||
        data?.title ||
        data?.document_title ||
        raw?.document_title ||
        data?.source_title ||
        raw?.source_title,
      extracted_text:
        canonical?.extracted_text ||
        data?.extracted_text ||
        data?.extractedText ||
        data?.text ||
        data?.evidence_text ||
        raw?.evidence_text,
    };
    const representedBeforeDocument = normalized.filter(
      (entry) => entry.category !== "document"
    );
    const description = getDocumentExcerpt(
      documentSource,
      representedBeforeDocument
    );
    const evidenceType = normalizeText(
      data?.evidence_type || raw?.evidence_type
    );
    if (
      !description &&
      /laboratory|lab_result/.test(evidenceType) &&
      representedBeforeDocument.some(
        (entry) => entry.category === "laboratory"
      )
    ) {
      continue;
    }

    const documentName =
      getEvidenceName(documentSource, documentSource, category) ||
      enrichedName;
    const key = [
      "document",
      documentId,
      normalizeText(documentName),
      normalizeText(description),
    ].join("|");
    if (seenKeys.has(key)) continue;
    seenKeys.add(key);
    if (documentId) seenDocumentIds.add(documentId);
    normalized.push({
      category,
      title: categoryTitle,
      name: documentName,
      description,
      sourceId: documentId,
    });
  }

  return normalized.filter((item) => item.name || item.description);
}

function CandidateCard({ candidate, evidence = [] }) {

  const name = displayClinicalValue(getCandidateName(candidate), "Potential condition").replaceAll("_", " ");









  const confidence =



    candidate?.confidence ??



    candidate?.score;





  const encounter =



    candidate?.encounter_id ||



    candidate?.encounter?.id;





  return (



    <section className="candidate-section">



      <div className="section-label">



        SIGNAL DETECTION



      </div>





      <div className="candidate-heading">



        <div>



          <h2>Potential condition identified</h2>





          <p className="section-description">{"SIGNAL identified a potential " + safeText(name, "condition") + " candidate based on supporting clinical evidence."}</p>



        </div>





        <span className="potential-badge">



          Potential &middot; Requires Review



        </span>



      </div>





      <div className="candidate-card">



        <div className="candidate-card-header">



          <div>



            <div className="candidate-disease">



              {safeText(name).toUpperCase()}



            </div>





            <div className="candidate-status">



              Potential &middot; Requires Review



            </div>



          </div>





          <span className="potential-badge">



            {safeText(



              candidate?.status,



              "POTENTIAL"



            ).toUpperCase()}



          </span>



        </div>





        <div className="candidate-details">



          <div>



            <span>Evidence items</span>



            <strong>{evidence.length}</strong>



          </div>





          <div>



            <span>Encounter</span>



            <strong>



              {safeText(encounter)}



            </strong>



          </div>





          {confidence !== undefined && (



            <div>



              <span>Confidence</span>



              <strong>



                {typeof confidence === "number"



                  ? `${Math.round(



                    confidence <= 1



                      ? confidence * 100



                      : confidence



                  )}%`



                  : safeText(confidence)}



              </strong>



            </div>



          )}



        </div>




        <div className="candidate-evidence-section">
          <h4>Supporting evidence</h4>

          {evidence.length > 0 ? (
            <div className="candidate-evidence-list">
              {evidence.map((item, index) => (
                <div
                  className="candidate-evidence-item"
                  key={item.sourceId || [item.category, item.name, index].join("-")}
                >
                  <div className="candidate-evidence-icon">
                    {String.fromCharCode(0x2713)}
                  </div>

                  <div className="candidate-evidence-content">
                    <div className="candidate-evidence-title">{item.title}</div>
                    {item.name && (
                      <div className="candidate-evidence-description">
                        {item.name}
                      </div>
                    )}
                    {item.description && item.description !== item.name && (
                      <div className="candidate-evidence-meta">
                        {item.description}
                      </div>
                    )}
                    {item.result && (
                      <div className="candidate-evidence-meta">
                        Result: <strong>{item.result}</strong>
                      </div>
                    )}
                    {(item.status || item.verification) && (
                      <div className="candidate-evidence-meta">
                        {item.status && (
                          <>
                            Status: <strong>{displayClinicalValue(item.status)}</strong>
                          </>
                        )}
                        {item.status && item.verification && String.fromCharCode(0x00b7)}
                        {item.verification && (
                          <>
                            Verification:{" "}
                            <strong>{displayClinicalValue(item.verification)}</strong>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="candidate-evidence-empty">
              No supporting evidence available.
            </div>
          )}
        </div>





      </div>



    </section>



  );



}





/* =========================================================



   Why Flagged



\========================================================= */





function DetectionExplanation({ evidence = [] }) {
  const categories = ["condition", "laboratory", "document"];
  const categoryTitles = {
    condition: "CONDITION",
    laboratory: "LABORATORY",
    document: "DOCUMENT",
  };
  const cards = categories.map((category) => {
    const categoryEvidence = evidence.filter(
      (item) => item.category === category
    );
    const value = categoryEvidence
      .map((item) => [item.name, item.result, item.description]
        .filter(Boolean)
        .filter((text, index, all) => all.indexOf(text) === index)
        .join(" | "))
      .filter(Boolean)
      .join(" | ");

    return {
      key: category,
      title: categoryTitles[category],
      value: value || "No " + category + " evidence",
    };
  });

  return (



    <section className="explanation-section">



      <div className="section-label">



        WHY WAS THIS FLAGGED?



      </div>





      <h2>Supporting clinical evidence</h2>





      <p className="section-description">



        SIGNAL found supporting evidence from the



        patient's available records.



      </p>





      <div className="explanation-grid">



        {cards.map((card) => (



          <div



            className="explanation-card"



            key={card.key}



          >



            <div className="explanation-card-label">



              {card.title}



            </div>





            <div className="explanation-card-value">



              {card.value}



            </div>





            {card.value !==



              "No condition evidence" &&



              card.value !==



              "No laboratory evidence" &&



              card.value !==



              "No document evidence" && (



                <div className="evidence-supported">



                  ✓ Supporting signal



                </div>



              )}



          </div>



        ))}



      </div>



    </section>



  );



}





/* =========================================================



   Next Action



\========================================================= */





function EncountersTab({ encounters }) {



  if (!encounters.length) {



    return (



      <div className="empty-state">



        No encounter records are available.



      </div>



    );



  }





  return (



    <section className="tab-section">



      <div className="section-label">



        ENCOUNTERS



      </div>





      <h2>Patient encounters</h2>





      <div className="encounter-list">



        {encounters.map((encounter, index) => {



          const facility =



            encounter?.facility_name ||



            encounter?.facility?.name ||



            encounter?.facility;





          const date =



            encounter?.date ||



            encounter?.start ||



            encounter?.period?.start ||



            encounter?.encounter_date;





          return (



            <div



              className="encounter-card"



              key={



                encounter?.id ||



                encounter?.encounter_id ||



                index



              }



            >



              <div className="encounter-date">



                {formatDateTime(date)}



              </div>





              <div className="encounter-main">



                <strong>



                  {safeText(



                    encounter?.type ||



                    encounter?.encounter_type,



                    "Encounter"



                  )}



                </strong>





                <span>



                  Facility:{" "}



                  {safeText(



                    facility,



                    "Not available"



                  )}



                </span>





                <span>



                  Provider:{" "}



                  {safeText(



                    encounter?.provider_name ||



                    encounter?.provider?.name,



                    "Not available"



                  )}



                </span>



              </div>





              <span className="status-badge">



                {safeText(



                  encounter?.status,



                  "unknown"



                )}



              </span>



            </div>



          );



        })}



      </div>



    </section>



  );



}





/* =========================================================



   Evidence



\========================================================= */





function EvidenceTab({



  conditions,



  labs,



  observations,



  documents,



  onAddDocument,



}) {



  return (



    <section className="tab-section">



      <div className="section-heading-row">



        <div>



          <div className="section-label">



            EVIDENCE



          </div>





          <h2>Source records</h2>





          <p className="section-description">



            Source-record evidence available for this



            patient.



          </p>



        </div>





        <button



          className="secondary-button"



          onClick={onAddDocument}



        >



          + Add Document



        </button>



      </div>





      <EvidenceGroup



        title="Conditions"



        items={conditions}



        renderItem={(item) =>



          item?.display ||



          item?.name ||



          item?.condition ||



          item?.code?.text ||



          "Condition"



        }



      />





      <EvidenceGroup



        title="Laboratory Results"



        items={labs}



        renderItem={(item) =>



          item?.test_name ||



          item?.name ||



          item?.display ||



          item?.code?.text ||



          "Laboratory result"



        }



        renderMeta={(item) => {



          const value =



            item?.value ??



            item?.result ??



            item?.interpretation;





          if (



            value &&



            typeof value === "object"



          ) {



            return (



              value.text ||



              value.display ||



              value.value ||



              value.code ||



              "Available"



            );



          }





          return safeText(value, "");



        }}



      />





      <EvidenceGroup



        title="Observations"



        items={observations}



        renderItem={(item) =>



          item?.name ||



          item?.display ||



          item?.code?.text ||



          "Observation"



        }



      />





      <div className="evidence-group">



        <div className="evidence-group-heading">



          <h3>Documents</h3>





          <button



            className="text-button"



            onClick={onAddDocument}



          >



            + Add Document



          </button>



        </div>





        {!documents.length ? (



          <div className="empty-state compact">



            No clinical documents uploaded.



          </div>



        ) : (



          documents.map((document, index) => (



            <div



              className="source-record"



              key={



                document?.id ||



                document?.document_id ||



                index



              }



            >



              <strong>



                {safeText(



                  document?.title ||



                  document?.file_name ||



                  document?.name,



                  "Clinical Document"



                )}



              </strong>





              <span>



                {safeText(



                  document?.document_type ||



                  document?.type,



                  "Clinical document"



                )}



              </span>





              <small>



                {document?.created_at



                  ? `Uploaded ${formatDate(



                    document.created_at



                  )}`



                  : "Available for detection"}



              </small>



            </div>



          ))



        )}



      </div>



    </section>



  );



}





function EvidenceGroup({



  title,



  items,



  renderItem,



  renderMeta,



}) {



  return (



    <div className="evidence-group">



      <h3>{title}</h3>





      {!items.length ? (



        <div className="empty-state compact">



          No {title.toLowerCase()} available.



        </div>



      ) : (



        items.map((item, index) => (



          <div



            className="source-record"



            key={item?.id || index}



          >



            <strong>



              {renderItem(item)}



            </strong>





            {renderMeta && (



              <span>



                {renderMeta(item)}



              </span>



            )}





            <small>



              {item?.date



                ? formatDate(item.date)



                : item?.recorded_date



                  ? formatDate(



                    item.recorded_date



                  )



                  : ""}



            </small>



          </div>



        ))



      )}



    </div>



  );



}





/* =========================================================



   Document Modal



\========================================================= */





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



              accept=".pdf,.doc,.docx,.txt"



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



              PDF · DOC · DOCX · TXT



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





  const conditions = useMemo(



    () => getConditions(context),



    [context]



  );





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

    loadWorkspace();
  }, [patientId]);

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





  async function handleReviewCandidate(candidate) {



    /*



     * Keep this as the transition into the Review stage.



     * Do not automatically create a case.



     *



     * If your existing application already has a review



     * route/action, connect it here.



     */



    try {



      await auditEvent({



        entity_type: "PATIENT",



        event_type: "CANDIDATE_REVIEW_STARTED",



        status: "STARTED",



        new_value: {



          disease:



            candidate?.disease ||



            candidate?.condition ||



            candidate?.condition_name ||



            "unknown",



        },



        metadata: {



          patient_id: patientId,



        },



      });





      const events =



        await listAuditEvents(



          "PATIENT",



          patientId



        );





      setAuditEvents(events || []);



    } catch (err) {



      console.error(



        "Unable to record review event",



        err



      );



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





          {detectionState === "completed" &&



            detectionResult && (



              <>



                <div className="detection-completed-strip">



                  <div>



                    <span className="completed-icon">



                      ✓



                    </span>





                    <div>



                      <strong>



                        Detection completed



                      </strong>





                      <span>



                        Detection results are ready for review.



                      </span>



                    </div>



                  </div>





                  <button



                    className="secondary-button"



                    onClick={handleDetection}



                  >



                    Run Again



                  </button>



                </div>





                {Array.isArray(



                  detectionResult?.candidates



                ) &&



                  detectionResult.candidates



                    .length > 0 ? (



                  <>



                    {detectionResult.candidates.map((candidate, index) => {
                      const candidateEvidence = normalizeCandidateEvidence(
                        candidate,
                        context
                      );
                      return (
                        <div
                          key={
                            candidate?.id ||
                            candidate?.candidate_id ||
                            index
                          }
                        >
                          <CandidateCard
                            candidate={candidate}
                            evidence={candidateEvidence}
                            onReview={handleReviewCandidate}
                          />
                          <DetectionExplanation evidence={candidateEvidence} />




                        </div>



                      );



                    })}



                  </>



                ) : (



                  <section className="no-candidate-panel">



                    <div className="section-label">



                      DETECTION COMPLETE



                    </div>





                    <h2>



                      No potential candidates



                      identified



                    </h2>





                    <p>



                      No candidate was returned



                      from the available patient



                      evidence.



                    </p>



                  </section>



                )}



              </>



            )}



          <RecordSummary



            conditions={conditions}



            labs={labs}



            encounters={encounters}

            observations={observations}

            documents={documents}



          />





          <DocumentsSection



            documents={documents}



            onAddDocument={() =>



              setShowDocumentModal(true)



            }



          />





          {detectionState === "completed" &&
            Array.isArray(detectionResult?.candidates) &&
            detectionResult.candidates.length > 0 && (
              <div className="continue-reporting-actions">
                {detectionResult.candidates.map((candidate, index) => (
                  <button
                    key={candidate?.candidate_id || candidate?.id || index}
                    type="button"
                    className="primary-button"
                    aria-label={"Continue reporting for " + getCandidateName(candidate)}
                    onClick={() => handleReviewCandidate(candidate)}
                  >
                    Continue Reporting
                  </button>
                ))}
              </div>
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







    </main>



  );



}
