import { useState } from "react";
import { useParams } from "react-router-dom";
import { followUp } from "../api/workflow.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";

const FOLLOW_UP_ACTIONS = ["REQUEST_INFORMATION", "INVESTIGATION", "OUTCOME_UPDATE", "CLOSE"];

export function FollowupsPage() {
  const { caseId: routeCaseId } = useParams();
  const [caseId, setCaseId] = useState(routeCaseId || "");
  const [action, setAction] = useState("REQUEST_INFORMATION");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState("");
  const [working, setWorking] = useState(false);

  async function run() {
    setWorking(true); setResult("");
    try { setResult(JSON.stringify(await followUp({ case_id: caseId, action, notes }), null, 2)); }
    catch (err) { setResult(`Error: ${err?.message || "Follow-up could not be processed."}`); }
    finally { setWorking(false); }
  }

  return <section className="followups-page">
    <PageHeader title="Follow-ups" subtitle="PHA follow-up processing is persisted locally; external PHA interaction is simulated by the backend." />
    <div className="panel form-grid">
      <label>Case ID<input value={caseId} onChange={(event) => setCaseId(event.target.value)} /></label>
      <label>Action<select value={action} onChange={(event) => setAction(event.target.value)}>{FOLLOW_UP_ACTIONS.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <button className="primary" onClick={run} disabled={!caseId || working}>Process follow-up</button>
      {working && <SignalLoading title="Processing Follow-up" message="Recording the selected public-health follow-up action." />}
      {result && <pre className="result">{result}</pre>}
    </div>
  </section>;
}
