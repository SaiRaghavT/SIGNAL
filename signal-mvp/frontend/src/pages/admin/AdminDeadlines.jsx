import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Clock3, ShieldCheck } from "lucide-react";
import "../../styles/AdminDeadlines.css";

// UI-only POC data. Replace this array with getAdminDeadlines() when that API is ready.
export const DEMO_DEADLINES = [
  { patient: "Maya Patel", caseId: "33333333-3333-4333-8333-333333333333", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-07T16:00:00-05:00", priority: "HIGH", status: "OVERDUE" },
  { patient: "Liam Chen", caseId: "44444444-4444-4444-8444-444444444444", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-07T19:45:00-05:00", priority: "URGENT", status: "OVERDUE" },
  { patient: "John Anderson", caseId: "11111111-1111-4111-8111-111111111111", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-08T20:30:00-05:00", priority: "URGENT", status: "DUE TODAY" },
  { patient: "Sarah Williams", caseId: "22222222-2222-4222-8222-222222222222", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-08T22:15:00-05:00", priority: "HIGH", status: "DUE TODAY" },
  { patient: "Jordan Rivera", caseId: "C98D3386-8A6E-479A-BC78-CC7236A71EB3", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-08T22:35:00-05:00", priority: "HIGH", status: "DUE TODAY", realCase: true, submissionMode: "IMMEDIATE" },
  { patient: "Emily Carter", caseId: "55555555-5555-4555-8555-555555555555", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-09T09:00:00-05:00", priority: "MEDIUM", status: "DUE SOON" },
  { patient: "Noah Thompson", caseId: "66666666-6666-4666-8666-666666666666", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-09T14:00:00-05:00", priority: "HIGH", status: "DUE SOON" },
  { patient: "Ava Robinson", caseId: "77777777-7777-4777-8777-777777777777", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-10T11:00:00-05:00", priority: "LOW", status: "DUE SOON" },
  { patient: "Ethan Brooks", caseId: "88888888-8888-4888-8888-888888888888", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-10T15:00:00-05:00", priority: "MEDIUM", status: "DUE SOON" },
  { patient: "Sophia Turner", caseId: "99999999-9999-4999-8999-999999999999", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-13T13:00:00-05:00", priority: "LOW", status: "ON TRACK" },
  { patient: "Mason Foster", caseId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-14T09:30:00-05:00", priority: "MEDIUM", status: "ON TRACK" },
  { patient: "Isabella Reed", caseId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-14T16:15:00-05:00", priority: "HIGH", status: "ON TRACK" },
  { patient: "Lucas Perry", caseId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-15T10:00:00-05:00", priority: "LOW", status: "ON TRACK" },
  { patient: "Amelia Powell", caseId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-15T14:45:00-05:00", priority: "MEDIUM", status: "ON TRACK" },
  { patient: "Henry Ward", caseId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-16T08:30:00-05:00", priority: "HIGH", status: "ON TRACK" },
  { patient: "Mila Price", caseId: "ffffffff-ffff-4fff-8fff-ffffffffffff", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-16T12:00:00-05:00", priority: "LOW", status: "ON TRACK" },
  { patient: "James Cooper", caseId: "12121212-1212-4212-8212-121212121212", condition: "Measles", jurisdiction: "TX", deadline: "2026-10-16T17:00:00-05:00", priority: "MEDIUM", status: "ON TRACK" },
];

const STATUS_ORDER = { OVERDUE: 0, "DUE TODAY": 1, "DUE SOON": 2, "ON TRACK": 3 };
const STATUSES = ["OVERDUE", "DUE TODAY", "DUE SOON", "ON TRACK"];
const PRIORITIES = ["URGENT", "HIGH", "MEDIUM", "LOW"];

function formatDeadline(value) {
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/Chicago",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function statusClass(status) {
  return status.toLowerCase().replaceAll(" ", "-");
}

function priorityClass(priority) {
  return priority.toLowerCase();
}

export default function AdminDeadlines() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [jurisdictionFilter, setJurisdictionFilter] = useState("ALL");

  const metrics = useMemo(() => ({
    overdue: DEMO_DEADLINES.filter((row) => row.status === "OVERDUE").length,
    today: DEMO_DEADLINES.filter((row) => row.status === "DUE TODAY").length,
    soon: DEMO_DEADLINES.filter((row) => row.status === "DUE SOON").length,
    onTrack: DEMO_DEADLINES.filter((row) => row.status === "ON TRACK").length,
  }), []);

  const rows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return DEMO_DEADLINES
      .filter((row) => statusFilter === "ALL" || row.status === statusFilter)
      .filter((row) => priorityFilter === "ALL" || row.priority === priorityFilter)
      .filter((row) => jurisdictionFilter === "ALL" || row.jurisdiction === jurisdictionFilter)
      .filter((row) => !query || [row.patient, row.caseId, row.condition, row.jurisdiction].join(" ").toLowerCase().includes(query))
      .sort((left, right) => STATUS_ORDER[left.status] - STATUS_ORDER[right.status] || new Date(left.deadline) - new Date(right.deadline));
  }, [search, statusFilter, priorityFilter, jurisdictionFilter]);

  function openCase(row) {
    if (!row.realCase) return;
    navigate(`/admin/queue/${encodeURIComponent(row.caseId)}/immediate`);
  }

  return (
    <main className="admin-deadlines-page">
      <header className="admin-deadlines-header">
        <div>
          <span className="admin-deadlines-eyebrow">ADMINISTRATOR / COMPLIANCE</span>
          <div className="admin-deadlines-title-line"><h1>Deadlines</h1><span className="admin-deadlines-demo-label">DEMO DATA</span></div>
          <p>Review reporting deadlines and prioritize cases requiring timely action.</p>
        </div>
      </header>

      <section className="admin-deadlines-metrics" aria-label="Deadline summary">
        <article className="admin-deadlines-metric overdue"><div><AlertCircle size={16} /></div><span>OVERDUE</span><strong>{metrics.overdue}</strong></article>
        <article className="admin-deadlines-metric today"><div><Clock3 size={16} /></div><span>DUE TODAY</span><strong>{metrics.today}</strong></article>
        <article className="admin-deadlines-metric soon"><div><Clock3 size={16} /></div><span>DUE SOON</span><strong>{metrics.soon}</strong></article>
        <article className="admin-deadlines-metric track"><div><ShieldCheck size={16} /></div><span>ON TRACK</span><strong>{metrics.onTrack}</strong></article>
      </section>

      <section className="admin-deadlines-panel" aria-label="Demo reporting deadlines">
        <div className="admin-deadlines-filters">
          <label className="admin-deadlines-search"><span>Search</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Patient, case ID, condition..." /></label>
          <label><span>Status</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="ALL">All</option>{STATUSES.map((status) => <option key={status} value={status}>{({ OVERDUE: "Overdue", "DUE TODAY": "Due Today", "DUE SOON": "Due Soon", "ON TRACK": "On Track" })[status]}</option>)}</select></label>
          <label><span>Priority</span><select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}><option value="ALL">All</option>{PRIORITIES.map((priority) => <option key={priority} value={priority}>{priority}</option>)}</select></label>
          <label><span>Jurisdiction</span><select value={jurisdictionFilter} onChange={(event) => setJurisdictionFilter(event.target.value)}><option value="ALL">All</option><option value="TX">TX</option></select></label>
        </div>

        <div className="admin-deadlines-table-wrap">
          <table className="admin-deadlines-table">
            <thead><tr><th>Patient</th><th>Case ID</th><th>Condition</th><th>Jurisdiction</th><th>Deadline</th><th>Priority</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>{rows.map((row) => (
              <tr key={row.caseId}>
                <td><strong>{row.patient}</strong></td>
                <td className="admin-deadlines-mono">{row.caseId}</td>
                <td>{row.condition}</td>
                <td>{row.jurisdiction}</td>
                <td>{formatDeadline(row.deadline)}</td>
                <td><span className={`admin-deadlines-priority ${priorityClass(row.priority)}`}>{row.priority}</span></td>
                <td><span className={`admin-deadlines-status ${statusClass(row.status)}`}>{row.status}</span></td>
                <td><button type="button" className="admin-deadlines-view" onClick={() => openCase(row)} disabled={!row.realCase} title={row.realCase ? "View case review" : "Demo row; no live case record"}>View</button></td>
              </tr>
            ))}</tbody>
          </table>
          {rows.length === 0 && <div className="admin-deadlines-empty">No demo deadlines match these filters.</div>}
        </div>
      </section>
    </main>
  );
}
