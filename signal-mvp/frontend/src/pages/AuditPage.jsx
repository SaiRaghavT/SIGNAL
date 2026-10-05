import React, { useState } from "react";
import { auditEvent } from "../api/workflow.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";

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
    <PageHeader title="Technical / Audit" subtitle="Write an audit event through the backend audit ledger." />
    <div className="panel">
      <label className="form-grid">Audit event payload<textarea className="code-input" value={body} onChange={(event) => setBody(event.target.value)} /></label>
      <div className="button-row"><button className="primary" onClick={createEvent} disabled={working}>Create audit event</button></div>
      {working && <SignalLoading title="Recording Audit Event" message="Sending the audit event to the backend event service." />}
      {result && <pre className="result">{result}</pre>}
    </div>
  </section>;
}
