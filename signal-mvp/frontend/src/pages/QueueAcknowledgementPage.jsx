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
  Building2,
  Check,
  Circle,
  ClipboardCheck,
  Clock3,
  FileCheck2,
  Send,
  ShieldCheck,
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
} from "../api/workflow.js";

import "../styles/queue-acknowledgement.css";


const asList = (value) =>
  Array.isArray(value) ? value : [];


const responseData = (response) =>
  response?.data ?? response;


const prettify = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());


function errorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (typeof detail?.message === "string") {
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


function SummaryCard({
  icon: Icon,
  label,
  value,
  subtitle,
  accent,
}) {
  return (
    <article
      className={`queue-summary-card ${
        accent || ""
      }`}
    >
      <Icon
        className="queue-summary-icon"
        size={16}
        aria-hidden="true"
      />

      <span className="queue-eyebrow">
        {label}
      </span>

      <strong>{value}</strong>

      <small>{subtitle}</small>
    </article>
  );
}


function QueueDetail({ label, value }) {
  return (
    <div className="queue-detail">
      <dt>{label}</dt>
      <dd>{value || "Not available"}</dd>
    </div>
  );
}


function SectionStatus({ label, state }) {
  const complete =
    state.validated === state.total &&
    state.total > 0;

  const partial =
    state.validated > 0 && !complete;

  return (
    <li
      className={`queue-check-row ${
        complete
          ? "is-complete"
          : partial
          ? "is-partial"
          : "is-pending"
      }`}
    >
      <span
        className="queue-check-icon"
        aria-hidden="true"
      >
        {complete ? (
          <Check size={14} />
        ) : (
          <Circle size={11} />
        )}
      </span>

      <span>{label}</span>

      <small>
        {state.validated}/{state.total} fields
      </small>
    </li>
  );
}


function LifecycleStep({
  label,
  state,
  note,
}) {
  const Icon =
    state === "complete"
      ? Check
      : state === "current"
      ? Clock3
      : Circle;

  return (
    <li
      className={`queue-lifecycle-step is-${state}`}
    >
      <span className="queue-lifecycle-marker">
        <Icon
          size={14}
          aria-hidden="true"
        />
      </span>

      <div>
        <strong>{label}</strong>
        <small>{note}</small>
      </div>
    </li>
  );
}


function NextStep({
  number,
  title,
  description,
  state,
}) {
  return (
    <li
      className={`queue-next-step is-${state}`}
    >
      <span className="queue-next-number">
        {number}
      </span>

      <div>
        <strong>{title}</strong>

        <p>{description}</p>
      </div>

      <span className="queue-next-badge">
        {state === "current"
          ? "Current"
          : state === "complete"
          ? "Complete"
          : "Pending"}
      </span>
    </li>
  );
}


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

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


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

      setCaseData(
        responseData(caseResponse)
      );

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
    prettify(caseData?.disease) ||
    "Not returned";

  const queueRecord =
    readiness?.record || null;

  const queueConfirmed =
    readiness?.ready === true &&
    queueRecord?.status === "READY";

  const queueReference =
    queueRecord?.record_id ||
    "Pending queue reference";

  const reportingFields =
    readiness?.reporting_fields || {};

  const sectionCounts =
    reportingFields.sections || {};

  const validationStage =
    stage(journey, "VALIDATION");

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

  const superAdminComplete =
    dispatchRecorded;

  const validated =
    validation?.valid === true ||
    validationStage?.data?.valid === true ||
    validationStage?.status ===
      "COMPLETED";

  const deadline =
    deadlineLabel(caseData?.deadline);

  const workflowStates = useMemo(
    () => ({
      validated: validated
        ? "complete"
        : "pending",

      queued: queueConfirmed
        ? "complete"
        : "pending",

      admin: superAdminComplete
        ? "complete"
        : queueConfirmed
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
      superAdminComplete,
      dispatchRecorded,
      phrAcknowledged,
    ]
  );


  const backToReview = () =>
    navigate(casePath);


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


  const queueStatus = queueConfirmed
    ? dispatchRecorded
      ? "Dispatched by authorized reporting"
      : "Ready for authorized reporting queue"
    : "Queue handoff not confirmed";

  const queueBadge = queueConfirmed
    ? "Ready for Queue"
    : "Pending";

  const phrStatus =
    phrAcknowledged
      ? "Acknowledgement recorded"
      : "Pending";

  const superAdminBadge =
    "Pending";

  const evidenceStatus =
    prettify(
      caseData?.reportability_evidence_status
    );

  const nextReviewState =
    superAdminComplete
      ? "complete"
      : queueConfirmed
      ? "current"
      : "pending";

  const nextDispatchState =
    dispatchRecorded
      ? "complete"
      : "pending";

  const nextAcknowledgementState =
    phrAcknowledged
      ? "complete"
      : "pending";


  return (
    <section className="queue-ack-page">

      {/* -------------------------------------------------
          PAGE HEADER
      -------------------------------------------------- */}

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
            Track queue receipt, Super Admin
            handoff, and Texas PHR
            acknowledgement for the reporting
            package.
          </p>

        </div>

        <button
          type="button"
          className="queue-back-button"
          onClick={backToReview}
        >
          <ArrowLeft size={15} />
          Back
        </button>

      </header>


      {/* -------------------------------------------------
          ERROR
      -------------------------------------------------- */}

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


      {/* -------------------------------------------------
          KPI CARDS
      -------------------------------------------------- */}

      <div className="queue-summary-grid">

        <SummaryCard
          icon={Building2}
          label="Reporting Jurisdiction"
          value={reportingJurisdiction}
          subtitle="State health authority"
          accent="accent-sage"
        />

        <SummaryCard
          icon={ShieldCheck}
          label="Reporting Condition"
          value={condition}
          subtitle={
            evidenceStatus
              ? `Evidence: ${evidenceStatus}`
              : "Case condition"
          }
          accent="accent-terra"
        />

        <SummaryCard
          icon={Clock3}
          label="Reporting Deadline"
          value={deadline}
          subtitle="Configured reporting deadline"
          accent="accent-blue"
        />

        <SummaryCard
          icon={FileCheck2}
          label="Reporting Fields"
          value={`${reportingFields.validated ?? 0} / ${
            reportingFields.total ?? 0
          }`}
          subtitle="Validated before queue submission"
          accent="accent-mauve"
        />

      </div>


      {/* -------------------------------------------------
          MAIN CONTENT
      -------------------------------------------------- */}

      <main className="queue-main-grid">

        {/* =================================================
            PRIMARY COLUMN
        ================================================== */}

        <div className="queue-primary-column">

          {/* Queue Handoff */}

          <article className="queue-card queue-confirmation-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  QUEUE HANDOFF
                </span>

                <h3>
                  Queue &amp; Acknowledgement
                </h3>
              </div>

              <span
                className={`queue-status-badge ${
                  queueConfirmed
                    ? "is-received"
                    : "is-pending"
                }`}
              >
                {queueBadge}
              </span>

            </header>


            <div
              className={`queue-confirmation-banner ${
                queueConfirmed
                  ? "is-confirmed"
                  : "is-unconfirmed"
              }`}
            >

              <div className="queue-banner-icon">
                {queueConfirmed ? (
                  <Check size={18} />
                ) : (
                  <Clock3 size={18} />
                )}
              </div>

              <div>

                <strong>
                  {queueConfirmed
                    ? "SIGNAL marked this reporting package ready for the authorized reporting queue."
                    : "Queue readiness has not been confirmed by SIGNAL."}
                </strong>

                <p>
                  {queueConfirmed
                    ? "The package is awaiting queue receipt and Super Admin review before any dispatch to Texas DSHS."
                    : "Return to Review & Validation and complete the backend queue handoff before continuing."}
                </p>

                <small>
                  This readiness record is not
                  a Texas DSHS submission or a
                  separate queue receipt.
                </small>

              </div>

            </div>


            <dl className="queue-detail-grid">

              <QueueDetail
                label="Queue"
                value="Super Admin Reporting Queue"
              />

              <QueueDetail
                label="Queue Status"
                value={queueStatus}
              />

              <QueueDetail
                label="Backend Readiness Reference"
                value={queueReference}
              />

              <QueueDetail
                label="Next Step"
                value={
                  queueConfirmed
                    ? "Super Admin Review & Dispatch"
                    : "Confirm queue handoff"
                }
              />

            </dl>

          </article>


          {/* Reporting Package */}

          <article className="queue-card queue-package-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  REPORTING PACKAGE
                </span>

                <h3>
                  Reporting Package
                </h3>
              </div>

              <span className="queue-card-note">
                {queueConfirmed
                  ? "Queued case"
                  : "Queue not confirmed"}
              </span>

            </header>


            <dl className="queue-package-details">

              <QueueDetail
                label="Patient"
                value={patientName}
              />

              <QueueDetail
                label="Condition"
                value={condition}
              />

              <QueueDetail
                label="Jurisdiction"
                value={reportingJurisdiction}
              />

              <QueueDetail
                label="Case ID"
                value={caseIdValue}
              />

            </dl>


            <div className="queue-contents">

              <div className="queue-subheading">

                <span className="queue-eyebrow">
                  SUBMISSION CONTENTS
                </span>

                <small>
                  {reportingFields.validated ?? 0}{" "}
                  of{" "}
                  {reportingFields.total ?? 0}{" "}
                  configured fields populated
                </small>

              </div>


              <ul>

                <SectionStatus
                  label="Patient identification"
                  state={
                    sectionCounts.patient_identification ||
                    {
                      validated: 0,
                      total: 0,
                    }
                  }
                />

                <SectionStatus
                  label="Clinical information"
                  state={
                    sectionCounts.clinical_information ||
                    {
                      validated: 0,
                      total: 0,
                    }
                  }
                />

                <SectionStatus
                  label="Laboratory evidence"
                  state={
                    sectionCounts.laboratory_evidence ||
                    {
                      validated: 0,
                      total: 0,
                    }
                  }
                />

                <SectionStatus
                  label="Reporting information"
                  state={
                    sectionCounts.reporting_information ||
                    {
                      validated: 0,
                      total: 0,
                    }
                  }
                />

              </ul>

            </div>

          </article>


          {/* Submission Lifecycle */}

          <article className="queue-card queue-lifecycle-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  WORKFLOW STATUS
                </span>

                <h3>
                  Submission Lifecycle
                </h3>
              </div>

              <span className="queue-card-note">
                Post-validation status
              </span>

            </header>


            <ol className="queue-lifecycle">

              <LifecycleStep
                label="Validated"
                state={workflowStates.validated}
                note={
                  validated
                    ? "Backend validation complete"
                    : "Backend validation pending"
                }
              />

              <LifecycleStep
                label="Added to Queue"
                state={workflowStates.queued}
                note={
                  queueConfirmed
                    ? "Queue receipt confirmed"
                    : "Awaiting queue confirmation"
                }
              />

              <LifecycleStep
                label="Super Admin Review"
                state={workflowStates.admin}
                note={
                  superAdminComplete
                    ? "Dispatch record exists"
                    : queueConfirmed
                    ? "Current step"
                    : "Pending queue handoff"
                }
              />

              <LifecycleStep
                label="Dispatched to Texas DSHS"
                state={workflowStates.dispatch}
                note={
                  dispatchRecorded
                    ? `Backend status: ${prettify(
                        submissionStatus
                      )}`
                    : "Pending authorized dispatch"
                }
              />

              <LifecycleStep
                label="Texas PHR Acknowledgement"
                state={
                  workflowStates.acknowledgement
                }
                note={
                  phrAcknowledged
                    ? "Acknowledgement recorded by backend"
                    : "Pending after dispatch"
                }
              />

            </ol>


            {simulatedDestination && (
              <p className="queue-simulation-note">
                A backend submission is recorded
                for a simulated destination. It does
                not confirm Texas DSHS dispatch or a
                Texas PHR acknowledgement.
              </p>
            )}

          </article>

        </div>


        {/* =================================================
            SIDE COLUMN
        ================================================== */}

        <aside className="queue-side-column">

          {/* Super Admin */}

          <article className="queue-card queue-ack-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  QUEUE RECEIPT
                </span>

                <h3>
                  Super Admin Acknowledgement
                </h3>
              </div>

              <span className="queue-status-badge is-pending">
                {superAdminBadge}
              </span>

            </header>


            <p className="queue-card-description">
              {queueConfirmed
                ? "SIGNAL recorded queue readiness. A separate receipt from the Super Admin Reporting Queue has not been recorded."
                : "This card will show receipt only after SIGNAL records a queue acknowledgement."}
            </p>


            <dl className="queue-detail-list">

              <QueueDetail
                label="Acknowledgement"
                value="Pending queue receipt"
              />

              <QueueDetail
                label="Queue"
                value="Super Admin Reporting Queue"
              />

              <QueueDetail
                label="Backend Readiness Reference"
                value={queueReference}
              />

              <QueueDetail
                label="Status"
                value={queueStatus}
              />

            </dl>

          </article>


          {/* Texas PHR */}

          <article className="queue-card queue-phr-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  PUBLIC HEALTH RECEIPT
                </span>

                <h3>
                  Texas PHR Acknowledgement
                </h3>
              </div>

              <span
                className={`queue-status-badge ${
                  phrAcknowledged
                    ? "is-received"
                    : "is-pending"
                }`}
              >
                {phrAcknowledged
                  ? "Received"
                  : "Pending"}
              </span>

            </header>


            <p className="queue-card-description">
              Texas DSHS is not contacted at the
              queue stage. The report is sent only
              after the Super Admin reviews and
              dispatches it through the authorized
              reporting channel.
            </p>


            <dl className="queue-detail-list">

              <QueueDetail
                label="Destination"
                value={reportingJurisdiction}
              />

              <QueueDetail
                label="Submission Status"
                value={
                  dispatchRecorded
                    ? prettify(submissionStatus)
                    : "Pending dispatch"
                }
              />

              <QueueDetail
                label="PHR Acknowledgement"
                value={phrStatus}
              />

              <QueueDetail
                label="Submission Reference"
                value={
                  submission?.submission_id ||
                  "Pending dispatch"
                }
              />

            </dl>


            {simulatedDestination && (
              <p className="queue-simulation-note">
                The recorded destination is simulated
                and does not represent Texas DSHS.
              </p>
            )}

          </article>


          {/* Next Steps */}

          <article className="queue-card queue-next-card">

            <header className="queue-card-heading">

              <div>
                <span className="queue-eyebrow">
                  NEXT STEPS
                </span>

                <h3>
                  What Happens Next
                </h3>
              </div>

              <ClipboardCheck
                size={17}
                aria-hidden="true"
              />

            </header>


            <ol className="queue-next-list">

              <NextStep
                number="1"
                title="Super Admin Review"
                description="Package is reviewed before dispatch."
                state={nextReviewState}
              />

              <NextStep
                number="2"
                title="Dispatch to Texas DSHS"
                description="Authorized reporting staff transmit the package through the approved reporting channel."
                state={nextDispatchState}
              />

              <NextStep
                number="3"
                title="Texas PHR Acknowledgement"
                description="Receipt is recorded after public-health submission."
                state={nextAcknowledgementState}
              />

            </ol>

          </article>


          {/* Back */}

          <button
            type="button"
            className="queue-return-button"
            onClick={backToReview}
          >
            <ArrowLeft size={14} />
            Back to Review &amp; Validation
          </button>

        </aside>

      </main>


      {/* Footer */}

      <div className="queue-reference-note">

        <UserRoundCheck
          size={13}
          aria-hidden="true"
        />

        <span>
          SIGNAL returns the readiness reference
          and workflow status. No Texas DSHS
          submission is created on this page.
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