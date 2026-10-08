import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { getAdminAudit } from "../../services/adminService.js";
import "../../styles/AdminAudit.css";

const DASH = "\u2014";

function asItems(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.items)) return response.items;
  if (Array.isArray(response?.events)) return response.events;
  if (Array.isArray(response?.records)) return response.records;
  return [];
}

function firstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && String(value).trim() !== "") ?? null;
}

function patientLabel(value) {
  if (typeof value === "string") return value.trim() || DASH;
  if (!value || typeof value !== "object") return DASH;
  return firstValue(
    value.name,
    value.full_name,
    [value.first_name, value.last_name].filter(Boolean).join(" "),
    value.patient_id,
  ) || DASH;
}

function normalizeAuditEvent(item, index) {
  const row = item && typeof item === "object" ? item : {};
  const detail = row.new_value && typeof row.new_value === "object" ? row.new_value : {};
  const metadata = row.metadata ?? row.metadata_json ?? row.meta_data ?? detail.metadata ?? null;
  const entityType = firstValue(row.entity_type, row.entityType, detail.entity_type, detail.entityType);
  const eventType = firstValue(row.event_type, row.eventType, row.action, row.type);
  const timestamp = firstValue(row.timestamp, row.event_timestamp, row.created_at, row.createdAt);
  const patient = firstValue(row.patient, row.patient_name, row.patientName, detail.patient, detail.patient_name);

  return {
    key: String(firstValue(row.audit_id, row.event_id, row.eventId, row.id, `${eventType || "event"}-${timestamp || index}`)),
    eventId: firstValue(row.audit_id, row.event_id, row.eventId, row.id) || DASH,
    eventType: eventType || DASH,
    entityType: entityType || DASH,
    caseId: firstValue(row.case_id, row.caseId, detail.case_id, detail.caseId, String(entityType || "").toUpperCase() === "CASE" ? row.entity_id : null) || DASH,
    patient: patientLabel(patient),
    actor: firstValue(row.actor_name, row.actor, row.actor_id, row.user_name, row.user, detail.actor_id, detail.reviewer_id) || DASH,
    role: firstValue(row.actor_role, row.role, row.user_role, detail.actor_role, detail.reviewer_role) || DASH,
    timestamp,
    stage: firstValue(row.workflow_stage, row.workflowStage, row.stage, detail.workflow_stage, metadata?.workflow_stage) || DASH,
    status: firstValue(row.status, detail.status) || DASH,
    reason: firstValue(row.reason, row.description, row.details, detail.reason, detail.description, detail.message) || DASH,
    metadata,
    raw: row,
  };
}

function formatTimestamp(value) {
  if (!value) return DASH;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function formatDetail(value) {
  if (value === undefined || value === null || value === "") return DASH;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.map(formatDetail).join(", ") : DASH;
  if (typeof value === "object") {
    const entries = Object.entries(value).slice(0, 8);
    return entries.length
      ? entries.map(([key, entry]) => `${key.replaceAll("_", " ")}: ${typeof entry === "object" && entry !== null ? Array.isArray(entry) ? `${entry.length} item(s)` : "Available" : formatDetail(entry)}`).join(" · ")
      : DASH;
  }
  return String(value);
}

function eventTone(value) {
  const normalized = String(value || "").toUpperCase();
  if (/(FAIL|ERROR|REJECT|BLOCK)/.test(normalized)) return "danger";
  if (/(SUCCESS|SUBMITTED|ACKNOWLEDGED|APPROVED|COMPLETED)/.test(normalized)) return "success";
  if (/(QUEUE|REVIEW|ATTEST|DISPATCH)/.test(normalized)) return "info";
  return "neutral";
}

function statusTone(value) {
  const normalized = String(value || "").toUpperCase();
  if (/(FAIL|ERROR|REJECT|BLOCK)/.test(normalized)) return "danger";
  if (/(SUCCESS|SUBMITTED|ACKNOWLEDGED|APPROVED|COMPLETED)/.test(normalized)) return "success";
  if (/(PENDING|REVIEW|QUEUED)/.test(normalized)) return "warning";
  return "neutral";
}

function isToday(value) {
  if (!value) return false;
  const date = new Date(value);
  const now = new Date();
  return !Number.isNaN(date.getTime()) && date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
}

function withinDays(value, days) {
  if (!value) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (days - 1));
  return date >= start && date <= now;
}

function detailEntries(event) {
  const entries = [
    ["Event ID", event.eventId], ["Event Type", event.eventType], ["Timestamp", formatTimestamp(event.timestamp)],
    ["Case ID", event.caseId], ["Actor", event.actor], ["Role", event.role],
    ["Workflow Stage", event.stage], ["Status", event.status], ["Details / Reason", event.reason],
  ];
  const meta = event.metadata ?? event.raw.new_value;
  if (meta && typeof meta === "object" && !Array.isArray(meta)) {
    Object.entries(meta).slice(0, 8).forEach(([key, value]) => entries.push([`Metadata · ${key.replaceAll("_", " ")}`, formatDetail(value)]));
  } else if (meta !== null && meta !== undefined) {
    entries.push(["Metadata", formatDetail(meta)]);
  }
  return entries;
}

export default function AdminAudit() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [eventFilter, setEventFilter] = useState("ALL");
  const [stageFilter, setStageFilter] = useState("ALL");
  const [dateFilter, setDateFilter] = useState("ALL");
  const [expanded, setExpanded] = useState(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setEvents(asItems(await getAdminAudit()).map(normalizeAuditEvent));
    } catch (loadError) {
      setEvents([]);
      setError("Unable to load audit trails.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const eventTypes = useMemo(() => [...new Set(events.map((event) => event.eventType).filter((value) => value !== DASH))].sort(), [events]);
  const stages = useMemo(() => [...new Set(events.map((event) => event.stage).filter((value) => value !== DASH))].sort(), [events]);

  const metrics = useMemo(() => ({
    total: events.length,
    today: events.filter((event) => isToday(event.timestamp)).length,
    cases: events.filter((event) => String(event.entityType).toUpperCase() === "CASE" || String(event.eventType).toUpperCase().startsWith("CASE_")).length,
    submissions: events.filter((event) => String(event.entityType).toUpperCase() === "SUBMISSION" || String(event.eventType).toUpperCase().includes("SUBMISSION")).length,
  }), [events]);

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();
    return events.filter((event) => {
      const matchesSearch = !query || [event.eventId, event.caseId, event.patient, event.actor, event.eventType].join(" ").toLowerCase().includes(query);
      const matchesEvent = eventFilter === "ALL" || event.eventType === eventFilter;
      const matchesStage = stageFilter === "ALL" || event.stage === stageFilter;
      const matchesDate = dateFilter === "ALL" || (dateFilter === "TODAY" ? isToday(event.timestamp) : withinDays(event.timestamp, Number(dateFilter)));
      return matchesSearch && matchesEvent && matchesStage && matchesDate;
    });
  }, [events, search, eventFilter, stageFilter, dateFilter]);

  return (
    <main className="admin-audit-page">
      <header className="admin-audit-header">
        <div>
          <span className="admin-audit-eyebrow">ADMINISTRATOR / AUDIT TRAILS</span>
          <h1>Audit Trails</h1>
          <p>Track administrative actions and workflow events across public health reporting.</p>
        </div>
        <button type="button" className="admin-audit-refresh" onClick={loadEvents} disabled={loading}>
          <RefreshCw size={15} className={loading ? "admin-audit-spin" : ""} />
          Refresh
        </button>
      </header>

      {error && <div className="admin-audit-error" role="alert"><span>{error}</span><button type="button" onClick={loadEvents}>Retry</button></div>}

      <section className="admin-audit-metrics" aria-label="Audit summary">
        {[["TOTAL EVENTS", metrics.total], ["TODAY", metrics.today], ["CASE EVENTS", metrics.cases], ["SUBMISSION EVENTS", metrics.submissions]].map(([label, value]) => (
          <article className="admin-audit-metric" key={label}><span>{label}</span><strong>{value}</strong></article>
        ))}
      </section>

      <section className="admin-audit-panel">
        <div className="admin-audit-filters">
          <label className="admin-audit-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search events, cases, actors..." aria-label="Search audit events" /></label>
          <select value={eventFilter} onChange={(event) => setEventFilter(event.target.value)} aria-label="Filter by event type">
            <option value="ALL">All Event Types</option>{eventTypes.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
          <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)} aria-label="Filter by workflow stage">
            <option value="ALL">All Workflow Stages</option>{stages.map((stage) => <option key={stage} value={stage}>{stage}</option>)}
          </select>
          <select value={dateFilter} onChange={(event) => setDateFilter(event.target.value)} aria-label="Filter by date">
            <option value="ALL">All Dates</option><option value="TODAY">Today</option><option value="7">Last 7 Days</option><option value="30">Last 30 Days</option>
          </select>
        </div>

        {loading ? <div className="admin-audit-state">Loading audit trails...</div> : error ? (
          <div className="admin-audit-state">Unable to display audit events.</div>
        ) : filteredEvents.length === 0 ? (
          <div className="admin-audit-state"><strong>No audit events found.</strong></div>
        ) : (
          <div className="admin-audit-table-wrap"><table className="admin-audit-table">
            <thead><tr><th>Timestamp</th><th>Event</th><th>Case</th><th>Patient</th><th>Actor</th><th>Workflow Stage</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>{filteredEvents.map((event) => <Fragment key={event.key}>
              <tr key={event.key}>
                <td>{formatTimestamp(event.timestamp)}</td><td><span className={`admin-audit-pill ${eventTone(event.eventType)}`}>{event.eventType}</span></td>
                <td className="admin-audit-mono">{event.caseId}</td><td>{event.patient}</td><td>{event.actor}</td><td>{event.stage}</td>
                <td><span className={`admin-audit-pill ${statusTone(event.status)}`}>{event.status}</span></td>
                <td><button type="button" className="admin-audit-view" aria-expanded={expanded === event.key} onClick={() => setExpanded(expanded === event.key ? null : event.key)}>{expanded === event.key ? "HIDE" : "VIEW"}</button></td>
              </tr>
              {expanded === event.key && <tr className="admin-audit-detail-row" key={`${event.key}-details`}><td colSpan={8}><dl className="admin-audit-details">{detailEntries(event).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{formatDetail(value)}</dd></div>)}</dl></td></tr>}
            </Fragment>)}</tbody>
          </table></div>
        )}
      </section>
    </main>
  );
}
