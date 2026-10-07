const STORAGE_PREFIX = "signal:missing-information:";

function storageKey(caseId) {
  return `${STORAGE_PREFIX}${encodeURIComponent(String(caseId || ""))}`;
}

export function readMissingInformation(caseId) {
  if (!caseId || typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(storageKey(caseId)) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function writeMissingInformation(caseId, values) {
  if (!caseId || typeof window === "undefined") return false;
  try {
    window.sessionStorage.setItem(storageKey(caseId), JSON.stringify(values || {}));
    return true;
  } catch {
    return false;
  }
}
