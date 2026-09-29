from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_valid_bundle():
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "test-patient-001",
                    "name": [
                        {
                            "family": "Test",
                            "given": ["Patient"]
                        }
                    ],
                    "gender": "male",
                    "birthDate": "1995-01-08",
                    "address": [
                        {
                            "line": ["123 Main Street"],
                            "city": "Austin",
                            "state": "Texas",
                            "postalCode": "78701",
                            "country": "US"
                        }
                    ]
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "condition-001",
                    "subject": {
                        "reference": "Patient/test-patient-001"
                    },
                    "code": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "14189004",
                                "display": "Measles (disorder)"
                            }
                        ]
                    },
                    "clinicalStatus": {
                        "coding": [{"code": "active"}]
                    },
                    "verificationStatus": {
                        "coding": [{"code": "confirmed"}]
                    }
                }
            }
        ]
    }


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "SIGNAL FHIR Ingestion API"
    assert data["status"] == "running"


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_valid_fhir_bundle():
    response = client.post(
        "/api/ingestion/fhir",
        json=create_valid_bundle()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert "data" in data


def test_normalized_patient():
    response = client.post(
        "/api/ingestion/fhir",
        json=create_valid_bundle()
    )

    patient = response.json()["data"]["patient"]

    assert patient["id"] == "test-patient-001"
    assert patient["name"] == "Patient Test"
    assert patient["date_of_birth"] == "1995-01-08"
    assert patient["gender"] == "male"


def test_normalized_measles():
    response = client.post(
        "/api/ingestion/fhir",
        json=create_valid_bundle()
    )

    conditions = response.json()["data"]["conditions"]

    assert len(conditions) == 1
    assert conditions[0]["code"] == "14189004"
    assert conditions[0]["display"] == "Measles (disorder)"
    assert conditions[0]["clinical_status"] == "active"
    assert conditions[0]["verification_status"] == "confirmed"


def test_dynamic_provenance():
    headers = {
        "X-Source-System": "Test-System",
        "X-FHIR-Version": "R4"
    }

    response = client.post(
        "/api/ingestion/fhir",
        json=create_valid_bundle(),
        headers=headers
    )

    assert response.status_code == 200

    provenance = response.json()["data"]["provenance"]

    assert provenance["source_system"] == "Test-System"
    assert provenance["source_format"] == "FHIR"
    assert provenance["fhir_version"] == "R4"
    assert provenance["ingested_at"] is not None


def test_non_bundle_rejected():
    payload = {
        "resourceType": "Patient",
        "id": "test-patient"
    }

    response = client.post(
        "/api/ingestion/fhir",
        json=payload
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Input must be a FHIR Bundle."


def test_invalid_entry_rejected():
    payload = {
        "resourceType": "Bundle",
        "entry": [
            {
                "invalid": "data"
            }
        ]
    }

    response = client.post(
        "/api/ingestion/fhir",
        json=payload
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "FHIR Bundle entry must contain a valid resource."
    )


def test_missing_resource_type_rejected():
    payload = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "id": "test-001"
                }
            }
        ]
    }

    response = client.post(
        "/api/ingestion/fhir",
        json=payload
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "FHIR resourceType is missing."
    )
