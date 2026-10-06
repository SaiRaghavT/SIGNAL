import { request } from "./client";
const listCases = (params = {}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== void 0 && q.set(k, String(v)));
  return request(`/api/cases${q.toString() ? `?${q}` : ""}`);
};
const getCase = (id) => request(`/api/cases/${encodeURIComponent(id)}`);
const updateCaseReportFields = (id, body) => request(`/api/cases/${encodeURIComponent(id)}/report-fields`, { method: "PATCH", body: JSON.stringify(body) });
const getCaseJourney = (id) => request(`/api/workflow/cases/${encodeURIComponent(id)}/journey`);
const getCaseTimeline = (id) => request(`/api/workflow/cases/${encodeURIComponent(id)}/timeline`);
const listCasesForPatient = (patientId) => listCases({ patient_id: patientId, page: 1, page_size: 10 });
const resetDemoCaseWorkflow = (id) => request(`/api/demo/cases/${encodeURIComponent(id)}/reset-workflow`, {
  method: "POST",
  body: JSON.stringify({ reset_scope: "REPORTING_WORKFLOW" }),
});
export {
  getCase,
  getCaseJourney,
  getCaseTimeline,
  listCases,
  listCasesForPatient,
  resetDemoCaseWorkflow,
  updateCaseReportFields
};
