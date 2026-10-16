export function getSignalSourceId(signal) {
  const evidence = signal?.evidence && typeof signal.evidence === "object"
    ? signal.evidence
    : {};
  const value = evidence.source_id ?? evidence.condition_id ?? evidence.lab_result_id ??
    evidence.document_id ?? signal?.source_id ?? signal?.condition_id ??
    signal?.lab_result_id ?? signal?.document_id;
  return value == null || value === "" ? "" : String(value);
}

export function groupSignalsByVerifiedSource(signals, patientContext = {}) {
  const sourceAliases = new Map();
  for (const lab of patientContext?.lab_results || patientContext?.labs || []) {
    const labId = lab?.lab_result_id ?? lab?.source_lab_result_id ?? lab?.diagnostic_report_id ?? lab?.id;
    if (labId == null || labId === "") continue;
    const canonicalLabId = String(labId);
    for (const alias of [lab.lab_result_id, lab.source_lab_result_id, lab.diagnostic_report_id, lab.id]) {
      if (alias != null && alias !== "") sourceAliases.set(String(alias), canonicalLabId);
    }
    for (const observation of lab.observations || []) {
      for (const alias of [observation?.observation_id, observation?.source_observation_id, observation?.id]) {
        if (alias != null && alias !== "") sourceAliases.set(String(alias), canonicalLabId);
      }
    }
  }

  const groups = new Map();
  (Array.isArray(signals) ? signals : []).forEach((signal, index) => {
    if (!signal || typeof signal !== "object") return;
    const rawSourceId = getSignalSourceId(signal);
    const sourceId = sourceAliases.get(rawSourceId) || rawSourceId;
    const key = sourceId ? `source:${sourceId}` : `unlinked:${index}`;
    const group = groups.get(key) || { key, sourceId, signals: [] };
    group.signals.push(signal);
    groups.set(key, group);
  });
  return [...groups.values()].map((group) => ({
    ...group,
    signals: group.signals.sort((left, right) => {
      const sourceType = (signal) => String(signal?.evidence?.source_type || "").toLowerCase();
      return Number(sourceType(right).includes("diagnosticreport")) - Number(sourceType(left).includes("diagnosticreport"));
    }),
  }));
}

export function getLabRecordFacts(record) {
  const values = [];
  if (record?.conclusion != null && String(record.conclusion).trim()) {
    values.push({ label: "Conclusion", value: String(record.conclusion) });
  }
  (Array.isArray(record?.observations) ? record.observations : []).forEach((observation) => {
    const raw = observation?.value;
    const value = raw && typeof raw === "object"
      ? [raw.text, raw.numeric, raw.code].find((item) => item != null && String(item).trim() !== "")
      : raw;
    if (value == null || String(value).trim() === "") return;
    const unit = raw && typeof raw === "object" ? raw.unit : "";
    values.push({
      label: observation?.code?.display || "Recorded value",
      value: [String(value), unit].filter(Boolean).join(" "),
    });
  });
  return {
    status: record?.report_status || "",
    values,
    hasResult: values.length > 0,
  };
}

export function formatBackendScore(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(2) : null;
  return String(value);
}

export function getSourceRecordText(record) {
  const value = record?.extracted_text ?? record?.text ?? record?.content;
  return typeof value === "string" ? value : "";
}
