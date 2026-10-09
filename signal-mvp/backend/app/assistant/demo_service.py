"""Deterministic patient demo data, isolated from production services."""

from __future__ import annotations

import re


DEMO_LABEL = "DEMO DATA — NOT A REAL PATIENT"

# These records are fabricated for UI demonstrations. They are not loaded from
# SIGNAL's database and their reporting rules are expressly nonauthoritative.
_PATIENTS = (
    {
        "patient_id": "DEMO-P001",
        "name": "Alex Morgan",
        "date_of_birth": "1990-04-12",
        "jurisdiction": "Texas (illustrative)",
        "encounters": [
            {"date": "2026-08-16", "type": "Urgent care visit", "facility": "Demo Clinic North"},
        ],
        "conditions": [
            {"condition": "Measles (synthetic demo diagnosis)", "status": "Active in demo record", "onset": "2026-08-14"},
        ],
        "symptoms": [
            {"symptom": "Fever and rash (synthetic demo symptoms)", "recorded": "2026-08-16"},
        ],
        "laboratory_results": [
            {"test": "Measles PCR (synthetic demo result)", "result": "Positive in demo record", "date": "2026-08-17"},
        ],
        "detection": {
            "explanation": "The fictional candidate was detected from the demo diagnosis and matching demo laboratory result.",
            "evidence": ["Synthetic demo diagnosis", "Synthetic demo laboratory result"],
            "missing_information": "Exposure history is unavailable in this demo record.",
        },
        "reporting": {
            "rule": "DEMO-TX-MEASLES-24H (illustrative only; not an authoritative Texas rule)",
            "calculation_basis": "Illustrative 24-hour interval from the synthetic positive result date; not a legal deadline.",
            "deadline": "2026-08-18 (illustrative demo date)",
            "status": "Past illustrative demo deadline; no real reporting action occurred.",
        },
        "case_status": "Awaiting demo clinical review",
        "submission_status": "Not submitted (demo only)",
        "follow_ups": ["Demo action: review the synthetic exposure history when available."],
        "notes": None,
    },
    {
        "patient_id": "DEMO-P002",
        "name": "Casey Morgan",
        "date_of_birth": "1984-11-03",
        "jurisdiction": "Oregon (illustrative)",
        "encounters": [
            {"date": "2026-09-04", "type": "Primary care visit", "facility": "Demo Clinic West"},
        ],
        "conditions": [
            {"condition": "Pertussis (synthetic demo diagnosis)", "status": "Under evaluation in demo record", "onset": "2026-09-02"},
        ],
        "symptoms": [
            {"symptom": "Persistent cough (synthetic demo symptom)", "recorded": "2026-09-04"},
        ],
        "laboratory_results": [
            {"test": "Pertussis PCR (synthetic demo test)", "result": "Pending in demo record", "date": "2026-09-04"},
        ],
        "detection": {
            "explanation": "The fictional candidate was detected from a demo diagnosis and cough symptom; the demo test is pending.",
            "evidence": ["Synthetic demo diagnosis", "Synthetic demo symptom"],
            "missing_information": "A final laboratory result is unavailable in this demo record.",
        },
        "reporting": {
            "rule": "DEMO-OR-PERTUSSIS-REVIEW (illustrative only; not an authoritative Oregon rule)",
            "calculation_basis": "No deadline is calculated in this demo because the synthetic test is pending.",
            "deadline": None,
            "status": "Unavailable in demo record",
        },
        "case_status": "Demo evidence review in progress",
        "submission_status": "Not submitted (demo only)",
        "follow_ups": ["Demo action: review the pending synthetic laboratory result."],
        "notes": None,
    },
    {
        "patient_id": "DEMO-P003",
        "name": "Riley Chen",
        "date_of_birth": "2001-02-20",
        "jurisdiction": "California (illustrative)",
        "encounters": [
            {"date": "2026-09-21", "type": "Emergency department visit", "facility": "Demo City Hospital"},
        ],
        "conditions": [
            {"condition": "Hepatitis A (synthetic demo diagnosis)", "status": "Active in demo record", "onset": "2026-09-20"},
        ],
        "symptoms": [
            {"symptom": "Nausea and fatigue (synthetic demo symptoms)", "recorded": "2026-09-21"},
        ],
        "laboratory_results": [
            {"test": "Hepatitis A IgM (synthetic demo result)", "result": "Reactive in demo record", "date": "2026-09-21"},
        ],
        "detection": {
            "explanation": "The fictional candidate was detected from the demo diagnosis and matching demo laboratory result.",
            "evidence": ["Synthetic demo diagnosis", "Synthetic demo laboratory result"],
            "missing_information": "Exposure source is unavailable in this demo record.",
        },
        "reporting": {
            "rule": "DEMO-CA-HEPA-REVIEW (illustrative only; not an authoritative California rule)",
            "calculation_basis": "Illustrative same-day review target for UI demonstration only.",
            "deadline": "2026-09-21 (illustrative demo date)",
            "status": "Demo case marked for immediate review; no real reporting action occurred.",
        },
        "case_status": "Demo case ready for administrator review",
        "submission_status": "Not submitted (demo only)",
        "follow_ups": ["Demo action: confirm the synthetic exposure history during review."],
        "notes": None,
    },
)

_BY_ID = {patient["patient_id"].casefold(): patient for patient in _PATIENTS}
_ID_PATTERN = re.compile(r"\bDEMO-P\d{3}\b", re.IGNORECASE)


def _response(status: str, message: str, **extra) -> dict:
    return {"mode": "demo", "label": DEMO_LABEL, "status": status, "message": message, **extra}


def _patient_from_name(question: str) -> list[dict]:
    normalized = question.casefold()
    matches = []
    for patient in _PATIENTS:
        name_words = patient["name"].casefold().split()
        if all(re.search(rf"\b{re.escape(word)}\b", normalized) for word in name_words):
            matches.append(patient)
    if matches:
        return matches

    # Permit a surname or a single distinctive name word, but return all
    # matches so shared surnames result in a selection prompt.
    return [
        patient for patient in _PATIENTS
        if any(re.search(rf"\b{re.escape(word.casefold())}\b", normalized)
               for word in patient["name"].split())
    ]


def _format_summary(patient: dict) -> dict:
    sections = [
        {"title": "Patient overview", "items": [
            ["Patient ID", patient["patient_id"]],
            ["Name", patient["name"]],
            ["Date of birth", patient["date_of_birth"]],
            ["Jurisdiction", patient["jurisdiction"]],
        ]},
        {"title": "Clinical summary", "items": [
            ["Encounters", patient["encounters"]],
            ["Conditions", patient["conditions"]],
            ["Symptoms", patient["symptoms"]],
            ["Laboratory results", patient["laboratory_results"]],
            ["Clinical notes", patient["notes"] or "Not available in this demo record"],
        ]},
        {"title": "SIGNAL detection", "items": [
            ["Explanation", patient["detection"]["explanation"]],
            ["Evidence", patient["detection"]["evidence"]],
            ["Missing information", patient["detection"]["missing_information"]],
        ]},
        {"title": "Reporting information (illustrative demo only)", "items": [
            ["Demo rule", patient["reporting"]["rule"]],
            ["Calculation basis", patient["reporting"]["calculation_basis"]],
            ["Demo deadline", patient["reporting"]["deadline"] or "Not available in this demo record"],
            ["Demo status", patient["reporting"]["status"]],
        ]},
        {"title": "Case, submission, and follow-up", "items": [
            ["Case review status", patient["case_status"]],
            ["Submission status", patient["submission_status"]],
            ["Follow-up", patient["follow_ups"]],
        ]},
    ]
    return _response(
        "summary",
        f"Synthetic demonstration summary for {patient['name']} ({patient['patient_id']}). No real patient records or workflow services were accessed.",
        selected_patient_id=patient["patient_id"],
        patient_name=patient["name"],
        sections=sections,
    )


def chat_with_synthetic_demo(question: str, selected_patient_id: str | None = None) -> dict:
    """Resolve and summarize only fixed demo records, without DB/service access."""
    clean_question = question.strip()
    if not clean_question:
        return _response("needs_patient", "Enter a synthetic demo patient name or ID, such as DEMO-P001.")

    identifier = _ID_PATTERN.search(clean_question)
    if identifier:
        patient = _BY_ID.get(identifier.group(0).casefold())
        return _format_summary(patient) if patient else _response(
            "no_match", "No synthetic demo record matches that ID. Only the predefined DEMO-P001 through DEMO-P003 records are available.",
        )

    matches = _patient_from_name(clean_question)
    if len(matches) > 1:
        return _response(
            "selection_required",
            "Several synthetic demo records match. Select the patient you mean:",
            candidates=[{"patient_id": patient["patient_id"], "name": patient["name"]} for patient in matches],
        )
    if len(matches) == 1:
        return _format_summary(matches[0])

    explicit_patient_request = bool(re.search(r"\b(patient|person|record|id)\b", clean_question, re.IGNORECASE))
    if explicit_patient_request:
        return _response("no_match", "No matching synthetic demo patient was found. Use one of the displayed demo names or IDs.")

    selected = _BY_ID.get((selected_patient_id or "").casefold())
    if selected:
        return _format_summary(selected)

    return _response("needs_patient", "Enter a synthetic demo patient name or ID, such as DEMO-P001.")
