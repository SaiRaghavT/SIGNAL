import { useEffect, useState } from "react";
import { CheckCircle2, Clock3, FileText, RotateCw } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";
import { listFollowUps } from "../../api/followups.js";
import { getAdminQueueCase, getAdminSubmission } from "../../services/adminService.js";
import { cleanPatientName } from "../../utils/patientNames.js";
import "../../styles/AdminSubmissionAcknowledgement.css";

function value(value, fallback = "—") {
  return value === undefined || value === null || String(value).trim() === "" ? fallback : String(value);
}

function formatTimestamp(value) {
  if (!value) return "—";
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime())
    ? String(value)
    : timestamp.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
}

export default function AdminSubmissionAcknowledgement() {
  const { submissionId } = useParams();
  const location = useLocation();
  const [submission, setSubmission] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [followup, setFollowup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const record = await getAdminSubmission(submissionId);
        const caseId = record?.case_id || record?.case?.case_id;
        const [caseResult, followupResult] = await Promise.allSettled([
          caseId ? getAdminQueueCase(caseId) : Promise.resolve(null),
          listFollowUps({ search: submissionId, page_size: 100 }),
        ]);
        if (!active) return;
        setSubmission(record);
        setCaseData(caseResult.status === "fulfilled" ? caseResult.value : null);
        const followups = followupResult.status === "fulfilled"
          ? followupResult.value?.items || []
          : [];
        setFollowup(followups.find((item) => item.submission_id === submissionId) || null);
        if (followupResult.status === "rejected") {
          setError(followupResult.reason?.message || "Follow-up information could not be loaded.");
        }
      } catch (requestError) {
        if (active) setError(requestError?.message || "Submission acknowledgement could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [submissionId]);

  const dispatchResponse = location.state?.dispatchResponse;
  const status = String(submission?.status || dispatchResponse?.status || "UNKNOWN").toUpperCase();
  const isSubmitted = status === "SUBMITTED";
  const destination = submission?.destination || dispatchResponse?.destination;
  const warnings = submission?.warnings || dispatchResponse?.warnings || [];
  const simulated = /mock|simulat/i.test(String(destination || ""))
    || warnings.some((warning) => /mock|simulat/i.test(String(warning)));
  const patient = submission?.patient || caseData?.patient || {};
  const patientName = cleanPatientName(patient.name || [patient.first_name, patient.last_name].filter(Boolean).join(" "));
  const condition = caseData?.clinical_evidence?.diagnosis
    || caseData?.condition
    || submission?.disease;
  const followupError = location.state?.followupError;

  if (loading) {
    return <main className="admin-submission-ack-page"><div className="admin-ack-state">Loading submission acknowledgement…</div></main>;
  }

  if (!submission) {
    return (
      <main className="admin-submission-ack-page">
        <div className="admin-ack-error" role="alert">{error || "Submission not found."}</div>
        <Link className="admin-ack-secondary" to="/admin/submissions">Go to Admin Submissions</Link>
      </main>
    );
  }

  return (
    <main className="admin-submission-ack-page">
      <header className={`admin-ack-header ${isSubmitted ? "success" : "warning"}`}>
        <div className="admin-ack-icon">{isSubmitted ? <CheckCircle2 size={23} /> : <Clock3 size={23} />}</div>
        <div>
          <span className="admin-ack-eyebrow">ADMINISTRATOR / SUBMISSION</span>
          <h1>Submission Acknowledgement</h1>
          <p>{isSubmitted ? "The case has been authorized and submitted successfully." : `Submission status: ${status}`}</p>
        </div>
      </header>

      {simulated && (
        <div className="admin-ack-simulation" role="status">
          This submission used a simulated destination or follow-up. No real PHA transmission is claimed.
        </div>
      )}
      {error && <div className="admin-ack-inline-error" role="alert">{error}</div>}
      {followupError && <div className="admin-ack-inline-error" role="alert">{followupError}</div>}

      <div className="admin-ack-layout">
        <div className="admin-ack-main">
          <section className="admin-ack-card">
            <header><span>01</span><div><h2>Case Summary</h2><p>Case details retrieved from SIGNAL.</p></div></header>
            <dl className="admin-ack-grid">
              <div><dt>Patient</dt><dd>{value(patientName)}</dd></div>
              <div><dt>Case ID</dt><dd className="monospace">{value(submission.case_id)}</dd></div>
              <div><dt>Condition</dt><dd>{value(condition)}</dd></div>
              <div><dt>Jurisdiction</dt><dd>{value(caseData?.jurisdiction || submission.jurisdiction)}</dd></div>
              <div><dt>Submission Mode</dt><dd>{value(submission.submission_mode || caseData?.submission_mode)}</dd></div>
            </dl>
          </section>

          <section className="admin-ack-card" id="submission-details">
            <header><span>02</span><div><h2>Submission Details</h2><p>Backend-confirmed dispatch information.</p></div></header>
            <dl className="admin-ack-grid">
              <div><dt>Submission ID</dt><dd className="monospace">{value(submission.submission_id || submissionId)}</dd></div>
              <div><dt>Destination</dt><dd>{value(destination)}</dd></div>
              <div><dt>Submission Status</dt><dd><span className={`admin-ack-status ${isSubmitted ? "good" : "pending"}`}>{value(submission.status)}</span></dd></div>
              <div><dt>Submitted At</dt><dd>{formatTimestamp(submission.created_at || submission.submitted_at)}</dd></div>
              <div><dt>ECR ID</dt><dd className="monospace">{value(submission.ecr_id || dispatchResponse?.ecr_id)}</dd></div>
              <div><dt>Acknowledgement / Reference ID</dt><dd className="monospace">{value(submission.acknowledgement?.acknowledgement_id || submission.acknowledgement_id || dispatchResponse?.acknowledgement_id)}</dd></div>
            </dl>
            {warnings.length > 0 && <div className="admin-ack-warnings"><strong>Warnings</strong><ul>{warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul></div>}
          </section>

          <section className="admin-ack-card">
            <header><span>03</span><div><h2>PHA Follow-up</h2><p>Follow-up record from the existing SIGNAL service.</p></div></header>
            {followup ? (
              <dl className="admin-ack-grid">
                <div><dt>Status</dt><dd>{value(followup.status)}</dd></div>
                <div><dt>Action</dt><dd>{value(followup.action)}</dd></div>
                <div><dt>Next Action</dt><dd>{value(followup.next_action)}</dd></div>
                <div><dt>Due Date</dt><dd>{formatDate(followup.due_date)}</dd></div>
                <div><dt>Created At</dt><dd>{formatTimestamp(followup.created_at)}</dd></div>
                <div className="wide"><dt>Notes</dt><dd>{value(followup.notes)}</dd></div>
              </dl>
            ) : (
              <div className="admin-ack-followup-empty">No follow-up record is available for this submission.</div>
            )}
          </section>
        </div>

        <aside className="admin-ack-actions">
          <div className="admin-ack-action-card">
            <FileText size={20} />
            <h2>Next Steps</h2>
            <p>Review the persisted submission record or return to reporting operations.</p>
            <button type="button" className="admin-ack-primary" onClick={() => document.getElementById("submission-details")?.scrollIntoView({ behavior: "smooth", block: "start" })}>View Submission</button>
            <Link className="admin-ack-secondary" to="/admin/queue">Return to Queue</Link>
            <Link className="admin-ack-secondary" to="/admin/submissions">Go to Admin Submissions</Link>
          </div>
        </aside>
      </div>
    </main>
  );
}
