from __future__ import annotations

import re
from typing import Any

from backend.app.anatomy.markers import get_anatomy_marker_for_region

_FINDING_RULES: tuple[dict[str, Any], ...] = (
    {
        "finding_id": "skin_change",
        "label": "Rash or skin changes",
        "pattern": re.compile(r"\b(?:rash|maculopapular|skin lesion|skin changes?)\b", re.I),
        "regions": (
            ("face", re.compile(r"\b(?:face|facial|cheek|forehead)\b", re.I)),
            ("trunk", re.compile(r"\b(?:trunk|chest|abdomen|torso)\b", re.I)),
        ),
    },
    {
        "finding_id": "eye_finding",
        "label": "Eye redness or irritation",
        "pattern": re.compile(r"\b(?:conjunctiv\w*|red eyes|eye redness|eye irritation)\b", re.I),
        "regions": (("eyes", re.compile(r"\b(?:eye|eyes|conjunctiv\w*)\b", re.I)),),
    },
    {
        "finding_id": "respiratory_symptom",
        "label": "Cough or respiratory symptoms",
        "pattern": re.compile(r"\b(?:cough|coryza|nasal congestion|runny nose|shortness of breath|dyspnea)\b", re.I),
        "regions": (),
    },
    {
        "finding_id": "fever",
        "label": "Fever",
        "pattern": re.compile(r"\b(?:fever|febrile|elevated temperature)\b", re.I),
        "regions": (),
    },
    {
        "finding_id": "pain_tenderness",
        "label": "Pain or tenderness",
        "pattern": re.compile(r"\b(?:pain|tenderness|soreness)\b", re.I),
        "regions": (),
    },
    {
        "finding_id": "gastrointestinal_symptom",
        "label": "Gastrointestinal symptoms",
        "pattern": re.compile(r"\b(?:nausea|vomiting|diarrhea|abdominal pain)\b", re.I),
        "regions": (("abdomen", re.compile(r"\b(?:abdominal|abdomen|stomach)\b", re.I)),),
    },
)

_CLAUSE_SPLIT = re.compile(r"\s+(?:but|however|although|yet)\s+|[;,]")
_NEGATED_BEFORE = re.compile(
    r"\b(?:no|not|denies?|denied|without|negative for|absence of|free of)\b"
    r"(?:\W+\w+){0,5}\W*$",
    re.I,
)
_NEGATED_AFTER = re.compile(r"^\W*(?:is\s+)?(?:absent|not present|ruled out)\b", re.I)
_UNCERTAIN = re.compile(r"\b(?:possible|possibly|suspected|question of|may have|might have|rule out|r/o)\b", re.I)
_HISTORICAL = re.compile(r"\b(?:history of|historical|previously|prior|resolved|former|last year|in \d{4})\b", re.I)
def _document_text(document: dict[str, Any]) -> str:
    return " ".join(
        value.strip()
        for value in (document.get("extracted_text"), document.get("text"), document.get("content"))
        if isinstance(value, str) and value.strip()
    )


def collect_anatomy_evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapt this patient's available canonical records for anatomy extraction.

    Clinical document text is preferred. Structured records are included as
    evidence too, so patients without uploaded notes can still contribute
    explicit symptom and body-region wording from their canonical data.
    """
    evidence: list[dict[str, Any]] = []
    evidence.extend(
        item for item in context.get("clinical_documents", [])
        if isinstance(item, dict)
    )

    for condition in context.get("conditions", []):
        if not isinstance(condition, dict):
            continue
        code = condition.get("code") or {}
        display = code.get("display") if isinstance(code, dict) else str(code)
        if not isinstance(display, str) or not display.strip():
            continue
        evidence.append({
            "document_id": condition.get("condition_id"),
            "source_document_id": condition.get("source_condition_id"),
            "document_type": "Condition",
            "title": display,
            "document_date": condition.get("onset_time") or condition.get("recorded_time"),
            "extracted_text": display,
            "provenance": condition.get("provenance") or {"source_resource": "Condition"},
            "evidence_kind": "structured_record",
        })

    for observation in context.get("observations", []):
        if not isinstance(observation, dict):
            continue
        code = observation.get("code") or {}
        display = code.get("display") if isinstance(code, dict) else str(code)
        value = observation.get("value") or {}
        value_text = value.get("text") if isinstance(value, dict) else str(value)
        text = " ".join(part.strip() for part in (display, value_text) if isinstance(part, str) and part.strip())
        if not text:
            continue
        evidence.append({
            "document_id": observation.get("observation_id"),
            "source_document_id": observation.get("source_observation_id"),
            "document_type": "Observation",
            "title": display or "Observation",
            "document_date": observation.get("effective_time"),
            "extracted_text": text,
            "provenance": observation.get("provenance") or {"source_resource": "Observation"},
            "evidence_kind": "structured_record",
        })

    for lab in context.get("lab_results", []):
        if not isinstance(lab, dict):
            continue
        test = lab.get("test") or {}
        title = test.get("display") if isinstance(test, dict) else str(test)
        parts = [title, lab.get("conclusion")]
        for result in lab.get("observations", []):
            if not isinstance(result, dict):
                continue
            code = result.get("code") or {}
            value = result.get("value") or {}
            parts.extend([
                code.get("display") if isinstance(code, dict) else str(code),
                value.get("text") if isinstance(value, dict) else str(value),
            ])
        text = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
        if not text:
            continue
        evidence.append({
            "document_id": lab.get("lab_result_id"),
            "source_document_id": lab.get("source_lab_result_id"),
            "document_type": "Laboratory result",
            "title": title or "Laboratory result",
            "document_date": lab.get("effective_time") or lab.get("issued_time"),
            "extracted_text": text,
            "provenance": lab.get("provenance") or {"source_resource": "DiagnosticReport"},
            "evidence_kind": "structured_record",
        })

    return evidence


def _assertion(clause: str, start: int, end: int) -> str:
    before = clause[:start]
    after = clause[end:]
    if _NEGATED_BEFORE.search(before) or _NEGATED_AFTER.search(after):
        return "absent"
    if _UNCERTAIN.search(clause):
        return "uncertain"
    if _HISTORICAL.search(clause):
        return "historical"
    return "present"


def _matching_clauses(text: str, pattern: re.Pattern[str]) -> list[tuple[str, re.Match[str]]]:
    matches: list[tuple[str, re.Match[str]]] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for clause in _CLAUSE_SPLIT.split(sentence):
            match = pattern.search(clause)
            if match:
                matches.append((clause.strip(), match))
    return matches


def derive_anatomy_findings(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract explainable anatomy indicators from note text without external AI calls.

    A model marker is assigned only when a rule identifies a supported region.
    Negated, uncertain, and historical mentions remain visible as evidence but
    do not produce an active marker.
    """
    findings: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        text = _document_text(document)
        if not text:
            continue
        for rule in _FINDING_RULES:
            matched_clauses = _matching_clauses(text, rule["pattern"])
            if not matched_clauses:
                continue
            candidates: list[tuple[str, re.Match[str], str, list[tuple[str | None, str | None]]]] = []
            assertions_with_regions: set[str] = set()
            for clause, match in matched_clauses:
                assertion = _assertion(clause, match.start(), match.end())
                regions = [
                    (region, region_pattern)
                    for region, region_pattern in rule["regions"]
                    if region_pattern.search(clause)
                ]
                if regions:
                    assertions_with_regions.add(assertion)
                candidates.append((clause, match, assertion, regions))

            source_id = document.get("source_document_id") or document.get("document_id")
            laterality = "unspecified"
            for clause, match, assertion, regions in candidates:
                # Prefer located evidence when the same note also has a generic
                # mention (for example, "rash evaluation") for that assertion.
                if not regions and assertion in assertions_with_regions:
                    continue
                if not regions:
                    # Anatomy output only contains findings with an explicitly
                    # documented body part; systemic/unlocated symptoms are omitted.
                    continue
                matched_regions = regions or [(None, None)]
                if rule["finding_id"] == "eye_finding":
                    if re.search(r"\b(?:bilateral|both eyes)\b", clause, re.I):
                        laterality = "bilateral"
                    elif re.search(r"\bleft eye\b", clause, re.I):
                        laterality = "left"
                    elif re.search(r"\bright eye\b", clause, re.I):
                        laterality = "right"
                    else:
                        laterality = "unspecified"
                for body_region, _region_pattern in matched_regions:
                    anchor = get_anatomy_marker_for_region(body_region)
                    if anchor is None:
                        # Keep anatomy output limited to regions represented by
                        # a genuine anchor in the active model.
                        continue
                    marker = None
                    if assertion == "present" and anchor:
                        marker = {
                            **anchor,
                            "model_anchor_id": anchor["id"],
                            "id": f"{rule['finding_id']}-{anchor['id']}",
                            "label": f"{rule['label']} · {body_region}",
                            "aria_label": f"Documented {match.group(0)} affecting {body_region}",
                        }
                    findings.append(
                        {
                            "finding_id": rule["finding_id"],
                            "label": rule["label"],
                            "concept": match.group(0),
                            "assertion": assertion,
                            "temporality": "historical" if assertion == "historical" else "current_or_unspecified",
                            "body_region": body_region,
                            "laterality": laterality,
                            "marker": marker,
                            "evidence_text": clause[:240],
                            "source": {
                                "document_id": str(source_id) if source_id else None,
                                "title": document.get("title") or document.get("document_type") or "Clinical document",
                                "date": document.get("document_date"),
                                "source_type": (document.get("provenance") or {}).get("source_resource"),
                                "evidence_kind": document.get("evidence_kind", "clinical_document"),
                            },
                            "extraction_method": "backend_rule_based",
                        }
                    )
    grouped: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    for finding in findings:
        key = (
            finding["finding_id"],
            finding["assertion"],
            finding["body_region"],
        )
        grouped_finding = grouped.get(key)
        if grouped_finding is None:
            grouped_finding = {
                **finding,
                "sources": [],
                "lateralities": [],
            }
            grouped_finding.pop("source", None)
            grouped_finding.pop("evidence_text", None)
            grouped[key] = grouped_finding

        if finding["laterality"] != "unspecified" and finding["laterality"] not in grouped_finding["lateralities"]:
            grouped_finding["lateralities"].append(finding["laterality"])

        source = {
            **finding["source"],
            "evidence_text": finding["evidence_text"],
        }
        source_identity = source.get("document_id") or (source.get("title"), source.get("date"))
        existing_source = next(
            (
                item for item in grouped_finding["sources"]
                if (item.get("document_id") or (item.get("title"), item.get("date"))) == source_identity
            ),
            None,
        )
        if existing_source is None:
            grouped_finding["sources"].append(source)
        else:
            excerpts = [
                excerpt.strip()
                for excerpt in (existing_source.get("evidence_text"), source.get("evidence_text"))
                if isinstance(excerpt, str) and excerpt.strip()
            ]
            existing_source["evidence_text"] = " … ".join(dict.fromkeys(excerpts))
    entities = list(grouped.values())
    for entity in entities:
        entity["entity_id"] = ":".join((
            entity["finding_id"],
            entity["assertion"],
            entity["body_region"] or "unspecified",
        ))
    return entities
