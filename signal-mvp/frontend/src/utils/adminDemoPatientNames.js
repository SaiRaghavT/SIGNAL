const DEMO_MEASLES_NAMES = Object.freeze({
  "33333333-3333-4333-8333-333333333333": "Alex Morgan (Demo)",
  "44444444-4444-4444-8444-444444444444": "Taylor Reed (Demo)",
  "55555555-5555-4555-8555-555555555555": "Casey Brooks (Demo)",
});

export function demoPatientName(caseId, condition) {
  const conditionText = String(condition ?? "").toLowerCase();
  const isMeasles = conditionText.includes("measles") || conditionText.includes("14189004");
  return isMeasles ? DEMO_MEASLES_NAMES[String(caseId)] ?? null : null;
}

export function demoMeaslesCondition(caseId) {
  return DEMO_MEASLES_NAMES[String(caseId)] ? "Measles" : null;
}
