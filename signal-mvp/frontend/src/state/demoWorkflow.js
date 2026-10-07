const VERSION = 1;
const CHANGE_EVENT = "signal:demo-workflow-change";

export const DEMO_WORKFLOW_STAGES = [
  "validation",
  "review",
  "attestation",
  "notification",
  "reporting",
  "submission",
  "acknowledgement",
];

const storageKey = (caseId) => `signal_demo_workflow_${encodeURIComponent(caseId)}`;

export function readDemoWorkflow(caseId) {
  if (!caseId || typeof window === "undefined") return null;
  try {
    const value = JSON.parse(window.sessionStorage.getItem(storageKey(caseId)) || "null");
    return value?.version === VERSION && value?.stages ? value : null;
  } catch {
    return null;
  }
}

function writeDemoWorkflow(caseId, current, stages) {
  if (!caseId || typeof window === "undefined") return null;
  const next = {
    version: VERSION,
    caseId,
    sessionId: current?.sessionId || `${Date.now()}`,
    startedAt: current?.startedAt || new Date().toISOString(),
    stages: { ...current?.stages, ...stages },
  };
  try {
    window.sessionStorage.setItem(storageKey(caseId), JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { caseId } }));
  } catch {
    return null;
  }
  return next;
}

export function resetDemoWorkflow(caseId) {
  return writeDemoWorkflow(caseId, null, Object.fromEntries(DEMO_WORKFLOW_STAGES.map((stage) => [stage, "NOT_STARTED"])));
}

export function completeDemoWorkflowStage(caseId, stage) {
  if (!DEMO_WORKFLOW_STAGES.includes(stage)) return readDemoWorkflow(caseId);
  return writeDemoWorkflow(caseId, readDemoWorkflow(caseId), { [stage]: "COMPLETED" });
}

export function demoWorkflowChangeEvent() {
  return CHANGE_EVENT;
}
