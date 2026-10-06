function readableEvidence(value) {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return "";
  const nested = value.evidence && typeof value.evidence === "object" ? value.evidence : {};
  return value.display || value.description || value.text || value.name ||
    value.value?.text || value.value?.numeric || value.value?.code ||
    nested.display || nested.description || nested.text || value.code ||
    value.source_id || "";
}

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
}

export function candidateForUi(candidate, context = {}) {
  const patient = context.patient || candidate.patient || {};
  const fullName = [patient.first_name, patient.last_name].filter(Boolean).join(" ").trim();
  const name = fullName || patient.name || "Name not provided";
  const patientAddress = patient.address && typeof patient.address === "object" ? patient.address : {};
  const conditions = context.conditions || [];
  const labResults = context.lab_results || [];
  const observations = context.observations || [];
  const encounters = context.encounters || [];
  const detectionEvidence = candidate.evidence || [];
  const confidence = Number(candidate.confidence || 0);
  const normalizedStatus = String(candidate.status || "POTENTIAL").toUpperCase();
  const birthDate = patient.date_of_birth;
  const age = birthDate ? Math.max(0, Math.floor((Date.now() - new Date(birthDate).getTime()) / 31557600000)) : null;
  const facility = typeof context.facility === "string" ? context.facility :
    context.facility?.name || encounters.find((item) => item.facility_id)?.facility_id || "Not available";
  const evidenceItems = detectionEvidence.map((item) => {
    const sourceId = item?.source_id;
    const record = [...conditions, ...labResults, ...observations].find((entry) =>
      [entry.condition_id, entry.lab_result_id, entry.observation_id, entry.source_condition_id, entry.source_lab_result_id, entry.source_observation_id].some((id) => id && id === sourceId)
    );
    const recordCode = record?.code || record?.test || {};
    const label = readableEvidence(item) || record?.display || recordCode.display || recordCode.code || "Clinical evidence";
    return {
      label,
      source: record?.provenance?.source_resource || item?.source_type || record?.provenance?.source || "FHIR clinical record",
      date: item?.date || record?.recorded_time || record?.onset_time || record?.issued_time || record?.effective_time || null,
      sourceId: sourceId || null,
      encounterId: record?.encounter_id || null,
    };
  }).filter((item) => item.label);
  const evidence = [...new Set(evidenceItems.map((item) => item.label))];
  const relatedEncounterIds = new Set(evidenceItems.map((item) => item.encounterId).filter(Boolean));
  const orderedEncounters = [...encounters].sort((a, b) => new Date(b.start_time || 0) - new Date(a.start_time || 0));
  const selectedEncounters = relatedEncounterIds.size
    ? orderedEncounters.filter((item) => relatedEncounterIds.has(item.encounter_id)).concat(orderedEncounters.filter((item) => !relatedEncounterIds.has(item.encounter_id)).slice(0, 9))
    : orderedEncounters.slice(0, 10);

  return {
    id: candidate.candidate_id,
    patientId: candidate.patient_id || patient.patient_id,
    patient: name,
    initials: name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase(),
    mrn: patient.source_patient_id || patient.patient_id || "Not available",
    dob: formatDate(patient.date_of_birth),
    sex: patient.sex || "Not available",
    age: age ?? "Not available",
    facility,
    condition: candidate.disease || "Condition requires review",
    jurisdiction: candidate.jurisdiction || patientAddress.state || patient.state || "Pending resolution",
    priority: confidence >= 0.9 ? "High" : confidence >= 0.75 ? "Medium" : "Review",
    detected: formatDate(candidate.created_at),
    status: normalizedStatus === "PROCESSED" ? "Pending Admin Verification" :
      normalizedStatus === "REJECTED" ? "Rejected" : "Needs Review",
    rule: candidate.disease || "Reporting rule pending",
    deadline: formatDate(candidate.deadline?.deadline || context.deadline?.deadline),
    confidence: confidence ? `${Math.round(confidence * 100)}%` : "Not scored",
    evidence: [...new Set(evidence)],
    evidenceItems,
    encounters: selectedEncounters.map((item) => ({ ...item, displayDate: formatDate(item.start_time), displayType: item.encounter_type || "Encounter" })),
    context,
    raw: candidate,
  };
}
