from datetime import datetime
from typing import Any

from backend.app.ingestion.hl7.parser import (
    get_field,
    get_first_segment,
    get_segments,
)


def _parse_hl7_date(value: str | None) -> datetime | None:
    """
    Parse common HL7 date/time formats.

    Supported examples:
        20260928
        202609281200
        20260928120030
    """

    if not value:
        return None

    value = value.strip()

    formats = (
        ("%Y%m%d%H%M%S", 14),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    )

    for fmt, length in formats:
        if len(value) < length:
            continue

        try:
            return datetime.strptime(
                value[:length],
                fmt,
            )
        except ValueError:
            continue

    return None


def _extract_component(
    value: str | None,
    component_index: int,
) -> str | None:
    """
    Extract a component from an HL7 composite field.

    Example:

        DOE^JOHN^A

    component 0 -> DOE
    component 1 -> JOHN
    component 2 -> A
    """

    if not value:
        return None

    components = value.split("^")

    if component_index >= len(components):
        return None

    result = components[component_index].strip()

    return result or None


def _extract_code(
    value: str | None,
) -> tuple[str | None, str | None, str | None]:
    """
    Extract code, display, and system from an HL7 CE/CWE-style field.

    Example:

        13950-1^Measles IgM^LN

    returns:

        code = 13950-1
        display = Measles IgM
        system = LN
    """

    if not value:
        return None, None, None

    components = value.split("^")

    code = (
        components[0].strip()
        if len(components) > 0
        else None
    )

    display = (
        components[1].strip()
        if len(components) > 1
        else None
    )

    system = (
        components[2].strip()
        if len(components) > 2
        else None
    )

    return (
        code or None,
        display or None,
        system or None,
    )


def map_patient(
    parsed_message: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Map HL7 PID into the SIGNAL canonical Patient shape.
    """

    pid = get_first_segment(
        parsed_message,
        "PID",
    )

    if pid is None:
        return None

    patient_identifier = get_field(
        pid,
        3,
    )

    patient_id = _extract_component(
        patient_identifier,
        0,
    )

    if not patient_id:
        return None

    patient_name = get_field(
        pid,
        5,
    )

    family_name = _extract_component(
        patient_name,
        0,
    )

    given_name = _extract_component(
        patient_name,
        1,
    )

    date_of_birth = _parse_hl7_date(
        get_field(pid, 7)
    )

    sex = get_field(
        pid,
        8,
    )

    address = get_field(
        pid,
        11,
    )

    address_components = (
        address.split("^")
        if address
        else []
    )

    return {
        "source_patient_id": patient_id,
        "date_of_birth": (
            date_of_birth.date()
            if date_of_birth
            else None
        ),
        "sex": sex,
        "address_line": (
            address_components[0]
            if len(address_components) > 0
            else None
        ),
        "city": (
            address_components[2]
            if len(address_components) > 2
            else None
        ),
        "state": (
            address_components[3]
            if len(address_components) > 3
            else None
        ),
        "postal_code": (
            address_components[4]
            if len(address_components) > 4
            else None
        ),
        "source": "hl7",
        "source_resource": "PID",
        "name": {
            "family": family_name,
            "given": given_name,
        },
    }


def map_encounter(
    parsed_message: dict[str, Any],
    patient_id: Any,
) -> dict[str, Any] | None:
    """
    Map HL7 PV1 into the SIGNAL canonical Encounter shape.
    """

    pv1 = get_first_segment(
        parsed_message,
        "PV1",
    )

    if pv1 is None:
        return None

    encounter_identifier = get_field(
        pv1,
        19,
    )

    if not encounter_identifier:
        encounter_identifier = (
            f"hl7-encounter-{patient_id}"
        )

    patient_class = get_field(
        pv1,
        2,
    )

    assigned_location = get_field(
        pv1,
        3,
    )

    attending_doctor = get_field(
        pv1,
        7,
    )

    return {
        "source_encounter_id": encounter_identifier,
        "patient_id": patient_id,
        "facility_id": assigned_location,
        "encounter_type": patient_class,
        "status": "active",
        "start_time": None,
        "end_time": None,
        "source": "hl7",
        "source_resource": "PV1",
        "provider_reference": attending_doctor,
    }


def map_observations(
    parsed_message: dict[str, Any],
    patient_id: Any,
    encounter_id: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Map all HL7 OBX segments into SIGNAL Observations.
    """

    observations: list[dict[str, Any]] = []

    for obx in get_segments(
        parsed_message,
        "OBX",
    ):
        observation_identifier = get_field(
            obx,
            3,
        )

        code, display, system = _extract_code(
            observation_identifier
        )

        if not code and not display:
            continue

        value_type = get_field(
            obx,
            2,
        )

        value = get_field(
            obx,
            5,
        )

        unit = get_field(
            obx,
            6,
        )

        status = get_field(
            obx,
            11,
        )

        observation_id = get_field(
            obx,
            1,
        )

        if not observation_id:
            observation_id = (
                f"observation-{len(observations) + 1}"
            )

        value_numeric = None
        value_text = None
        value_code = None
        value_system = None

        if value_type in {"NM", "SN"}:
            try:
                value_numeric = float(value)
            except (TypeError, ValueError):
                value_text = value

        elif value_type in {"CE", "CWE"}:
            (
                value_code,
                value_text,
                value_system,
            ) = _extract_code(value)

        else:
            value_text = value

        observations.append(
            {
                "source_observation_id": observation_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "observation_code": code,
                "observation_system": system,
                "observation_display": display,
                "status": status,
                "value_numeric": value_numeric,
                "value_text": value_text,
                "unit": unit,
                "value_system": value_system,
                "value_code": value_code,
                "effective_time": _parse_hl7_date(
                    get_field(obx, 14)
                ),
                "source": "hl7",
                "source_resource": "OBX",
            }
        )

    return observations


def map_lab_result(
    parsed_message: dict[str, Any],
    patient_id: Any,
    encounter_id: Any | None = None,
) -> dict[str, Any] | None:
    """
    Map HL7 ORC/OBR into the SIGNAL canonical LabResult shape.

    Identifier priority:

        ORC-2 → OBR-2 → OBR-3

    ORC-2 is the placer/order identifier.
    OBR-2 is the placer order number.
    OBR-3 is the filler order number.
    """

    obr = get_first_segment(
        parsed_message,
        "OBR",
    )

    if obr is None:
        return None

    orc = get_first_segment(
        parsed_message,
        "ORC",
    )

    # Prefer ORC-2: Placer Order Number.
    source_lab_result_id = (
        get_field(orc, 2)
        if orc
        else None
    )

    # Fallback to OBR-2: Placer Order Number.
    if not source_lab_result_id:
        source_lab_result_id = get_field(
            obr,
            2,
        )

    # Final fallback to OBR-3: Filler Order Number.
    if not source_lab_result_id:
        source_lab_result_id = get_field(
            obr,
            3,
        )

    # Last-resort deterministic identifier.
    if not source_lab_result_id:
        source_lab_result_id = (
            f"hl7-lab-{patient_id}"
        )

    test_identifier = get_field(
        obr,
        4,
    )

    test_code, test_display, test_system = (
        _extract_code(test_identifier)
    )

    return {
        "source_lab_result_id": source_lab_result_id,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "test_code": test_code,
        "test_system": test_system,
        "test_display": test_display,
        "report_status": get_field(
            obr,
            25,
        ),
        "category": "laboratory",
        "effective_time": _parse_hl7_date(
            get_field(obr, 7)
        ),
        "issued_time": _parse_hl7_date(
            get_field(obr, 22)
        ),
        "performer_reference": get_field(
            obr,
            32,
        ),
        "conclusion": None,
        "source": "hl7",
        "source_resource": "OBR",
    }


def map_hl7_message(
    parsed_message: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert a parsed HL7 message into canonical
    intermediate objects.

    This function does not write to PostgreSQL.
    """

    patient = map_patient(
        parsed_message
    )

    if patient is None:
        raise ValueError(
            "HL7 message does not contain a valid PID segment."
        )

    patient_source_id = patient[
        "source_patient_id"
    ]

    encounter = map_encounter(
        parsed_message,
        patient_source_id,
    )

    encounter_source_id = (
        encounter["source_encounter_id"]
        if encounter
        else None
    )

    observations = map_observations(
        parsed_message,
        patient_source_id,
        encounter_source_id,
    )

    lab_result = map_lab_result(
        parsed_message,
        patient_source_id,
        encounter_source_id,
    )

    return {
        "message_type": parsed_message.get(
            "message_type"
        ),
        "patient": patient,
        "encounter": encounter,
        "observations": observations,
        "lab_result": lab_result,
    }