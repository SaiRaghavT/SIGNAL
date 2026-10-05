import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases } from "../api/cases.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { ErrorState } from "../components/ui/Loading.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import { StatusBadge } from "../components/ui/StatusBadge.jsx";

export function CasesPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    listCases()
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err?.message || "Unable to load cases."); });
    return () => { active = false; };
  }, []);

  return (
    <section className="cases-page">
      <PageHeader title="Cases" subtitle="Review persisted cases and their current reporting status." />
      <div className="panel">
        {error ? <ErrorState message={error} /> : !data ? (
          <SignalLoading title="Loading Cases" message="Retrieving case records and reporting information." />
        ) : (
          <div className="patients-table-scroll">
            <table>
              <thead><tr><th>Case</th><th>Disease</th><th>Jurisdiction</th><th>Status</th><th>Reportability</th><th>Updated</th></tr></thead>
              <tbody>{(data.items || []).map((item) => (
                <tr key={item.case_id}>
                  <td><Link to={`/cases/${encodeURIComponent(item.case_id)}`}>{item.case_id}</Link></td>
                  <td>{item.disease || "—"}</td>
                  <td>{item.jurisdiction || "—"}</td>
                  <td><StatusBadge value={item.status} /></td>
                  <td><StatusBadge value={item.reportability_decision} /></td>
                  <td>{item.updated_at ? new Date(item.updated_at).toLocaleString() : "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
