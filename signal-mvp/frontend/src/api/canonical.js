import { request } from "./client";
const getCanonicalPatient = (patientId) => request(`/api/canonical/patients/${encodeURIComponent(patientId)}`);
const getCanonicalPatientAnatomy = (patientId, { refresh = false } = {}) => {
  const refreshQuery = refresh ? `?refresh=true&_=${Date.now()}` : "";
  return request(`/api/canonical/patients/${encodeURIComponent(patientId)}/anatomy${refreshQuery}`, {
    cache: refresh ? "no-store" : "default",
  });
};
const listCanonicalPatients = (params = {}) => {
  const { signal, ...queryParams } = params;
  const query = new URLSearchParams();
  Object.entries(queryParams).forEach(([key, value]) => value !== undefined && value !== "" && query.set(key, String(value)));
  return request(`/api/canonical/patients${query.size ? `?${query}` : ""}`, { signal });
};
export {
  getCanonicalPatient,
  getCanonicalPatientAnatomy,
  listCanonicalPatients
};
