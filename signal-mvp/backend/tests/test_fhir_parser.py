import sys
from pathlib import Path

# Add backend/ to Python path
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from app.ingestion.fhir.fhir_parser import FHIRParser


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


def test_fhir_file_exists():
    """Verify that the sample FHIR file exists."""

    assert FHIR_FILE.exists()


def test_fhir_parser_loads_file():
    """Verify that the FHIR JSON file can be loaded."""

    parser = FHIRParser(FHIR_FILE)

    data = parser.load()

    assert isinstance(data, dict)
    assert data.get("resourceType") == "Bundle"


def test_fhir_parser_resource_counts():
    """Verify expected FHIR resource counts."""

    parser = FHIRParser(FHIR_FILE)

    summary = parser.summary()

    assert summary["Patient"] == 1
    assert summary["Organization"] == 2
    assert summary["Practitioner"] == 2
    assert summary["Encounter"] == 10
    assert summary["Observation"] == 59
    assert summary["Immunization"] == 10
    assert summary["DiagnosticReport"] == 2
    assert summary["Claim"] == 12
    assert summary["ExplanationOfBenefit"] == 10
    assert summary["Condition"] == 4
    assert summary["MedicationRequest"] == 2
    assert summary["CarePlan"] == 2
    assert summary["Procedure"] == 3


def test_patient_is_available():
    """Verify that a Patient resource can be retrieved."""

    parser = FHIRParser(FHIR_FILE)

    patient = parser.get_patient()

    assert patient is not None
    assert patient["resourceType"] == "Patient"
    assert patient.get("id") is not None


def test_conditions_are_available():
    """Verify that Condition resources can be retrieved."""

    parser = FHIRParser(FHIR_FILE)

    conditions = parser.get_conditions()

    assert len(conditions) == 4


def test_measles_condition_exists():
    """Verify that the Measles condition exists."""

    parser = FHIRParser(FHIR_FILE)

    conditions = parser.get_conditions()

    measles = []

    for condition in conditions:

        coding = (
            condition
            .get("code", {})
            .get("coding", [])
        )

        if not coding:
            continue

        code = coding[0].get("code")

        if code == "14189004":
            measles.append(condition)

    assert len(measles) == 1

    measles_condition = measles[0]

    assert measles_condition["resourceType"] == "Condition"