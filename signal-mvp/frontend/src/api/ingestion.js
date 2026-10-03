import { request } from "./client";
const ingestFhir = (bundle, source = "fhir") => request(`/api/ingestion/fhir?source=${encodeURIComponent(source)}`, { method: "POST", body: JSON.stringify(bundle) });
const ingestFhirBatch = (bundles, source = "fhir") => request(`/api/ingestion/fhir/batch?source=${encodeURIComponent(source)}`, { method: "POST", body: JSON.stringify({ bundles }) });
const ingestHl7 = (message) => request("/api/ingestion/hl7", { method: "POST", body: JSON.stringify({ message }) });
async function ingestDocument(file, patientId, sourceDocumentId, documentType, title) {
  const form = new FormData();
  form.append("file", file);
  form.append("patient_id", patientId);
  form.append("source_document_id", sourceDocumentId);
  if (documentType) form.append("document_type", documentType);
  if (title) form.append("title", title);
  return request("/api/ingestion/documents", { method: "POST", body: form });
}
export {
  ingestDocument,
  ingestFhir,
  ingestFhirBatch,
  ingestHl7
};
