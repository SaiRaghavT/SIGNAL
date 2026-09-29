import sys
from pathlib import Path

# Add backend/ to Python path
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from app.ingestion.fhir.fhir_parser import FHIRParser
from app.ingestion.fhir.normalizer import normalize_bundle


# Project root:
# signal-mvp/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

FHIR_FILE = (
    PROJECT_ROOT
    / "data"
    / "synthea"
    / "fhir"
    / "sample_patient.json"
)


def get_normalized_data():
    """
    Parse the FHIR Bundle and normalize it.
    """

    parser = FHIRParser(FHIR_FILE)

    resources = parser.parse()

    normalized = normalize_bundle(resources)

    return normalized


def test_normalized_patient_exists():
    """Verify that the normalized patient exists."""

    normalized = get_normalized_data()

    assert "patient" in normalized
    assert normalized["patient"] is not None


def test_normalized_patient_fields():
    """Verify normalized Patient fields."""

    normalized = get_normalized_data()

    patient = normalized["patient"]

    assert patient["id"] is not None
    assert patient["name"] is not None
    assert patient["date_of_birth"] is not None
    assert patient["gender"] is not None


def test_normalized_patient_location():
    """Verify patient location normalization."""

    normalized = get_normalized_data()

    location = normalized["location"]

    assert location["address"] is not None
    assert location["city"] == "Austin"
    assert location["state"] == "Texas"
    assert location["postal_code"] == "78701"
    assert location["country"] == "US"


def test_normalized_conditions():
    """Verify Condition resources are normalized."""

    normalized = get_normalized_data()

    conditions = normalized["conditions"]

    assert len(conditions) == 4

    for condition in conditions:
        assert condition["id"] is not None
        assert condition["code"] is not None
        assert condition["display"] is not None
        assert condition["patient_id"] is not None


def test_normalized_measles_condition():
    """Verify the Measles condition is preserved during normalization."""

    normalized = get_normalized_data()

    conditions = normalized["conditions"]

    measles = [
        condition
        for condition in conditions
        if condition.get("code") == "14189004"
    ]

    assert len(measles) == 1

    measles_condition = measles[0]

    assert measles_condition["display"] == "Measles (disorder)"
    assert measles_condition["clinical_status"] == "active"
    assert measles_condition["verification_status"] == "confirmed"


def test_normalized_encounters():
    """Verify Encounter resources are normalized."""

    normalized = get_normalized_data()

    encounters = normalized["encounters"]

    assert len(encounters) == 10

    for encounter in encounters:
        assert encounter["id"] is not None
        assert encounter["status"] is not None
        assert encounter["patient_id"] is not None


def test_normalized_observations():
    """Verify Observation resources are normalized."""

    normalized = get_normalized_data()

    observations = normalized["observations"]

    assert len(observations) == 59

    for observation in observations:
        assert observation["id"] is not None
        assert observation["code"] is not None
        assert observation["patient_id"] is not None


def test_normalized_immunizations():
    """Verify Immunization resources are normalized."""

    normalized = get_normalized_data()

    immunizations = normalized["immunizations"]

    assert len(immunizations) == 10

    for immunization in immunizations:
        assert immunization["id"] is not None
        assert immunization["vaccine_code"] is not None
        assert immunization["patient_id"] is not None


def test_normalized_diagnostic_reports():
    """Verify DiagnosticReport resources are normalized."""

    normalized = get_normalized_data()

    reports = normalized["diagnostic_reports"]

    assert len(reports) == 2

    for report in reports:
        assert report["id"] is not None
        assert report["code"] is not None
        assert report["patient_id"] is not None


def test_normalized_medications():
    """Verify MedicationRequest resources are normalized."""

    normalized = get_normalized_data()

    medications = normalized["medications"]

    assert len(medications) == 2

    for medication in medications:
        assert medication["id"] is not None
        assert medication["medication_code"] is not None
        assert medication["patient_id"] is not None


def test_normalized_procedures():
    """Verify Procedure resources are normalized."""

    normalized = get_normalized_data()

    procedures = normalized["procedures"]

    assert len(procedures) == 3

    for procedure in procedures:
        assert procedure["id"] is not None
        assert procedure["code"] is not None
        assert procedure["patient_id"] is not None


def test_normalized_schema():
    """Verify the complete normalized schema exists."""

    normalized = get_normalized_data()

    expected_keys = {
    "provenance",
    "patient",
    "location",
    "conditions",
    "encounters",
    "observations",
    "immunizations",
    "diagnostic_reports",
    "medications",
    "procedures",
    "allergies",
}

    assert set(normalized.keys()) == expected_keys