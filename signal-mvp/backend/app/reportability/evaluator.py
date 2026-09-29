from .models import ReportabilityInput, ReportabilityAssessment

def evaluate_reportability(data: ReportabilityInput) -> ReportabilityAssessment:
    reasons = []
    warnings = []

    if data.jurisdiction_status != "RESOLVED" or not data.jurisdiction:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "JURISDICTION_UNRESOLVED",
            ["Jurisdiction could not be resolved."],
            ["Resolve jurisdiction before applying reporting rules."]
        )

    if not data.disease:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "MISSING_DISEASE",
            ["Disease information is missing."],
            ["Disease classification is required."]
        )

    if not data.laboratory_evidence:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "INCOMPLETE_EVIDENCE",
            ["No laboratory evidence is available."],
            ["Additional evidence is required."]
        )

    lab_statuses = [
        str(x.get("status", "")).upper()
        for x in data.laboratory_evidence
    ]

    if "PENDING" in lab_statuses:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "HOLD", "PENDING_LAB",
            ["A laboratory result is still pending."],
            ["Wait for the final laboratory result."]
        )

    if "INCONCLUSIVE" in lab_statuses:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "INCONCLUSIVE_LAB",
            ["Laboratory evidence is inconclusive."],
            ["Review laboratory evidence."]
        )

    ai_condition = data.ai_evidence.get("condition")
    if ai_condition and ai_condition.lower() != data.disease.lower():
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "CONFLICTING_DISEASE_CLASSIFICATION",
            ["AI condition classification conflicts with candidate disease."],
            ["Review the conflicting disease classifications."]
        )

    ai_confidence = data.ai_evidence.get("confidence")
    positive_lab = any(
        str(x.get("result", "")).upper() in {"POSITIVE", "DETECTED"}
        for x in data.laboratory_evidence
    )

    if positive_lab and isinstance(ai_confidence, (int, float)) and ai_confidence < 0.50:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "CONFLICTING_AI_AND_LAB",
            ["Laboratory evidence is positive but AI confidence is low."],
            ["Review the conflicting evidence."]
        )

    if positive_lab:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "PROCEED_TO_RULES", "LAB_POSITIVE",
            ["Positive laboratory evidence is available."],
            ["Apply jurisdiction-specific reporting rules."]
        )

    negative_lab = any(
        str(x.get("result", "")).upper() in {"NEGATIVE", "NOT_DETECTED"}
        for x in data.laboratory_evidence
    )

    if negative_lab:
        return ReportabilityAssessment(
            data.candidate_id, data.jurisdiction, data.disease,
            "NEEDS_REVIEW", "LAB_NEGATIVE",
            ["Laboratory evidence is negative."],
            ["Review the complete evidence before final determination."]
        )

    return ReportabilityAssessment(
        data.candidate_id, data.jurisdiction, data.disease,
        "NEEDS_REVIEW", "UNKNOWN_EVIDENCE",
        ["Laboratory evidence could not be classified."],
        ["Review laboratory evidence."]
    )
