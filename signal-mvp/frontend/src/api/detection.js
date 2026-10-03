import { request } from "./client";
const detectCandidates = (patientId) => request("/api/detection/candidates", { method: "POST", body: JSON.stringify({ patient_id: patientId }) });
const extractEvidence = (documents) => request("/api/detection/evidence", { method: "POST", body: JSON.stringify({ documents }) });
const analyzeCluster = (body) => request("/api/clusters/analyze", { method: "POST", body: JSON.stringify(body) });
const processCandidate = (body) => request("/api/candidate/process", { method: "POST", body: JSON.stringify(body) });
const disposeCandidate = (body) => request("/api/candidate/disposition", { method: "POST", body: JSON.stringify(body) });
export {
  analyzeCluster,
  detectCandidates,
  disposeCandidate,
  extractEvidence,
  processCandidate
};
