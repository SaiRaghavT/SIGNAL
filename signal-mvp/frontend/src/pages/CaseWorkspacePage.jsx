import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  getCase,
  getCaseJourney,
  getCaseTimeline,
  updateCaseReportFields,
} from "../api/cases.js";

import {
  attestCase,
  getCaseValidation,
  getCaseAttestation,
  getCaseReview,
  queueCase,
  reviewCase,
  updateCaseReview,
  validateCase,
  getImmediateNotification,
} from "../api/workflow.js";

import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import {
  CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT,
  getOpenClinicalInformationRequest,
  resolveClinicalInformationRequest,
} from "../utils/clinicalInformationRequests.js";
import "../styles/case-workspace.css";


/* =========================================================
   HELPERS
   ========================================================= */

const pretty = (value) => {
  if (value === null || value === undefined) return "Not available";

  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  return String(value);
};

const readable = (value) => {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  if (typeof value === "object") {
    return pretty(value);
  }

  return String(value);
};

const DEMO_REVIEW_SAMPLE = { patient: {}, reportFields: {} };

const hasValue = (value) =>
  value !== null &&
  value !== undefined &&
  value !== "";

const hasEvidence = (value) => {
  if (!hasValue(value)) return false;

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (typeof value === "object") {
    return Object.keys(value).length > 0;
  }

  return true;
};


function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}


function patientName(patient) {
  return (
    [
      patient?.first_name,
      patient?.last_name,
    ]
      .filter(Boolean)
      .join(" ") ||
    patient?.name ||
    "Patient"
  );
}


function currentReviewer() {
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const raw = storage.getItem("signal-user");

      if (!raw) continue;

      const user = JSON.parse(raw);

      if (user) {
        return {
          id:
            user.email ||
            user.name ||
            "reporting_user",

          name:
            user.name ||
            "Reporting Staff",

          role: user.role === "Clinical Staff"
            ? "REPORTING_STAFF"
            : user.role || "REPORTING_STAFF",
        };
      }
    } catch {
      // Fall back to configured reporting user.
    }
  }

  return {
    id: "reporting_user",
    name: "Reporting Staff",
    role: "REPORTING_STAFF",
  };
}


/* =========================================================
   VALIDATION GROUPS
   ========================================================= */

const VALIDATION_GROUPS = [
  {
    key: "patient",
    label: "Patient & Administrative",
  },
  {
    key: "clinical",
    label: "Clinical Information",
  },
  {
    key: "laboratory",
    label: "Laboratory Information",
  },
  {
    key: "reporting",
    label: "Reporting Information",
  },
  {
    key: "jurisdiction",
    label: "Jurisdiction & Disease",
  },
];


/* =========================================================
   VALIDATION STATUS
   ========================================================= */

function getValidationStatus(validation) {
  if (!validation) {
    return "NOT_CHECKED";
  }

  if (
    validation.valid === true &&
    validation.ready_for_review === true &&
    validation.status !== "INVALID"
  ) {
    return "VALID";
  }

  if (
    validation.status === "INVALID" ||
    validation.valid === false
  ) {
    return "INVALID";
  }

  return "ATTENTION";
}


function getValidationCounts(validation) {
  const errors = Array.isArray(validation?.errors)
    ? validation.errors.length
    : 0;

  const warnings = Array.isArray(validation?.warnings)
    ? validation.warnings.length
    : 0;

  const missing =
    Array.isArray(validation?.missing_fields)
      ? validation.missing_fields.length
      : Array.isArray(validation?.completion_required)
        ? validation.completion_required.length
        : 0;

  const total =
    Number(
      validation?.validated_field_count ??
      validation?.valid_field_count ??
      validation?.validated_fields_count ??
      0
    ) || 0;

  const valid = Math.max(
    0,
    total - errors - missing
  );

  return {
    valid,
    attention: warnings + missing,
    blocking: errors,
    total,
  };
}


/* =========================================================
   FIELD GROUPING
   ========================================================= */

function getMissingFields(validation) {
  const values = [
    ...(Array.isArray(validation?.missing_fields)
      ? validation.missing_fields
      : []),

    ...(Array.isArray(validation?.completion_required)
      ? validation.completion_required
      : []),
  ];

  return [
    ...new Set(
      values
        .filter(Boolean)
        .map((item) => String(item))
    ),
  ];
}


function fieldGroup(field) {
  const prefix = String(field)
    .split(".")[0]
    .toLowerCase();

  if (prefix === "patient") {
    return "patient";
  }

  if (
    prefix === "clinical" ||
    prefix === "rash_fever"
  ) {
    return "clinical";
  }

  if (prefix === "laboratory") {
    return "laboratory";
  }

  if (
    prefix === "reporting" ||
    prefix === "provider" ||
    prefix === "facility"
  ) {
    return "reporting";
  }

  if (
    prefix === "jurisdiction" ||
    prefix === "disease"
  ) {
    return "jurisdiction";
  }

  return "reporting";
}


function validationGroupStatus(
  validation,
  groupKey,
  currentMissingFields = null
) {
  const hasCurrentCaseState = Array.isArray(currentMissingFields);
  const missingFields = hasCurrentCaseState
    ? currentMissingFields
    : getMissingFields(validation);

  const errors = !hasCurrentCaseState && Array.isArray(validation?.errors)
    ? validation.errors.map(String)
    : [];

  const relevantMissing = missingFields.filter(
    (field) => fieldGroup(field) === groupKey
  );

  const relevantErrors = errors.filter((item) => {
    const lower = item.toLowerCase();

    if (groupKey === "patient") {
      return (
        lower.includes("patient") ||
        lower.includes("dob") ||
        lower.includes("date of birth")
      );
    }

    if (groupKey === "clinical") {
      return (
        lower.includes("clinical") ||
        lower.includes("symptom") ||
        lower.includes("onset") ||
        lower.includes("rash") ||
        lower.includes("fever")
      );
    }

    if (groupKey === "laboratory") {
      return (
        lower.includes("laboratory") ||
        lower.includes("lab") ||
        lower.includes("test")
      );
    }

    if (groupKey === "reporting") {
      return (
        lower.includes("report") ||
        lower.includes("provider") ||
        lower.includes("facility")
      );
    }

    if (groupKey === "jurisdiction") {
      return (
        lower.includes("jurisdiction") ||
        lower.includes("disease") ||
        lower.includes("rule")
      );
    }

    return false;
  });

  if (
    relevantMissing.length > 0 ||
    relevantErrors.length > 0
  ) {
    return "ATTENTION";
  }

  if (
    hasCurrentCaseState ||
    validation?.status === "VALID" ||
    validation?.valid === true
  ) {
    return "COMPLETE";
  }

  return "NOT_CHECKED";
}


/* =========================================================
   COMPONENT
   ========================================================= */

export default function CaseWorkspacePage() {
  const { patientId: routePatientId = "", caseId = "" } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [journey, setJourney] = useState(null);
  const [validation, setValidation] = useState(null);
  const [review, setReview] = useState(null);
  const [attestation, setAttestation] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [notification, setNotification] = useState(null);
  const [adminInformationRequest, setAdminInformationRequest] = useState(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const demoReviewPreview = false;

  const [reviewDecision, setReviewDecision] =
    useState("APPROVE");

  const [reviewComments, setReviewComments] =
    useState("");

  const [attestationComments, setAttestationComments] =
    useState("");

  const [reviewChecked, setReviewChecked] =
    useState(false);

  const [refreshKey, setRefreshKey] =
    useState(0);

  useEffect(() => {
    const refreshInformationRequest = () => {
      setAdminInformationRequest(getOpenClinicalInformationRequest(caseId));
    };
    refreshInformationRequest();
    window.addEventListener(CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT, refreshInformationRequest);
    window.addEventListener("storage", refreshInformationRequest);
    return () => {
      window.removeEventListener(CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT, refreshInformationRequest);
      window.removeEventListener("storage", refreshInformationRequest);
    };
  }, [caseId]);

  function restoreSessionWorkflow(persistedReview, persistedAttestation) {
    setReview(persistedReview || null);
    setAttestation(persistedAttestation || null);
    setReviewDecision(persistedReview?.status === "DRAFT" ? persistedReview?.payload?.draft_decision || "APPROVE" : persistedReview?.status || "APPROVE");
    setReviewComments(persistedReview?.payload?.comments || "");
    setAttestationComments(persistedAttestation?.payload?.comments || "");
    setReviewChecked(Boolean(persistedReview?.payload?.review_confirmed || persistedReview?.status === "APPROVE"));
  }

  async function persistReviewDraft(changes = {}) {
    if (!caseId || demoReviewPreview) return;
    // Keep an approved review intact. Draft autosaves after approval are not
    // needed for the dispatch gate and older API processes may reject them.
    // A changed decision or comment is persisted by the explicit Save Review action.
    if (review?.status === "APPROVE") return;
    const reviewer = currentReviewer();
    const payload = {
      reviewer_id: reviewer.id,
      reviewer_role: reviewer.role,
      decision: "DRAFT",
      draft_decision: changes.reviewDecision || reviewDecision,
      comments: changes.reviewComments ?? reviewComments,
      review_confirmed: changes.reviewChecked ?? reviewChecked,
    };
    try {
      const saved = review
        ? await updateCaseReview(caseId, payload)
        : await reviewCase(caseId, payload);
      setReview(saved);
    } catch (requestError) {
      setError(requestError?.message || "Unable to save review details.");
    }
  }


  /* =======================================================
     LOAD DATA
     ======================================================= */

  const reload = useCallback(async () => {
    const [
      caseResponse,
      journeyResponse,
      validationResponse,
      timelineResponse,
      notificationResponse,
      reviewResponse,
      attestationResponse,
    ] = await Promise.all([
      getCase(caseId),
      getCaseJourney(caseId),
      getCaseValidation(caseId),
      getCaseTimeline(caseId),
      getImmediateNotification(caseId),
      getCaseReview(caseId),
      getCaseAttestation(caseId),
    ]);

    setData(caseResponse);
    setJourney(journeyResponse);
    setValidation(validationResponse);
    restoreSessionWorkflow(reviewResponse, attestationResponse);

    setTimeline(
      timelineResponse?.events || []
    );

    setNotification(
      notificationResponse || null
    );

  }, [caseId]);


  useEffect(() => {
    let active = true;

    async function initialize() {
      setLoading(true);
      setError("");

      try {
        const [
          caseResponse,
          journeyResponse,
          validationResponse,
          timelineResponse,
          notificationResponse,
          reviewResponse,
          attestationResponse,
        ] = await Promise.all([
          getCase(caseId),
          getCaseJourney(caseId),
          getCaseValidation(caseId),
          getCaseTimeline(caseId),
          getImmediateNotification(caseId),
          getCaseReview(caseId),
          getCaseAttestation(caseId),
        ]);

        if (!active) return;

        setData(caseResponse);
        setJourney(journeyResponse);
        setValidation(validationResponse);
        restoreSessionWorkflow(reviewResponse, attestationResponse);

        setTimeline(
          timelineResponse?.events || []
        );

        setNotification(
          notificationResponse || null
        );

      } catch (requestError) {
        if (active) {
          setError(
            requestError?.message ||
            "Unable to load the case."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    initialize();

    return () => {
      active = false;
    };
  }, [caseId, refreshKey]);


  /* =======================================================
     DERIVED DATA
     ======================================================= */

  const validationCounts = useMemo(
    () => demoReviewPreview
      ? {
          valid: Object.keys(DEMO_REVIEW_SAMPLE.reportFields).length,
          attention: 0,
          blocking: 0,
          total: Object.keys(DEMO_REVIEW_SAMPLE.reportFields).length,
        }
      : getValidationCounts(validation),
    [demoReviewPreview, validation]
  );

  const validationStatus = useMemo(
    () => demoReviewPreview ? "VALID" : getValidationStatus(validation),
    [demoReviewPreview, validation]
  );

  const missingFields = useMemo(
    () => demoReviewPreview ? [] : getMissingFields(validation),
    [demoReviewPreview, validation]
  );

  const reviewApproved = demoReviewPreview
    ? demoReviewConfirmed
    : review?.status === "APPROVE";

  const attested = demoReviewPreview
    ? demoAttestationConfirmed
    : attestation?.status === "ATTESTED";

  const readyForReview =
    demoReviewPreview ||
    validationStatus === "VALID" &&
    validation?.ready_for_review === true;

  const workflowConfirmed = reviewApproved && attested && reviewChecked;

  const canSubmitToQueue =
    readyForReview && workflowConfirmed;


  /* =======================================================
     CASE DATA
     ======================================================= */

  const patient = demoReviewPreview
    ? DEMO_REVIEW_SAMPLE.patient
    : data?.patient || {};
  const currentCaseMissingFields = demoReviewPreview
    ? []
    : Array.isArray(data?.required_missing_fields)
      ? [
          ...data.required_missing_fields,
          ...(data?.warnings || []).filter((warning) =>
            /^(Facility name|Provider information)/i.test(warning)
          ),
        ]
      : null;
  const reportFieldValue = (field) => {
    if (demoReviewPreview) {
      return DEMO_REVIEW_SAMPLE.reportFields[field] ?? "Not available";
    }
    const value = data?.report_fields?.[field];
    if (value === null || value === undefined || value === "") {
      return "Not available";
    }
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return readable(value);
  };

  const condition =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.condition) ||
    data?.disease ||
    data?.condition ||
    "Not available";

  const jurisdiction =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.jurisdiction) ||
    data?.jurisdiction ||
    data?.reporting_jurisdiction ||
    "Not available";

  const facility =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.facility) ||
    data?.facility?.name ||
    data?.facility?.facility_name ||
    data?.facility?.facility_id ||
    "Not available";

  const provider =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.provider) ||
    data?.provider?.name ||
    "Not available";

  const reportability =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.reportability) ||
    data?.final_decision ||
    data?.reportability_decision ||
    data?.reportability ||
    "Not available";

  const reportingRule =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.ruleId) ||
    data?.rule_id ||
    data?.reportability_rule ||
    data?.reporting_rule ||
    "Not available";

  const deadline =
    (demoReviewPreview && DEMO_REVIEW_SAMPLE.deadline) ||
    data?.deadline ||
    data?.reporting_deadline ||
    null;


  /* =======================================================
     REPORTING DATA
     ======================================================= */

  const reportingData = [
    {
      group: "Patient",
      groupKey: "patient",
      items: [
        ["Patient Name", reportFieldValue("patient.case_name")],
        ["Date of Birth", reportFieldValue("patient.date_of_birth")],
        ["Sex", reportFieldValue("patient.sex")],
        ["Address", reportFieldValue("patient.current_address")],
        ["City", reportFieldValue("patient.city")],
        ["County", reportFieldValue("patient.county")],
        ["ZIP Code", reportFieldValue("patient.zip")],
        ["Country of Residence", reportFieldValue("patient.country_of_residence")],
        ["Hispanic", reportFieldValue("patient.hispanic")],
        ["Race", reportFieldValue("patient.race")],
      ],
    },
    {
      group: "Clinical",
      groupKey: "clinical",
      items: [
        ["Hospitalized", reportFieldValue("clinical.hospitalized")],
        ["ICU Admission", reportFieldValue("clinical.icu_admission")],
        ["Admission Date", reportFieldValue("clinical.admission_date")],
        ["Discharge Date", reportFieldValue("clinical.discharge_date")],
        ["Hospital", reportFieldValue("clinical.hospital")],
        ["Illness Onset Date", reportFieldValue("clinical.illness_onset_date")],
        ["Diagnosis Date", reportFieldValue("clinical.diagnosis_date")],
        ["Diagnosis", reportFieldValue("clinical.diagnosis")],
        ["Confirmation Method", reportFieldValue("clinical.confirmation_method")],
      ],
    },
    {
      group: "Laboratory",
      groupKey: "laboratory",
      items: [
        ["IgM", reportFieldValue("laboratory.igm")],
        ["IgG", reportFieldValue("laboratory.igg")],
        ["PCR", reportFieldValue("laboratory.pcr")],
        ["Culture", reportFieldValue("laboratory.culture")],
      ],
    },
    {
      group: "Rash and Fever",
      groupKey: "clinical",
      items: [
        ["Rash", reportFieldValue("rash_fever.rash")],
        ["Rash Location", reportFieldValue("rash_fever.rash_location")],
        ["Rash Onset Date", reportFieldValue("rash_fever.rash_onset_date")],
        ["Rash Duration", reportFieldValue("rash_fever.rash_duration")],
        ["Fever", reportFieldValue("rash_fever.fever")],
        ["Fever Onset Date", reportFieldValue("rash_fever.fever_onset_date")],
        ["Highest Temperature", reportFieldValue("rash_fever.highest_temperature")],
        ["Cough", reportFieldValue("rash_fever.cough")],
        ["Coryza", reportFieldValue("rash_fever.coryza")],
        ["Conjunctivitis", reportFieldValue("rash_fever.conjunctivitis")],
        ["Koplik Spots", reportFieldValue("rash_fever.koplik_spots")],
      ],
    },
    {
      group: "Reporting",
      groupKey: "reporting",
      items: [
        ["Reporting Facility", facility],
        ["Reporting Provider", provider],
        ["Reported By", reportFieldValue("reporting.reported_by")],
        ["Reporting Agency", reportFieldValue("reporting.agency")],
        ["Reporting Email", reportFieldValue("reporting.email")],
        ["Reporting Phone", reportFieldValue("reporting.phone")],
        ["Earliest Date Reported", reportFieldValue("reporting.earliest_date_reported")],
        ["Investigated By", reportFieldValue("reporting.investigated_by")],
        ["Investigating Agency", reportFieldValue("reporting.investigating_agency")],
        ["Investigating Agency Email", reportFieldValue("reporting.investigating_agency_email")],
        ["Investigating Agency Phone", reportFieldValue("reporting.investigating_agency_phone")],
        ["Investigation Start Date", reportFieldValue("reporting.investigation_start_date")],
      ],
    },
    {
      group: "Reporting Decision",
      groupKey: "jurisdiction",
      items: [
        [
          "Reportability",
          reportability,
        ],
        [
          "Reporting Rule",
          reportingRule,
        ],
        [
          "Deadline",
          formatDate(deadline),
        ],
      ],
    },
  ];


  /* =======================================================
     ACTIONS
     ======================================================= */

  async function runValidation() {
    setBusy("validate");
    setError("");

    try {
      await validateCase(caseId);
      await reload();
    } catch (requestError) {
      setError(
        requestError?.message ||
        "Validation failed."
      );
    } finally {
      setBusy("");
    }
  }


  async function saveReview() {
    if (!reviewChecked) {
      setError(
        "Confirm that you reviewed the reporting values and available evidence."
      );
      return;
    }

    if (demoReviewPreview) {
      setError("");
      setDemoReviewConfirmed(true);
      return;
    }

    setBusy("review");
    setError("");

    try {
      const reviewer = currentReviewer();
      const savedReview = await reviewCase(caseId, {
        reviewer_id: reviewer.id,
        reviewer_role: reviewer.role,
        decision: reviewDecision,
        comments: reviewComments.trim() || undefined,
      });
      setReview(savedReview);
      setReviewChecked(true);
    } catch (requestError) {
      setError(
        requestError?.message ||
        "Unable to save the reviewer decision."
      );
    } finally {
      setBusy("");
    }
  }


  async function saveAttestation() {
    if (!reviewApproved) {
      setError("Approve the Human Review before completing attestation.");
      return;
    }
    if (demoReviewPreview) {
      setError("");
      setDemoAttestationConfirmed(true);
      return;
    }
    setBusy("attest");
    setError("");

    try {
      const reviewer = currentReviewer();
      const savedAttestation = await attestCase(caseId, {
        reviewer_id: reviewer.id,
        reviewer_role: reviewer.role,
        attestation_status: "ATTESTED",
        comments: attestationComments.trim() || undefined,
      });
      setAttestation(savedAttestation);
    } catch (requestError) {
      setError(
        requestError?.message ||
        "Unable to complete attestation."
      );
    } finally {
      setBusy("");
    }
  }


  async function submitToQueue() {
    if (!caseId || busy) return;
    setBusy("queue");
    setError("");
    try {
      const reviewer = currentReviewer();
      const queueResult = await queueCase(caseId, { actor_id: reviewer.id });
      resolveClinicalInformationRequest(caseId);
      setAdminInformationRequest(null);
      const patientId = routePatientId || data?.patient?.patient_id || data?.patient_id;
      const queuePath = patientId
        ? `/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(caseId)}/queue`
        : `/cases/${encodeURIComponent(caseId)}/queue`;
      navigate(queuePath, { state: { queueResult } });
    } catch (requestError) {
      const detail = requestError?.data?.detail;
      const validation = detail?.validation;
      const incompleteFields = [
        ...(validation?.missing_fields || []),
        ...(validation?.completion_required || []),
      ].filter(Boolean);
      const uniqueIncompleteFields = [...new Set(incompleteFields.map(String))];
      const validationMessage = uniqueIncompleteFields.length
        ? ` Complete these required fields first: ${uniqueIncompleteFields.join("; ")}`
        : "";
      setError(
        `${typeof detail === "string" ? detail : detail?.message || requestError?.message || "Unable to submit the case to the Admin queue."}${validationMessage}`
      );
    } finally {
      setBusy("");
    }
  }


  /* =======================================================
     LOADING
     ======================================================= */

  if (loading) {
    return (
      <section className="review-validation-page">
        <SignalLoading
          title="Loading Review & Validation"
          message="Loading the case, validation state, reviewer decision, and attestation status from SIGNAL."
        />
      </section>
    );
  }


  /* =======================================================
     ERROR
     ======================================================= */

  if (!data) {
    return (
      <section className="review-validation-page">
        <div className="review-validation-empty">
          <h2>
            Unable to load reporting case
          </h2>

          <p>
            {error ||
              "The requested case could not be loaded."}
          </p>

          <button
            type="button"
            className="review-validation-submit"
            onClick={() =>
              setRefreshKey(
                (value) => value + 1
              )
            }
          >
            Retry
          </button>
        </div>
      </section>
    );
  }


  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <section className="review-validation-page">

      {/* HEADER */}

      <header className="review-validation-header">

        <div>
          <span className="review-validation-eyebrow">
            SIGNAL · PATIENT WORKSPACE
          </span>

          <h1>
            Reporting Review
          </h1>

          <p>
            Review mapped reporting values, validation
            checks, and source evidence before authorized
            submission.
          </p>
        </div>

        <div className="review-validation-header-actions">
        <button
          type="button"
          className="review-validation-back"
          onClick={() =>
            navigate(-1)
          }
        >
          ← Back
        </button>
        </div>

      </header>


      {/* BREADCRUMB */}

      <nav
        className="review-validation-breadcrumb"
        aria-label="Reporting workflow"
      >
        {[
          "Patient",
          "Active Patient",
          "Data Extraction",
          "Texas Measles CRF",
        ].map((item) => (
          <span
            key={item}
            className="review-validation-breadcrumb-item"
          >
            {item}
          </span>
        ))}

        <span className="review-validation-breadcrumb-separator">
          ›
        </span>

        <span className="review-validation-breadcrumb-item active">
          Review & Validation
        </span>
      </nav>

      {demoReviewPreview && (
        <div className="review-validation-demo-notice" role="status">
          Demo preview: sample values only. They are not saved to this Case. Workflow API actions are disabled; the button below opens a simulated queue acknowledgement.
        </div>
      )}

      {adminInformationRequest && !demoReviewPreview && (
        <div className="review-validation-message error" role="alert">
          <strong>Additional information requested by Administrator</strong>
          <span>Please complete the missing information and resubmit this case for administrative review.</span>
          {adminInformationRequest.missingFields?.length > 0 && (
            <ul>
              {adminInformationRequest.missingFields.map((field, index) => (
                <li key={`${field}-${index}`}>{String(field)}</li>
              ))}
            </ul>
          )}
        </div>
      )}


      {/* ERROR */}

      {error && (
        <div
          className="review-validation-message error"
          role="alert"
        >
          <strong>
            Unable to complete action.
          </strong>

          <span>
            {error}
          </span>
        </div>
      )}


      {/* MAIN GRID */}

      <div className="review-validation-grid">

        {/* =================================================
            LEFT
            ================================================= */}

        <div className="review-validation-left">

          {/* REPORTING DATA */}

          <section className="review-validation-card review-validation-reporting-data">

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Reporting Data
                </h2>

                <p>
                  Mapped values from available patient
                  records
                </p>
              </div>

            </div>


            <div className="review-validation-data-list">

              {reportingData.map((section) => {
                const status = reviewApproved ? "COMPLETE" : "NOT_CHECKED";
                const heading = {
                  Patient: "Patient Information",
                  Clinical: "Clinical Information",
                  Laboratory: "Laboratory Information",
                  "Rash and Fever": "Rash and Fever",
                  Reporting: "Reporting Information",
                  "Reporting Decision": "Reporting Decision",
                }[section.group] || section.group;

                return (
                  <div className="review-validation-data-section" key={section.group}>
                    <div className="review-validation-data-row">
                      <span className="review-validation-data-label">{heading}</span>
                      <span
                        className={`review-validation-section-status ${status.toLowerCase()}`}
                        role="img"
                        aria-label={`${heading}: complete`}
                        title="Complete"
                      >
                        {"\u2713"}
                      </span>
                    </div>
                    <dl className="review-validation-field-values">
                      {section.items.map(([label, value]) => (
                        <div className="review-validation-field-value" key={label}>
                          <dt>{label}</dt>
                          <dd>{readable(value)}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                );
              })}

            </div>

          </section>


          {/* SOURCE EVIDENCE */}

          <section className="review-validation-card review-validation-source-evidence">

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Source Evidence
                </h2>

                <p>
                  Records used to populate reporting values
                </p>
              </div>

              <span className="review-validation-badge neutral">
                {[
                  data?.clinical_evidence,
                  data?.laboratory_evidence,
                  data?.ai_evidence,
                ].filter(hasEvidence).length}{" "}
                source records
              </span>

            </div>


            <div className="review-validation-evidence-list">

              <EvidenceRow
                date={
                  data?.clinical_evidence?.date ||
                  data?.clinical_evidence?.encounter_date
                }
                type="Clinical"
                title="Clinical presentation evidence"
                subtitle="Source evidence linked"
                available={hasEvidence(
                  data?.clinical_evidence
                )}
              />

              <EvidenceRow
                date={
                  data?.laboratory_evidence?.test_date
                }
                type="Laboratory Result"
                title="Laboratory evidence"
                subtitle="Source evidence linked"
                available={hasEvidence(
                  data?.laboratory_evidence
                )}
              />

              <EvidenceRow
                date={
                  data?.ai_evidence?.date
                }
                type="Detection"
                title="Initial detection evidence"
                subtitle="Detection evidence available"
                available={hasEvidence(
                  data?.ai_evidence
                )}
              />

            </div>

          </section>


          {/* HUMAN REVIEW */}

          <section
            className="review-validation-card review-validation-human-card"
            id="case-human-review"
          >

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Human Review
                </h2>

                <p>
                  Confirm the mapped reporting values
                  before queue handoff.
                </p>
                <p className="review-session-only-note">
                  {demoReviewPreview
                    ? "Sample review shown for this preview; no workflow record was created."
                    : "Review decisions are recorded in the case workflow."}
                </p>
              </div>

              <span
                className={`review-validation-badge ${
                  reviewApproved
                    ? "success"
                    : "neutral"
                }`}
              >
                {reviewApproved
                  ? demoReviewPreview ? "Demo Complete" : "Persisted"
                  : "Pending"}
              </span>

            </div>


            {!reviewApproved && (
              <>
                <label className="review-validation-decision-option">

                  <input
                    type="radio"
                    name="review-decision"
                    value="APPROVE"
                    checked={
                      reviewDecision ===
                      "APPROVE"
                    }
                    onChange={(event) =>
                      (() => {
                        setReviewDecision(event.target.value);
                        persistReviewDraft({ reviewDecision: event.target.value });
                      })()
                    }
                  />

                  <span>
                    <strong>
                      Ready to Add to Queue
                    </strong>

                    <span>
                      All available reporting
                      information has been reviewed.
                    </span>
                  </span>

                </label>


                <label className="review-validation-decision-option">

                  <input
                    type="radio"
                    name="review-decision"
                    value="REQUEST_INFORMATION"
                    checked={
                      reviewDecision ===
                      "REQUEST_INFORMATION"
                    }
                    onChange={(event) =>
                      (() => {
                        setReviewDecision(event.target.value);
                        persistReviewDraft({ reviewDecision: event.target.value });
                      })()
                    }
                  />

                  <span>
                    <strong>
                      Request Information
                    </strong>

                    <span>
                      Additional information is required
                      before queue handoff.
                    </span>
                  </span>

                </label>


                <label className="review-validation-review-check">

                  <input
                    type="checkbox"
                    checked={reviewChecked}
                    onChange={(event) =>
                      (() => {
                        setReviewChecked(event.target.checked);
                        persistReviewDraft({ reviewChecked: event.target.checked });
                      })()
                    }
                  />

                  <span>
                    I reviewed the reporting values and
                    available source evidence.
                  </span>

                </label>


                <label className="review-validation-comment-field">

                  <span>
                    Reviewer Comments
                  </span>

                  <textarea
                    value={reviewComments}
                    onChange={(event) =>
                      (() => {
                        setReviewComments(event.target.value);
                        persistReviewDraft({ reviewComments: event.target.value });
                      })()
                    }
                    placeholder="Add review comments if required..."
                    maxLength={2000}
                  />

                </label>


                <div className="review-validation-review-footer">

                  <span>
                    Reviewer:{" "}
                    {currentReviewer().name}
                  </span>

                  <button
                    type="button"
                    className="review-validation-secondary-button"
                    disabled={
                      busy !== "" ||
                      !reviewChecked ||
                      (
                        reviewDecision ===
                        "REQUEST_INFORMATION" &&
                        !reviewComments.trim()
                      )
                    }
                    onClick={saveReview}
                  >
                    {busy === "review"
                      ? "Confirming..."
                      : "Save Review"}
                  </button>

                </div>
              </>
            )}


            {reviewApproved && (
              <div className="review-validation-approved">

                <div className="review-validation-approved-icon">
                  ✓
                </div>

                <div>
                  <strong>
                    {demoReviewPreview
                      ? "Sample case review complete"
                      : "Case approved for queue handoff"}
                  </strong>

                  <span>
                      {demoReviewPreview ? "Sample reviewer: " : "Reviewed by "}
                    {(demoReviewPreview ? "Demo Clinical Staff" : review?.payload?.reviewer_id) ||
                      review?.actor_id ||
                      "Reporting Staff"}
                  </span>

                  {review?.payload?.comments && (
                    <span>
                      {review.payload.comments}
                    </span>
                  )}
                </div>

              </div>
            )}

          </section>


          {/* ATTESTATION */}

          <section
            className="review-validation-card review-validation-attestation-card"
            id="case-attestation"
          >

              <div className="review-validation-card-header">

                <div>
                  <h2>
                    Attestation
                  </h2>

                  <p>
                    Final confirmation before authorized
                    queue handoff.
                  </p>
                  <p className="review-session-only-note">
                    {demoReviewPreview
                      ? "Sample attestation shown for this preview; no workflow record was created."
                      : "Attestation is recorded in the case workflow."}
                  </p>
                </div>

                <span
                  className={`review-validation-badge ${
                    attested
                      ? "success"
                      : "warning"
                  }`}
                >
                  {attested
                    ? demoReviewPreview ? "Demo Complete" : "Persisted"
                    : "Pending"}
                </span>

              </div>


              {attested ? (
                <div className="review-validation-approved">

                  <div className="review-validation-approved-icon">
                    ✓
                  </div>

                  <div>
                    <strong>
                      {demoReviewPreview
                        ? "Sample attestation complete"
                        : "Attestation recorded for this case"}
                    </strong>

                    <span>
                      {(demoReviewPreview ? "Demo Clinical Staff" : attestation?.payload?.reviewer_id) ||
                        attestation?.actor_id ||
                        "Reporting Staff"}
                    </span>

                    <span>
                      {demoReviewPreview
                        ? "Sample timestamp — demo only"
                        : attestation?.created_at
                        ? formatDate(
                            attestation.created_at
                          )
                        : "Timestamp not available"}
                    </span>
                  </div>

                </div>
              ) : (
                <>
                  {!reviewApproved && (
                    <p className="review-validation-attestation-prerequisite">
                      Approve Human Review to enable attestation.
                    </p>
                  )}
                  <label className="review-validation-comment-field">

                    <span>
                      Attestation Comments
                    </span>

                    <textarea
                      value={
                        attestationComments
                      }
                      onChange={(event) =>
                        (() => {
                          setAttestationComments(event.target.value);
                        })()
                      }
                      disabled={!reviewApproved}
                      placeholder="Optional attestation comments..."
                      maxLength={2000}
                    />

                  </label>

                  <div className="review-validation-review-footer">

                    <span>
                      Reviewer:{" "}
                      {currentReviewer().name}
                    </span>

                    <button
                      type="button"
                      className="review-validation-secondary-button"
                      disabled={
                        busy !== "" || !reviewApproved
                      }
                      onClick={
                        saveAttestation
                      }
                    >
                      {busy === "attest"
                        ? "Confirming..."
                        : "Save Attestation"}
                    </button>

                  </div>
                </>
              )}

          </section>

        </div>


        {/* =================================================
            RIGHT
            ================================================= */}

        <div className="review-validation-right">

          {/* VALIDATION SUMMARY */}

          <section className="review-validation-card review-validation-summary">

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Validation Summary
                </h2>

                <p>
                  Current reporting package status
                </p>
              </div>

              <span
                className={`review-validation-badge ${
                  validationStatus === "VALID"
                    ? "success"
                    : "warning"
                }`}
              >
                {validationStatus === "VALID"
                  ? "Evidence Updated"
                  : "Needs Attention"}
              </span>

            </div>


            <div className="review-validation-metrics">

              <Metric
                value={
                  validationCounts.valid
                }
                label="Valid"
                variant="valid"
              />

              <Metric
                value={
                  validationCounts.attention
                }
                label="Need Attention"
                variant="attention"
              />

              <Metric
                value={
                  validationCounts.blocking
                }
                label="Blocking"
                variant="blocking"
              />

            </div>


            <div className="review-validation-evidence-notice">

              <span className="review-validation-evidence-icon">
                ✓
              </span>

              <div>

                <strong>
                  {validationStatus ===
                  "VALID"
                    ? "All required reporting fields have supporting evidence"
                    : "Reporting package requires attention"}
                </strong>

                <span>
                  SIGNAL uses the persisted validation
                  response to determine readiness.
                </span>

              </div>

            </div>


            <div className="review-validation-checklist">

              {VALIDATION_GROUPS.map(
                (group) => {
                  const status =
                    validationGroupStatus(
                      validation,
                      group.key,
                      currentCaseMissingFields
                    );

                  return (
                    <div
                      className="review-validation-check"
                      key={group.key}
                    >

                      <span
                        className={`review-validation-check-icon ${
                          status === "COMPLETE"
                            ? "complete"
                            : status === "ATTENTION"
                              ? "attention"
                              : "pending"
                        }`}
                      >
                        {status ===
                        "COMPLETE"
                          ? "✓"
                          : status ===
                            "ATTENTION"
                            ? "!"
                            : "○"}
                      </span>

                      <span className="review-validation-check-label">
                        {group.label}
                      </span>

                      <span className="review-validation-check-status">
                        {status ===
                        "COMPLETE"
                          ? "Complete"
                          : status ===
                            "ATTENTION"
                            ? "Needs attention"
                            : "Not checked"}
                      </span>

                    </div>
                  );
                }
              )}

            </div>


            <div className="review-validation-validation-action">

              <button
                type="button"
                className="review-validation-secondary-button"
                disabled={
                  demoReviewPreview || busy !== ""
                }
                onClick={
                  runValidation
                }
              >
                {busy === "validate"
                  ? "Validating..."
                  : "Refresh Validation"}
              </button>

            </div>

          </section>


          {/* CASE SUMMARY */}

          <section className="review-validation-card review-validation-case-summary-card">

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Case Summary
                </h2>

                <p>
                  Reporting case context
                </p>
              </div>

              <span className="review-validation-badge neutral">
                {data.status ||
                  "Case"}
              </span>

            </div>


            <div className="review-validation-case-summary">

              <SummaryItem
                label="Patient"
                value={patientName(patient)}
              />

              <SummaryItem
                label="DOB"
                value={
                  patient?.date_of_birth ||
                  "Not available"
                }
              />

              <SummaryItem
                label="Condition"
                value={condition}
              />

              <SummaryItem
                label="Jurisdiction"
                value={
                  jurisdiction === "TX"
                    ? "Texas"
                    : jurisdiction
                }
              />

              <SummaryItem
                label="Case Status"
                value={
                  demoReviewPreview
                    ? "Demo preview (sample only)"
                    : data.status || "Not available"
                }
              />

            </div>

          </section>


          {/* WHAT HAPPENS NEXT */}

          <section className="review-validation-card review-validation-queue-readiness-card">

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Queue Readiness
                </h2>

                <p>
                  Final workflow state
                </p>
              </div>

              <span
                className={`review-validation-badge ${
                  canSubmitToQueue
                    ? "success"
                    : "warning"
                }`}
              >
                {canSubmitToQueue
                  ? "Ready"
                  : "Pending"}
              </span>

            </div>


            <div className="review-validation-readiness">

              <ReadinessRow
                label="Validation"
                complete={
                  validationStatus ===
                  "VALID"
                }
              />

              <ReadinessRow
                label="Human Review"
                complete={
                  reviewApproved
                }
              />

              <ReadinessRow
                label="Attestation"
                complete={
                  attested
                }
              />

              <ReadinessRow
                label="Queue Handoff"
                complete={false}
                current={
                  canSubmitToQueue
                }
              />

            </div>

          </section>


          {/* REPORTING DATA DETAILS */}

          <section className="review-validation-card review-validation-reporting-decision-card">

            <div className="review-validation-card-header">

              <div>
                <h2>
                  Reporting Decision
                </h2>

                <p>
                  Backend-derived reporting context
                </p>
              </div>

            </div>


            <div className="review-validation-decision-summary">

              <SummaryItem
                label="Reportability"
                value={reportability}
              />

              <SummaryItem
                label="Reporting Rule"
                value={reportingRule}
              />

              <SummaryItem
                label="Deadline"
                value={formatDate(deadline)}
              />

              <SummaryItem
                label="Reporting Facility"
                value={facility}
              />

              <SummaryItem
                label="Reporting Provider"
                value={provider}
              />

            </div>

          </section>

        </div>

      </div>


      {/* =================================================
          BOTTOM ACTION
          ================================================= */}

      <footer className="review-validation-action-bar">

        <div className="review-validation-action-copy">

          <strong>
            {demoReviewPreview
                ? "Demo package is ready to preview"
                : "Ready to continue?"}
          </strong>

          <span>
            {demoReviewPreview
              ? "The demo button below only simulates submission and does not save or send this sample package."
              : "Confirm your reviewer decision and attestation before submitting the package to the authorized reporting queue."}
          </span>

        </div>


        <button
          type="button"
          className="review-validation-submit"
          disabled={
            busy !== "" ||
            !workflowConfirmed
          }
          onClick={
            submitToQueue
          }
        >
          {demoReviewPreview
              ? "Submit Demo to Queue"
            : "Submit to Queue"}
        </button>

      </footer>

    </section>
  );
}


/* =========================================================
   SMALL COMPONENTS
   ========================================================= */

function Metric({
  value,
  label,
  variant,
}) {
  return (
    <div className="review-validation-metric">

      <div
        className={`review-validation-metric-value ${variant}`}
      >
        {value}
      </div>

      <div className="review-validation-metric-label">
        {label}
      </div>

    </div>
  );
}


function SummaryItem({
  label,
  value,
}) {
  return (
    <div className="review-validation-summary-item">

      <span>
        {label}
      </span>

      <strong>
        {readable(value)}
      </strong>

    </div>
  );
}


function ReadinessRow({
  label,
  complete,
  current,
}) {
  return (
    <div className="review-validation-readiness-row">

      <span
        className={`review-validation-readiness-icon ${
          complete
            ? "complete"
            : current
              ? "current"
              : "pending"
        }`}
      >
        {complete
          ? "✓"
          : current
            ? "●"
            : "○"}
      </span>

      <span>
        {label}
      </span>

      <small>
        {complete
          ? "Complete"
          : current
            ? "Ready"
            : "Pending"}
      </small>

    </div>
  );
}


function EvidenceRow({
  date,
  type,
  title,
  subtitle,
  available,
}) {
  return (
    <div className="review-validation-evidence-row">

      <div className="review-validation-evidence-date">

        {date
          ? formatDate(date)
          : "Available"}

        <span>
          {type}
        </span>

      </div>


      <div
        className={`review-validation-evidence-check ${
          available
            ? "available"
            : "unavailable"
        }`}
      >
        {available ? "✓" : "–"}
      </div>


      <div className="review-validation-evidence-content">

        <div className="review-validation-evidence-title">
          {title}
        </div>

        <div className="review-validation-evidence-subtitle">
          {available
            ? subtitle
            : "No source evidence returned"}
        </div>

      </div>


      <button
        type="button"
        className="review-validation-evidence-link"
        disabled={!available}
      >
        {available
          ? "View Source"
          : "Unavailable"}
      </button>

    </div>
  );
}
