from sqlalchemy.orm import Session

from backend.app.models.patient import Patient
from backend.app.models.encounter import Encounter
from backend.app.models.condition import Condition
from backend.app.models.observation import Observation
from backend.app.models.lab_result import LabResult
from backend.app.models.clinical_document import ClinicalDocument


def save_patient(
    db: Session,
    patient: Patient,
) -> Patient:
    """
    Persist a canonical Patient to the current database transaction.

    If the same source + source_patient_id already exists,
    return the existing patient instead of creating a duplicate.
    """

    existing_patient = (
        db.query(Patient)
        .filter(
            Patient.source == patient.source,
            Patient.source_patient_id == patient.source_patient_id,
        )
        .first()
    )

    if existing_patient:
        return existing_patient

    db.add(patient)
    db.flush()
    db.refresh(patient)

    return patient


def save_encounter(
    db: Session,
    encounter: Encounter,
) -> Encounter:
    """
    Persist a canonical Encounter to the current database transaction.

    Prevents duplicate encounters using:
    (source, source_encounter_id)
    """

    existing_encounter = (
        db.query(Encounter)
        .filter(
            Encounter.source == encounter.source,
            Encounter.source_encounter_id == encounter.source_encounter_id,
        )
        .first()
    )

    if existing_encounter:
        return existing_encounter

    db.add(encounter)
    db.flush()
    db.refresh(encounter)

    return encounter


def save_condition(
    db: Session,
    condition: Condition,
) -> Condition:
    """
    Persist a canonical Condition to the current database transaction.

    Prevents duplicate conditions using:
    (source, source_condition_id)
    """

    existing_condition = (
        db.query(Condition)
        .filter(
            Condition.source == condition.source,
            Condition.source_condition_id == condition.source_condition_id,
        )
        .first()
    )

    if existing_condition:
        return existing_condition

    db.add(condition)
    db.flush()
    db.refresh(condition)

    return condition


def save_observation(
    db: Session,
    observation: Observation,
) -> Observation:
    """
    Persist a canonical Observation to the current database transaction.

    Prevents duplicate observations using:
    (source, source_observation_id)
    """

    existing_observation = (
        db.query(Observation)
        .filter(
            Observation.source == observation.source,
            Observation.source_observation_id
            == observation.source_observation_id,
        )
        .first()
    )

    if existing_observation:
        return existing_observation

    db.add(observation)
    db.flush()
    db.refresh(observation)

    return observation


def save_lab_result(
    db: Session,
    lab_result: LabResult,
    observation_source_ids: list[str],
) -> LabResult:
    """
    Persist a LabResult and link it to existing Observations.

    Observations are resolved using:
        (source, source_observation_id)

    Establishes the LabResult -> Observation
    many-to-many relationship.
    """

    existing_lab_result = (
        db.query(LabResult)
        .filter(
            LabResult.source == lab_result.source,
            LabResult.source_lab_result_id
            == lab_result.source_lab_result_id,
        )
        .first()
    )

    if existing_lab_result:
        lab_result = existing_lab_result
    else:
        db.add(lab_result)
        db.flush()

    for source_observation_id in observation_source_ids:

        observation = (
            db.query(Observation)
            .filter(
                Observation.source == lab_result.source,
                Observation.source_observation_id
                == source_observation_id,
            )
            .first()
        )

        if observation is None:
            continue

        if observation not in lab_result.observations:
            lab_result.observations.append(observation)

    db.flush()
    db.refresh(lab_result)

    return lab_result


def save_clinical_document(
    db: Session,
    document: ClinicalDocument,
) -> ClinicalDocument:
    """
    Persist a canonical ClinicalDocument to the current database transaction.

    Prevents duplicate documents using:
    (source, source_document_id)
    """

    existing_document = (
        db.query(ClinicalDocument)
        .filter(
            ClinicalDocument.source == document.source,
            ClinicalDocument.source_document_id
            == document.source_document_id,
        )
        .first()
    )

    if existing_document:
        return existing_document

    db.add(document)
    db.flush()
    db.refresh(document)

    return document