// Compatibility exports for screens that use the SIGNAL API naming convention.
// All requests go through the existing shared HTTP client and API modules.
import { apiBaseUrl, request } from "./client.js";
import { getCase, getCaseJourney, updateCaseReportFields } from "./cases.js";
import {
  getCaseAttestation,
  getCaseReview,
  getCaseValidation,
  getSubmissionReadiness,
  getFormDefinition,
  getImmediateNotification,
  processAcknowledgement,
  recordImmediateNotification,
  reviewCase,
  retrySubmission,
  submitEcr,
  trackSubmission,
  updateCaseReview,
  validateCase,
  markSubmissionReady,
  validateAttestation,
  attestCase,
  calculateDeadline,
  evaluateDeadline,
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
const renderForm = (caseId, formId, formVersion, fieldValues = {}) => request("/api/agents/form-rendering/render", {
  method: "POST",
  body: JSON.stringify({ case_id: caseId, form_id: formId, form_version: formVersion, field_values: fieldValues }),
});
const renderUrl = (renderId) => `${apiBaseUrl}/api/agents/form-rendering/${encodeURIComponent(renderId)}`;
const downloadRenderUrl = (renderId) => `${apiBaseUrl}/api/forms/${encodeURIComponent(renderId)}/download`;

export {
  attestation,
  persistAttestation,
  calculateDeadline,
  evaluateDeadlineEscalation,
  getCase,
  getCaseAttestation,
  getCaseReview,
  getCaseValidation,
  getSubmissionReadiness,
  getFormDefinition,
  getImmediateNotification,
  getJourney,
  manualReporting,
  markSubmissionReady,
  processAcknowledgement,
  renderForm,
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
