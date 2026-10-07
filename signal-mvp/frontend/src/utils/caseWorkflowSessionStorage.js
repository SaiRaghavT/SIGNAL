const STORAGE_PREFIX = "signal:case-workflow-session:";

function storageKey(caseId) {
  return `${STORAGE_PREFIX}${encodeURIComponent(String(caseId || ""))}`;
}

export function readCaseWorkflowSession(caseId) {
  if (!caseId || typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(storageKey(caseId)) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function writeCaseWorkflowSession(caseId, value) {
  if (!caseId || typeof window === "undefined") return false;
  try {
    window.sessionStorage.setItem(storageKey(caseId), JSON.stringify(value || {}));
    return true;
  } catch {
    return false;
  }
}
