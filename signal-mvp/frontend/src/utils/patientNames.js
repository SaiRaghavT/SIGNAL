export function cleanPatientName(value) {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) {
    return value.map((part) => {
      if (typeof part === "string") return part;
      if (!part || typeof part !== "object") return "";
      const given = Array.isArray(part.given) ? part.given.join(" ") : part.given;
      return [given, part.family].filter(Boolean).join(" ");
    }).map(cleanPatientName).filter(Boolean).join(" ");
  }
  if (typeof value === "object") {
    const given = Array.isArray(value.given) ? value.given.join(" ") : value.given;
    value = value.full_name || value.patient_name || value.name ||
      [value.first_name || given, value.last_name || value.family].filter(Boolean).join(" ");
  }
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/\d+/g, " ")
    .replace(/[_|#,:;]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
