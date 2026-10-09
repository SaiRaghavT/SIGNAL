
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
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
import { getAdminQueueCase } from "../../services/adminService.js";
import "../../styles/AdminImmediateReview.css";

const DEMO_CASE_DETAILS = {
  "MEASLES-001": {
    condition: "Measles",
    jurisdiction: "Texas",
    healthDepartment: "Texas Department of State Health Services",
    priority: "Urgent",
    reportingMode: "Immediate",
    status: "READY_FOR_REVIEW",
    deadline: "2026-10-10T09:00:00",
    reportability: "REPORT",
    reportingRule: "MEASLES-TX",
    evidenceStatus: "VALID",
    clinicalEvidence: {
      symptoms: ["Fever", "Cough", "Rash"],
      rashOnsetDate: "2026-10-07",
      clinicalAssessment: "Suspected measles",
    },
    laboratoryEvidence: {
      testName: "Measles IgM",
      result: "Positive",
      resultStatus: "LAB_POSITIVE",
    },
    detectionEvidence: {
      candidateDetected: true,
      confidence: "High",
      explanation:
        "Clinical symptoms and a positive measles IgM result support review for measles reporting.",
    },
    reportFields: {
      condition: "Measles",
      jurisdiction: "Texas",
      rashOnsetDate: "2026-10-07",
    },
    validation: {
      status: "VALID",
      errors: [],
      missingInformation: [],
    },
    reviewStatus: "PENDING_REVIEW",
  },
  "RABIES-002": {
    condition: "Rabies exposure",
    jurisdiction: "Texas",
    healthDepartment: "Texas Department of State Health Services",
    priority: "High",
    reportingMode: "Immediate",
    status: "READY_FOR_REVIEW",
    deadline: "2026-10-10T12:00:00",
    reportability: "REVIEW",
    reportingRule: "RABIES-TX",
    evidenceStatus: "VALID",
    clinicalEvidence: {
      symptoms: ["Animal exposure"],
      exposureDate: "2026-10-08",
      clinicalAssessment: "Possible rabies exposure",
    },
    laboratoryEvidence: {
      testName: "Rabies testing",
      result: "Not available",
      resultStatus: "NOT_AVAILABLE",
    },
    detectionEvidence: {
      candidateDetected: true,
      confidence: "Medium",
      explanation:
        "Reported animal exposure requires clinical review and jurisdiction-specific assessment.",
    },
    reportFields: {
      condition: "Rabies exposure",
      jurisdiction: "Texas",
      exposureDate: "2026-10-08",
    },
    validation: {
      status: "VALID",
      errors: [],
      missingInformation: [],
    },
    reviewStatus: "PENDING_REVIEW",
  },
};

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

  if (typeof directName === "string") return directName;

  const firstName = getField(record, "first_name", "firstName");
  const lastName = getField(record, "last_name", "lastName");

  return [firstName, lastName].filter(Boolean).join(" ") || "—";
}

function getPatientId(data) {
  const record = getPatientRecord(data);

  return getField(
    record,
    "patientId",
    "patient_id",
    "patient_identifier",
    "mrn",
    "id"
  ) ?? "—";
}

function getPatientDob(data) {
  const record = getPatientRecord(data);

  return getField(
    record,
    "dob",
    "date_of_birth",
    "dateOfBirth",
    "birth_date",
    "birthDate"
  ) ?? "—";
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

function Detail({ label, value }) {
  return (
    <div className="admin-immediate-detail">
      <span className="admin-immediate-detail-label">{label}</span>
      <span className="admin-immediate-detail-value">{display(value)}</span>
    </div>
  );
}

function EvidenceRows({ data }) {
  return (
    <div className="admin-immediate-evidence-rows">
      {Object.entries(data ?? {}).map(([key, value]) => (
        <div className="admin-immediate-evidence-row" key={key}>
          <span className="admin-immediate-evidence-label">
            {formatLabel(key)}
          </span>
          <div className="admin-immediate-evidence-value">
            {display(value)}
          </div>
        </div>
      ))}
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <section className="admin-immediate-section">
      <div className="admin-immediate-section-heading">
        {Icon && <Icon size={18} />}
        <h3>{title}</h3>
      </div>
      {children}
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

  useEffect(() => {
    let active = true;

    async function loadPatientDetails() {
      setPatientLoading(true);

      try {
        const result = await getAdminQueueCase(caseId);

        if (active) {
          setBackendCase(unwrapCase(result));
        }
      } catch (error) {
        console.error("Unable to load patient details:", error);

        if (active) {
          setBackendCase(null);
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
      setPatientLoading(false);
    }

    return () => {
      active = false;
    };
  }, [caseId]);

  const caseData = useMemo(() => {
    const staticDetails =
      DEMO_CASE_DETAILS[caseId] ?? DEMO_CASE_DETAILS["MEASLES-001"];

    const passedCase = location.state?.caseData ?? {};

    // Backend values may supply real case fields; demo details fill gaps.
    return {
      ...staticDetails,
      ...passedCase,
      ...(backendCase ?? {}),
    };
  }, [caseId, location.state, backendCase]);

  // Demographics come from the backend response only.
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

  const clinicalEvidence =
    getField(caseData, "clinicalEvidence", "clinical_evidence") ?? {};

  const laboratoryEvidence =
    getField(caseData, "laboratoryEvidence", "laboratory_evidence") ?? {};

  const detectionEvidence =
    getField(caseData, "detectionEvidence", "detection_evidence") ??
    getField(caseData, "aiEvidence", "ai_evidence") ??
    {};

  const reportFields =
    getField(caseData, "reportFields", "report_fields") ?? {};


  const condition =
    getField(caseData, "condition", "disease_name", "disease") ?? "—";

  const jurisdiction =
    getField(caseData, "jurisdiction", "state") ?? "Texas";

  const handleAuthorizeAndSubmit = () => {
    const submissionId = `SUB-DEMO-${Date.now()}`;

    const submission = {
      submissionId,
      caseId,
      patientName,
      patientId,
      condition,
      jurisdiction,
      status: "SUBMITTED",
      submittedAt: new Date().toISOString(),
      mode: getField(caseData, "reportingMode", "reporting_mode", "mode") ??
        "Immediate",
      demo: true,
    };

    navigate(
      `/admin/submission-journey/${encodeURIComponent(submissionId)}`,
      {
        state: {
          submission,
          caseData,
        },
      }
    );
  };

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
            {formatLabel(
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
          <p>{patientName} · {patientId}</p>
        </div>

        <div className="admin-immediate-case-badges">
          <span className="admin-immediate-priority-badge">
            <AlertTriangle size={14} />
            {formatLabel(getField(caseData, "priority", "severity") ?? "Urgent")}
          </span>
        </div>
      </div>

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

          <Section title="Clinical Evidence" icon={HeartPulse}>
            <EvidenceRows data={clinicalEvidence} />
          </Section>

          <Section title="Laboratory Evidence" icon={FileText}>
            <EvidenceRows data={laboratoryEvidence} />
          </Section>

          <Section title="AI Detection Evidence" icon={ShieldCheck}>
            <EvidenceRows data={detectionEvidence} />
          </Section>

          <Section title="Reporting Form Fields" icon={FileCheck2}>
            <EvidenceRows data={reportFields} />
          </Section>

          
        </div>

        <aside className="admin-immediate-review-sidebar">
          <Section title="Reportability Decision" icon={ShieldCheck}>
            <div className="admin-immediate-decision-value">
              {formatLabel(
                getField(caseData, "reportability", "reportabilityDecision",
                  "reportability_decision") ?? "Pending Review"
              )}
            </div>

            <Detail
              label="Reporting Rule"
              value={getField(caseData, "reportingRule", "reporting_rule")}
            />
            <Detail
              label="Evidence Status"
              value={getField(caseData, "evidenceStatus", "evidence_status")}
            />
          </Section>

          <Section title="Jurisdiction" icon={MapPin}>
            <Detail label="State" value={jurisdiction} />
            <Detail
              label="Health Department"
              value={getField(caseData, "healthDepartment", "health_department")}
            />
            <Detail
              label="Reporting Deadline"
              value={formatDateTime(
                getField(caseData, "deadline", "reportingDeadline",
                  "reporting_deadline")
              )}
            />
          </Section>

          <Section title="Authorization" icon={FileCheck2}>
            <p className="admin-immediate-authorization-copy">
              Authorize this case to continue through the local demo
              submission journey. No external report will be transmitted.
            </p>

            <button
              type="button"
              className="admin-immediate-authorize-button"
              onClick={handleAuthorizeAndSubmit}
            >
              <CheckCircle2 size={17} />
              Authorize &amp; Submit
            </button>

            <p className="admin-immediate-demo-note">
              Demo mode · No external transmission
            </p>
          </Section>
        </aside>
      </div>
    </div>
  );
}
