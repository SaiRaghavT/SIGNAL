import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, ChevronDown, Clock3, FileCheck2, Layers3, RefreshCw } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { dispatchAdminBatch, getAdminBatch, getAdminQueueCase } from "../../services/adminService.js";
import "../../styles/AdminBatchReview.css";

const DASH = "—";

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function textValue(value, fallback = DASH) {
  return value === undefined || value === null || String(value).trim() === "" ? fallback : String(value);
}

function formatLabel(value) {
  return String(value).replace(/([a-z0-9])([A-Z])/g, "$1 $2").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayValue(value) {
  if (value === undefined || value === null || value === "") return DASH;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.map(displayValue).join(", ") : DASH;
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${formatLabel(key)}: ${displayValue(item)}`).join(" · ") || DASH;
  return String(value);
}

function timestamp(value) {
  if (!value) return DASH;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function caseIdOf(item) {
  return item?.case_id || item?.caseId || item?.id || "";
}

function patientNameOf(item) {
  const patient = objectValue(item?.patient);
  return item?.patient_name || item?.patientName || patient.name || [patient.first_name, patient.last_name].filter(Boolean).join(" ") || DASH;
}

function caseIdsOf(batch) {
  if (Array.isArray(batch?.case_ids)) return batch.case_ids.map((item) => typeof item === "string" ? item : caseIdOf(item)).filter(Boolean);
  if (Array.isArray(batch?.caseIds)) return batch.caseIds.map((item) => typeof item === "string" ? item : caseIdOf(item)).filter(Boolean);
  if (Array.isArray(batch?.cases)) return batch.cases.map(caseIdOf).filter(Boolean);
  return [];
}

function caseIsReady(item) {
  const missing = Array.isArray(item?.missing_information) ? item.missing_information : [];
  return missing.length === 0
    && Boolean(item?.report_id)
    && String(item?.review_status || "").toUpperCase() === "APPROVE"
    && String(item?.attestation_status || "").toUpperCase() === "ATTESTED"
    && ["QUEUED", "READY_FOR_SUBMISSION"].includes(String(item?.queue_status || "").toUpperCase());
}

function isInvalid(item) {
  const state = String(item?.reportability || item?.case_status || "").toUpperCase();
  return ["INVALID", "NOT_REPORTABLE", "REJECTED", "REJECT"].includes(state);
}

function EvidenceRows({ title, data }) {
  const values = Array.isArray(data)
    ? data.map((entry, index) => [`Entry ${index + 1}`, entry])
    : Object.entries(objectValue(data));
  return (
    <section className="batch-evidence-section">
      <h4>{title}</h4>
      {values.length ? <dl>{values.map(([key, value], index) => <div key={`${key}-${index}`}><dt>{Array.isArray(data) ? key : formatLabel(key)}</dt><dd>{displayValue(value)}</dd></div>)}</dl> : <p className="batch-muted">No data available.</p>}
    </section>
  );
}

function normalizeDispatchResult(response, caseIds) {
  const results = Array.isArray(response?.results) ? response.results : [];
  return results.map((result, index) => ({
    ...result,
    case_id: result?.case_id || result?.caseId || caseIds[index] || "",
    submission_id: result?.submission_id || result?.submissionId || "",
  }));
}

export default function AdminBatchReview() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const [batch, setBatch] = useState(null);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dispatching, setDispatching] = useState(false);
  const [error, setError] = useState("");
  const [dispatchResult, setDispatchResult] = useState(null);

  const loadBatch = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const batchResponse = await getAdminBatch(batchId);
      setBatch(batchResponse);
      const ids = caseIdsOf(batchResponse);
      const detailed = await Promise.all(ids.map(async (id) => {
        try {
          return await getAdminQueueCase(id);
        } catch (loadError) {
          return { case_id: id, detail_error: loadError?.message || "Case details could not be loaded." };
        }
      }));
      setCases(detailed);
    } catch (loadError) {
      setError(loadError?.message || "Unable to load this batch.");
      setBatch(null);
      setCases([]);
    } finally {
      setLoading(false);
    }
  }, [batchId]);

  useEffect(() => { loadBatch(); }, [loadBatch]);

  const stats = useMemo(() => {
    const missingCases = cases.filter((item) => Array.isArray(item?.missing_information) && item.missing_information.length > 0).length;
    const missingFields = cases.reduce((total, item) => total + (Array.isArray(item?.missing_information) ? item.missing_information.length : 0), 0);
    const validCases = cases.filter((item) => !item?.detail_error && !isInvalid(item) && Array.isArray(item?.missing_information) && item.missing_information.length === 0).length;
    return {
      total: caseIdsOf(batch).length,
      valid: validCases,
      missingCases,
      missingFields,
      ready: cases.filter(caseIsReady).length,
      invalid: cases.filter(isInvalid).length,
    };
  }, [batch, cases]);

  const destination = textValue(
    batch?.destination || batch?.destination_name || batch?.destinationName ||
    dispatchResult?.destination || dispatchResult?.results?.find((item) => item?.destination)?.destination,
  );
  const condition = textValue(batch?.condition || batch?.disease || batch?.disease_name || batch?.diseaseName);
  const reportingWindow = textValue(batch?.reporting_window || batch?.reportingWindow || batch?.window || batch?.date_range || batch?.dateRange);
  const status = textValue(batch?.status || batch?.batch_status || batch?.batchStatus);
  const batchIdValue = textValue(batch?.batch_id || batch?.batchId || batchId);
  const displayBatchId = textValue(batch?.display_batch_id || batch?.displayBatchId);
  const hasLinkedCases = caseIdsOf(batch).length > 0;
  const isPending = String(status).toUpperCase() === "PENDING";
  const results = dispatchResult?.results || [];
  const successfulResults = results.filter((result) => String(result?.status || "").toUpperCase() === "SUBMITTED");
  const failedResults = results.filter((result) => String(result?.status || "").toUpperCase() !== "SUBMITTED");
  const warningItems = [
    ...(dispatchResult?.warnings || []).map((message) => ({ caseId: "", message })),
    ...results.flatMap((result) => (result?.warnings || []).map((message) => ({ caseId: result.case_id, message }))),
  ];
  const errorItems = (dispatchResult?.errors || []).map((message) => ({ caseId: "", message }));

  async function handleDispatch() {
    setDispatching(true);
    setError("");
    try {
      const response = await dispatchAdminBatch(batchId);
      const normalizedResults = normalizeDispatchResult(response, caseIdsOf(batch));
      const confirmedSuccesses = normalizedResults.filter((item) => String(item?.status || "").toUpperCase() === "SUBMITTED");
      const result = { ...response, results: normalizedResults };
      setDispatchResult(result);
      setBatch((current) => ({ ...current, ...response }));
      if (confirmedSuccesses.length === 1 && confirmedSuccesses[0]?.submission_id) {
        navigate(`/admin/submission-journey/${encodeURIComponent(confirmedSuccesses[0].submission_id)}`);
      }
    } catch (dispatchError) {
      setError(dispatchError?.message || "Batch dispatch failed. The database queue record is still available for review.");
    } finally {
      setDispatching(false);
    }
  }

  if (loading) return <main className="admin-batch-review-page"><div className="batch-state"><RefreshCw className="batch-spin" size={20} /> Loading batch review…</div></main>;
  if (!batch) return <main className="admin-batch-review-page"><button className="batch-back" type="button" onClick={() => navigate("/admin/queue")}><ArrowLeft size={16} /> Return to Queue</button><div className="batch-alert error" role="alert">{error || "Batch not found."}</div></main>;

  return (
    <main className="admin-batch-review-page">
      <div className="batch-topbar"><button className="batch-back" type="button" onClick={() => navigate("/admin/queue")}><ArrowLeft size={16} /> Reporting Queue</button><span>Reporting Queue <b>›</b> Batch Review</span></div>
      <header className="batch-header">
        <div><div className="batch-eyebrow">ADMINISTRATOR / BATCH REPORTING</div><h1>Batch Review</h1><p>Review the backend-generated reporting batch before authorization and dispatch.</p></div>
        <div className="batch-id"><span>BATCH RECORD ID</span><strong>{batchIdValue}</strong></div>
      </header>

      {error && <div className="batch-alert error" role="alert">{error}</div>}

      <section className="batch-summary" aria-label="Batch summary">
        <div><span>Batch ID</span><strong>{batchIdValue}</strong></div>
        {displayBatchId !== DASH && <div><span>Batch Label</span><strong>{displayBatchId}</strong></div>}
        <div><span>Destination</span><strong>{destination}</strong></div>
        <div><span>Condition</span><strong>{condition}</strong></div>
        <div><span>Reporting Window</span><strong>{reportingWindow}</strong></div>
        <div><span>Status</span><strong>{status}</strong></div>
      </section>

      <section className="batch-kpis">
        <article><span>Cases</span><strong>{stats.total}</strong></article>
        <article><span>Valid Cases</span><strong>{stats.valid}</strong></article>
        <article className={stats.missingCases ? "warning" : "good"}><span>Cases With Missing Information</span><strong>{stats.missingCases}</strong></article>
        <article><span>Ready for Submission</span><strong>{stats.ready}</strong></article>
      </section>

      {dispatchResult && (
        <section className={`batch-dispatch-result ${failedResults.length ? "partial" : "success"}`} aria-live="polite">
          <h2>{failedResults.length ? "Batch dispatch completed with failures" : "Batch dispatch completed"}</h2>
          <dl>
            <div><dt>Batch ID</dt><dd>{textValue(dispatchResult.batch_id || batchIdValue)}</dd></div>
            <div><dt>Batch Status</dt><dd>{textValue(dispatchResult.status)}</dd></div>
            <div><dt>Cases Submitted</dt><dd>{successfulResults.length} of {stats.total}</dd></div>
            <div><dt>Destination</dt><dd>{destination}</dd></div>
          </dl>
          {successfulResults.length > 0 && <div className="batch-result-list"><strong>Submission IDs</strong><ul>{successfulResults.map((item, index) => <li key={item.submission_id || index}><span>{textValue(item.case_id)}</span>{item.submission_id ? <Link to={`/admin/submission-journey/${encodeURIComponent(item.submission_id)}`}><code>{item.submission_id}</code></Link> : <code>{textValue(item.submission_id)}</code>}</li>)}</ul></div>}
          {failedResults.length > 0 && <div className="batch-result-list errors"><strong>Cases not submitted</strong><ul>{failedResults.map((item, index) => <li key={`${item.case_id}-${index}`}><span>{textValue(item.case_id)} · {textValue(item.status)}</span><p>{(item.errors || []).map(displayValue).join("; ") || "The backend did not confirm submission for this case."}</p></li>)}</ul></div>}
          {errorItems.length > 0 && <div className="batch-result-list errors"><strong>Errors</strong><ul>{errorItems.map((item, index) => <li key={`${item.caseId}-${index}`}><span>{textValue(item.caseId)}</span><p>{displayValue(item.message)}</p></li>)}</ul></div>}
          {warningItems.length > 0 && <div className="batch-result-list"><strong>Warnings</strong><ul>{warningItems.map((item, index) => <li key={`${item.caseId}-${index}`}><span>{textValue(item.caseId)}</span><p>{displayValue(item.message)}</p></li>)}</ul></div>}
          <p className="batch-muted">This summary reflects backend submission results. It does not assert receipt by a public health authority.</p>
        </section>
      )}

      <div className="batch-layout">
        <div className="batch-main">
          <section className="batch-card">
            <header className="batch-card-header"><div><Layers3 size={19} /><div><h2>Included Cases</h2><p>Each case remains individually identifiable and read-only.</p></div></div><span>{stats.total} cases</span></header>
            {cases.length === 0 ? <div className="batch-empty">This backend batch does not contain any case IDs.</div> : (
              <div className="batch-table-wrap"><table className="batch-table"><thead><tr><th>Patient</th><th>Case ID</th><th>Condition</th><th>Jurisdiction</th><th>Deadline</th><th>Priority</th><th>Status</th><th>Review Status</th><th>Attestation Status</th><th>Details</th></tr></thead>
                <tbody>{cases.map((item) => {
                  const id = caseIdOf(item);
                  const mode = String(item?.submission_mode || "").toUpperCase();
                  const reviewPath = mode === "IMMEDIATE" ? `/admin/queue/${encodeURIComponent(id)}/immediate` : mode === "INDIVIDUAL" ? `/admin/queue/${encodeURIComponent(id)}/individual` : null;
                  return <tr key={id}>
                    <td>{patientNameOf(item)}</td><td><code>{textValue(id)}</code></td><td>{textValue(item?.condition || item?.disease)}</td><td>{textValue(item?.jurisdiction)}</td><td>{timestamp(item?.deadline)}</td><td>{textValue(item?.priority || item?.severity)}</td><td><span className="batch-status">{textValue(item?.case_status || item?.queue_status)}</span></td><td>{textValue(item?.review_status)}</td><td>{textValue(item?.attestation_status)}</td>
                    <td><details className="batch-case-details"><summary><ChevronDown size={14} /> View</summary>
                      {item?.detail_error ? <p className="batch-alert error">{item.detail_error}</p> : <>
                        {reviewPath && <Link className="batch-case-link" to={reviewPath}>Open case review</Link>}
                        <dl className="batch-case-facts"><div><dt>Reportability</dt><dd>{textValue(item?.reportability)}</dd></div><div><dt>Submission Mode</dt><dd>{textValue(item?.submission_mode)}</dd></div><div><dt>Queue Status</dt><dd>{textValue(item?.queue_status)}</dd></div><div><dt>Report ID</dt><dd>{textValue(item?.report_id)}</dd></div></dl>
                        {Array.isArray(item?.missing_information) && item.missing_information.length > 0 && <div className="batch-missing"><strong>Missing Information</strong><ul>{item.missing_information.map((missing, index) => <li key={`${missing}-${index}`}>{displayValue(missing)}</li>)}</ul></div>}
                        <EvidenceRows title="Clinical Evidence" data={item?.clinical_evidence} />
                        <EvidenceRows title="Laboratory Evidence" data={item?.laboratory_evidence} />
                        <EvidenceRows title="AI Evidence" data={item?.ai_evidence} />
                        <EvidenceRows title="Reporting Data" data={item?.report_fields} />
                      </>}
                    </details></td>
                  </tr>;
                })}</tbody>
              </table></div>
            )}
          </section>

          <section className="batch-card batch-validation-card">
            <header className="batch-card-header"><div><FileCheck2 size={19} /><div><h2>Validation Summary</h2><p>Readiness derived from each included Case record.</p></div></div></header>
            <dl className="batch-validation-grid">
              <div><dt>Total Cases</dt><dd>{stats.total}</dd></div><div><dt>Ready Cases</dt><dd>{stats.ready}</dd></div><div><dt>Missing Information Count</dt><dd>{stats.missingFields}</dd></div><div><dt>Invalid Cases</dt><dd>{stats.invalid}</dd></div>
              <div><dt>Review State</dt><dd>{cases.filter((item) => String(item?.review_status || "").toUpperCase() === "APPROVE").length} approved / {stats.total}</dd></div><div><dt>Attestation State</dt><dd>{cases.filter((item) => String(item?.attestation_status || "").toUpperCase() === "ATTESTED").length} attested / {stats.total}</dd></div>
            </dl>
          </section>
        </div>

        <aside className="batch-sidebar">
          <section className="batch-auth-card"><div className="batch-auth-icon"><FileCheck2 size={20} /></div><span>AUTHORIZATION</span><h2>Batch Authorization Required</h2><p>Authorize dispatch for this backend-generated batch.</p>
            <dl><div><dt>Destination</dt><dd>{destination}</dd></div><div><dt>Batch ID</dt><dd>{batchIdValue}</dd></div><div><dt>Cases</dt><dd>{stats.total}</dd></div><div><dt>Status</dt><dd>{status}</dd></div></dl>
            {dispatchResult && <div className="batch-dispatch-count"><CheckCircle2 size={16} /> {successfulResults.length} case submissions confirmed</div>}
            {!hasLinkedCases && <div className="batch-alert warning">This batch record has no linked Case IDs, so it cannot be dispatched.</div>}
            <button type="button" className="batch-primary" onClick={handleDispatch} disabled={!isPending || !hasLinkedCases || dispatching || Boolean(dispatchResult)}>{dispatching ? "Dispatching batch…" : dispatchResult ? "BATCH DISPATCHED" : "AUTHORIZE & SUBMIT BATCH"}</button>
            <button type="button" className="batch-secondary" onClick={() => navigate("/admin/queue")} disabled={dispatching}>Return to Queue</button>
          </section>
          <section className="batch-card batch-sidebar-validation"><h3>Readiness</h3><p>{stats.ready} of {stats.total} cases meet the visible dispatch eligibility checks.</p>{stats.ready !== stats.total && <div className="batch-alert warning">Some cases may be rejected by the backend dispatch eligibility checks.</div>}</section>
        </aside>
      </div>
    </main>
  );
}
