const uploadPatientDocument = async ({
  patientId,
  file,
  documentType,
  title,
}) => {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("patient_id", patientId);
  formData.append(
    "source_document_id",
    `UI-${crypto.randomUUID()}`
  );

  if (documentType) {
    formData.append("document_type", documentType);
  }

  if (title) {
    formData.append("title", title);
  }

  const baseUrl =
    import.meta.env.VITE_API_URL ||
    "http://127.0.0.1:8000";

  const response = await fetch(
    `${baseUrl}/api/ingestion/documents`,
    {
      method: "POST",
      body: formData,
    }
  );

  const contentType =
    response.headers.get("content-type") || "";

  const data =
    contentType.includes("application/json")
      ? await response.json()
      : {};

  if (!response.ok) {
    throw new Error(
      data?.detail ||
        data?.message ||
        "Document upload failed."
    );
  }

  return data;
};

export { uploadPatientDocument };