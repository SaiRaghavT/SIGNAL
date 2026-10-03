import { request } from "./client";
const assembleCase = (body) => request("/api/agents/case-assembly/assemble", { method: "POST", body: JSON.stringify(body) });
const calculateDeadline = (body) => request("/api/agents/deadline/calculate", { method: "POST", body: JSON.stringify(body) });
const evaluateDeadline = (body) => request("/api/agents/deadline-escalation/evaluate", { method: "POST", body: JSON.stringify(body) });
const validateAttestation = (body) => request("/api/agents/attestation/validate", { method: "POST", body: JSON.stringify(body) });
const prepareManualReport = (body) => request("/api/agents/manual-reporting/prepare", { method: "POST", body: JSON.stringify(body) });
const renderForm = (body) => request("/api/agents/form-rendering/render", { method: "POST", body: JSON.stringify(body) });
const getFormDefinition = (formId) => request(`/api/agents/form-rendering/forms/${encodeURIComponent(formId)}`);
const submitEcr = (caseId) => request("/api/agents/ecr-submission/submit", { method: "POST", body: JSON.stringify({ case_id: caseId }) });
const trackSubmission = (submissionId) => request("/api/agents/submission-tracking/track", { method: "POST", body: JSON.stringify({ submission_id: submissionId }) });
const acknowledge = (submissionId) => request("/api/agents/acknowledgement/process", { method: "POST", body: JSON.stringify({ submission_id: submissionId }) });
const retrySubmission = (submissionId, reason) => request("/api/agents/retry-resubmission/retry", { method: "POST", body: JSON.stringify({ submission_id: submissionId, reason }) });
const followUp = (body) => request("/api/agents/public-health-followup/process", { method: "POST", body: JSON.stringify(body) });
const auditEvent = (body) => request("/api/agents/audit/events", { method: "POST", body: JSON.stringify(body) });
const listAuditEvents = (entityType, entityId) => {
  const query = new URLSearchParams({ entity_type: entityType, entity_id: entityId });
  return request(`/api/agents/audit/events?${query}`);
};
const documentIntelligence = (documents) => request("/api/agents/document-intelligence/process", { method: "POST", body: JSON.stringify({ documents }) });
const nlpEvidence = (documents) => request("/api/agents/nlp-evidence/extract", { method: "POST", body: JSON.stringify({ documents }) });
export {
  acknowledge,
  assembleCase,
  auditEvent,
  listAuditEvents,
  calculateDeadline,
  documentIntelligence,
  evaluateDeadline,
  followUp,
  getFormDefinition,
  nlpEvidence,
  prepareManualReport,
  renderForm,
  retrySubmission,
  submitEcr,
  trackSubmission,
  validateAttestation
};
