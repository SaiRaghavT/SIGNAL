import { request } from "./client.js";

const PAGE_SIZE = 100;
const MAX_SEARCH_PAGES = 20;

const SOURCES = [
  ["patient count", "/api/canonical/patients?page=1&page_size=1"],
  ["analytics summary", "/api/analytics/summary"],
  ["reporting status", "/api/dashboard/reporting-status"],
  ["reportability summary", "/api/analytics/reporting"],
  ["deadline summary", "/api/dashboard/deadlines"],
];

function buildUrl(path, params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return `${path}${query.size ? `?${query}` : ""}`;
}

async function loadRecords(path, params = {}) {
  const firstPage = await request(buildUrl(path, {
    ...params,
    page: 1,
    page_size: PAGE_SIZE,
  }));
  const pages = Math.min(Number(firstPage.pages) || 1, MAX_SEARCH_PAGES);
  const remaining = await Promise.all(
    Array.from({ length: pages - 1 }, (_, index) => request(buildUrl(path, {
      ...params,
      page: index + 2,
      page_size: PAGE_SIZE,
    }))),
  );
  return {
    items: [firstPage, ...remaining].flatMap((page) => Array.isArray(page.items) ? page.items : []),
    total: Number(firstPage.total) || 0,
    truncated: Number(firstPage.pages) > MAX_SEARCH_PAGES,
  };
}

function searchTerm(question, previousTerm) {
  const normalized = question.trim();
  const explicitId = normalized.match(/\b(?:[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}|[a-z]{2,}-\d{3,})\b/i);
  if (explicitId) return explicitId[0];

  const explicit = normalized.match(/\b(?:for|about|named|called)\s+(.+)$/i);
  let candidate = explicit?.[1] || normalized;
  candidate = candidate
    .replace(/^(?:please\s+)?(?:can you\s+)?(?:find|search(?: for)?|look up|show|tell me about|get|retrieve)\s+/i, "")
    .replace(/^(?:the\s+)?(?:patient|case|candidate|submission|follow[- ]?up|record)\s+/i, "")
    .replace(/[?.,!]+$/g, "")
    .trim();

  const stopWords = new Set([
    "a", "about", "all", "and", "another", "are", "case", "cases", "candidate", "candidates",
    "count", "details", "find", "for", "give", "happened", "how", "in", "is", "list", "many",
    "me", "of", "open", "patient", "patients", "please", "record", "records",
    "search", "show", "status", "submission", "submissions", "the", "there", "total",
    "tell", "what", "which", "with", "who", "why", "by", "coming", "deadline", "deadlines",
    "detection", "detections", "disease", "due", "id", "jurisdiction", "jurisdictions",
    "name", "or", "overdue", "review", "reportable", "requiring", "needing",
    "signal", "summarize", "summary", "up", "upcoming", "breakdown", "analytics",
    "follow-up", "follow-ups", "followup", "followups", "follow",
  ]);
  const words = candidate.split(/\s+/).filter((word) => word && !stopWords.has(word.toLowerCase()));
  if (!words.length && /\b(?:their|them|that|those|this|these|same|it)\b/i.test(normalized)) {
    return previousTerm || "";
  }
  if (!words.length) return "";
  return words.join(" ").slice(0, 120);
}

function asCountRows(value) {
  return Object.entries(value || {}).map(([label, count]) => `${label}: ${count}`);
}

function nameOf(patient = {}) {
  return patient.full_name || patient.name
    || [patient.first_name, patient.last_name].filter(Boolean).join(" ")
    || "Name not available";
}

function summarizePatient(item) {
  const condition = item.condition || item.conditions?.map?.((entry) => entry.condition_display).filter(Boolean).join(", ");
  return {
    id: item.patient_id,
    title: nameOf(item),
    detail: [condition, item.county, item.state].filter(Boolean).join(" · ") || "Patient record",
    href: item.patient_id ? `/patients/${encodeURIComponent(item.patient_id)}` : undefined,
  };
}

function summarizeCase(item) {
  const patient = item.patient && typeof item.patient === "object" ? nameOf(item.patient) : "";
  const disease = String(item.disease || "");
  const diseaseCode = disease.match(/snomed\.info\/sct\|([^|]+)/i)?.[1];
  return {
    id: item.case_id,
    title: patient || `Case ${String(item.case_id || "").slice(0, 8)}`,
    detail: [diseaseCode ? `SNOMED code ${diseaseCode}` : disease, item.status || item.final_decision, item.jurisdiction, item.severity].filter(Boolean).join(" · "),
    href: item.case_id ? `/cases/${encodeURIComponent(item.case_id)}` : undefined,
  };
}

function summarizeCandidate(item) {
  const patient = item.patient && typeof item.patient === "object" ? nameOf(item.patient) : "";
  return {
    id: item.candidate_id,
    title: [patient, item.disease || item.disease_id].filter(Boolean).join(" · ") || "Candidate",
    detail: [item.status, item.disposition, item.jurisdiction].filter(Boolean).join(" · "),
    href: item.patient_id ? `/patients/${encodeURIComponent(item.patient_id)}` : undefined,
  };
}

function summarizeSubmission(item) {
  return {
    id: item.submission_id || item.record_id,
    title: [nameOf(item.patient), item.disease || "Submission"].filter(Boolean).join(" · "),
    detail: [item.status || item.workflow_status, item.jurisdiction, item.destination].filter(Boolean).join(" · "),
    href: item.case_id ? `/cases/${encodeURIComponent(item.case_id)}` : undefined,
  };
}

function summarizeFollowUp(item) {
  return {
    id: item.followup_id,
    title: [nameOf(item.patient), item.disease || item.action || "Follow-up"].filter(Boolean).join(" · "),
    detail: [item.status, item.next_action, item.due_date].filter(Boolean).join(" · "),
    href: item.case_id ? `/follow-ups/case/${encodeURIComponent(item.case_id)}` : undefined,
  };
}

function listRecords(records, summarize) {
  return records?.items?.slice(0, 6).map(summarize) || [];
}

function filterCandidateRecords(records, term) {
  const words = term.toLowerCase().split(/\s+/).filter(Boolean);
  const items = records.items.filter((item) => {
    const searchable = JSON.stringify(item).toLowerCase();
    return words.every((word) => searchable.includes(word));
  });
  return { ...records, items, total: items.length };
}

export async function answerWithSignalData(question, previousTerm = "") {
  const term = searchTerm(question, previousTerm);
  const normalized = question.toLowerCase();
  const sourceErrors = [];
  const data = {};

  await Promise.all(SOURCES.map(async ([label, path]) => {
    try {
      data[label] = await request(path);
    } catch (error) {
      sourceErrors.push(`${label}: ${error.message}`);
    }
  }));

  const shouldSearch = Boolean(term);
  const recordSources = [
    ["patients", "/api/canonical/patients"],
    ["cases", "/api/cases"],
    ["candidates", "/api/candidates"],
    ["submissions", "/api/clinical/submissions"],
    ["follow-ups", "/api/follow-ups"],
  ];
  const needsList = shouldSearch
    || /\b(show|list|recent|latest|which|who|find|search)\b/i.test(question)
    || (!shouldSearch && /\b(candidates?|detection|follow[- ]?ups?)\b/i.test(question));
  const records = {};
  if (needsList) {
    await Promise.all(recordSources.map(async ([label, path]) => {
      if (!shouldSearch && !normalized.includes(label.replace("-", " ").split(" ")[0])) return;
      try {
        const loadedRecords = await loadRecords(path, shouldSearch && label !== "candidates" ? { search: term } : {});
        records[label] = shouldSearch && label === "candidates"
          ? filterCandidateRecords(loadedRecords, term)
          : loadedRecords;
      } catch (error) {
        sourceErrors.push(`${label}: ${error.message}`);
      }
    }));
  }

  const summary = data["analytics summary"] || {};
  const totalPatients = data["patient count"]?.total;
  const dashboardReporting = data["reporting status"] || {};
  const reportability = data["reportability summary"] || {};
  const deadlineSummary = data["deadline summary"] || {};
  const deadlineAnalytics = {
    by_status: deadlineSummary.by_status,
    overdue: Number(deadlineSummary.by_status?.OVERDUE) || 0,
    upcoming: Number(deadlineSummary.by_status?.UPCOMING) || 0,
    total: Number(summary.deadlines) || 0,
  };
  const results = [];

  if (shouldSearch) {
    results.push(...listRecords(records.patients, summarizePatient));
    results.push(...listRecords(records.cases, summarizeCase));
    results.push(...listRecords(records.candidates, summarizeCandidate));
    results.push(...listRecords(records.submissions, summarizeSubmission));
    results.push(...listRecords(records["follow-ups"], summarizeFollowUp));
  }

  let answer;
  if (shouldSearch && results.length) {
    const foundCount = Object.values(records).reduce((total, result) => total + result.total, 0);
    answer = `I found ${foundCount} matching backend record${foundCount === 1 ? "" : "s"} across patients, cases, candidates, submissions, and follow-ups. Here are the first ${Math.min(results.length, 6)} matches.`;
  } else if (shouldSearch) {
    answer = `I couldn't find a matching record for “${term}” in the patient, case, candidate, submission, or follow-up data. Try a full name, patient/case ID, disease, or jurisdiction.`;
  } else if (/\b(find|search)\b/.test(normalized)) {
    answer = "Enter a patient name, patient ID, case ID, candidate ID, disease, or jurisdiction and I’ll search the matching SIGNAL records.";
  } else if (/\b(deadlines?|due|overdue|upcoming|urgent|at risk|coming up)\b/.test(normalized)) {
    const counts = asCountRows(deadlineAnalytics.by_status);
    answer = counts.length
      ? `Deadline records by status: ${counts.join("; ")}. ${deadlineAnalytics.overdue ?? 0} are overdue and ${deadlineAnalytics.upcoming ?? 0} are upcoming.`
      : deadlineAnalytics.total === 0
        ? "There are currently no deadline records in SIGNAL."
        : `SIGNAL has ${deadlineAnalytics.total} deadline records, but the backend did not return status counts.`;
    const deadlineItems = deadlineSummary.items || [];
    results.push(...deadlineItems.slice(0, 6).map((item) => ({
      id: item.case_id,
      title: item.message || `Deadline for case ${item.case_id}`,
      detail: [item.status, item.deadline, item.minutes_remaining != null ? `${item.minutes_remaining} min remaining` : ""].filter(Boolean).join(" · "),
      href: item.case_id ? `/cases/${encodeURIComponent(item.case_id)}` : undefined,
    })));
  } else if (/\b(jurisdiction|county|state|region)\b/.test(normalized)) {
    const jurisdictions = asCountRows(dashboardReporting.jurisdictions || {});
    answer = jurisdictions.length
      ? `Cases by jurisdiction: ${jurisdictions.join("; ")}.`
      : "The backend did not return jurisdiction counts.";
  } else if (/\b(submission|submitted|acknowledg|transmission)\b/.test(normalized)) {
    const counts = asCountRows(dashboardReporting.submissions || {});
    answer = counts.length
      ? `Submissions by status: ${counts.join("; ")}.`
      : `SIGNAL reports ${summary.submitted_cases ?? 0} cases with a submission.`;
    if (records.submissions) results.push(...listRecords(records.submissions, summarizeSubmission));
  } else if (/\b(follow[- ]?up)\b/.test(normalized)) {
    answer = records["follow-ups"]
      ? `The backend returned ${records["follow-ups"].total} follow-up record${records["follow-ups"].total === 1 ? "" : "s"}.`
      : "Use a patient name, case ID, or follow-up ID to look up a specific follow-up record.";
    if (records["follow-ups"]) results.push(...listRecords(records["follow-ups"], summarizeFollowUp));
  } else if (/\b(candidate|detection)\b/.test(normalized)) {
    answer = records.candidates
      ? `The backend returned ${records.candidates.total} candidate record${records.candidates.total === 1 ? "" : "s"} for this query.`
      : "Candidate detection is available through the Candidates data API. Ask with a patient name, disease, or candidate ID to look up matching records.";
    if (records.candidates) results.push(...listRecords(records.candidates, summarizeCandidate));
  } else if (/\b(case|review|reportable)\b/.test(normalized)) {
    const counts = asCountRows(dashboardReporting.cases || {});
    answer = `SIGNAL has ${summary.cases ?? dashboardReporting.quality?.case_count ?? "an unavailable number of"} cases, including ${dashboardReporting.quality?.cases_needing_review ?? reportability.needs_review ?? 0} needing review and ${reportability.reportable_cases ?? 0} marked reportable.${counts.length ? ` Case statuses: ${counts.join("; ")}.` : ""}`;
    if (records.cases) {
      const caseItems = records.cases.items.filter((item) => !/\breview\b/.test(normalized)
        || [item.status, item.final_decision, item.reportability_decision, item.jurisdiction_status]
          .some((status) => String(status || "").toUpperCase() === "NEEDS_REVIEW"));
      results.push(...caseItems.slice(0, 6).map(summarizeCase));
    }
  } else {
    const submissionCount = summary.submissions ?? "—";
    answer = [
      `Live SIGNAL overview: ${totalPatients ?? "—"} patients; ${summary.cases ?? dashboardReporting.quality?.case_count ?? "—"} cases; ${dashboardReporting.quality?.cases_needing_review ?? reportability.needs_review ?? "—"} needing review; ${reportability.reportable_cases ?? "—"} reportable; ${submissionCount} ${submissionCount === 1 ? "submission" : "submissions"}.`,
      `Upcoming deadlines: ${deadlineSummary.by_status?.UPCOMING ?? (deadlineAnalytics.total === 0 ? 0 : "—")}.`,
    ].join(" ");
  }

  const suggestions = shouldSearch && results.length
    ? ["Show cases needing review", "What deadlines are coming up?", "Summarize submissions", "Find another patient or case"]
    : /\b(patient|case|candidate)\b/i.test(normalized)
      ? ["Find a patient or case by name or ID", "Show cases needing review", "What deadlines are coming up?", "Summarize submissions"]
      : ["How many patients and cases are in SIGNAL?", "Show cases needing review", "Which deadlines are coming up?", "Find a patient or case by name or ID"];

  return {
    answer,
    results: results.slice(0, 6),
    suggestions,
    sourceErrors,
    searchTerm: term,
  };
}
