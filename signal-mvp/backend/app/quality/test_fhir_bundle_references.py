from backend.app.ingestion.fhir.parser import parse_fhir_bundle
from backend.app.quality.fhir_quality import validate_fhir_data_quality


def _bundle(patient_reference="Patient/p1", encounter_reference="Encounter/e1"):
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "fullUrl": "urn:uuid:patient-entry",
                "resource": {"resourceType": "Patient", "id": "p1"},
            },
            {
                "fullUrl": "urn:uuid:encounter-entry",
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e1",
                    "subject": {"reference": patient_reference},
                },
            },
            {
                "fullUrl": "urn:uuid:condition-entry",
                "resource": {
                    "resourceType": "Condition",
                    "id": "c1",
                    "subject": {"reference": patient_reference},
                    "encounter": {"reference": encounter_reference},
                },
            },
            {
                "fullUrl": "urn:uuid:document-entry",
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": "d1",
                    "subject": {"reference": patient_reference},
                    "context": {"encounter": [{"reference": encounter_reference}]},
                },
            },
        ],
    }


def _validate(bundle):
    parsed = parse_fhir_bundle(bundle)
    return validate_fhir_data_quality(parsed, bundle["entry"])


def test_bundle_local_urn_full_urls_resolve_patient_encounter_and_document_context():
    bundle = _bundle(
        patient_reference="urn:uuid:patient-entry",
        encounter_reference="urn:uuid:encounter-entry",
    )

    result = _validate(bundle)

    assert result["status"] == "passed"
    assert result["error_count"] == 0


def test_relative_patient_and_encounter_references_resolve_in_bundle():
    result = _validate(_bundle())

    assert result["status"] == "passed"
    assert result["error_count"] == 0


def test_absolute_external_reference_resolves_by_type_and_id_as_before():
    result = _validate(
        _bundle(
            patient_reference="https://example.org/fhir/Patient/p1",
            encounter_reference="https://example.org/fhir/Encounter/e1",
        )
    )

    assert result["status"] == "passed"
    assert result["error_count"] == 0


def test_missing_patient_and_encounter_references_remain_errors():
    result = _validate(
        _bundle(
            patient_reference="Patient/missing-patient",
            encounter_reference="Encounter/missing-encounter",
        )
    )

    assert result["error_count"] == 5
    assert sum(issue["field"] == "subject.reference" for issue in result["issues"]) == 3
    assert sum(issue["field"] == "encounter.reference" for issue in result["issues"]) == 1
    assert sum(issue["field"] == "context.encounter" for issue in result["issues"]) == 1
    assert any("unknown Patient/missing-patient" in issue["message"] for issue in result["issues"])
    assert any("unknown Encounter/missing-encounter" in issue["message"] for issue in result["issues"])


def test_references_to_wrong_resource_type_remain_errors():
    result = _validate(
        _bundle(
            patient_reference="urn:uuid:encounter-entry",
            encounter_reference="urn:uuid:patient-entry",
        )
    )

    assert result["error_count"] == 5
    assert any("expected Patient" in issue["message"] for issue in result["issues"])
    assert any("expected Encounter" in issue["message"] for issue in result["issues"])


def test_malformed_references_remain_errors():
    result = _validate(_bundle(patient_reference="not-a-reference", encounter_reference=""))

    assert result["error_count"] == 5
    assert any("valid Patient reference" in issue["message"] for issue in result["issues"])
    assert any("invalid Encounter reference" in issue["message"] for issue in result["issues"])
