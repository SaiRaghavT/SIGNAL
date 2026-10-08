const API_BASE = "/api/admin";

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      `Request failed with status ${response.status}`;

    throw new Error(
      typeof message === "string" ? message : JSON.stringify(message)
    );
  }

  return data;
}

// ---------------------------------------------------------
// ADMIN DASHBOARD
// ---------------------------------------------------------

export async function getAdminDashboard() {
  return request(`${API_BASE}/dashboard`);
}

// ---------------------------------------------------------
// REPORTING QUEUE
// ---------------------------------------------------------

export async function getAdminQueue(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  });

  const query = searchParams.toString();

  return request(
    `${API_BASE}/queue${query ? `?${query}` : ""}`
  );
}

export async function getAdminQueueCase(caseId) {
  if (!caseId) {
    throw new Error("caseId is required");
  }

  return request(
    `${API_BASE}/queue/${encodeURIComponent(caseId)}`
  );
}

// ---------------------------------------------------------
// CLINICAL STAFF → ADMIN QUEUE
// ---------------------------------------------------------

export async function queueCase(caseId, submissionMode) {
  if (!caseId) {
    throw new Error("caseId is required");
  }

  if (!["IMMEDIATE", "INDIVIDUAL", "BATCH"].includes(submissionMode)) {
    throw new Error(
      "submissionMode must be IMMEDIATE, INDIVIDUAL, or BATCH"
    );
  }

  return request(`/api/cases/${encodeURIComponent(caseId)}/queue`, {
    method: "POST",
    body: JSON.stringify({
      submission_mode: submissionMode,
    }),
  });
}

// ---------------------------------------------------------
// CASE DISPATCH
// ---------------------------------------------------------

export async function dispatchCase(caseId) {
  if (!caseId) {
    throw new Error("caseId is required");
  }

  return request(
    `${API_BASE}/cases/${encodeURIComponent(caseId)}/dispatch`,
    {
      method: "POST",
    }
  );
}

// ---------------------------------------------------------
// SUBMISSIONS
// ---------------------------------------------------------

export async function getAdminSubmissions(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  });

  const query = searchParams.toString();

  return request(
    `${API_BASE}/submissions${query ? `?${query}` : ""}`
  );
}

export async function clearAdminSessionSubmissions(submissionIds) {
  if (!Array.isArray(submissionIds) || submissionIds.length === 0) {
    return { deleted: 0, submission_ids: [] };
  }

  return request(`${API_BASE}/session/submissions`, {
    method: "DELETE",
    body: JSON.stringify({ submission_ids: submissionIds }),
  });
}

export async function getAdminSubmission(submissionId) {
  if (!submissionId) {
    throw new Error("submissionId is required");
  }

  return request(
    `${API_BASE}/submissions/${encodeURIComponent(submissionId)}`
  );
}

// ---------------------------------------------------------
// ACKNOWLEDGEMENT
// ---------------------------------------------------------

export async function acknowledgeSubmission(submissionId, payload = {}) {
  if (!submissionId) {
    throw new Error("submissionId is required");
  }

  return request(
    `${API_BASE}/submissions/${encodeURIComponent(
      submissionId
    )}/acknowledge`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

// ---------------------------------------------------------
// RETRY
// ---------------------------------------------------------

export async function retrySubmission(submissionId) {
  if (!submissionId) {
    throw new Error("submissionId is required");
  }

  return request(
    `${API_BASE}/submissions/${encodeURIComponent(
      submissionId
    )}/retry`,
    {
      method: "POST",
    }
  );
}

// ---------------------------------------------------------
// BATCHES
// ---------------------------------------------------------

export async function getAdminBatches(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  });

  const query = searchParams.toString();

  return request(
    `${API_BASE}/batches${query ? `?${query}` : ""}`
  );
}

export async function createAdminBatch(caseIds) {
  if (!Array.isArray(caseIds) || caseIds.length === 0) {
    throw new Error("At least one case ID is required");
  }

  return request(`${API_BASE}/batches`, {
    method: "POST",
    body: JSON.stringify({
      case_ids: caseIds,
    }),
  });
}

export async function getAdminBatch(batchId) {
  if (!batchId) {
    throw new Error("batchId is required");
  }

  return request(
    `${API_BASE}/batches/${encodeURIComponent(batchId)}`
  );
}

export async function dispatchAdminBatch(batchId) {
  if (!batchId) {
    throw new Error("batchId is required");
  }

  return request(
    `${API_BASE}/batches/${encodeURIComponent(batchId)}/dispatch`,
    {
      method: "POST",
    }
  );
}

// ---------------------------------------------------------
// DEADLINES
// ---------------------------------------------------------

export async function getAdminDeadlines(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  });

  const query = searchParams.toString();

  return request(
    `${API_BASE}/deadlines${query ? `?${query}` : ""}`
  );
}

// ---------------------------------------------------------
// AUDIT
// ---------------------------------------------------------

export async function getAdminAudit(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  });

  const query = searchParams.toString();

  return request(
    `${API_BASE}/audit${query ? `?${query}` : ""}`
  );
}
