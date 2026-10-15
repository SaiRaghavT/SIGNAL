export function cleanPatientName(value) {
  if (value === null || value === undefined) return "";

  if (Array.isArray(value)) {
    return value.map((part) => cleanPatientName(part)).filter(Boolean).join(" ");
  }

  if (typeof value === "object") {
    const given = Array.isArray(value.given) ? value.given.join(" ") : value.given;
    value = value.full_name || value.patient_name || value.name ||
      [value.first_name || given, value.last_name || value.family].filter(Boolean).join(" ");
  }

  return String(value)
    .replace(/\d+/g, " ")
    .replace(/[_|#,:;]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
