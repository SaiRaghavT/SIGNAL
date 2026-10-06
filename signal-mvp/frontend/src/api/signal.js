// Compatibility exports for screens that use the SIGNAL API naming convention.
// All requests go through the existing shared HTTP client and API modules.
import { apiBaseUrl, request } from "./client.js";
import { getCase, getCaseJourney, updateCaseReportFields } from "./cases.js";
import {
  getCaseAttestation,
  getCaseReview,
  getCaseValidation,
  getImmediateNotification,
  processAcknowledgement,
  recordImmediateNotification,
  reviewCase,
  retrySubmission,
  submitEcr,
  trackSubmission,
  updateCaseReview,
  validateCase,
  validateAttestation,
  attestCase,
  calculateDeadline,
  evaluateDeadline,
  followUp,
} from "./workflow.js";

const getJourney = getCaseJourney;
const updateCaseReport = updateCaseReportFields;
const attestation = validateAttestation;
const persistAttestation = attestCase;
const evaluateDeadlineEscalation = evaluateDeadline;
const manualReporting = (caseId, reportingMethod, notes = "") => request("/api/agents/manual-reporting/prepare", {
  method: "POST",
  body: JSON.stringify({ case_id: caseId, reporting_method: reportingMethod, notes }),
});
const renderForm = (caseId, body) => request("/api/agents/form-rendering/render", {
  method: "POST",
  body: JSON.stringify({ case_id: caseId, ...body }),
});
const renderSeedPatientForm = (patientId, body) => request(`/api/forms/seed-patients/${encodeURIComponent(patientId)}/render`, {
  method: "POST",
  body: JSON.stringify({ case_id: patientId, ...body }),
});
const renderUrl = (renderId) => `${apiBaseUrl}/api/agents/form-rendering/${encodeURIComponent(renderId)}`;
const downloadRenderUrl = (renderId) => `${apiBaseUrl}/api/forms/${encodeURIComponent(renderId)}/download`;
const processFollowup = (caseId, action, notes = "", submissionId) => followUp({
  case_id: caseId,
  action,
  ...(notes.trim() ? { notes: notes.trim() } : {}),
  ...(submissionId ? { submission_id: submissionId } : {}),
});

export {
  attestation,
  persistAttestation,
  calculateDeadline,
  evaluateDeadlineEscalation,
  getCase,
  getCaseAttestation,
  getCaseReview,
  getCaseValidation,
  getImmediateNotification,
  getJourney,
  processFollowup,
  manualReporting,
  processAcknowledgement,
  renderForm,
  renderSeedPatientForm,
  renderUrl,
  downloadRenderUrl,
  recordImmediateNotification,
  reviewCase,
  retrySubmission,
  submitEcr,
  trackSubmission,
  updateCaseReview,
  updateCaseReport,
  validateCase,
};
