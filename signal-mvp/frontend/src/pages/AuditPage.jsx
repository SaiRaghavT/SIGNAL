import React, { useState } from "react";
import { Activity, Check, ScrollText, ShieldCheck } from "lucide-react";
import { auditEvent } from "../api/workflow.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";
import "../styles/audit-page.css";

export function AuditPage() {
  const [body, setBody] = useState('{"entity_type":"case","entity_id":"CASE-ID","event_type":"UI_ACTION","actor_type":"user","actor_id":"reporting_user","source_agent":"frontend","status":"SUCCESS","description":"Frontend audit event","metadata":{}}');
  const [result, setResult] = useState("");
  const [working, setWorking] = useState(false);

  async function createEvent() {
    setWorking(true); setResult("");
    try { setResult(JSON.stringify(await auditEvent(JSON.parse(body)), null, 2)); }
    catch (err) { setResult(`Error: ${err?.message || "Unable to record audit event."}`); }
    finally { setWorking(false); }
  }

  return <section className="audit-page">
    <PageHeader title="Technical / Audit" subtitle="Record a traceable event in the SIGNAL backend audit ledger." />
    <div className="audit-intro">
      <span className="audit-intro-icon"><ScrollText size={22} /></span>
      <div><strong>Keep workflow actions accountable</strong><p>Submit a structured event payload and review the backend response. Events are recorded only after the audit service accepts them.</p></div>
      <span className="audit-ledger-tag"><ShieldCheck size={15} /> Backend ledger</span>
    </div>

    <div className="audit-workspace">
      <section className="audit-composer">
        <div className="audit-composer-heading"><div><span>EVENT COMPOSER</span><h3>Create an audit event</h3><p>Enter valid JSON using the supported audit event fields.</p></div><span className="audit-code-badge">JSON</span></div>
        <label className="audit-payload-label" htmlFor="audit-payload">Event payload</label>
        <textarea id="audit-payload" className="code-input audit-code-input" value={body} onChange={(event) => setBody(event.target.value)} spellCheck="false" />
        <div className="audit-composer-footer"><span>Include entity, event, actor, source, and status details.</span><button className="primary" onClick={createEvent} disabled={working}>{working ? "Recording…" : <><Check size={16} /> Record event</>}</button></div>
        {working && <SignalLoading title="Recording audit event" message="Sending the event to the backend audit ledger." />}
      </section>

      <aside className="audit-guide">
        <span className="audit-guide-kicker"><Activity size={15} /> AUDIT LEDGER</span>
        <h3>What gets recorded</h3>
        <p>Each event should explain what happened, which entity it affected, and which workflow component recorded it.</p>
        <ul><li><strong>Entity</strong><span>Patient, case, submission, or workflow record</span></li><li><strong>Actor</strong><span>User or service responsible for the event</span></li><li><strong>Outcome</strong><span>Success, failure, or review status</span></li></ul>
        <div className="audit-guide-note"><ShieldCheck size={16} /><span>The backend response confirms whether the event was persisted.</span></div>
      </aside>
    </div>

    {result && <section className="audit-result"><div><span>BACKEND RESPONSE</span><h3>Event result</h3></div><pre className="result">{result}</pre></section>}
  </section>;
}
