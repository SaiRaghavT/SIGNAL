import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  ArrowLeft,
  Check,
  Clock3,
  ShieldCheck,
  Send,
  UserRoundCheck,
} from "lucide-react";

import { SignalLoading } from "../components/ui/SignalLoading.jsx";

import {
  getCase,
  getCaseJourney,
} from "../api/cases.js";

import {
  getCaseValidation,
  getSubmissionReadiness,
  calculateDeadline,
} from "../api/workflow.js";

import "../styles/queue-acknowledgement.css";


/* =========================================================
   HELPERS
   ========================================================= */

const asList = (value) =>
  Array.isArray(value) ? value : [];


const responseData = (response) =>
  response?.data ?? response;


const prettify = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );


function conditionLabel(value, displayValue) {
  const display = String(displayValue || "").trim();
  if (display) return prettify(display);

  const raw = String(value || "").trim();
  const snomedCode = raw.match(/(?:\||\/)(\d+)$/)?.[1];
  if (/^(measles|rubeola)$/i.test(raw) || ["14189004", "14168008", "7180009"].includes(snomedCode)) {
    return "Measles";
  }

  // Avoid exposing terminology URLs or opaque codes as a condition label.
  if (/^https?:\/\//i.test(raw) || /^\d+$/.test(raw)) {
    return "Condition recorded";
  }
  return prettify(raw) || "Not returned";
}


function errorMessage(error) {
  const detail =
    error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (
    typeof detail?.message === "string"
  ) {
    return detail.message;
  }

  return (
    error?.message ||
    "Unable to load queue status from SIGNAL."
  );
}


function patientLabel(patient) {
  const name = [
    patient?.first_name,
    patient?.last_name,
  ]
    .filter(
      (part) =>
        typeof part === "string" &&
        part.trim()
    )
    .join(" ");

  return (
    name ||
    patient?.name ||
    "Patient name not returned"
  );
}


function jurisdictionLabel(value) {
  const raw = String(value || "").trim();

  if (/^(tx|texas)$/i.test(raw)) {
    return "Texas DSHS";
  }

  return raw || "Not returned";
}


function deadlineLabel(value) {
  const raw =
    typeof value === "object" && value
      ? value.deadline
      : value;

  if (
    !raw ||
    !Number.isFinite(Date.parse(raw))
  ) {
    return "Not available";
  }

  return new Date(raw).toLocaleString(
    undefined,
    {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }
  );
}


function stage(journey, name) {
  return (
    asList(journey?.journey).find(
      (item) => item.stage === name
    ) || null
  );
}


/* =========================================================
   SMALL UI COMPONENTS
   ========================================================= */

function StatusCard({
  label,
  value,
  subtitle,
  accent = "sage",
}) {
  return (
    <article
      className={`queue-status-card accent-${accent}`}
    >
      <span className="queue-eyebrow">
        {label}
      </span>

      <strong>{value}</strong>

      <small>{subtitle}</small>
    </article>
  );
}


function LifecycleStep({
  label,
  state,
  note,
}) {
  const isComplete = state === "complete";
  const isCurrent = state === "current";

  return (
    <li
      className={`queue-lifecycle-step ${
        isComplete
          ? "is-complete"
          : isCurrent
          ? "is-current"
          : "is-pending"
      }`}
    >
      <span className="queue-lifecycle-marker">
        {isComplete ? (
          <Check
            size={14}
            aria-hidden="true"
          />
        ) : isCurrent ? (
          <Clock3
            size={14}
            aria-hidden="true"
          />
        ) : (
          <span
            className="queue-lifecycle-dot"
            aria-hidden="true"
          />
        )}
      </span>

      <div className="queue-lifecycle-content">
        <strong>{label}</strong>
        <small>{note}</small>
      </div>
    </li>
  );
}


/* =========================================================
   PAGE
   ========================================================= */

export default function QueueAcknowledgementPage() {
  const {
    patientId: routePatientId,
    caseId = "",
  } = useParams();

  const navigate = useNavigate();

  const location = useLocation();

  const [caseData, setCaseData] =
    useState(null);

  const [journey, setJourney] =
    useState(null);

  const [validation, setValidation] =
    useState(null);

  const [readiness, setReadiness] =
    useState(null);

  const [calculatedDeadline, setCalculatedDeadline] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


  /* =======================================================
     LOAD BACKEND STATE
     ======================================================= */

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [
        caseResponse,
        journeyResponse,
        validationResponse,
        readinessResponse,
      ] = await Promise.all([
        getCase(caseId),
        getCaseJourney(caseId),
        getCaseValidation(caseId),
        getSubmissionReadiness(caseId),
      ]);

      const loadedCase = responseData(caseResponse);
      setCaseData(loadedCase);

      const savedDeadline = loadedCase?.deadline || loadedCase?.reporting_deadline;
      if (savedDeadline) {
        setCalculatedDeadline(null);
      } else {
        setCalculatedDeadline(null);
        const disease = String(loadedCase?.disease || "").trim();
        const code = disease.match(/(?:\||\/)(\d+)$/)?.[1];
        const isMeasles = /^(measles|rubeola)$/i.test(disease) || ["14189004", "14168008", "7180009"].includes(code);
        const jurisdiction = String(loadedCase?.jurisdiction || "").trim();
        if (isMeasles && jurisdiction && loadedCase?.created_at) {
          try {
            const deadlineResponse = await calculateDeadline({
              event_time: loadedCase.created_at,
              disease: "measles",
              jurisdiction: /^texas$/i.test(jurisdiction) ? "TX" : jurisdiction,
            });
            setCalculatedDeadline(responseData(deadlineResponse));
          } catch {
            // Keep the queue page usable when no rule is configured.
          }
        }
      }

      setJourney(
        responseData(journeyResponse)
      );

      setValidation(
        responseData(validationResponse)
      );

      setReadiness(
        responseData(readinessResponse)
      );
    } catch (requestError) {
      setError(
        errorMessage(requestError)
      );
    } finally {
      setLoading(false);
    }
  }, [caseId]);


  useEffect(() => {
    load();
  }, [load]);


  /* =======================================================
     CASE DATA
     ======================================================= */

  const patient =
    caseData?.patient || {};

  const patientName =
    patientLabel(patient);

  const actualPatientId =
    routePatientId ||
    patient.patient_id ||
    caseData?.patient_id ||
    "";

  const casePath = actualPatientId
    ? `/patients/${encodeURIComponent(
        actualPatientId
      )}/case/${encodeURIComponent(caseId)}`
    : `/cases/${encodeURIComponent(caseId)}`;

  const caseIdValue =
    caseData?.case_id || caseId;

  const reportingJurisdiction =
    jurisdictionLabel(
      caseData?.jurisdiction
    );

  const condition =
    conditionLabel(caseData?.disease, caseData?.disease_display || caseData?.condition_display);

  const deadline =
    deadlineLabel(
      caseData?.deadline || caseData?.reporting_deadline || calculatedDeadline?.deadline
    );

  const deadlineSubtitle = caseData?.deadline || caseData?.reporting_deadline
    ? "Configured reporting deadline"
    : calculatedDeadline?.calculation_basis || "No reporting deadline rule is available";


  /* =======================================================
     QUEUE STATE
     ======================================================= */

  const queueRecord =
    readiness?.record || null;

  const demoSubmission =
    queueRecord?.payload?.demo_submission === true ||
    location.state?.queueResult?.demo_submission === true ||
    location.state?.demoSubmission === true;

  const queuedForCompletion =
    queueRecord?.status === "QUEUED";

  const queueConfirmed = demoSubmission || (
    readiness?.ready === true &&
    ["READY", "QUEUED", "READY_FOR_SUBMISSION"].includes(queueRecord?.status)
  );

  const queueReference =
    queueRecord?.record_id || (demoSubmission ? "Demo handoff persisted" : "Pending queue reference");


  /* =======================================================
     VALIDATION STATE
     ======================================================= */

  const validationStage =
    stage(journey, "VALIDATION");

  const validated = demoSubmission ||
    validation?.valid === true ||
    validationStage?.data?.valid === true ||
    validationStage?.status ===
      "COMPLETED";


  /* =======================================================
     SUBMISSION STATE
     ======================================================= */

  const submissions = asList(
    stage(journey, "SUBMISSION")
      ?.data?.submissions
  );

  const submission =
    submissions.at(-1) || null;

  const submissionStatus =
    String(
      submission?.status || ""
    ).toUpperCase();

  const destination =
    String(
      submission?.destination || ""
    ).toUpperCase();

  const simulatedDestination =
    destination === "MOCK_PHA";

  const dispatchRecorded =
    [
      "SUBMITTED",
      "ACKNOWLEDGED",
    ].includes(submissionStatus) &&
    !simulatedDestination;

  const phrAcknowledged =
    dispatchRecorded &&
    submissionStatus === "ACKNOWLEDGED" &&
    !simulatedDestination;


  /* =======================================================
     DISPLAY STATES
     ======================================================= */

  const workflowStates = useMemo(
    () => ({
      validated: validated
        ? "complete"
        : "pending",

      queued: queueConfirmed
        ? "complete"
        : "pending",

      admin:
        dispatchRecorded
          ? "complete"
          : queueConfirmed && !queuedForCompletion
          ? "current"
          : "pending",

      dispatch: dispatchRecorded
        ? "complete"
        : "pending",

      acknowledgement:
        phrAcknowledged
          ? "complete"
          : "pending",
    }),
    [
      validated,
      queueConfirmed,
      queuedForCompletion,
      dispatchRecorded,
      phrAcknowledged,
    ]
  );


  const queueStatus = queueConfirmed
    ? queuedForCompletion ? "QUEUED" : "READY"
    : "PENDING";

  const queueStatusSubtitle =
    queueConfirmed
      ? queuedForCompletion
        ? "Queued; required reporting details remain"
        : "Ready for authorized reporting"
      : "Queue handoff not confirmed";


  const adminStatus =
    dispatchRecorded
      ? "Complete"
      : queueConfirmed && !queuedForCompletion
      ? "Current"
      : queuedForCompletion
      ? "Pending completion"
      : "Pending";


  const dispatchStatus =
    dispatchRecorded
      ? prettify(submissionStatus)
      : "Pending";


  const phrStatus =
    phrAcknowledged
      ? "Acknowledged"
      : "Pending";


  /* =======================================================
     NAVIGATION
     ======================================================= */

  const backToPatients = () => {
    navigate("/patients");
  };


  /* =======================================================
     LOADING
     ======================================================= */

  if (loading) {
    return (
      <section className="queue-ack-page">
        <SignalLoading
          title="Loading Queue & Acknowledgement"
          message="Retrieving the case, validation, and queue state from SIGNAL."
        />
      </section>
    );
  }


  /* =======================================================
     ERROR
     ======================================================= */

  if (!caseData) {
    return (
      <section className="queue-ack-page">

        <div
          className="queue-page-error"
          role="alert"
        >
          <strong>
            Unable to load Queue &
            Acknowledgement
          </strong>

          <p>{error}</p>

          <button
            type="button"
            onClick={load}
          >
            Retry
          </button>
        </div>

      </section>
    );
  }


  /* =======================================================
     MAIN UI
     ======================================================= */

  return (
    <section className="queue-ack-page">

      {/* =================================================
          HEADER
          ================================================= */}

      <header className="queue-page-header">

        <div className="queue-page-header-content">

          <span className="queue-page-kicker">
            SIGNAL · PATIENT WORKSPACE
          </span>

          <h2>
            Queue &amp; Acknowledgement
          </h2>

          <div className="queue-patient-heading">

            <div className="queue-patient-name">
              {patientName}
            </div>

            <div className="queue-patient-meta">

              <span>
                Case ID:{" "}
                <strong>
                  {caseIdValue}
                </strong>
              </span>

              <span>
                Condition:{" "}
                <strong>
                  {condition}
                </strong>
              </span>

              <span>
                Jurisdiction:{" "}
                <strong>
                  {reportingJurisdiction}
                </strong>
              </span>

            </div>

          </div>

          <p>
            Track the reporting package from
            authorized queue handoff through
            public-health acknowledgement.
          </p>

          {demoSubmission && (
            <p className="queue-demo-notice" role="status">
              Demo queue handoff saved for demonstration. External dispatch is disabled.
            </p>
          )}

        </div>


        <button
          type="button"
          className="queue-back-button"
          onClick={backToPatients}
        >
          <ArrowLeft size={15} />
          Back
        </button>

      </header>


      {/* =================================================
          ERROR
          ================================================= */}

      {error && (
        <div
          className="queue-inline-error"
          role="alert"
        >
          {error}

          <button
            type="button"
            onClick={load}
          >
            Retry
          </button>
        </div>
      )}


      {/* =================================================
          STATUS CARDS
          ================================================= */}

      <div className="queue-summary-grid">

        <StatusCard
          label="Queue Status"
          value={queueStatus}
          subtitle={queueStatusSubtitle}
          accent="sage"
        />

        <StatusCard
          label="Reporting Condition"
          value={condition}
          subtitle={reportingJurisdiction}
          accent="terra"
        />

        <StatusCard
          label="Reporting Deadline"
          value={deadline}
          subtitle={deadlineSubtitle}
          accent="blue"
        />

      </div>


      {/* =================================================
          MAIN CONTENT
          ================================================= */}

      <main className="queue-main-grid">

        {/* =================================================
            LEFT — QUEUE STATUS
            ================================================= */}

        <div className="queue-primary-column">

          <article className="queue-card queue-status-card-main">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  QUEUE STATUS
                </span>

                <h3>
                  Authorized Reporting Queue
                </h3>
              </div>

              <span
                className={`queue-status-badge ${
                  queueConfirmed
                    ? "is-received"
                    : "is-pending"
                }`}
              >
                {queueConfirmed
                  ? queuedForCompletion ? "QUEUED" : "READY"
                  : "PENDING"}
              </span>

            </header>


            <div
              className={`queue-status-banner ${
                queueConfirmed
                  ? "is-ready"
                  : "is-pending"
              }`}
            >

              <div className="queue-status-banner-icon">

                {queueConfirmed ? (
                  <Check
                    size={19}
                    aria-hidden="true"
                  />
                ) : (
                  <Clock3
                    size={19}
                    aria-hidden="true"
                  />
                )}

              </div>


              <div>

                <strong>
                  {queueConfirmed
                    ? queuedForCompletion
                      ? "Case added to the reporting queue with completion still required."
                      : "Reporting package is ready for authorized reporting staff."
                    : "Reporting package is not yet confirmed in the authorized queue."}
                </strong>

                <p>
                  {queueConfirmed
                    ? queuedForCompletion
                      ? "Complete the missing reporting details before Super Admin review or dispatch."
                      : "Super Admin review is the next step before any dispatch to Texas DSHS."
                    : "Return to Reporting Review and complete the required queue handoff."}
                </p>

              </div>

            </div>


            <div className="queue-reference-block">

              <span className="queue-eyebrow">
                QUEUE REFERENCE
              </span>

              <strong>
                {queueReference}
              </strong>

            </div>


            <div className="queue-next-action">

              <div>
                <span className="queue-eyebrow">
                  NEXT ACTION
                </span>

                <strong>
                  {queueConfirmed
                    ? queuedForCompletion
                      ? "Complete Reporting Details"
                      : "Super Admin Review & Dispatch"
                    : "Confirm Queue Handoff"}
                </strong>

                <p>
                  {queueConfirmed
                    ? queuedForCompletion
                      ? "The case is in the queue, but required details must be completed before dispatch."
                      : "An authorized reporting user reviews the package and dispatches it through the approved reporting channel."
                    : "The case must be confirmed as queue-ready before authorized reporting staff can continue."}
                </p>
              </div>

            </div>

          </article>


          {/* =================================================
              LIFECYCLE
              ================================================= */}

          <article className="queue-card queue-lifecycle-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  SUBMISSION STATUS
                </span>

                <h3>
                  Reporting Lifecycle
                </h3>
              </div>

              <ShieldCheck
                size={17}
                aria-hidden="true"
              />

            </header>


            <ol className="queue-lifecycle">

              <LifecycleStep
                label="Validated"
                state={
                  workflowStates.validated
                }
                note={
                  validated
                    ? "Complete"
                    : "Pending validation"
                }
              />

              <LifecycleStep
                label="Added to Queue"
                state={
                  workflowStates.queued
                }
                note={
                  queueConfirmed
                    ? queuedForCompletion
                      ? "Queued; completion pending"
                      : "Queue ready"
                    : "Pending queue handoff"
                }
              />

              <LifecycleStep
                label="Super Admin Review"
                state={
                  workflowStates.admin
                }
                note={
                  adminStatus
                }
              />

              <LifecycleStep
                label="Dispatch to Texas DSHS"
                state={
                  workflowStates.dispatch
                }
                note={
                  dispatchStatus
                }
              />

              <LifecycleStep
                label="PHR Acknowledgement"
                state={
                  workflowStates.acknowledgement
                }
                note={
                  phrStatus
                }
              />

            </ol>

          </article>

        </div>


        {/* =================================================
            RIGHT — CURRENT RECEIPT
            ================================================= */}

        <aside className="queue-side-column">

          <article className="queue-card queue-receipt-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  CURRENT STATUS
                </span>

                <h3>
                  Reporting Handoff
                </h3>
              </div>

              <span
                className={`queue-status-badge ${
                  queueConfirmed
                    ? "is-received"
                    : "is-pending"
                }`}
              >
                {queueConfirmed
                  ? queuedForCompletion ? "Queued" : "Ready"
                  : "Pending"}
              </span>

            </header>


            <div className="queue-receipt-row">

              <span>
                Queue
              </span>

              <strong>
                {queuedForCompletion
                  ? "Super Admin Reporting Queue · Completion Needed"
                  : "Super Admin Reporting Queue"}
              </strong>

            </div>


            <div className="queue-receipt-row">

              <span>
                Queue Reference
              </span>

              <strong>
                {queueReference}
              </strong>

            </div>


            <div className="queue-receipt-row">

              <span>
                Next Action
              </span>

              <strong>
                {queueConfirmed
                  ? queuedForCompletion
                    ? "Complete reporting details"
                    : "Super Admin Review"
                  : "Complete Queue Handoff"}
              </strong>

            </div>


            <div className="queue-receipt-row">

              <span>
                Texas DSHS
              </span>

              <strong>
                {dispatchRecorded
                  ? "Dispatched"
                  : "Not dispatched"}
              </strong>

            </div>


            <div className="queue-receipt-row">

              <span>
                PHR Acknowledgement
              </span>

              <strong>
                {phrAcknowledged
                  ? "Received"
                  : "Pending"}
              </strong>

            </div>

          </article>


          {/* =================================================
              IMPORTANT STATUS
              ================================================= */}

          <article className="queue-card queue-important-card">

  <div className="queue-important-icon">
    <UserRoundCheck
      size={18}
      aria-hidden="true"
    />
  </div>

  <div>

    <span className="queue-eyebrow">
      AUTHORIZED REPORTING
    </span>

    <h3>
      Submitted to Admin Reporting Queue
    </h3>

    <p>
      The reporting package has been successfully
      handed off to the authorized reporting staff
      for review and dispatch through the approved
      reporting channel.
    </p>

  </div>

</article>


          {/* =================================================
              BACK
              ================================================= */}

          <button
  type="button"
  className="queue-back-button"
  onClick={() => navigate("/patients")}
>
  <ArrowLeft size={16} aria-hidden="true" />
  Back
</button>

        </aside>

      </main>


      {/* =================================================
          FOOTER
          ================================================= */}

      <div className="queue-reference-note">

        <UserRoundCheck
          size={13}
          aria-hidden="true"
        />

        <span>
          SIGNAL tracks queue readiness,
          authorized dispatch, and public-health
          acknowledgement separately.
        </span>

        {location.state?.queueResult?.ready && (
          <Send
            size={13}
            aria-hidden="true"
          />
        )}

      </div>

    </section>
  );
}
