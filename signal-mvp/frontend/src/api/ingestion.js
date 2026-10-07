import { request } from "./client";

const uploadPatientDocument = (formData) => request("/api/ingestion/documents", {
  method: "POST",
  body: formData,
});

export { uploadPatientDocument };
