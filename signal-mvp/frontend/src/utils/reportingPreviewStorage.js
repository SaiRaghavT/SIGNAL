const STORAGE_PREFIX = "signal:reporting-preview:";

function storageKey(caseId) {
  return `${STORAGE_PREFIX}${encodeURIComponent(String(caseId || ""))}`;
}

export function readReportingPreview(caseId) {
  if (!caseId || typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(storageKey(caseId)) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function writeReportingPreview(caseId, values) {
  if (!caseId || typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(storageKey(caseId), JSON.stringify(values || {}));
  } catch {
    // Browser storage can be unavailable; the in-page preview still works.
  }
}
