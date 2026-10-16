import { request } from "./client";
const getCanonicalPatient = (patientId) => request(`/api/canonical/patients/${encodeURIComponent(patientId)}`);
const listCanonicalPatients = (params = {}) => {
  const { signal, ...queryParams } = params;
  const query = new URLSearchParams();
  Object.entries(queryParams).forEach(([key, value]) => value !== undefined && value !== "" && query.set(key, String(value)));
  return request(`/api/canonical/patients${query.size ? `?${query}` : ""}`, { signal });
};
export {
  getCanonicalPatient,
  listCanonicalPatients
};