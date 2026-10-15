import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Clock3,
  FileCheck2,
  FileText,
  HeartPulse,
  MapPin,
  ShieldCheck,
  UserRound,
  AlertTriangle,
} from "lucide-react";

import {
  dispatchCase,
  getAdminQueueCase,
  simulateAdminDemoSubmission,
} from "../../services/adminService.js";

import { cleanPatientName } from "../../utils/patientNames.js";
import { apiBaseUrl } from "../../api/client.js";
import { SignalLoading } from "../../components/ui/SignalLoading.jsx";
import "../../styles/AdminImmediateReview.css";

function unwrapCase(result) {
  let value = result?.data ?? result;

  if (value?.case && typeof value.case === "object") {
    value = value.case;
  } else if (value?.record && typeof value.record === "object") {
    value = value.record;
  }

  return value;
}

function getField(object, ...keys) {
  for (const key of keys) {
    const value = object?.[key];

    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return null;
}

function getPatientRecord(data) {
  const candidate = unwrapCase(data);

  return (
    candidate?.patient ??
    candidate?.patientDetails ??
    candidate?.patient_details ??
    candidate?.canonicalPatient ??
    candidate?.canonical_patient ??
    candidate
  );
}

function getPatientName(data) {
  const record = getPatientRecord(data);

  const directName = getField(
    record,
    "patientName",
    "patient_name",
    "full_name",
    "patient_full_name",
    "display_name",
    "name"
  );

  if (typeof directName === "string") {
    return cleanPatientName(directName);
  }

  const firstName = getField(record, "first_name", "firstName");
  const lastName = getField(record, "last_name", "lastName");

  return (
    cleanPatientName([firstName, lastName].filter(Boolean).join(" ")) ||
    "—"
  );
}

function getPatientId(data) {
  const record = getPatientRecord(data);

  return (
    getField(
      record,
      "patientId",
      "patient_id",
      "patient_identifier",
      "mrn",
      "id"
    ) ?? "—"
  );
}

function getPatientDob(data) {
  const record = getPatientRecord(data);

  return (
    getField(
      record,
      "dob",
      "date_of_birth",
      "dateOfBirth",
      "birth_date",
      "birthDate"
    ) ?? "—"
  );
}

function getPatientSex(data) {
  const record = getPatientRecord(data);

  return getField(record, "sex", "gender", "administrative_gender") ?? "—";
}

function formatDate(value) {
  if (!value || value === "—") return "—";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
}

function formatDateTime(value) {
  if (!value || value === "—") return "—";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString();
}

function formatLabel(value) {
  return String(value ?? "—")
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatReviewStatus(value) {
  const status = String(value ?? "").trim().toUpperCase();
  if (status === "APPROVE" || status === "APPROVED") return "Approved";
  return formatLabel(value);
}

function display(value) {
  if (value === null || value === undefined || value === "") return "—";

  if (typeof value === "boolean") return value ? "Yes" : "No";

  if (Array.isArray(value)) {
    return value.length ? value.map(display).join(", ") : "—";
  }

  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => `${formatLabel(key)}: ${display(item)}`)
      .join("; ");
  }

  return String(value);
}

function getLabSummary(lab) {
  const test = getField(lab, "test_name", "testName", "test", "name");
  const observations = Array.isArray(lab.observations) ? lab.observations : [];
  const observedResults = observations
    .map((observation) => {
      const value = observation?.value;
      return getField(value, "text", "numeric", "code")
        ?? getField(observation, "result", "value_text", "value_numeric");
    })
    .filter((value) => value !== undefined && value !== null && String(value).trim());

  return {
    Test: typeof test === "object"
      ? getField(test, "display", "name", "code")
      : test,
    Result: getField(lab, "result", "conclusion") ?? [...new Set(observedResults.map(String))].join(", "),
    Status: getField(lab, "report_status", "status"),
    Specimen: getField(lab, "specimen", "specimen_type", "specimenType"),
    Date: getField(lab, "effective_time", "collection_date", "collected_at", "issued_time"),
  };
}

function Detail({ label, value }) {
  return (
    <div className="admin-immediate-detail">
      <span className="admin-immediate-detail-label">{label}:</span>
      <span className="admin-immediate-detail-value">{display(value)}</span>
    </div>
  );
}

function Section({ title, icon: Icon, complete = false, collapsible = false, children }) {
  const heading = (
    <div className="admin-immediate-section-heading">
      <div className="admin-immediate-section-title">
        {Icon && <Icon size={18} />}
        <h3>{title}</h3>
      </div>
      {complete && (
        <span className="admin-immediate-completeness">
          <span>All required fields are present</span>
          <Check className="admin-immediate-section-complete" size={18} aria-hidden="true" />
        </span>
      )}
    </div>
  );

  return (
    <section className="admin-immediate-section">
      {collapsible ? (
        <details className="admin-immediate-collapsible-section">
          <summary>{heading}</summary>
          <div className="admin-immediate-collapsible-content">{children}</div>
        </details>
      ) : <>{heading}{children}</>}
    </section>
  );
}

export default function AdminImmediateReview() {
  const navigate = useNavigate();
  const location = useLocation();
  const { caseId: routeCaseId } = useParams();

  const caseId =
    location.state?.caseData?.caseId ??
    location.state?.caseData?.case_id ??
    routeCaseId;

  const [backendCase, setBackendCase] = useState(null);
  const [patientLoading, setPatientLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadPatientDetails() {
      setPatientLoading(true);
      setError("");

      try {
        const result = await getAdminQueueCase(caseId);
        const loadedCase = unwrapCase(result);
        if (!loadedCase || typeof loadedCase !== "object") {
          throw new Error("The Admin API returned no case details.");
        }

        if (active) {
          setBackendCase(loadedCase);
        }
      } catch (error) {
        console.error("Unable to load patient details:", error);

        if (active) {
          setBackendCase(null);
          setError(error?.message || "Unable to load this case from the Admin API.");
        }
      } finally {
        if (active) {
          setPatientLoading(false);
        }
      }
    }

    if (caseId) {
      loadPatientDetails();
    } else {
      setBackendCase(null);
      setError("The selected case does not have a case ID.");
      setPatientLoading(false);
    }

    return () => {
      active = false;
    };
  }, [caseId]);

  const caseData = backendCase ?? {};

  const patientName = patientLoading
    ? "Loading…"
    : getPatientName(backendCase);

  const patientId = patientLoading
    ? "Loading…"
    : getPatientId(backendCase);

  const patientDob = patientLoading
    ? "Loading…"
    : getPatientDob(backendCase);

  const patientSex = patientLoading
    ? "Loading…"
    : getPatientSex(backendCase);

  const condition =
    getField(caseData, "condition", "disease_name", "disease") ?? "—";

  const jurisdiction =
    getField(caseData, "jurisdiction", "state") ?? "—";

  const allFieldsPresent = Boolean(caseData.validation?.valid)
    && !(caseData.missing_information || []).length;

  const laboratoryEvidence = getField(caseData, "laboratory_evidence", "laboratoryEvidence") ?? [];
  const seenLaboratoryRecords = new Set();
  const laboratoryItems = (Array.isArray(laboratoryEvidence) ? laboratoryEvidence : [laboratoryEvidence])
    .filter((item) => item && typeof item === "object")
    .map(getLabSummary)
    // Clinical notes can be stored alongside observations, but are not lab tests.
    .filter((summary) => !String(summary.Test ?? "").toLowerCase().includes("note"))
    .filter((summary) => Object.values(summary).some((value) => value !== undefined && value !== null && String(value).trim()))
    .sort((left, right) => new Date(right.Date ?? 0).getTime() - new Date(left.Date ?? 0).getTime())
    .filter((summary) => {
      const key = String(summary.Test ?? JSON.stringify(summary)).trim().toLowerCase();
      if (seenLaboratoryRecords.has(key)) return false;
      seenLaboratoryRecords.add(key);
      return true;
    })
    .slice(0, 5);
  const aiEvidence = getField(caseData, "aiEvidence", "ai_evidence") ?? {};
  const aiInfoItems = Object.entries(aiEvidence)
    .filter(([key, value]) => /confidence|model|decision|status/i.test(key)
      && (typeof value === "string" || typeof value === "number" || typeof value === "boolean"))
    .slice(0, 3);

  const handleAuthorizeAndSubmit = async () => {
    if (submitting) return;

    if (!caseId) {
      setError("Cannot submit: case ID is missing.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const response = caseData.demo_submission
        ? await simulateAdminDemoSubmission(caseId)
        : await dispatchCase(caseId);

      const result =
        response?.submission ??
        response?.data?.submission ??
        response?.data ??
        response;

      const status = String(result?.status ?? "").toUpperCase();

      if (status !== "SUBMITTED") {
        const errors = Array.isArray(result?.errors)
          ? result.errors.join("; ")
          : "";

        throw new Error(
          errors || "The backend did not confirm successful submission."
        );
      }

      const submissionId =
        result?.submission_id ??
        result?.submissionId ??
        response?.submission_id ??
        response?.data?.submission_id;

      if (!submissionId) {
        throw new Error(
          "The backend response did not contain a submission ID."
        );
      }

      const submission = {
        ...result,
        submissionId,
        submission_id: submissionId,
        caseId,
        case_id: caseId,
        patientName,
        patientId,
        condition,
        jurisdiction,
        status,
        submittedAt:
          result?.submitted_at ??
          result?.created_at ??
          new Date().toISOString(),
        mode:
          getField(caseData, "reportingMode", "reporting_mode", "mode") ??
          "Immediate",
      };

      navigate(
        `/admin/submission-journey/${encodeURIComponent(submissionId)}`,
        {
          state: {
            submission,
            caseData,
            dispatchResponse: response,
          },
        }
      );
    } catch (err) {
      console.error("Admin dispatch failed:", err);

      setError(
        err?.response?.data?.detail ??
          err?.message ??
          "Unable to authorize and submit the case."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (patientLoading) {
    return (
      <div className="admin-immediate-review-page">
        <header className="admin-immediate-review-header">
          <button
            type="button"
            className="admin-immediate-back-button"
            onClick={() => navigate("/admin/queue")}
          >
            <ArrowLeft size={16} />
            Back to Queue
          </button>

          <div className="admin-immediate-review-title-row">
            <div>
              <span className="admin-immediate-eyebrow">
                SIGNAL / ADMINISTRATOR
              </span>
              <h1>Immediate Reporting Review</h1>
              <p>Review the reporting evidence before authorization.</p>
            </div>
          </div>
        </header>

        <SignalLoading
          title="Loading Immediate Review"
          message="Retrieving patient details and immediate reporting evidence."
        />
      </div>
    );
  }
    return (
    <div className="admin-immediate-review-page">
      <header className="admin-immediate-review-header">
        <button
          type="button"
          className="admin-immediate-back-button"
          onClick={() => navigate("/admin/queue")}
        >
          <ArrowLeft size={16} />
          Back to Queue
        </button>

        <div className="admin-immediate-review-title-row">
          <div>
            <span className="admin-immediate-eyebrow">
              SIGNAL / ADMINISTRATOR
            </span>
            <h1>Immediate Reporting Review</h1>
            <p>Review the reporting evidence before authorization.</p>
          </div>

          <span className="admin-immediate-status-badge">
            <Clock3 size={14} />
            {formatReviewStatus(
              getField(caseData, "reviewStatus", "review_status", "status") ??
                "Pending Review"
            )}
          </span>
        </div>
      </header>

      <div className="admin-immediate-case-banner">
        <div className="admin-immediate-case-icon">
          <HeartPulse size={24} />
        </div>

        <div className="admin-immediate-case-main">
          <span className="admin-immediate-case-id">{caseId}</span>
          <h2>{condition}</h2>
          <p>
            {patientName} · {patientId}
          </p>
        </div>

        <div className="admin-immediate-case-badges">
          <span className="admin-immediate-priority-badge">
            <AlertTriangle size={14} />
            {formatLabel(
              getField(caseData, "priority", "severity") ?? "—"
            )}
          </span>
        </div>
      </div>

      {error && (
        <div role="alert" className="admin-immediate-error">
          {error}
        </div>
      )}

      {submitting && (
        <SignalLoading
          title="Authorizing Case"
          message="Authorizing and preparing immediate report submission."
        />
      )}

      <div className="admin-immediate-review-grid">
        <div className="admin-immediate-review-main">
          <Section title="Patient Information" icon={UserRound}>
            <div className="admin-immediate-details-grid">
              <Detail label="Patient Name" value={patientName} />
              <Detail label="Patient ID" value={patientId} />
              <Detail label="Date of Birth" value={formatDate(patientDob)} />
              <Detail label="Sex" value={patientSex} />
            </div>
          </Section>

          <Section title="Candidate Evidence" icon={HeartPulse} complete={allFieldsPresent} collapsible>
            <div className="admin-immediate-details-grid">
              <Detail label="Condition" value={condition} />
              <Detail label="Reportability decision" value={formatLabel(getField(caseData, "reportability", "reportability_decision"))} />
              <Detail label="Reporting rule" value={getField(caseData, "rule_id", "reportingRule", "reporting_rule")} />
              <Detail label="Clinical Staff review status" value={formatReviewStatus(getField(caseData, "review_status", "reviewStatus"))} />
            </div>
          </Section>

          <Section title="Laboratory Evidence" icon={FileText} complete={allFieldsPresent} collapsible>
            <div className="admin-immediate-lab-list">
              {laboratoryItems.length ? laboratoryItems.map((summary, index) => (
                <details className="admin-immediate-lab-record" key={`lab-${index}`}>
                  <summary>
                    <strong>{display(summary.Test)}</strong>
                    <span>{display(summary.Status)}</span>
                    <time>{formatDateTime(summary.Date)}</time>
                  </summary>
                  <div className="admin-immediate-details-grid">
                    {Object.entries(summary).filter(([, value]) => value !== undefined && value !== null && String(value).trim()).map(([label, value]) => (
                      <Detail key={`${index}-${label}`} label={label} value={label === "Date" ? formatDateTime(value) : value} />
                    ))}
                  </div>
                </details>
              )) : <p>No laboratory evidence is available for this case.</p>}
            </div>
          </Section>

          <Section title="AI Detection Evidence" icon={ShieldCheck} complete={allFieldsPresent} collapsible>
            {aiInfoItems.length ? (
              <div className="admin-immediate-details-grid">
                {aiInfoItems.map(([key, value]) => (
                  <Detail key={key} label={formatLabel(key)} value={value} />
                ))}
              </div>
            ) : <p>No concise AI details are available for this case.</p>}
          </Section>

          <Section title="Reporting Form" icon={FileCheck2}>
            {caseData.report?.document_url ? (
              <div className="admin-immediate-report-document">
                <p>{caseData.report.form_id} · Version {caseData.report.form_version || "Not recorded"}</p>
                <a href={`${apiBaseUrl}${caseData.report.document_url}`} target="_blank" rel="noreferrer">
                  Open patient reporting form
                </a>
              </div>
            ) : (
              <p className="admin-immediate-report-empty">No generated reporting form is available for this case.</p>
            )}
          </Section>
        </div>

        <aside className="admin-immediate-review-sidebar">
          <Section title="Reportability Decision" icon={ShieldCheck}>
            <div className="admin-immediate-decision-value">
              {formatLabel(
                getField(
                  caseData,
                  "reportability",
                  "reportabilityDecision",
                  "reportability_decision"
                ) ?? "Pending Review"
              )}
            </div>

            <Detail
              label="Reporting Rule"
              value={getField(caseData, "rule_id", "reportingRule", "reporting_rule")}
            />

            <Detail
              label="Human Review Status"
              value={formatReviewStatus(getField(caseData, "review_status", "reviewStatus"))}
            />
          </Section>

          <Section title="Jurisdiction" icon={MapPin}>
            <Detail label="State" value={jurisdiction} />

            <Detail
              label="Health Department"
              value="DSHS"
            />

            <Detail
              label="Reporting Deadline"
              value={formatDateTime(
                getField(
                  caseData,
                  "deadline",
                  "reportingDeadline",
                  "reporting_deadline"
                )
              )}
            />
          </Section>

          <Section title="Authorization" icon={FileCheck2}>
            <p className="admin-immediate-authorization-copy">
              Authorize this case to submit its reporting package through the configured reporting channel.
            </p>

            <button
              type="button"
              className="admin-immediate-authorize-button"
              onClick={handleAuthorizeAndSubmit}
              disabled={submitting || !backendCase}
            >
              <CheckCircle2 size={17} />
              {submitting ? "Submitting..." : "Authorize & Submit"}
            </button>

          </Section>
        </aside>
      </div>
    </div>
  );
}
