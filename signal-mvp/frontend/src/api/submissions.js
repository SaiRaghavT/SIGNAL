import { request } from "./client.js";

export function listSubmissions({ page = 1, page_size = 100 } = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(page_size),
  });
  return request(`/api/submissions?${query.toString()}`);
}

export function listClinicalSubmissionTracking({ page = 1, page_size = 100 } = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(page_size),
  });
  return request(`/api/clinical/submissions?${query.toString()}`);
}

export function getSubmissionAcknowledgement(submissionId) {
  if (!submissionId) throw new Error("submissionId is required");
  return request(`/api/submissions/${encodeURIComponent(submissionId)}/acknowledgement`);
}
