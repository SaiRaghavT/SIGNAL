
const API_BASE_URL =
  import.meta.env.VITE_SIGNAL_API_URL || "http://localhost:8000";

export function getPhaResourceUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      // Keep the HTTP error message if the response isn't JSON.
    }

    throw new Error(message);
  }

  return response.json();
}

export async function getIncomingReports() {
  return request("/api/pha/reports");
}

export async function getReportDetails(submissionId) {
  return request(
    `/api/pha/reports/${encodeURIComponent(submissionId)}`
  );
}

export async function acknowledgePhaReceipt(submissionId) {
  return request(
    `/api/pha/reports/${encodeURIComponent(submissionId)}/acknowledgement`,
    { method: "POST" }
  );
}

export async function submitPhaDecision(submissionId, payload) {
  return request(
    `/api/pha/reports/${encodeURIComponent(submissionId)}/decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: payload.decision,
        reviewer: payload.reviewer,
        reason: payload.reason || null,
        requested_information: payload.requested_information || null,
      }),
    }
  );
}

export async function getPhaDecisionHistory(submissionId) {
  return request(
    `/api/pha/reports/${encodeURIComponent(submissionId)}/decisions`
  );
}
