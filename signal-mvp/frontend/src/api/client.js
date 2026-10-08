const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
async function request(path, options = {}) {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof data === "object" ? data?.detail : null;
    const caseReasons = Array.isArray(detail?.cases)
      ? detail.cases.filter((item) => !item.eligible).map((item) => `${item.patient?.name || item.patient?.patient_id || item.case_id}: ${(item.blockers || []).join(", ")}`).join("; ")
      : "";
    const message = typeof detail === "string"
      ? detail
      : typeof detail?.message === "string"
        ? [detail.message, caseReasons].filter(Boolean).join(" ")
        : Array.isArray(detail)
          ? detail.map((item) => item?.msg).filter(Boolean).join("; ") || `Request failed (${response.status})`
          : `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}
async function requestBlob(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    const detail = typeof data === "object" ? data?.detail : null;
    const message = typeof detail === "string"
      ? detail
      : typeof detail?.message === "string"
        ? detail.message
        : Array.isArray(detail)
          ? detail.map((item) => item?.msg).filter(Boolean).join("; ") || `Request failed (${response.status})`
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.blob();
}
const apiBaseUrl = API_BASE_URL;
export {
  apiBaseUrl,
  request,
  requestBlob
};
