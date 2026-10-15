import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Clock3, RefreshCw, ShieldCheck } from "lucide-react";
import { SignalLoading } from "../../components/ui/SignalLoading.jsx";
import "../../styles/AdminDeadlines.css";

// UI-only POC data. Demo deadlines are relative to today in Texas so status
// examples stay current whenever the app is opened on a different date.
function centralDateFromToday(daysFromToday) {
  const todayParts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(new Date());
  const today = Object.fromEntries(todayParts.map(({ type, value }) => [type, Number(value)]));
  return new Date(Date.UTC(today.year, today.month - 1, today.day + daysFromToday, 18)).toISOString();
}

function demoDeadline({ patient, caseId, daysFromToday, priority, realCase = false }) {
  const status = daysFromToday < 0
    ? "OVERDUE"
    : daysFromToday === 0
      ? "DUE TODAY"
      : daysFromToday <= 4
        ? "DUE SOON"
        : "ON TRACK";

  return {
    patient,
    caseId,
    condition: "Measles",
    jurisdiction: "TX",
    deadline: centralDateFromToday(daysFromToday),
    priority,
    status,
    ...(realCase ? { realCase: true, submissionMode: "IMMEDIATE" } : {}),
  };
}

export const DEMO_DEADLINES = [
  demoDeadline({ patient: "Maya Patel", caseId: "33333333-3333-4333-8333-333333333333", daysFromToday: -4, priority: "HIGH" }),
  demoDeadline({ patient: "Liam Chen", caseId: "44444444-4444-4444-8444-444444444444", daysFromToday: -2, priority: "URGENT" }),
  demoDeadline({ patient: "John Anderson", caseId: "11111111-1111-4111-8111-111111111111", daysFromToday: 0, priority: "URGENT" }),
  demoDeadline({ patient: "Sarah Williams", caseId: "22222222-2222-4222-8222-222222222222", daysFromToday: 0, priority: "HIGH" }),
  demoDeadline({ patient: "Jordan Rivera", caseId: "C98D3386-8A6E-479A-BC78-CC7236A71EB3", daysFromToday: 0, priority: "HIGH", realCase: true }),
  demoDeadline({ patient: "Emily Carter", caseId: "55555555-5555-4555-8555-555555555555", daysFromToday: 1, priority: "MEDIUM" }),
  demoDeadline({ patient: "Noah Thompson", caseId: "66666666-6666-4666-8666-666666666666", daysFromToday: 2, priority: "HIGH" }),
  demoDeadline({ patient: "Ava Robinson", caseId: "77777777-7777-4777-8777-777777777777", daysFromToday: 3, priority: "LOW" }),
  demoDeadline({ patient: "Ethan Brooks", caseId: "88888888-8888-4888-8888-888888888888", daysFromToday: 4, priority: "MEDIUM" }),
  demoDeadline({ patient: "Sophia Turner", caseId: "99999999-9999-4999-8999-999999999999", daysFromToday: 5, priority: "LOW" }),
  demoDeadline({ patient: "Mason Foster", caseId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", daysFromToday: 6, priority: "MEDIUM" }),
  demoDeadline({ patient: "Isabella Reed", caseId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", daysFromToday: 7, priority: "HIGH" }),
  demoDeadline({ patient: "Lucas Perry", caseId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", daysFromToday: 8, priority: "LOW" }),
  demoDeadline({ patient: "Amelia Powell", caseId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", daysFromToday: 9, priority: "MEDIUM" }),
  demoDeadline({ patient: "Henry Ward", caseId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", daysFromToday: 10, priority: "HIGH" }),
  demoDeadline({ patient: "Mila Price", caseId: "ffffffff-ffff-4fff-8fff-ffffffffffff", daysFromToday: 11, priority: "LOW" }),
  demoDeadline({ patient: "James Cooper", caseId: "12121212-1212-4212-8212-121212121212", daysFromToday: 12, priority: "MEDIUM" }),
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
  const [loading, setLoading] = useState(false);

  const metrics = useMemo(() => ({
    overdue: DEMO_DEADLINES.filter((row) => row.status === "OVERDUE").length,
    today: DEMO_DEADLINES.filter((row) => row.status === "DUE TODAY").length,
    soon: DEMO_DEADLINES.filter((row) => row.status === "DUE SOON").length,
    onTrack: DEMO_DEADLINES.filter((row) => row.status === "ON TRACK").length,
  }), []);

  const handleRefresh = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 450);
  };

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
        <button type="button" className="admin-deadlines-refresh" onClick={handleRefresh} disabled={loading} aria-label="Refresh deadlines">
          <RefreshCw size={15} className={loading ? "admin-deadlines-spin" : ""} />
          Refresh
        </button>
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
          {loading ? (
            <SignalLoading
              title="Loading Deadlines"
              message="Retrieving compliance and reporting deadline records."
            />
          ) : (
            <>
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
            </>
          )}
        </div>
      </section>
    </main>
  );
}
