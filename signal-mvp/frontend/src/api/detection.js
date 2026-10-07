import { request } from "./client";

const detectPatientCandidates = (patientId) => request("/api/detection/candidates", {
  method: "POST",
  body: JSON.stringify({ patient_id: patientId }),
});
const getCandidate = (candidateId) => request(`/api/candidates/${encodeURIComponent(candidateId)}`);
const processCandidate = (candidateId) => request("/api/candidate/process", {
  method: "POST",
  body: JSON.stringify({ candidate_id: candidateId }),
});
const persistDetectedCandidate = (patientId, candidate) => request("/api/detection/candidates/persist", {
  method: "POST",
  body: JSON.stringify({ patient_id: patientId, candidate }),
});

export { detectPatientCandidates, getCandidate, persistDetectedCandidate, processCandidate };
