import { request } from "./client";

const detectPatientCandidates = (patientId) => request("/api/detection/candidates", {
  method: "POST",
  body: JSON.stringify({ patient_id: patientId }),
});

export { detectPatientCandidates };
