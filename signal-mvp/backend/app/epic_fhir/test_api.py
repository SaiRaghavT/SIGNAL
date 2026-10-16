from fastapi import HTTPException

from backend.app.epic_fhir import api
from backend.app.epic_fhir.client import PatientSearchResult
from backend.app.canonical.patient_mapper import map_fhir_patient
from backend.app.canonical.persistence import save_patient


def test_import_uses_canonical_ingestion_with_epic_provenance(monkeypatch):
    patient = {"resourceType": "Patient", "id": "actual-epic-resource-id"}
    calls = {}

    class MockClient:
        def search_patient(self, identifier):
            assert identifier == "sandbox-mrn"
            return PatientSearchResult(1, 1, [patient], [])

        def close(self):
            pass

    def fake_ingest(*, db, payload, source):
        calls.update(payload=payload, source=source)
        return {"status": "success", "counts": {"patients": 1}}

    monkeypatch.setattr(api, "_configured_client", MockClient)
    monkeypatch.setattr(api, "ingest_fhir_bundle", fake_ingest)
    response = api.import_epic_patient(
        api.PatientLookupRequest(identifier="sandbox-mrn"),
        db=object(),
    )

    assert response["patient_count"] == 1
    assert response["source"] == "epic_sandbox"
    assert calls["source"] == "epic_sandbox"
    assert calls["payload"]["entry"][0]["resource"] == patient


def test_import_does_not_ingest_zero_or_multiple_patient_matches(monkeypatch):
    class MockClient:
        def __init__(self, result):
            self.result = result

        def search_patient(self, _identifier):
            return self.result

        def close(self):
            pass

    ingested = []
    monkeypatch.setattr(api, "ingest_fhir_bundle", lambda **kwargs: ingested.append(kwargs))
    monkeypatch.setattr(
        api,
        "_configured_client",
        lambda: MockClient(PatientSearchResult(0, 1, [], [{"resourceType": "OperationOutcome"}])),
    )
    no_match = api.import_epic_patient(api.PatientLookupRequest(identifier="x"), db=object())
    assert no_match["status"] == "no_match"
    assert no_match["operation_outcome_count"] == 1

    two_patients = [
        {"resourceType": "Patient", "id": "one"},
        {"resourceType": "Patient", "id": "two"},
    ]
    monkeypatch.setattr(
        api,
        "_configured_client",
        lambda: MockClient(PatientSearchResult(2, 2, two_patients, [])),
    )
    try:
        api.import_epic_patient(api.PatientLookupRequest(identifier="x"), db=object())
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError("Multiple Patient matches must not be imported")
    assert ingested == []


def test_search_raw_bundle_requires_server_opt_in(monkeypatch):
    monkeypatch.setattr(api.settings, "epic_raw_response_enabled", False)
    monkeypatch.setattr(
        api,
        "_configured_client",
        lambda: (_ for _ in ()).throw(AssertionError("must reject before network")),
    )
    try:
        api.search_epic_patient(
            api.PatientLookupRequest(identifier="x", include_fhir_response=True)
        )
    except HTTPException as error:
        assert error.status_code == 403
    else:
        raise AssertionError("Raw response should require server opt-in")


def test_search_returns_raw_fhir_bundle_only_when_requested(monkeypatch):
    raw_bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [{"resource": {"resourceType": "Patient", "id": "opaque-test-id"}}],
    }

    class MockClient:
        def search_patient(self, _identifier):
            return PatientSearchResult(
                bundle_total=1,
                entry_count=1,
                patients=[raw_bundle["entry"][0]["resource"]],
                operation_outcomes=[],
                raw_bundles=[raw_bundle],
            )

        def close(self):
            pass

    monkeypatch.setattr(api.settings, "epic_raw_response_enabled", True)
    monkeypatch.setattr(api, "_configured_client", MockClient)
    response = api.search_epic_patient(
        api.PatientLookupRequest(identifier="x", include_fhir_response=True)
    )
    assert response["fhir_bundles"] == [raw_bundle]
    assert response["patient_count"] == 1


def test_canonical_patient_persistence_returns_existing_epic_identity():
    incoming = map_fhir_patient(
        {"resourceType": "Patient", "id": "same-source-id"},
        source="epic_sandbox",
    )
    existing = object()

    class Query:
        def filter(self, *criteria):
            assert len(criteria) == 2
            return self

        def first(self):
            return existing

    class Database:
        def query(self, _model):
            return Query()

        def add(self, _patient):
            raise AssertionError("Existing source identity must not be added again")

    assert save_patient(Database(), incoming) is existing
