from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.agents.candidate_disposition.schemas import CandidateDispositionRequest
from backend.app.agents.candidate_disposition.service import determine_candidate_disposition
from backend.app.canonical.query_service import (
    CanonicalPatientNotFoundError,
    get_patient_context,
)
from backend.app.case.assembler import assemble_case
from backend.app.case.models import CaseAssemblyInput
from backend.app.ecr.builder import build_ecr
from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction
from backend.app.rckms.decision_support import evaluate_decision_support
from backend.app.reportability.evaluator import evaluate_reportability
from backend.app.reportability.models import ReportabilityInput
from backend.app.schemas.validation import validate_ecr
from backend.app.smart_field_population.mapper import populate_report_fields
from backend.app.submission.service import submit_ecr

from .schemas import CandidateProcessRequest


def _get_canonical_patient_id(
    request: CandidateProcessRequest,
) -> UUID:
    """
    Resolve the canonical patient UUID used by the workflow.

    Current SIGNAL detection uses the patient UUID as the candidate_id,
    so candidate_id is used as the fallback when patient_id is not
    explicitly available on the request.
    """

    patient_id = request.patient_id

    if patient_id:
        return (
            patient_id
            if isinstance(patient_id, UUID)
            else UUID(str(patient_id))
        )

    try:
        return UUID(str(request.candidate_id))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Provide patient_id as a valid UUID, or use a UUID-valued "
            "candidate_id."
        ) from exc


def _select_relevant_encounter(
    canonical_context: dict[str, Any],
    disease: str | None,
    laboratory_evidence: list[dict[str, Any]],
    clinical_evidence: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Select the encounter most directly associated with the candidate.

    Selection priority:

    1. Encounter referenced by laboratory evidence.
    2. Encounter referenced by clinical evidence.
    3. Encounter referenced by a matching condition.
    4. None if no reliable relationship exists.
    """

    encounters = canonical_context.get("encounters", [])

    if not encounters:
        return None

    encounter_by_id = {
        str(encounter["encounter_id"]): encounter
        for encounter in encounters
        if encounter.get("encounter_id")
    }

    # ---------------------------------------------------------
    # 1. Laboratory evidence
    # ---------------------------------------------------------

    for lab in laboratory_evidence:
        encounter_id = lab.get("encounter_id")

        if encounter_id:
            encounter = encounter_by_id.get(str(encounter_id))

            if encounter:
                return encounter

    # ---------------------------------------------------------
    # 2. Clinical evidence
    # ---------------------------------------------------------

    if isinstance(clinical_evidence, dict):
        encounter_id = clinical_evidence.get("encounter_id")

        if encounter_id:
            encounter = encounter_by_id.get(str(encounter_id))

            if encounter:
                return encounter

    # ---------------------------------------------------------
    # 3. Matching disease condition
    # ---------------------------------------------------------

    if disease:
        disease_normalized = disease.casefold()

        for condition in canonical_context.get(
            "conditions",
            [],
        ):
            code = condition.get("code") or {}

            display = str(
                code.get("display", "")
            ).casefold()

            if disease_normalized in display:
                encounter_id = condition.get(
                    "encounter_id"
                )

                if encounter_id:
                    encounter = encounter_by_id.get(
                        str(encounter_id)
                    )

                    if encounter:
                        return encounter

    return None


def _build_canonical_patient(
    canonical_patient: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert the canonical Patient response into the patient
    structure expected by downstream SIGNAL workflow components.
    """

    address = canonical_patient.get("address") or {}

    first_name = canonical_patient.get("first_name")
    last_name = canonical_patient.get("last_name")

    full_name = " ".join(
        part
        for part in [
            first_name,
            last_name,
        ]
        if part
    )

    return {
        "patient_id": canonical_patient.get(
            "patient_id"
        ),
        "source_patient_id": canonical_patient.get(
            "source_patient_id"
        ),
        "first_name": first_name,
        "last_name": last_name,
        "name": full_name,
        "date_of_birth": canonical_patient.get(
            "date_of_birth"
        ),
        "sex": canonical_patient.get("sex"),

        # Flatten address fields because the existing
        # downstream form mapper expects these fields.
        "address": address.get("line"),
        "city": address.get("city"),
        "county": address.get("county"),
        "state": address.get("state"),
        "zip": address.get("postal_code"),
        "postal_code": address.get(
            "postal_code"
        ),

        "provenance": canonical_patient.get(
            "provenance",
            {},
        ),
    }


def _build_canonical_facility(
    encounter: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Build the facility context available from the current
    canonical data model.

    The current Encounter model only stores facility_id.
    It does not contain facility name/address/state/county.
    """

    if not encounter:
        return {}

    facility_id = encounter.get("facility_id")

    if not facility_id:
        return {}

    return {
        "facility_id": facility_id,
        "source": (
            encounter.get("provenance", {})
            .get("source")
        ),
        "source_resource": (
            encounter.get("provenance", {})
            .get("source_resource")
        ),
    }


def _build_provider_context(
    canonical_context: dict[str, Any],
    laboratory_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep source Practitioner references without inventing contact data."""
    references: list[str] = []
    for lab in laboratory_evidence:
        reference = lab.get("performer_reference")
        if isinstance(reference, str) and "Practitioner" in reference:
            references.append(reference)
    for document in canonical_context.get("clinical_documents", []):
        reference = document.get("author_reference")
        if isinstance(reference, str) and "Practitioner" in reference:
            references.append(reference)

    unique_references = list(dict.fromkeys(references))
    if not unique_references:
        return {
            "status": "MISSING",
            "missing_fields": ["name", "phone", "address"],
        }

    return {
        "status": "REFERENCE_ONLY",
        "reference": unique_references[0],
        "references": unique_references,
        "reference_source": "canonical lab/document performer or author reference",
        "missing_fields": ["name", "phone", "address"],
    }


def _build_laboratory_evidence(
    request: CandidateProcessRequest,
    canonical_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Use candidate laboratory evidence while enriching it with
    canonical LabResult data when a matching lab result exists.

    Detection evidence remains the workflow input;
    canonical data provides authoritative persisted context.
    """

    request_labs = request.laboratory_evidence

    canonical_labs = canonical_context.get(
        "lab_results",
        [],
    )

    if not request_labs:
        return canonical_labs

    canonical_by_id = {}

    for lab in canonical_labs:
        lab_id = lab.get("lab_result_id")

        if lab_id:
            canonical_by_id[str(lab_id)] = lab

        source_lab_id = lab.get(
            "source_lab_result_id"
        )

        if source_lab_id:
            canonical_by_id[
                str(source_lab_id)
            ] = lab

    enriched: list[dict[str, Any]] = []

    for lab in request_labs:
        merged = dict(lab)

        lab_id = (
            lab.get("lab_result_id")
            or lab.get("source_lab_result_id")
        )

        canonical_lab = (
            canonical_by_id.get(str(lab_id))
            if lab_id
            else None
        )

        if canonical_lab:
            merged = {
                **canonical_lab,
                **merged,
            }

        enriched.append(merged)

    return enriched


def _calculate_laboratory_decision(
    laboratory_evidence: list[dict[str, Any]],
) -> str | None:
    """
    Normalize laboratory evidence into the decision vocabulary
    expected by reconciliation.

    Supports both the current canonical LabResult structure:

        report_status
        conclusion

    and older evidence structures:

        status
        result
    """

    lab_decisions: list[str] = []

    for lab in laboratory_evidence:

        report_status = str(
            lab.get(
                "report_status",
                lab.get("status", ""),
            )
        ).strip().upper()

        conclusion = str(
            lab.get(
                "conclusion",
                lab.get("result", ""),
            )
        ).strip().upper()

        positive = lab.get("positive")

        # -----------------------------------------------------
        # Explicit boolean positive signal
        # -----------------------------------------------------

        if positive is True:
            lab_decisions.append("POSITIVE")
            continue

        # -----------------------------------------------------
        # Pending
        # -----------------------------------------------------

        if report_status in {
            "PENDING",
            "IN_PROGRESS",
        }:
            lab_decisions.append("PENDING")
            continue

        if conclusion in {
            "PENDING",
            "IN PROGRESS",
        }:
            lab_decisions.append("PENDING")
            continue

        # -----------------------------------------------------
        # Inconclusive
        # -----------------------------------------------------

        if report_status in {
            "INCONCLUSIVE",
            "INDETERMINATE",
        }:
            lab_decisions.append(
                "INCONCLUSIVE"
            )
            continue

        if conclusion in {
            "INCONCLUSIVE",
            "INDETERMINATE",
        }:
            lab_decisions.append(
                "INCONCLUSIVE"
            )
            continue

        # -----------------------------------------------------
        # Positive
        # -----------------------------------------------------

        if conclusion in {
            "POSITIVE",
            "DETECTED",
            "REACTIVE",
            "PRESENT",
        }:
            lab_decisions.append("POSITIVE")
            continue

        # -----------------------------------------------------
        # Negative
        # -----------------------------------------------------

        if conclusion in {
            "NEGATIVE",
            "NOT DETECTED",
            "NON-REACTIVE",
            "NONREACTIVE",
            "ABSENT",
        }:
            lab_decisions.append("NEGATIVE")
            continue

    # ---------------------------------------------------------
    # Resolve multiple laboratory signals
    # ---------------------------------------------------------

    if "PENDING" in lab_decisions:
        return "PENDING"

    if "INCONCLUSIVE" in lab_decisions:
        return "INCONCLUSIVE"

    if (
        "POSITIVE" in lab_decisions
        and "NEGATIVE" in lab_decisions
    ):
        return "INCONCLUSIVE"

    if "POSITIVE" in lab_decisions:
        return "POSITIVE"

    if "NEGATIVE" in lab_decisions:
        return "NEGATIVE"

    return None


def process_candidate(
    request: CandidateProcessRequest,
    db: Session,
) -> dict[str, Any]:
    """
    Run the SIGNAL candidate workflow.

    Workflow:

        Candidate
            ↓
        Canonical Patient Context
            ↓
        Relevant Encounter
            ↓
        Jurisdiction
            ↓
        Reportability
            ↓
        Rule Evaluation
            ↓
        Reconciliation
            ↓
        Smart Field Population
            ↓
        Case Assembly
            ↓
        eCR
            ↓
        Validation
            ↓
        Submission
    """

    # =========================================================
    # 1. LOAD CANONICAL PATIENT CONTEXT
    # =========================================================

    patient_id = _get_canonical_patient_id(
        request
    )

    try:
        canonical_context = get_patient_context(
            db=db,
            patient_id=patient_id,
        )

    except CanonicalPatientNotFoundError:
        raise

    # =========================================================
    # 2. CANONICAL PATIENT
    # =========================================================

    canonical_patient = canonical_context[
        "patient"
    ]

    patient = _build_canonical_patient(
        canonical_patient
    )

    # =========================================================
    # 3. EVIDENCE
    # =========================================================

    clinical_evidence = dict(
        request.clinical_evidence or {}
    )

    ai_evidence = dict(
        request.ai_evidence or {}
    )

    laboratory_evidence = (
        _build_laboratory_evidence(
            request=request,
            canonical_context=canonical_context,
        )
    )

    # =========================================================
    # 4. RELEVANT ENCOUNTER
    # =========================================================

    relevant_encounter = (
        _select_relevant_encounter(
            canonical_context=canonical_context,
            disease=request.disease,
            laboratory_evidence=laboratory_evidence,
            clinical_evidence=clinical_evidence,
        )
    )

    # If the selected encounter has an ID and the
    # clinical evidence doesn't already contain it,
    # preserve that canonical relationship.

    if (
        relevant_encounter
        and relevant_encounter.get("encounter_id")
        and not clinical_evidence.get("encounter_id")
    ):
        clinical_evidence[
            "encounter_id"
        ] = relevant_encounter[
            "encounter_id"
        ]

    # =========================================================
    # 5. FACILITY
    # =========================================================

    facility = _build_canonical_facility(
        relevant_encounter
    )

    # =========================================================
    # 6. PROVIDER
    # =========================================================

    # Practitioner references are retained when present, but the current
    # canonical model cannot resolve them to a name or contact information.
    provider = _build_provider_context(
        canonical_context,
        laboratory_evidence,
    )

    # =========================================================
    # 7. JURISDICTION INPUT
    # =========================================================

    patient_address = (
        canonical_patient.get("address")
        or {}
    )

    patient_state = patient_address.get(
        "state"
    )

    patient_county = patient_address.get(
        "county"
    )

    # Current Encounter only stores facility_id.
    # There is currently no canonical facility
    # state/county available.
    #
    # Request values are therefore used only as
    # optional supplemental facility context.

    facility_state = (
        request.facility_state
    )

    facility_county = (
        request.facility_county
    )

    # =========================================================
    # 8. JURISDICTION
    # =========================================================

    jurisdiction = resolve_jurisdiction(
        JurisdictionInput(
            candidate_id=request.candidate_id,
            patient_state=patient_state,
            patient_county=patient_county,
            facility_state=facility_state,
            facility_county=facility_county,
            disease=request.disease,
        )
    )

    # =========================================================
    # 9. REPORTABILITY
    # =========================================================

    reportability = evaluate_reportability(
        ReportabilityInput(
            candidate_id=request.candidate_id,
            jurisdiction=jurisdiction.jurisdiction,
            jurisdiction_status=jurisdiction.status,
            disease=request.disease,
            clinical_evidence=clinical_evidence,
            laboratory_evidence=laboratory_evidence,
            ai_evidence=ai_evidence,
        )
    )

    # =========================================================
    # 10. RULE / DECISION SUPPORT
    # =========================================================

    rule_result = evaluate_decision_support(
        candidate_id=request.candidate_id,
        disease=request.disease,
        jurisdiction=jurisdiction.jurisdiction,
        laboratory_evidence=laboratory_evidence,
        clinical_evidence=clinical_evidence,
    )

    # =========================================================
    # 11. AI DECISION
    # =========================================================

    ai_condition = ai_evidence.get(
        "condition"
    )

    ai_decision = None

    if (
        ai_condition
        and request.disease
    ):
        ai_decision = (
            "POSITIVE"
            if str(ai_condition).casefold()
            == request.disease.casefold()
            else "NEGATIVE"
        )

    # =========================================================
    # 12. LABORATORY DECISION
    # =========================================================

    laboratory_decision = (
        _calculate_laboratory_decision(
            laboratory_evidence
        )
    )

    # =========================================================
    # 13. RECONCILIATION
    # =========================================================

    reconciliation = determine_candidate_disposition(
        CandidateDispositionRequest(
            candidate_id=request.candidate_id,
            ai_decision=ai_decision,
            ai_confidence=ai_evidence.get(
                "confidence"
            ),
            laboratory_decision=(
                laboratory_decision
            ),
            rule_decision=(
                rule_result.decision
            ),
            jurisdiction_status=(
                jurisdiction.status
            ),
            reportability_decision=(
                reportability.decision
            ),
            human_review_required=(
                rule_result.human_review_required
            ),
            conflicts=rule_result.conflicts,
        )
    )

    # =========================================================
    # 14. CANDIDATE DATA
    # =========================================================

    candidate_data = {
        "candidate_id": request.candidate_id,
        "disease": request.disease,

        "patient": patient,
        "provider": provider,
        "facility": facility,

        "encounter": (
            relevant_encounter
            if relevant_encounter
            else {}
        ),

        "clinical_evidence": (
            clinical_evidence
        ),

        "laboratory_evidence": (
            laboratory_evidence
        ),

        "ai_evidence": ai_evidence,

        "jurisdiction": (
            jurisdiction.jurisdiction
        ),

        "jurisdiction_status": (
            jurisdiction.status
        ),

        "reportability_decision": (
            reportability.decision
        ),

        "reportability_evidence_status": (
            reportability.evidence_status
        ),

        "reconciliation_decision": (
            reconciliation.final_decision
        ),
    }

    # =========================================================
    # 15. SMART FIELD POPULATION
    # =========================================================

    print("\n========== BEFORE AGENT 27 ==========")
    print(
        "candidate_data keys:",
        list(candidate_data.keys()),
    )

    print("\nlaboratory_evidence:")

    for lab in candidate_data.get(
        "laboratory_evidence",
        [],
    ):
        print(lab)

    print("\nlab_evidence:")
    print(
        candidate_data.get("lab_evidence")
    )

    print("\nevidence:")
    print(
        candidate_data.get("evidence")
    )

    print("=====================================\n")

    smart_fields = populate_report_fields(
        candidate_data
    )

    # =========================================================
    # 16. CASE ASSEMBLY
    # =========================================================

    case = assemble_case(
        CaseAssemblyInput(
            candidate_id=request.candidate_id,
            patient=patient,
            facility=facility,
            provider=provider,
            disease=request.disease,
            clinical_evidence=clinical_evidence,
            laboratory_evidence=laboratory_evidence,
            ai_evidence=ai_evidence,
            jurisdiction=(
                jurisdiction.jurisdiction
            ),
            jurisdiction_status=(
                jurisdiction.status
            ),
            reportability_decision=(
                reportability.decision
            ),
            reportability_evidence_status=(
                reportability.evidence_status
            ),
            final_decision=(
                reconciliation.final_decision
            ),
            rule_id=rule_result.rule_id,
            report_fields=smart_fields.fields,
            required_missing_fields=(
                smart_fields.required_missing_fields
            ),
        ),
        db,
    )

    # =========================================================
    # 17. eCR BUILD
    # =========================================================

    ecr = build_ecr(case)

    # =========================================================
    # 18. VALIDATION
    # =========================================================

    validation = validate_ecr(
        ecr,
        smart_fields,
    )

    # =========================================================
    # 19. SUBMISSION
    # =========================================================

    submission = submit_ecr(
        ecr,
        validation,
    )

    # =========================================================
    # 20. RESPONSE
    # =========================================================

    return {
        "candidate_id": request.candidate_id,

        "workflow_status": (
            reconciliation.final_decision
        ),

        "canonical_context": {
            "patient_id": str(patient_id),
            "encounter_id": (
                relevant_encounter.get(
                    "encounter_id"
                )
                if relevant_encounter
                else None
            ),
            "facility_id": (
                facility.get("facility_id")
            ),
            "provider": provider,
        },

        "jurisdiction": {
            "value": (
                jurisdiction.jurisdiction
            ),
            "status": jurisdiction.status,
            "reasons": jurisdiction.reasons,
        },

        "reportability": {
            "decision": (
                reportability.decision
            ),
            "evidence_status": (
                reportability.evidence_status
            ),
            "reasons": reportability.reasons,
            "warnings": reportability.warnings,
        },

        "rule_evaluation": {
            "decision": (
                rule_result.decision
            ),
            "rule_id": rule_result.rule_id,
            "reasons": rule_result.reasons,
            "warnings": rule_result.warnings,
            "llm_reasoning": (
                rule_result.llm_reasoning
            ),
        },

        "reconciliation": {
            "final_decision": (
                reconciliation.final_decision
            ),
            "reasons": reconciliation.reasons,
            "warnings": reconciliation.warnings,
        },

        "smart_field_population": {
            "fields": smart_fields.fields,
            "populated_fields": (
                smart_fields.populated_fields
            ),
            "missing_fields": (
                smart_fields.missing_fields
            ),
            "sources": smart_fields.sources,
            "confidence": (
                smart_fields.confidence
            ),
            "warnings": smart_fields.warnings,
        },

        "case": {
            "case_id": case.case_id,
            "status": case.status,
            "warnings": case.warnings,
        },

        "ecr": {
            "ecr_id": ecr.ecr_id,
            "status": ecr.status,
            "rule_id": ecr.rule_id,
            "warnings": ecr.warnings,
        },

        "validation": {
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "completion_required": validation.completion_required,
        },

        "submission": {
            "status": submission.status,
            "submission_id": (
                submission.submission_id
            ),
            "destination": (
                submission.destination
            ),
            "errors": submission.errors,
            "warnings": submission.warnings,
        },
    }
