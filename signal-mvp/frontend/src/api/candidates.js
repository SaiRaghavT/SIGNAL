import { request } from "./client.js";

export function listCandidates(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return request(`/api/candidates${query.size ? `?${query}` : ""}`);
}

export function getCandidate(candidateId) {
  return request(`/api/candidates/${encodeURIComponent(candidateId)}`);
}

export function detectPatientCandidates(patientId) {
  return request("/api/detection/candidates", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId }),
  });
}
