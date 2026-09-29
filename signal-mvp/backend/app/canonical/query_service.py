from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.patient import Patient
from backend.app.models.encounter import Encounter
from backend.app.models.condition import Condition
from backend.app.models.observation import Observation
from backend.app.models.lab_result import LabResult
from backend.app.models.clinical_document import ClinicalDocument


class CanonicalPatientNotFoundError(ValueError):
    """Raised when a requested patient does not exist."""


def _patient_to_dict(patient: Patient) -> dict[str, Any]:
    return {
        "patient_id": str(patient.patient_id),
        "source_patient_id": patient.source_patient_id,
        "date_of_birth": (
            patient.date_of_birth.isoformat()
            if patient.date_of_birth
            else None
        ),
        "sex": patient.sex,
        "address": {
            "line": patient.address_line,
            "city": patient.city,
            "county": patient.county,
            "state": patient.state,
            "postal_code": patient.postal_code,
        },
        "provenance": {
            "source": patient.source,
            "source_resource": patient.source_resource,
        },
    }


def _encounter_to_dict(encounter: Encounter) -> dict[str, Any]:
    return {
        "encounter_id": str(encounter.encounter_id),
        "source_encounter_id": encounter.source_encounter_id,
        "patient_id": str(encounter.patient_id),
        "facility_id": encounter.facility_id,
        "encounter_type": encounter.encounter_type,
        "status": encounter.status,
        "start_time": (
            encounter.start_time.isoformat()
            if encounter.start_time
            else None
        ),
        "end_time": (
            encounter.end_time.isoformat()
            if encounter.end_time
            else None
        ),
        "provenance": {
            "source": encounter.source,
            "source_resource": encounter.source_resource,
        },
    }


def _condition_to_dict(condition: Condition) -> dict[str, Any]:
    return {
        "condition_id": str(condition.condition_id),
        "source_condition_id": condition.source_condition_id,
        "patient_id": str(condition.patient_id),
        "encounter_id": (
            str(condition.encounter_id)
            if condition.encounter_id
            else None
        ),
        "code": {
            "system": condition.condition_system,
            "code": condition.condition_code,
            "display": condition.condition_display,
        },
        "clinical_status": condition.clinical_status,
        "verification_status": condition.verification_status,
        "onset_time": (
            condition.onset_time.isoformat()
            if condition.onset_time
            else None
        ),
        "recorded_time": (
            condition.recorded_time.isoformat()
            if condition.recorded_time
            else None
        ),
        "provenance": {
            "source": condition.source,
            "source_resource": condition.source_resource,
        },
    }


def _observation_to_dict(observation: Observation) -> dict[str, Any]:
    return {
        "observation_id": str(observation.observation_id),
        "source_observation_id": observation.source_observation_id,
        "patient_id": str(observation.patient_id),
        "encounter_id": (
            str(observation.encounter_id)
            if observation.encounter_id
            else None
        ),
        "code": {
            "system": observation.observation_system,
            "code": observation.observation_code,
            "display": observation.observation_display,
        },
        "status": observation.status,
        "value": {
            "numeric": (
                float(observation.value_numeric)
                if observation.value_numeric is not None
                else None
            ),
            "text": observation.value_text,
            "unit": observation.unit,
            "system": observation.value_system,
            "code": observation.value_code,
        },
        "effective_time": (
            observation.effective_time.isoformat()
            if observation.effective_time
            else None
        ),
        "provenance": {
            "source": observation.source,
            "source_resource": observation.source_resource,
        },
    }


def _lab_result_to_dict(lab_result: LabResult) -> dict[str, Any]:
    return {
        "lab_result_id": str(lab_result.lab_result_id),
        "source_lab_result_id": lab_result.source_lab_result_id,
        "patient_id": str(lab_result.patient_id),
        "encounter_id": (
            str(lab_result.encounter_id)
            if lab_result.encounter_id
            else None
        ),
        "test": {
            "system": lab_result.test_system,
            "code": lab_result.test_code,
            "display": lab_result.test_display,
        },
        "report_status": lab_result.report_status,
        "category": lab_result.category,
        "effective_time": (
            lab_result.effective_time.isoformat()
            if lab_result.effective_time
            else None
        ),
        "issued_time": (
            lab_result.issued_time.isoformat()
            if lab_result.issued_time
            else None
        ),
        "performer_reference": lab_result.performer_reference,
        "conclusion": lab_result.conclusion,
        "observations": [
            {
                "observation_id": str(observation.observation_id),
                "source_observation_id": observation.source_observation_id,
                "code": {
                    "system": observation.observation_system,
                    "code": observation.observation_code,
                    "display": observation.observation_display,
                },
                "value": {
                    "numeric": (
                        float(observation.value_numeric)
                        if observation.value_numeric is not None
                        else None
                    ),
                    "text": observation.value_text,
                    "unit": observation.unit,
                    "code": observation.value_code,
                    "system": observation.value_system,
                },
                "status": observation.status,
                "effective_time": (
                    observation.effective_time.isoformat()
                    if observation.effective_time
                    else None
                ),
            }
            for observation in lab_result.observations
        ],
        "provenance": {
            "source": lab_result.source,
            "source_resource": lab_result.source_resource,
        },
    }


def _clinical_document_to_dict(
    document: ClinicalDocument,
) -> dict[str, Any]:
    return {
        "document_id": str(document.document_id),
        "source_document_id": document.source_document_id,
        "patient_id": str(document.patient_id),
        "encounter_id": (
            str(document.encounter_id)
            if document.encounter_id
            else None
        ),
        "document_type": document.document_type,
        "document_status": document.document_status,
        "title": document.title,
        "document_date": (
            document.document_date.isoformat()
            if document.document_date
            else None
        ),
        "author_reference": document.author_reference,
        "content_type": document.content_type,
        "content_location": document.content_location,
        "extracted_text": document.extracted_text,
        "provenance": {
            "source": document.source,
            "source_resource": document.source_resource,
        },
    }


def get_patient_context(
    db: Session,
    patient_id: UUID,
) -> dict[str, Any]:
    """
    Retrieve the complete canonical context for one patient.

    This is the primary read interface for downstream SIGNAL
    components such as AI agents, reportability logic, case
    assembly, and workflow services.
    """

    patient = (
        db.query(Patient)
        .filter(Patient.patient_id == patient_id)
        .first()
    )

    if patient is None:
        raise CanonicalPatientNotFoundError(
            f"Patient not found: {patient_id}"
        )

    encounters = (
        db.query(Encounter)
        .filter(Encounter.patient_id == patient_id)
        .order_by(Encounter.start_time.asc())
        .all()
    )

    conditions = (
        db.query(Condition)
        .filter(Condition.patient_id == patient_id)
        .order_by(Condition.recorded_time.asc())
        .all()
    )

    observations = (
        db.query(Observation)
        .filter(Observation.patient_id == patient_id)
        .order_by(Observation.effective_time.asc())
        .all()
    )

    lab_results = (
        db.query(LabResult)
        .filter(LabResult.patient_id == patient_id)
        .order_by(LabResult.effective_time.asc())
        .all()
    )

    clinical_documents = (
        db.query(ClinicalDocument)
        .filter(ClinicalDocument.patient_id == patient_id)
        .order_by(ClinicalDocument.document_date.asc())
        .all()
    )

    return {
        "patient": _patient_to_dict(patient),
        "encounters": [
            _encounter_to_dict(encounter)
            for encounter in encounters
        ],
        "conditions": [
            _condition_to_dict(condition)
            for condition in conditions
        ],
        "observations": [
            _observation_to_dict(observation)
            for observation in observations
        ],
        "lab_results": [
            _lab_result_to_dict(lab_result)
            for lab_result in lab_results
        ],
        "clinical_documents": [
            _clinical_document_to_dict(document)
            for document in clinical_documents
        ],
    }