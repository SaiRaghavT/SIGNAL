import React, { useState } from "react";
import { trackSubmission, acknowledge, retrySubmission } from "../api/workflow.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import { SignalLoading } from "../components/ui/SignalLoading.jsx";

export function SubmissionsPage() {
  const [id, setId] = useState("");
  const [result, setResult] = useState("");
  const [operation, setOperation] = useState("");

  async function run(label, action) {
    setOperation(label); setResult("");
    try { setResult(JSON.stringify(await action(), null, 2)); }
    catch (err) { setResult(`Error: ${err?.message || "Submission action failed."}`); }
    finally { setOperation(""); }
  }

  const loadingCopy = operation === "Track"
    ? ["Checking Submission", "Retrieving the current submission status."]
    : operation === "Acknowledgement"
      ? ["Processing Response", "Processing the public-health acknowledgement."]
      : ["Retrying Submission", "Retrying the submission through its configured destination."];

  return <section className="submissions-page">
    <PageHeader title="Submissions" subtitle="Submission actions available in the backend. No submission-list endpoint is currently exposed." />
    <div className="panel form-grid">
      <label>Submission ID<input value={id} onChange={(event) => setId(event.target.value)} /></label>
      <div className="button-row">
        <button className="primary" onClick={() => run("Track", () => trackSubmission(id))} disabled={!id || Boolean(operation)}>Track</button>
        <button onClick={() => run("Acknowledgement", () => acknowledge(id))} disabled={!id || Boolean(operation)}>Process acknowledgement</button>
        <button onClick={() => run("Retry", () => retrySubmission(id))} disabled={!id || Boolean(operation)}>Retry</button>
      </div>
      {operation && <SignalLoading title={loadingCopy[0]} message={loadingCopy[1]} />}
      {result && <pre className="result">{result}</pre>}
    </div>
  </section>;
}
