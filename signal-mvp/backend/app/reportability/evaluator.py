from .models import ReportabilityInput, ReportabilityAssessment


def _normalize(value: object) -> str:
    return str(value or "").strip().casefold()


def _is_positive_lab(lab: dict) -> bool:
    if lab.get("positive") is True:
        return True

    conclusion = _normalize(lab.get("conclusion"))

    if any(
        term in conclusion
        for term in ("positive", "detected", "reactive", "present")
    ):
        return True

    result = _normalize(lab.get("result"))
    return result in {"positive", "detected", "reactive"}


def _is_negative_lab(lab: dict) -> bool:
    conclusion = _normalize(lab.get("conclusion"))

    if any(
        term in conclusion
        for term in ("negative", "not detected", "non-reactive")
    ):
        return True

    result = _normalize(lab.get("result"))
    return result in {"negative", "not detected", "non-reactive"}


def _is_pending_lab(lab: dict) -> bool:
    status = _normalize(lab.get("report_status") or lab.get("status"))
    result = _normalize(lab.get("result"))

    return (
        status in {"pending", "in progress", "in_progress"}
        or result in {"pending", "in progress", "in_progress"}
    )


def _is_inconclusive_lab(lab: dict) -> bool:
    status = _normalize(lab.get("report_status") or lab.get("status"))
    result = _normalize(lab.get("result"))

    return (
        status in {"inconclusive", "indeterminate"}
        or result in {"inconclusive", "indeterminate"}
    )


def evaluate_reportability(data: ReportabilityInput) -> ReportabilityAssessment:
    reasons = []
    warnings = []

    if data.jurisdiction_status != "RESOLVED" or not data.jurisdiction:
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "JURISDICTION_UNRESOLVED",
            ["Jurisdiction could not be resolved."],
            ["Resolve jurisdiction before applying reporting rules."],
        )

    if not data.disease:
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "MISSING_DISEASE",
            ["Disease information is missing."],
            ["Disease classification is required."],
        )

    if not data.laboratory_evidence:
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "INCOMPLETE_EVIDENCE",
            ["No laboratory evidence is available."],
            ["Additional evidence is required."],
        )

    labs = data.laboratory_evidence

    # Check pending first
    if any(_is_pending_lab(lab) for lab in labs):
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "HOLD",
            "PENDING_LAB",
            ["A laboratory result is still pending."],
            ["Wait for the final laboratory result."],
        )

    # Check inconclusive
    if any(_is_inconclusive_lab(lab) for lab in labs):
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "INCONCLUSIVE_LAB",
            ["Laboratory evidence is inconclusive."],
            ["Review laboratory evidence."],
        )

    positive_lab = any(_is_positive_lab(lab) for lab in labs)
    negative_lab = any(_is_negative_lab(lab) for lab in labs)

    # Conflicting laboratory evidence
    if positive_lab and negative_lab:
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "CONFLICTING_LAB_RESULTS",
            ["Laboratory evidence contains conflicting results."],
            ["Review the laboratory results before applying reporting rules."],
        )

    ai_condition = data.ai_evidence.get("condition")

    if (
        ai_condition
        and str(ai_condition).casefold() != data.disease.casefold()
    ):
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "CONFLICTING_DISEASE_CLASSIFICATION",
            ["AI condition classification conflicts with candidate disease."],
            ["Review the conflicting disease classifications."],
        )

    ai_confidence = data.ai_evidence.get("confidence")

    if (
        positive_lab
        and isinstance(ai_confidence, (int, float))
        and ai_confidence < 0.50
    ):
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "CONFLICTING_AI_AND_LAB",
            ["Laboratory evidence is positive but AI confidence is low."],
            ["Review the conflicting evidence."],
        )

    if positive_lab:
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "PROCEED_TO_RULES",
            "LAB_POSITIVE",
            ["Positive laboratory evidence is available."],
            ["Apply jurisdiction-specific reporting rules."],
        )

    if negative_lab:
        return ReportabilityAssessment(
            data.candidate_id,
            data.jurisdiction,
            data.disease,
            "NEEDS_REVIEW",
            "LAB_NEGATIVE",
            ["Laboratory evidence is negative."],
            ["Review the complete evidence before final determination."],
        )

    return ReportabilityAssessment(
        data.candidate_id,
        data.jurisdiction,
        data.disease,
        "NEEDS_REVIEW",
        "UNKNOWN_EVIDENCE",
        ["Laboratory evidence could not be classified."],
        ["Review laboratory evidence."],
    )