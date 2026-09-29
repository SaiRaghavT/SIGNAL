import json
from pathlib import Path

from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction

from backend.app.reportability.models import ReportabilityInput
from backend.app.reportability.evaluator import evaluate_reportability

from backend.app.case.models import CaseAssemblyInput
from backend.app.case.assembler import assemble_case

from backend.app.ecr.builder import build_ecr

from backend.app.schemas.validation import validate_ecr

from backend.app.submission.service import submit_ecr


DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "texas"
    / "measles"
    / "member3_reportability_test.json"
)


def load_candidates():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    candidates = load_candidates()

    print(f"Loaded {len(candidates)} candidates")
    print("=" * 90)

    for candidate in candidates:

        candidate_id = candidate["candidate_id"]

        # ---------------------------------------------------------
        # 1. JURISDICTION
        # ---------------------------------------------------------
        patient = candidate.get("patient", {})
        facility = candidate.get("facility", {})

        jurisdiction_input = JurisdictionInput(
            candidate_id=candidate_id,
            patient_state=patient.get("state"),
            patient_county=patient.get("county"),
            facility_state=facility.get("state"),
            facility_county=facility.get("county"),
            disease=candidate.get("disease"),
        )

        jurisdiction_result = resolve_jurisdiction(jurisdiction_input)

        # ---------------------------------------------------------
        # 2. REPORTABILITY ASSESSMENT
        # ---------------------------------------------------------
        reportability_input = ReportabilityInput(
            candidate_id=candidate_id,
            jurisdiction=jurisdiction_result.jurisdiction,
            jurisdiction_status=jurisdiction_result.status,
            disease=candidate.get("disease"),
            clinical_evidence=candidate.get("clinical_evidence", {}),
            laboratory_evidence=candidate.get("laboratory_evidence", []),
            ai_evidence=candidate.get("ai_evidence", {}),
        )

        reportability_result = evaluate_reportability(
            reportability_input
        )

        # ---------------------------------------------------------
        # 3. CASE ASSEMBLY
        # ---------------------------------------------------------
        case_input = CaseAssemblyInput(
            candidate_id=candidate_id,
            patient=patient,
            facility=facility,
            provider=candidate.get("provider", {}),
            disease=candidate.get("disease_info"),
            clinical_evidence=candidate.get(
                "clinical_evidence", {}
            ),
            laboratory_evidence=candidate.get(
                "laboratory_evidence", []
            ),
            ai_evidence=candidate.get(
                "ai_evidence", {}
            ),
            jurisdiction=jurisdiction_result.jurisdiction,
            jurisdiction_status=jurisdiction_result.status,
            reportability_decision=reportability_result.decision,
            reportability_evidence_status=(
                reportability_result.evidence_status
            ),
        )

        signal_case = assemble_case(case_input)

        # ---------------------------------------------------------
        # 4. ECR BUILD
        # ---------------------------------------------------------
        ecr = build_ecr(signal_case)

        # ---------------------------------------------------------
        # 5. ECR VALIDATION
        # ---------------------------------------------------------
        validation = validate_ecr(ecr)

        # ---------------------------------------------------------
        # 6. MOCK PHA SUBMISSION
        # ---------------------------------------------------------
        submission = submit_ecr(
            ecr,
            validation,
        )

        # ---------------------------------------------------------
        # 7. SUMMARY
        # ---------------------------------------------------------
        print(
            f"{candidate_id} | "
            f"Jurisdiction: {jurisdiction_result.status} | "
            f"Reportability: {reportability_result.decision} | "
            f"Case: {signal_case.status} | "
            f"ECR: {ecr.status} | "
            f"Validation: "
            f"{'VALID' if validation.valid else 'INVALID'} | "
            f"Submission: {submission.status}"
        )

    print("=" * 90)
    print("Member 3 workflow test completed.")


if __name__ == "__main__":
    main()