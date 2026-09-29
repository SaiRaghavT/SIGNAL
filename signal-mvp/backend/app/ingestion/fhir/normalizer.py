from __future__ import annotations

from typing import Any, Dict, List


def get_first_coding(
    element: Dict[str, Any] | None
) -> Dict[str, Any]:
    """
    Return the first coding object from a FHIR
    CodeableConcept-like element.
    """

    if not isinstance(element, dict):
        return {}

    coding = element.get("coding", [])

    if not isinstance(coding, list) or not coding:
        return {}

    first = coding[0]

    return first if isinstance(first, dict) else {}


def get_reference_id(
    reference: Any
) -> str | None:
    """
    Return a FHIR resource reference.

    Example:
        Patient/123
    """

    if not isinstance(reference, str):
        return None

    return reference


def normalize_patient(
    patient: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Normalize a FHIR Patient resource.
    """

    name = None

    names = patient.get("name", [])

    if isinstance(names, list) and names:

        first_name = names[0]

        if isinstance(first_name, dict):

            given = first_name.get("given", [])
            family = first_name.get("family")

            parts = []

            if isinstance(given, list):
                parts.extend(
                    str(value)
                    for value in given
                    if value
                )

            if family:
                parts.append(str(family))

            if parts:
                name = " ".join(parts)

    return {
        "id": patient.get("id"),
        "name": name,
        "date_of_birth": patient.get("birthDate"),
        "gender": patient.get("gender"),
    }


def normalize_condition(
    condition: Dict[str, Any]
) -> Dict[str, Any]:

    coding = get_first_coding(
        condition.get("code")
    )

    clinical_status = get_first_coding(
        condition.get("clinicalStatus")
    )

    verification_status = get_first_coding(
        condition.get("verificationStatus")
    )

    subject = condition.get(
        "subject",
        {}
    )

    encounter = condition.get(
        "encounter",
        {}
    )

    return {
        "id": condition.get("id"),
        "system": coding.get("system"),
        "code": coding.get("code"),
        "display": coding.get("display"),
        "clinical_status": clinical_status.get("code"),
        "clinical_status_display": clinical_status.get("display"),
        "verification_status": verification_status.get("code"),
        "verification_status_display": verification_status.get("display"),
        "onset": condition.get("onsetDateTime"),
        "recorded_date": condition.get("recordedDate"),
        "patient_id": get_reference_id(
            subject.get("reference")
        ),
        "encounter_id": get_reference_id(
            encounter.get("reference")
        ),
    }


def normalize_encounter(
    encounter: Dict[str, Any]
) -> Dict[str, Any]:

    subject = encounter.get(
        "subject",
        {}
    )

    encounter_class = encounter.get(
        "class",
        {}
    )

    class_code = None
    class_display = None

    if isinstance(encounter_class, dict):
        class_code = encounter_class.get("code")
        class_display = encounter_class.get("display")

    period = encounter.get(
        "period",
        {}
    )

    return {
        "id": encounter.get("id"),
        "status": encounter.get("status"),
        "class_code": class_code,
        "class_display": class_display,
        "start": period.get("start"),
        "end": period.get("end"),
        "patient_id": get_reference_id(
            subject.get("reference")
        ),
    }


def normalize_observation(
    observation: Dict[str, Any]
) -> Dict[str, Any]:

    coding = get_first_coding(
        observation.get("code")
    )

    subject = observation.get(
        "subject",
        {}
    )

    value = None
    value_type = None
    unit = None

    if "valueQuantity" in observation:

        quantity = observation.get(
            "valueQuantity",
            {}
        )

        if isinstance(quantity, dict):

            value = quantity.get("value")
            value_type = "Quantity"
            unit = quantity.get("unit")

    elif "valueCodeableConcept" in observation:

        concept = observation.get(
            "valueCodeableConcept",
            {}
        )

        value_coding = get_first_coding(
            concept
        )

        value = (
            value_coding.get("display")
            or value_coding.get("code")
        )

        value_type = "CodeableConcept"

    elif "valueString" in observation:

        value = observation.get(
            "valueString"
        )

        value_type = "string"

    elif "valueBoolean" in observation:

        value = observation.get(
            "valueBoolean"
        )

        value_type = "boolean"

    elif "valueInteger" in observation:

        value = observation.get(
            "valueInteger"
        )

        value_type = "integer"

    return {
        "id": observation.get("id"),
        "status": observation.get("status"),
        "code": coding.get("code"),
        "system": coding.get("system"),
        "display": coding.get("display"),
        "value": value,
        "value_type": value_type,
        "unit": unit,
        "effective_date": observation.get(
            "effectiveDateTime"
        ),
        "patient_id": get_reference_id(
            subject.get("reference")
        ),
    }


def normalize_immunization(
    immunization: Dict[str, Any]
) -> Dict[str, Any]:

    vaccine = get_first_coding(
        immunization.get("vaccineCode")
    )

    patient = immunization.get(
        "patient",
        {}
    )

    return {
        "id": immunization.get("id"),
        "vaccine_code": vaccine.get("code"),
        "vaccine_display": vaccine.get("display"),
        "status": immunization.get("status"),
        "occurrence": (
            immunization.get(
                "occurrenceDateTime"
            )
            or immunization.get(
                "occurrenceString"
            )
        ),
        "patient_id": get_reference_id(
            patient.get("reference")
        ),
    }


def normalize_diagnostic_report(
    report: Dict[str, Any]
) -> Dict[str, Any]:

    coding = get_first_coding(
        report.get("code")
    )

    subject = report.get(
        "subject",
        {}
    )

    return {
        "id": report.get("id"),
        "status": report.get("status"),
        "code": coding.get("code"),
        "system": coding.get("system"),
        "display": coding.get("display"),
        "effective_date": report.get(
            "effectiveDateTime"
        ),
        "issued": report.get("issued"),
        "patient_id": get_reference_id(
            subject.get("reference")
        ),
    }


def normalize_medication(
    medication: Dict[str, Any]
) -> Dict[str, Any]:

    medication_code = {}

    medication_reference = medication.get(
        "medicationReference"
    )

    medication_concept = medication.get(
        "medicationCodeableConcept"
    )

    if isinstance(
        medication_concept,
        dict
    ):
        medication_code = get_first_coding(
            medication_concept
        )

    subject = medication.get(
        "subject",
        {}
    )

    return {
        "id": medication.get("id"),
        "medication_code": medication_code.get(
            "code"
        ),
        "medication_display": medication_code.get(
            "display"
        ),
        "status": medication.get(
            "status"
        ),
        "authored_on": medication.get(
            "authoredOn"
        ),
        "patient_id": get_reference_id(
            subject.get("reference")
        ),
        "medication_reference": (
            medication_reference.get("reference")
            if isinstance(
                medication_reference,
                dict
            )
            else None
        ),
    }


def normalize_procedure(
    procedure: Dict[str, Any]
) -> Dict[str, Any]:

    coding = get_first_coding(
        procedure.get("code")
    )

    subject = procedure.get(
        "subject",
        {}
    )

    performed = (
        procedure.get("performedDateTime")
        or procedure.get("performedPeriod")
    )

    return {
        "id": procedure.get("id"),
        "status": procedure.get("status"),
        "code": coding.get("code"),
        "system": coding.get("system"),
        "display": coding.get("display"),
        "performed": performed,
        "patient_id": get_reference_id(
            subject.get("reference")
        ),
    }


def normalize_allergy(
    allergy: Dict[str, Any]
) -> Dict[str, Any]:

    coding = get_first_coding(
        allergy.get("code")
    )

    patient = allergy.get(
        "patient",
        {}
    )

    return {
        "id": allergy.get("id"),
        "code": coding.get("code"),
        "system": coding.get("system"),
        "display": coding.get("display"),
        "clinical_status": (
            get_first_coding(
                allergy.get("clinicalStatus")
            ).get("code")
        ),
        "verification_status": (
            get_first_coding(
                allergy.get("verificationStatus")
            ).get("code")
        ),
        "patient_id": get_reference_id(
            patient.get("reference")
        ),
    }


def normalize_bundle(
    resources: Dict[str, List[Dict[str, Any]]],
    provenance: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Normalize grouped FHIR resources into
    the SIGNAL normalized structure.

    Provenance is supplied by the ingestion layer
    and is not hard-coded here.
    """

    from app.models.normalized_patient import (
        create_normalized_patient
    )

    normalized = create_normalized_patient()

    # --------------------------------------------------
    # Provenance
    # --------------------------------------------------

    if provenance:
        normalized["provenance"].update(
            provenance
        )

    # --------------------------------------------------
    # Patient
    # --------------------------------------------------

    patients = resources.get(
        "Patient",
        []
    )

    if patients:

        patient = patients[0]

        normalized["patient"] = normalize_patient(
            patient
        )

        addresses = patient.get(
            "address",
            []
        )

        if (
            isinstance(addresses, list)
            and addresses
            and isinstance(
                addresses[0],
                dict
            )
        ):

            address = addresses[0]

            lines = address.get(
                "line",
                []
            )

            address_text = None

            if isinstance(lines, list):
                address_text = ", ".join(
                    str(line)
                    for line in lines
                    if line
                )

            normalized["location"] = {
                "address": address_text,
                "city": address.get("city"),
                "state": address.get("state"),
                "postal_code": address.get("postalCode"),
                "country": address.get("country"),
            }

    # --------------------------------------------------
    # Conditions
    # --------------------------------------------------

    normalized["conditions"] = [
        normalize_condition(condition)
        for condition in resources.get(
            "Condition",
            []
        )
    ]

    # --------------------------------------------------
    # Encounters
    # --------------------------------------------------

    normalized["encounters"] = [
        normalize_encounter(encounter)
        for encounter in resources.get(
            "Encounter",
            []
        )
    ]

    # --------------------------------------------------
    # Observations
    # --------------------------------------------------

    normalized["observations"] = [
        normalize_observation(observation)
        for observation in resources.get(
            "Observation",
            []
        )
    ]

    # --------------------------------------------------
    # Immunizations
    # --------------------------------------------------

    normalized["immunizations"] = [
        normalize_immunization(immunization)
        for immunization in resources.get(
            "Immunization",
            []
        )
    ]

    # --------------------------------------------------
    # Diagnostic Reports
    # --------------------------------------------------

    normalized["diagnostic_reports"] = [
        normalize_diagnostic_report(report)
        for report in resources.get(
            "DiagnosticReport",
            []
        )
    ]

    # --------------------------------------------------
    # Medications
    # --------------------------------------------------

    normalized["medications"] = [
        normalize_medication(medication)
        for medication in resources.get(
            "MedicationRequest",
            []
        )
    ]

    # --------------------------------------------------
    # Procedures
    # --------------------------------------------------

    normalized["procedures"] = [
        normalize_procedure(procedure)
        for procedure in resources.get(
            "Procedure",
            []
        )
    ]

    # --------------------------------------------------
    # Allergies
    # --------------------------------------------------

    normalized["allergies"] = [
        normalize_allergy(allergy)
        for allergy in resources.get(
            "AllergyIntolerance",
            []
        )
    ]

    return normalized