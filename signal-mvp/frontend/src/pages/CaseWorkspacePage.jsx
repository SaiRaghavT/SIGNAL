import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  getCase,
  getCaseJourney,
  getCaseTimeline,
  updateCaseReportFields,
} from "../api/cases.js";

import {
  getCaseValidation,
  markSubmissionReady,
  validateCase,
  getImmediateNotification,
} from "../api/workflow.js";

import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { readCaseWorkflowSession, writeCaseWorkflowSession } from "../utils/caseWorkflowSessionStorage.js";
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
        };
      }
    } catch {
      // Fall back to configured reporting user.
    }
  }

  return {
    id: "reporting_user",
    name: "Reporting Staff",
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
    validation.status === "VALID" &&
    validation.valid === true &&
    validation.ready_for_review === true
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
  groupKey
) {
  const missingFields = getMissingFields(validation);

  const errors = Array.isArray(validation?.errors)
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

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

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

  function saveSessionWorkflow(update) {
    const next = {
      ...readCaseWorkflowSession(caseId),
      ...update,
    };
    return writeCaseWorkflowSession(caseId, next);
  }

  function restoreSessionWorkflow() {
    const saved = readCaseWorkflowSession(caseId);
    setReview(saved.review || null);
    setAttestation(saved.attestation || null);
    setReviewDecision(saved.reviewDecision || saved.review?.payload?.decision || "APPROVE");
    setReviewComments(saved.reviewComments || saved.review?.payload?.comments || "");
    setAttestationComments(saved.attestationComments || saved.attestation?.payload?.comments || "");
    setReviewChecked(saved.reviewChecked === true);
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
    ] = await Promise.all([
      getCase(caseId),
      getCaseJourney(caseId),
      getCaseValidation(caseId),
      getCaseTimeline(caseId),
      getImmediateNotification(caseId),
    ]);

    setData(caseResponse);
    setJourney(journeyResponse);
    setValidation(validationResponse);
    restoreSessionWorkflow();

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
        ] = await Promise.all([
          getCase(caseId),
          getCaseJourney(caseId),
          getCaseValidation(caseId),
          getCaseTimeline(caseId),
          getImmediateNotification(caseId),
        ]);

        if (!active) return;

        setData(caseResponse);
        setJourney(journeyResponse);
        setValidation(validationResponse);
        restoreSessionWorkflow();

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
    () => getValidationCounts(validation),
    [validation]
  );

  const validationStatus = useMemo(
    () => getValidationStatus(validation),
    [validation]
  );

  const missingFields = useMemo(
    () => getMissingFields(validation),
    [validation]
  );

  const reviewApproved =
    review?.status === "APPROVE";

  const attested =
    attestation?.status === "ATTESTED";

  const readyForReview =
    validationStatus === "VALID" &&
    validation?.ready_for_review === true;

  const canSubmitToQueue =
    readyForReview &&
    reviewApproved &&
    attested &&
    reviewChecked;


  /* =======================================================
     CASE DATA
     ======================================================= */

  const patient = data?.patient || {};

  const condition =
    data?.disease ||
    data?.condition ||
    "Measles";

  const jurisdiction =
    data?.jurisdiction ||
    data?.reporting_jurisdiction ||
    "Texas";

  const facility =
    data?.facility?.name ||
    data?.facility?.facility_name ||
    data?.facility?.facility_id ||
    "Not available";

  const provider =
    data?.provider?.name ||
    "Not available";

  const reportability =
    data?.final_decision ||
    data?.reportability_decision ||
    data?.reportability ||
    "Not available";

  const reportingRule =
    data?.rule_id ||
    data?.reportability_rule ||
    data?.reporting_rule ||
    "Not available";

  const deadline =
    data?.deadline ||
    data?.reporting_deadline ||
    null;


  /* =======================================================
     REPORTING DATA
     ======================================================= */

  const reportingData = [
    {
      group: "Clinical",
      items: [
        [
          "Illness Onset Date",
          data?.clinical_evidence?.illness_onset_date ||
          data?.clinical?.illness_onset_date ||
          data?.report_fields?.["clinical.illness_onset_date"] ||
          "Not available",
        ],
        [
          "Hospitalized",
          data?.clinical_evidence?.hospitalized ??
          data?.clinical?.hospitalized ??
          data?.report_fields?.["clinical.hospitalized"] ??
          "Not available",
        ],
        [
          "Key Symptoms",
          data?.clinical_evidence?.symptoms ||
          data?.clinical_evidence?.key_symptoms ||
          data?.clinical?.symptoms ||
          data?.report_fields?.["clinical.symptoms"] ||
          "Not available",
        ],
      ],
    },

    {
      group: "Laboratory",
      items: [
        [
          "Test",
          data?.laboratory_evidence?.test_name ||
          data?.laboratory_evidence?.test ||
          data?.laboratory?.test_name ||
          data?.report_fields?.["laboratory.test_name"] ||
          "Not available",
        ],
        [
          "Result",
          data?.laboratory_evidence?.result ||
          data?.laboratory?.result ||
          data?.report_fields?.["laboratory.result"] ||
          "Not available",
        ],
        [
          "Test Date",
          data?.laboratory_evidence?.test_date ||
          data?.laboratory?.test_date ||
          data?.report_fields?.["laboratory.test_date"] ||
          "Not available",
        ],
      ],
    },

    {
      group: "Reporting",
      items: [
        [
          "Reporting Facility",
          facility,
        ],
        [
          "Reporting Provider",
          provider,
        ],
      ],
    },

    {
      group: "Reporting Decision",
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

    setBusy("review");
    setError("");

    try {
      const reviewer = currentReviewer();
      const timestamp = new Date().toISOString();
      const temporaryReview = {
        status: reviewDecision,
        actor_id: reviewer.id,
        created_at: timestamp,
        payload: {
          reviewer_id: reviewer.id,
          decision: reviewDecision,
          comments: reviewComments.trim() || undefined,
          temporary_session_only: true,
        },
      };
      if (!saveSessionWorkflow({ review: temporaryReview, reviewDecision, reviewComments, reviewChecked })) {
        throw new Error("Browser session storage is unavailable. The review was not saved.");
      }
      setReview(temporaryReview);
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
    setBusy("attest");
    setError("");

    try {
      const reviewer = currentReviewer();
      const temporaryAttestation = {
        status: "ATTESTED",
        actor_id: reviewer.id,
        created_at: new Date().toISOString(),
        payload: {
          reviewer_id: reviewer.id,
          comments: attestationComments.trim() || undefined,
          temporary_session_only: true,
        },
      };
      if (!saveSessionWorkflow({ attestation: temporaryAttestation, attestationComments })) {
        throw new Error("Browser session storage is unavailable. The attestation was not saved.");
      }
      setAttestation(temporaryAttestation);
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
      const result = await markSubmissionReady(caseId, {
        actor_id: reviewer.id,
        review_confirmed: true,
        review_decision: review?.status,
        attestation_confirmed: true,
      });
      const queueResult = result?.data ?? result;
      if (queueResult?.ready !== true || queueResult?.record?.status !== "READY") {
        throw new Error("SIGNAL did not confirm that this case is ready for the reporting queue.");
      }
      const patientId = routePatientId || data?.patient?.patient_id || data?.patient_id;
      const queuePath = patientId
        ? `/patients/${encodeURIComponent(patientId)}/case/${encodeURIComponent(caseId)}/queue`
        : `/cases/${encodeURIComponent(caseId)}/queue`;
      navigate(queuePath, { state: { queueResult } });
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : detail?.message || requestError?.message || "Unable to confirm queue readiness.");
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
            Review & Validation
          </h1>

          <p>
            Review mapped reporting values, validation
            checks, and source evidence before authorized
            submission.
          </p>
        </div>

        <button
          type="button"
          className="review-validation-back"
          onClick={() =>
            navigate(-1)
          }
        >
          ← Back
        </button>

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
                const groupKey = section.group === "Clinical"
                  ? "clinical"
                  : section.group === "Laboratory"
                    ? "laboratory"
                    : section.group === "Reporting Decision"
                      ? "jurisdiction"
                      : "reporting";
                const status = validationGroupStatus(validation, groupKey);
                const heading = {
                  Clinical: "Clinical Information",
                  Laboratory: "Laboratory Information",
                  Reporting: "Reporting Information",
                  "Reporting Decision": "Reporting Decision",
                }[section.group] || section.group;

                return (
                  <div className="review-validation-data-row" key={section.group}>
                    <span className="review-validation-data-label">{heading}</span>
                    <span
                      className={`review-validation-section-status ${status.toLowerCase()}`}
                      role="img"
                      aria-label={`${heading}: ${status === "COMPLETE" ? "complete" : status === "ATTENTION" ? "needs attention" : "not checked"}`}
                      title={status === "COMPLETE" ? "Complete" : status === "ATTENTION" ? "Needs attention" : "Not checked"}
                    >
                      {status === "COMPLETE" ? "✓" : status === "ATTENTION" ? "!" : "○"}
                    </span>
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
                  Review confirmation is temporary and stays in this browser session.
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
                  ? "Session Confirmed"
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
                        saveSessionWorkflow({ reviewDecision: event.target.value });
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
                        saveSessionWorkflow({ reviewDecision: event.target.value });
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
                        saveSessionWorkflow({ reviewChecked: event.target.checked });
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
                        saveSessionWorkflow({ reviewComments: event.target.value });
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
                      : "Confirm for This Session"}
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
                    Case approved for queue handoff in this browser session
                  </strong>

                  <span>
                      Temporarily confirmed by{" "}
                    {review?.payload?.reviewer_id ||
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
                    Attestation is temporary and stays in this browser session.
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
                    ? "Session Confirmed"
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
                      Attestation confirmed for this browser session
                    </strong>

                    <span>
                      {attestation?.payload?.reviewer_id ||
                        attestation?.actor_id ||
                        "Reporting Staff"}
                    </span>

                    <span>
                      {attestation?.created_at
                        ? formatDate(
                            attestation.created_at
                          )
                        : "Session timestamp not available"}
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
                          saveSessionWorkflow({ attestationComments: event.target.value });
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
                        : "Confirm for This Session"}
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
                      group.key
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
                  busy !== ""
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
                  data.status ||
                  "Not available"
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
            Ready to continue?
          </strong>

          <span>
            Confirm your reviewer decision and
            attestation before submitting the package
            to the authorized reporting queue.
          </span>

        </div>


        <button
          type="button"
          className="review-validation-submit"
          disabled={
            busy !== "" ||
            !canSubmitToQueue
          }
          onClick={
            submitToQueue
          }
        >
          Submit to Queue →
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
