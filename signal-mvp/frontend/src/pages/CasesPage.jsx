import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases } from "../api/cases.js";
import { listCandidates } from "../api/candidates.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { ErrorState } from "../components/ui/Loading.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { StatusBadge } from "../components/ui/StatusBadge.jsx";

function Pagination({ page, pages, total, onPageChange }) {
  if (pages > 1) return (
    <div className="cases-pagination" aria-label="Cases pages">
      <span>Showing {(page - 1) * 10 + 1}–{Math.min(page * 10, total)} of {total}</span>
      <div>
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button>
        {Array.from({ length: pages }, (_, index) => index + 1).map((number) => (
          <button type="button" key={number} aria-current={number === page ? "page" : undefined} className={number === page ? "current" : ""} onClick={() => onPageChange(number)}>{number}</button>
        ))}
        <button type="button" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Next</button>
      </div>
    </div>
  );
  return total > 0 ? <div className="cases-pagination"><span>Showing {total} of {total}</span></div> : null;
}

export function CasesPage() {
  const [data, setData] = useState(null);
  const [candidateData, setCandidateData] = useState(null);
  const [casePage, setCasePage] = useState(1);
  const [candidatePage, setCandidatePage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      listCases({ page: casePage, page_size: 10 }),
      listCandidates({ page: candidatePage, page_size: 10 }),
    ]).then(([caseResult, candidateResult]) => {
      if (!active) return;
      setData(caseResult);
      setCandidateData(candidateResult);
    }).catch((err) => {
      if (active) setError(err?.message || "Unable to load cases and detected candidates.");
    });
    return () => { active = false; };
  }, [casePage, candidatePage]);

  const cases = data?.items || [];
  const candidates = candidateData?.items || [];
  return (
    <section className="cases-page">
      <PageHeader title="Cases" subtitle="Persisted reporting cases and FHIR-backed candidates awaiting case review." />
      {error ? <div className="panel"><ErrorState message={error} /></div> : !data || !candidateData ? (
        <div className="panel"><SignalLoading title="Loading Cases" message="Retrieving case records and FHIR-backed candidates." /></div>
      ) : <>
        <div className="cases-summary">
          <div className="panel"><strong>{data.total || 0}</strong><span>Persisted reporting cases</span></div>
          <div className="panel"><strong>{candidateData.total || 0}</strong><span>FHIR candidates available for review</span></div>
        </div>
        <section className="panel cases-list-panel">
          <div className="cases-section-heading"><div><h2>Reporting Cases</h2><p>Cases assembled through the clinical review workflow.</p></div></div>
          {cases.length ? <div className="patients-table-scroll">
            <table>
              <thead><tr><th>Case</th><th>Disease</th><th>Jurisdiction</th><th>Status</th><th>Reportability</th><th>Updated</th></tr></thead>
              <tbody>{cases.map((item) => (
                <tr key={item.case_id}>
                  <td><Link to={`/cases/${encodeURIComponent(item.case_id)}`}>{item.case_id}</Link></td>
                  <td>{item.disease || "—"}</td>
                  <td>{item.jurisdiction || "Not resolved"}</td>
                  <td><StatusBadge value={item.status} /></td>
                  <td><StatusBadge value={item.reportability_decision} /></td>
                  <td>{item.updated_at ? new Date(item.updated_at).toLocaleString() : "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div> : <div className="cases-empty">No reporting cases have been assembled yet. Review a candidate to create a case.</div>}
          <Pagination page={casePage} pages={data.pages || Math.ceil((data.total || 0) / 10)} total={data.total || 0} onPageChange={setCasePage}/>
        </section>
        <section className="panel cases-list-panel">
          <div className="cases-section-heading">
            <div><h2>FHIR Candidates for Review</h2><p>Candidate records detected from seeded clinical data. These are not reporting cases until reviewed.</p></div>
            <span>{candidateData.total || 0} records</span>
          </div>
          {candidates.length ? <div className="patients-table-scroll">
            <table>
              <thead><tr><th>Patient</th><th>Candidate ID</th><th>Condition</th><th>Evidence</th><th>Jurisdiction</th><th>Status</th><th>Updated</th><th>Action</th></tr></thead>
              <tbody>{candidates.map((candidate) => {
                const patient = candidate.patient || {};
                const patientName = [patient.first_name, patient.last_name].filter(Boolean).join(" ") || candidate.patient_id;
                const evidence = (candidate.evidence || []).map((item) => item.display || item.source_type).filter(Boolean).join(", ");
                return <tr key={candidate.candidate_id}>
                  <td>{patientName}</td>
                  <td>{candidate.candidate_id}</td>
                  <td>{candidate.disease || "Not specified"}</td>
                  <td>{evidence || "Source evidence available"}</td>
                  <td>{candidate.jurisdiction || "Not resolved"}</td>
                  <td><StatusBadge value={candidate.status || "Detected"} /></td>
                  <td>{candidate.updated_at ? new Date(candidate.updated_at).toLocaleString() : "—"}</td>
                  <td><Link to={`/candidates/${encodeURIComponent(candidate.candidate_id)}`}>Review</Link></td>
                </tr>;
              })}</tbody>
            </table>
          </div> : <div className="cases-empty">No candidates are currently available from the database.</div>}
          <Pagination page={candidatePage} pages={candidateData.pages || Math.ceil((candidateData.total || 0) / 10)} total={candidateData.total || 0} onPageChange={setCandidatePage}/>
        </section>
      </>}
    </section>
  );
}
