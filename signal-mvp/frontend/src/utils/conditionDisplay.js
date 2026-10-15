const SYNTHETIC_DIAGNOSIS_NOTE =
  /\s*\(\s*synthetic test diagnosis;\s*terminology mapping to be confirmed by local profile\s*\)\s*$/i;

export function cleanConditionDisplay(value) {
  if (typeof value !== "string") return value;
  return value.replace(SYNTHETIC_DIAGNOSIS_NOTE, "").trim();
}
