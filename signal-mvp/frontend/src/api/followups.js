import { request } from "./client.js";

export function listFollowUps(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const encoded = query.toString();
  return request(`/api/follow-ups${encoded ? `?${encoded}` : ""}`);
}

export function createFollowUp(payload) {
  return request("/api/follow-ups", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function ensureSubmissionFollowUp(caseId, submissionId) {
  const findExisting = async () => {
    const result = await listFollowUps({ search: submissionId, page_size: 100 });
    return (result?.items || []).find((item) => item.submission_id === submissionId) || null;
  };

  const existing = await findExisting();
  if (existing) return existing;

  try {
    return await createFollowUp({
      case_id: caseId,
      submission_id: submissionId,
      action: "OUTCOME_UPDATE",
      next_action: "Review the public health authority acknowledgement",
      notes: "Outcome tracking created after successful submission. Any simulated destination or follow-up is identified by the backend.",
    });
  } catch (error) {
    // A request can time out after the backend commits. Recheck by the actual
    // submission ID before surfacing the error so that a retry cannot duplicate it.
    const committed = await findExisting().catch(() => null);
    if (committed) return committed;
    throw error;
  }
}
