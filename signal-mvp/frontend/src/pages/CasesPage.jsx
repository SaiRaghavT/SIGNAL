import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getCase, listCases } from "../api/cases.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/cases.css";

const API_PAGE_SIZE = 100;
const ROWS_PER_PAGE = 10;
const EMPTY_VALUE = "—";

const FILTERS = [
  { id: "all", label: "All Cases" },
  { id: "review", label: "Needs Review", tone: "review" },
  { id: "deadline", label: "Deadline Risk", tone: "deadline" },
  { id: "ready", label: "Report-Ready", tone: "ready" },
];

function text(value) {
  if (typeof value === "string" || typeof value === "number") {
    const cleaned = String(value).replace(/\s+/g, " ").trim();
    return cleaned || "";
  }
  return "";
}

function formatDate(value) {
  if (!value) return EMPTY_VALUE;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return EMPTY_VALUE;
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function patientName(patient = {}) {
  const direct = text(patient.name || patient.full_name || patient.patient_name);
  if (direct) return direct;
  const first = text(patient.first_name || patient.given_name || patient.given);
  const last = text(patient.last_name || patient.family_name || patient.family);
  if (first || last) return [first, last].filter(Boolean).join(" ");
  const name = Array.isArray(patient.name) ? patient.name[0] : null;
  if (name && typeof name === "object") {
    return [
      ...(Array.isArray(name.given) ? name.given : [name.given]),
      name.family,
    ].map(text).filter(Boolean).join(" ");
  }
  return EMPTY_VALUE;
}

function firstText(record, keys) {
  for (const key of keys) {
    const value = text(record?.[key]);
    if (value) return value;
  }
  return "";
}

function caseEvidence(detail) {
  const labs = Array.isArray(detail?.laboratory_evidence) ? detail.laboratory_evidence : [];
  const lab = labs.find((entry) => entry && typeof entry === "object");
  if (lab) {
    const nestedEvidence = lab.evidence && typeof lab.evidence === "object" ? lab.evidence : {};
    const name = firstText(lab, ["test_name", "test", "display", "analyte", "component", "name"])
      || firstText(nestedEvidence, ["test_name", "test", "display", "analyte", "name"]);
    const result = firstText(lab, ["result", "result_value", "interpretation", "value", "report_status"])
      || firstText(nestedEvidence, ["result", "result_value", "interpretation", "value"]);
    const title = [name, result].filter(Boolean).join(" · ") || firstText(lab, ["code", "lab_result_id"]);
    const source = firstText(lab, ["source_system", "source", "laboratory_name", "performing_lab"])
      || firstText(nestedEvidence, ["source_system", "source", "laboratory_name"]);
    const date = firstText(lab, ["result_date", "collected_at", "observation_date", "date", "effective_at"])
      || firstText(nestedEvidence, ["result_date", "collected_at", "date"]);
    const secondary = [source, date ? formatDate(date) : ""].filter(Boolean).join(" · ");
    return { title: title || "Laboratory evidence", secondary };
  }

  const clinical = detail?.clinical_evidence;
  if (clinical && typeof clinical === "object") {
    const ignored = ["encounter_id", "patient_id", "source_id", "source_system"];
    const meaningful = Object.entries(clinical).find(([key, value]) => !ignored.includes(key) && text(value));
    if (meaningful) {
      return {
        title: `${meaningful[0].replaceAll("_", " ")}: ${text(meaningful[1])}`,
        secondary: firstText(clinical, ["source_system", "source"]),
      };
    }
  }

  const ai = detail?.ai_evidence;
  const aiTrigger = firstText(ai, ["trigger_reason", "reason", "evidence_summary", "summary"]);
  return {
    title: aiTrigger || "No trigger evidence recorded",
    secondary: "",
  };
}

function missingCategories(detail) {
  const missing = Array.isArray(detail?.required_missing_fields) ? detail.required_missing_fields : [];
  if (!missing.length) return "None";
  const categories = {
    patient: "Patient information",
    clinical: "Clinical information",
    rash_fever: "Clinical information",
    laboratory: "Laboratory evidence",
    reporting: "Reporting information",
    provider: "Provider information",
    facility: "Facility information",
  };
  const labels = missing.reduce((result, field) => {
    const prefix = String(field).split(".")[0];
    const label = categories[prefix] || String(field).replaceAll("_", " ");
    if (!result.includes(label)) result.push(label);
    return result;
  }, []);
  return labels.join(", ");
}

function statusTone(value) {
  const normalized = String(value || "").toUpperCase();
  if (/SUBMITTED|ACKNOWLEDGED|COMPLETE|APPROV|READY|REPORT$/.test(normalized)) return "success";
  if (/OVERDUE|CRITICAL|REJECT|FAILED/.test(normalized)) return "danger";
  if (/NEEDS_REVIEW|UNDER_REVIEW|INVESTIGATION|PENDING|HOLD/.test(normalized)) return "warning";
  if (/POTENTIAL|WITHIN_WINDOW/.test(normalized)) return "info";
  return "";
}

function titleCase(value) {
  return String(value || EMPTY_VALUE)
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

async function getAllCases() {
  const firstPage = await listCases({ page: 1, page_size: API_PAGE_SIZE });
  const items = [...(firstPage.items || [])];
  const pages = Math.ceil((firstPage.total || 0) / API_PAGE_SIZE);
  for (let page = 2; page <= pages; page += 1) {
    const result = await listCases({ page, page_size: API_PAGE_SIZE });
    items.push(...(result.items || []));
  }
  return { items, total: firstPage.total || 0, metrics: firstPage.metrics || {} };
}

async function withConcurrency(items, limit, mapper) {
  const results = new Array(items.length);
  let nextIndex = 0;
  async function worker() {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await mapper(items[index]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}

export function CasesPage() {
  const [cases, setCases] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [activeFilter, setActiveFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadCases() {
      setLoading(true);
      setError("");
      try {
        const caseResult = await getAllCases();
        const enriched = await withConcurrency(caseResult.items, 8, async (item) => {
          const detail = await getCase(item.case_id);
          return { ...item, detail };
        });
        if (active) {
          setCases(enriched);
          setMetrics({ ...caseResult.metrics, candidate_cases: caseResult.total });
          setPage(1);
        }
      } catch (loadError) {
        if (active) setError(loadError?.message || "Unable to load case records.");
      } finally {
        if (active) setLoading(false);
      }
    }
    loadCases();
    return () => { active = false; };
  }, []);

  const counts = useMemo(() => ({
    all: metrics.candidate_cases ?? 0,
    review: metrics.needs_review ?? 0,
    deadline: metrics.at_risk_deadlines ?? 0,
    ready: metrics.report_ready ?? 0,
  }), [metrics]);

  const filteredCases = useMemo(() => {
    if (activeFilter === "review") return cases.filter((item) => item.needs_review);
    if (activeFilter === "deadline") return cases.filter((item) => item.deadline_risk);
    if (activeFilter === "ready") return cases.filter((item) => item.report_ready);
    return cases;
  }, [activeFilter, cases]);

  const pageCount = Math.max(1, Math.ceil(filteredCases.length / ROWS_PER_PAGE));
  const visibleCases = filteredCases.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE);
  const firstVisible = filteredCases.length ? (page - 1) * ROWS_PER_PAGE + 1 : 0;
  const lastVisible = Math.min(page * ROWS_PER_PAGE, filteredCases.length);

  function selectFilter(filterId) {
    setActiveFilter(filterId);
    setPage(1);
  }

  return (
    <section className="cases-page">
      <PageHeader
        title="Cases"
        subtitle="Manage the complete lifecycle of reportable-condition cases from candidate detection through disposition and audit."
      />

      {loading ? (
        <SignalLoading title="Loading Cases" message="Retrieving persisted case records and backend workflow states." />
      ) : error ? (
        <div className="cases-management"><div className="cases-error" role="alert">Unable to load cases. {error}</div></div>
      ) : (
        <>
          <div className="cases-kpi-grid" aria-label="Case metrics">
            <article className="cases-kpi candidate">
              <span className="cases-kpi-label">CANDIDATE CASES</span>
              <strong className="cases-kpi-value">{counts.all}</strong>
              <span className="cases-kpi-description">Evidence-linked candidates</span>
            </article>
            <article className="cases-kpi deadline">
              <span className="cases-kpi-label">AT-RISK DEADLINES</span>
              <strong className="cases-kpi-value">{counts.deadline}</strong>
              <span className="cases-kpi-description">Configured reporting windows</span>
            </article>
            <article className="cases-kpi review">
              <span className="cases-kpi-label">NEEDS REVIEW</span>
              <strong className="cases-kpi-value">{counts.review}</strong>
              <span className="cases-kpi-description">Evidence or missing-data exceptions</span>
            </article>
            <article className="cases-kpi ready">
              <span className="cases-kpi-label">REPORT-READY</span>
              <strong className="cases-kpi-value">{counts.ready}</strong>
              <span className="cases-kpi-description">Validated for authorized submission</span>
            </article>
          </div>

          <section className="cases-management" aria-labelledby="cases-management-title">
            <header className="cases-management-header">
              <div>
                <h3 id="cases-management-title">Case Management</h3>
                <p>Longitudinal case record: detection trigger, evidence, jurisdiction decision, reporting rule, deadline, and disposition.</p>
              </div>
              <span className="cases-record-count">{counts.all} {counts.all === 1 ? "record" : "records"}</span>
            </header>

            <nav className="cases-filters" aria-label="Filter cases">
              {FILTERS.map((filter) => (
                <button
                  key={filter.id}
                  type="button"
                  className={`cases-filter${filter.tone ? ` ${filter.tone}` : ""}${activeFilter === filter.id ? " active" : ""}`}
                  aria-pressed={activeFilter === filter.id}
                  onClick={() => selectFilter(filter.id)}
                >
                  {filter.label} ({counts[filter.id]})
                </button>
              ))}
            </nav>

            {visibleCases.length === 0 ? (
              <div className="cases-empty">
                <strong>{counts.all ? "No cases in this view" : "No case records"}</strong>
                <p>{counts.all ? "No persisted case records match the selected filter." : "The backend has not returned any case records."}</p>
              </div>
            ) : (
              <div className="cases-table-scroll">
                <table className="cases-table">
                  <thead>
                    <tr>
                      <th scope="col">Patient / Condition</th>
                      <th scope="col">Trigger / Evidence</th>
                      <th scope="col">Jurisdiction / Rule</th>
                      <th scope="col">Deadline</th>
                      <th scope="col">Disposition</th>
                      <th scope="col">Priority</th>
                      <th scope="col">Missing Info</th>
                      <th scope="col">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCases.map((item) => {
                      const detail = item.detail || {};
                      const evidence = caseEvidence(detail);
                      const disposition = item.status || item.final_decision || item.reportability_decision;
                      const priority = text(item.severity) || EMPTY_VALUE;
                      const priorityTone = ["HIGH", "CRITICAL"].includes(priority.toUpperCase())
                        ? "danger"
                        : priority.toUpperCase() === "MEDIUM" ? "warning" : "";
                      const missing = missingCategories(detail);
                      return (
                        <tr key={item.case_id}>
                          <td>
                            <span className="cases-cell-primary">{patientName(detail.patient)}</span>
                            <span className="cases-cell-secondary">{text(item.disease) || EMPTY_VALUE}</span>
                          </td>
                          <td>
                            <span className="cases-cell-primary">{evidence.title}</span>
                            {evidence.secondary && <span className="cases-cell-secondary">{evidence.secondary}</span>}
                          </td>
                          <td>
                            <span className="cases-cell-primary">{text(item.jurisdiction) || EMPTY_VALUE}</span>
                            <span className="cases-rule">{text(item.rule_id) || EMPTY_VALUE}</span>
                          </td>
                          <td>{formatDate(item.deadline)}</td>
                          <td><span className={`cases-pill ${statusTone(disposition)}`}>{titleCase(disposition)}</span></td>
                          <td><span className={`cases-pill ${priorityTone}`}>{titleCase(priority)}</span></td>
                          <td><span className={`cases-pill ${missing === "None" ? "success" : "warning"}`}>{missing}</span></td>
                          <td><Link className="cases-action" to={`/cases/${encodeURIComponent(item.case_id)}`}>Open case</Link></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {filteredCases.length > ROWS_PER_PAGE && (
              <footer className="cases-pagination">
                <span>Showing {firstVisible}–{lastVisible} of {filteredCases.length} cases</span>
                <div>
                  <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>Previous</button>
                  <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount}>Next</button>
                </div>
              </footer>
            )}
          </section>
        </>
      )}
    </section>
  );
}
