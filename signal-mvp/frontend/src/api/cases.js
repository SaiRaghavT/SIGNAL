import { request } from "./client";
const listCases = (params = {}) => {
  const { signal, ...queryParams } = params;
  const q = new URLSearchParams();
  Object.entries(queryParams).forEach(([k, v]) => v !== void 0 && q.set(k, String(v)));
  return request(`/api/cases${q.toString() ? `?${q}` : ""}`, { signal });
};
const getCase = (id) => request(`/api/cases/${encodeURIComponent(id)}`);
const updateCaseReportFields = (id, body) => request(`/api/cases/${encodeURIComponent(id)}/report-fields`, { method: "PATCH", body: JSON.stringify(body) });
const getCaseJourney = (id) => request(`/api/workflow/cases/${encodeURIComponent(id)}/journey`);
const getCaseTimeline = (id) => request(`/api/workflow/cases/${encodeURIComponent(id)}/timeline`);
const listCasesForPatient = (patientId) => listCases({ patient_id: patientId, page: 1, page_size: 10 });
export {
  getCase,
  getCaseJourney,
  getCaseTimeline,
  listCases,
  listCasesForPatient,
  updateCaseReportFields
};
