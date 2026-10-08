const STORAGE_KEY = "signal-clinical-information-requests";
export const CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT = "signal-clinical-information-request-updated";

function readRequests() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(stored) ? stored.filter((request) => request?.caseId) : [];
  } catch {
    return [];
  }
}

function writeRequests(requests) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(requests));
  window.dispatchEvent(new CustomEvent(CLINICAL_INFORMATION_REQUEST_UPDATED_EVENT));
}

export function getOpenClinicalInformationRequest(caseId) {
  if (!caseId) return null;
  return readRequests().find((request) => request.caseId === caseId && request.status === "OPEN") || null;
}

export function countOpenClinicalInformationRequests() {
  return readRequests().filter((request) => request.status === "OPEN").length;
}

export function upsertClinicalInformationRequest(request) {
  if (!request?.caseId) throw new Error("caseId is required for an information request.");
  const current = readRequests();
  const existingOpen = current.find((item) => item.caseId === request.caseId && item.status === "OPEN");
  const nextRequest = {
    caseId: request.caseId,
    patientId: request.patientId || existingOpen?.patientId || null,
    patientName: request.patientName || existingOpen?.patientName || null,
    missingFields: Array.isArray(request.missingFields) ? [...request.missingFields] : [],
    message: request.message,
    requestedAt: request.requestedAt || new Date().toISOString(),
    status: "OPEN",
    source: "ADMIN_INDIVIDUAL_REVIEW",
  };
  const withoutOpenForCase = current.filter((item) => !(item.caseId === request.caseId && item.status === "OPEN"));
  const updatedRequest = existingOpen ? { ...existingOpen, ...nextRequest } : nextRequest;
  writeRequests([...withoutOpenForCase, updatedRequest]);
  return updatedRequest;
}

export function resolveClinicalInformationRequest(caseId, resolvedAt = new Date().toISOString()) {
  if (!caseId) return false;
  const current = readRequests();
  let resolved = false;
  const next = current.map((request) => {
    if (request.caseId !== caseId || request.status !== "OPEN") return request;
    resolved = true;
    return { ...request, status: "RESOLVED", resolvedAt };
  });
  if (resolved) writeRequests(next);
  return resolved;
}
