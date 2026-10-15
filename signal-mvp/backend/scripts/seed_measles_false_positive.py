"""Ingest and assemble the synthetic measles false-positive workflow case."""

import hashlib
import json
from pathlib import Path

from backend.app.agents.reportability_workflow.schemas import CandidateWorkflowInput
from backend.app.agents.reportability_workflow.service import process_candidate
from backend.app.candidate.service import persist_detection_candidates
from backend.app.database import SessionLocal
from backend.app.ingestion.fhir.service import ingest_fhir_bundle
from backend.app.models.case import Case
from backend.app.models.encounter import Encounter
from backend.app.models.patient import Patient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = PROJECT_ROOT / "data" / "edge_cases" / "Emily_Carter_measles_false_positive_FHIR.json"
SOURCE = "synthetic_false_positive"
SCENARIO_ID = "measles-false-positive"


def main() -> None:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    patient_resource = next(
        entry["resource"] for entry in bundle["entry"]
        if entry.get("resource", {}).get("resourceType") == "Patient"
    )
    encounter_resource = next(
        entry["resource"] for entry in bundle["entry"]
        if entry.get("resource", {}).get("resourceType") == "Encounter"
    )

    db = SessionLocal()
    try:
        ingest_fhir_bundle(db=db, payload=bundle, source=SOURCE)
        patient = db.query(Patient).filter(
            Patient.source == SOURCE,
            Patient.source_patient_id == patient_resource["id"],
        ).one()
        encounter = db.query(Encounter).filter(
            Encounter.source == SOURCE,
            Encounter.source_encounter_id == encounter_resource["id"],
        ).one()

        scenario_evidence = {
            "scenario_id": SCENARIO_ID,
            "title": "Synthetic measles false positive",
            "description": (
                "Measles-like symptoms with a negative measles PCR. Measles IgG is positive "
                "but represents prior immunity, not acute infection."
            ),
            "synthetic": True,
        }
        pcr_signal = {
            "trigger_type": "LAB_RESULT",
            "test": "Measles virus PCR",
            "result": "Not detected",
            "status": "final",
            "report_status": "final",
            "encounter_id": str(encounter.encounter_id),
        }
        detection_key = hashlib.sha256(
            f"{patient.patient_id}\x1fmeasles\x1f{encounter.encounter_id}".encode("utf-8")
        ).hexdigest()
        candidates = persist_detection_candidates(db, {
            "patient_id": str(patient.patient_id),
            "candidates": [{
                "disease_id": "measles",
                "encounter_id": str(encounter.encounter_id),
                "trigger_types": ["synthetic_false_positive_edge_case"],
                "confidence": 0.99,
                "evidence": [scenario_evidence],
                "signals": [pcr_signal],
            }],
        })
        candidate = candidates[0]
        if candidate.detection_key != detection_key:
            raise RuntimeError("The false-positive candidate key was not stable.")

        if not candidate.case_id:
            result = process_candidate(
                CandidateWorkflowInput(
                    candidate_id=candidate.candidate_id,
                    patient_id=patient.patient_id,
                    disease="measles",
                    patient_state=patient.state,
                    clinical_evidence={
                        "candidate_evidence": [scenario_evidence],
                        "candidate_signals": [pcr_signal],
                    },
                    laboratory_evidence=[pcr_signal],
                    ai_evidence={"condition": "measles", "confidence": 0.99},
                ),
                db,
            )
            candidate.status = "PROCESSED"
            candidate.case_id = result["case"]["case_id"]
            candidate.jurisdiction = result["jurisdiction"].get("value")
            db.commit()
        else:
            existing_case = db.query(Case).filter(Case.case_id == candidate.case_id).one_or_none()
            if existing_case is not None:
                existing_case.reportability_decision = "NOT_REPORTABLE"
                existing_case.reportability_evidence_status = "SYNTHETIC_FALSE_POSITIVE_RULED_OUT"
                existing_case.final_decision = "NOT_REPORTABLE"
                existing_case.status = "NOT_REPORTABLE"
                db.commit()
            result = {"workflow_status": "NOT_REPORTABLE", "case": {"case_id": candidate.case_id}}

        print(
            f"Seeded synthetic measles false-positive candidate {candidate.candidate_id}; "
            f"case={candidate.case_id}; workflow={result['workflow_status']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
