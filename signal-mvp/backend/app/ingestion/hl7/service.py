from typing import Any

from sqlalchemy.orm import Session

from backend.app.ingestion.hl7.mapper import map_hl7_message
from backend.app.ingestion.hl7.parser import parse_hl7_message
from backend.app.ingestion.hl7.validator import (
    validate_hl7_data_quality,
)
from backend.app.models.encounter import Encounter
from backend.app.models.lab_result import LabResult
from backend.app.models.observation import Observation
from backend.app.models.patient import Patient


def _get_or_create_patient(
    db: Session,
    patient_data: dict[str, Any],
) -> Patient:
    """
    Find an existing HL7 patient or create a new
    canonical Patient.
    """

    source_patient_id = patient_data[
        "source_patient_id"
    ]

    patient = (
        db.query(Patient)
        .filter(
            Patient.source == "hl7",
            Patient.source_patient_id
            == source_patient_id,
        )
        .first()
    )

    if patient is not None:
        name = patient_data.get("name") or {}
        if patient.first_name is None and name.get("given"):
            patient.first_name = name["given"]
        if patient.last_name is None and name.get("family"):
            patient.last_name = name["family"]
        return patient

    name = patient_data.get("name") or {}
    patient = Patient(
        source_patient_id=source_patient_id,
        first_name=name.get("given"),
        last_name=name.get("family"),
        date_of_birth=patient_data.get(
            "date_of_birth"
        ),
        sex=patient_data.get("sex"),
        address_line=patient_data.get(
            "address_line"
        ),
        city=patient_data.get("city"),
        state=patient_data.get("state"),
        postal_code=patient_data.get(
            "postal_code"
        ),
        source="hl7",
        source_resource="PID",
    )

    db.add(patient)
    db.flush()
    db.refresh(patient)

    return patient


def _get_or_create_encounter(
    db: Session,
    encounter_data: dict[str, Any],
    patient: Patient,
) -> Encounter:
    """
    Find an existing HL7 encounter or create a new one.
    """

    source_encounter_id = encounter_data[
        "source_encounter_id"
    ]

    encounter = (
        db.query(Encounter)
        .filter(
            Encounter.source == "hl7",
            Encounter.source_encounter_id
            == source_encounter_id,
        )
        .first()
    )

    if encounter is not None:
        return encounter

    encounter = Encounter(
        source_encounter_id=source_encounter_id,
        patient_id=patient.patient_id,
        facility_id=encounter_data.get(
            "facility_id"
        ),
        encounter_type=encounter_data.get(
            "encounter_type"
        ),
        status=encounter_data.get(
            "status"
        ),
        start_time=encounter_data.get(
            "start_time"
        ),
        end_time=encounter_data.get(
            "end_time"
        ),
        source="hl7",
        source_resource="PV1",
    )

    db.add(encounter)
    db.flush()
    db.refresh(encounter)

    return encounter


def _get_or_create_observation(
    db: Session,
    observation_data: dict[str, Any],
    patient: Patient,
    encounter: Encounter | None,
) -> Observation:
    """
    Find an existing HL7 observation or create a new one.
    """

    source_observation_id = observation_data[
        "source_observation_id"
    ]

    observation = (
        db.query(Observation)
        .filter(
            Observation.source == "hl7",
            Observation.source_observation_id
            == source_observation_id,
        )
        .first()
    )

    if observation is not None:
        return observation

    observation = Observation(
        source_observation_id=(
            source_observation_id
        ),
        patient_id=patient.patient_id,
        encounter_id=(
            encounter.encounter_id
            if encounter
            else None
        ),
        observation_code=observation_data.get(
            "observation_code"
        ),
        observation_system=observation_data.get(
            "observation_system"
        ),
        observation_display=observation_data.get(
            "observation_display"
        ),
        status=observation_data.get(
            "status"
        ),
        value_numeric=observation_data.get(
            "value_numeric"
        ),
        value_text=observation_data.get(
            "value_text"
        ),
        unit=observation_data.get(
            "unit"
        ),
        value_system=observation_data.get(
            "value_system"
        ),
        value_code=observation_data.get(
            "value_code"
        ),
        effective_time=observation_data.get(
            "effective_time"
        ),
        source="hl7",
        source_resource="OBX",
    )

    db.add(observation)
    db.flush()
    db.refresh(observation)

    return observation


def _get_or_create_lab_result(
    db: Session,
    lab_result_data: dict[str, Any],
    patient: Patient,
    encounter: Encounter | None,
    observations: list[Observation],
) -> LabResult:
    """
    Find an existing HL7 LabResult or create a new one.

    Also associates the LabResult with observations
    generated from OBX segments.
    """

    source_lab_result_id = lab_result_data[
        "source_lab_result_id"
    ]

    lab_result = (
        db.query(LabResult)
        .filter(
            LabResult.source == "hl7",
            LabResult.source_lab_result_id
            == source_lab_result_id,
        )
        .first()
    )

    if lab_result is None:
        lab_result = LabResult(
            source_lab_result_id=(
                source_lab_result_id
            ),
            patient_id=patient.patient_id,
            encounter_id=(
                encounter.encounter_id
                if encounter
                else None
            ),
            test_code=lab_result_data.get(
                "test_code"
            ),
            test_system=lab_result_data.get(
                "test_system"
            ),
            test_display=lab_result_data.get(
                "test_display"
            ),
            report_status=lab_result_data.get(
                "report_status"
            ),
            category=lab_result_data.get(
                "category"
            ),
            effective_time=lab_result_data.get(
                "effective_time"
            ),
            issued_time=lab_result_data.get(
                "issued_time"
            ),
            performer_reference=lab_result_data.get(
                "performer_reference"
            ),
            conclusion=lab_result_data.get(
                "conclusion"
            ),
            source="hl7",
            source_resource="OBR",
        )

        db.add(lab_result)
        db.flush()
        db.refresh(lab_result)

    for observation in observations:
        if observation not in lab_result.observations:
            lab_result.observations.append(
                observation
            )

    db.flush()
    db.refresh(lab_result)

    return lab_result


def ingest_hl7_message(
    db: Session,
    message: str,
) -> dict[str, Any]:
    """
    Parse, validate, map, and persist one HL7 v2
    message into the SIGNAL canonical database.

    Processing order:

        Parse
          ↓
        Quality Gate
          ↓
        Map
          ↓
        Persist
    """

    try:
        # --------------------------------------------------
        # 1. Parse
        # --------------------------------------------------

        parsed_message = parse_hl7_message(
            message
        )

        # --------------------------------------------------
        # 2. Data Quality Gate
        # --------------------------------------------------

        quality_result = (
            validate_hl7_data_quality(
                parsed_message
            )
        )

        if quality_result["error_count"] > 0:
            raise ValueError(
                "HL7 data quality validation failed: "
                f"{quality_result['error_count']} "
                "errors found."
            )

        # --------------------------------------------------
        # 3. Map
        # --------------------------------------------------

        mapped = map_hl7_message(
            parsed_message
        )

        # --------------------------------------------------
        # 4. Patient
        # --------------------------------------------------

        patient = _get_or_create_patient(
            db,
            mapped["patient"],
        )

        # --------------------------------------------------
        # 5. Encounter
        # --------------------------------------------------

        encounter = None

        if mapped["encounter"] is not None:
            encounter = _get_or_create_encounter(
                db,
                mapped["encounter"],
                patient,
            )

        # --------------------------------------------------
        # 6. Observations
        # --------------------------------------------------

        observations: list[Observation] = []

        for observation_data in mapped[
            "observations"
        ]:
            observation = (
                _get_or_create_observation(
                    db,
                    observation_data,
                    patient,
                    encounter,
                )
            )

            observations.append(
                observation
            )

        # --------------------------------------------------
        # 7. Lab Result
        # --------------------------------------------------

        lab_result = None

        if mapped["lab_result"] is not None:
            lab_result = _get_or_create_lab_result(
                db,
                mapped["lab_result"],
                patient,
                encounter,
                observations,
            )

        # --------------------------------------------------
        # 8. Commit
        # --------------------------------------------------

        db.commit()

        # --------------------------------------------------
        # 9. Result
        # --------------------------------------------------

        return {
            "status": "success",
            "source": "hl7",
            "message_type": mapped[
                "message_type"
            ],
            "patient_id": str(
                patient.patient_id
            ),
            "encounter_id": (
                str(encounter.encounter_id)
                if encounter
                else None
            ),
            "quality": {
                "status": quality_result[
                    "status"
                ],
                "error_count": quality_result[
                    "error_count"
                ],
                "warning_count": quality_result[
                    "warning_count"
                ],
                "issue_count": quality_result[
                    "issue_count"
                ],
            },
            "counts": {
                "patients": 1,
                "encounters": (
                    1
                    if encounter
                    else 0
                ),
                "observations": len(
                    observations
                ),
                "lab_results": (
                    1
                    if lab_result
                    else 0
                ),
            },
        }

    except Exception:
        db.rollback()
        raise