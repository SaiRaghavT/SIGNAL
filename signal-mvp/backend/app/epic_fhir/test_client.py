import base64
import json
import uuid
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization

from backend.app.canonical.patient_mapper import map_fhir_patient
from backend.app.epic_fhir.client import EpicFHIRClient, EpicFHIRClientError


@pytest.fixture
def client_and_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = Path.cwd() / f".epic-test-key-{uuid.uuid4().hex}.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "mock-secret-token"})
        return httpx.Response(200, json={"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = EpicFHIRClient(
        client_id="mock-client",
        token_url="https://fhir.example.test/oauth2/token",
        fhir_base_url="https://fhir.example.test/r4",
        patient_identifier_system="urn:oid:2.16.840.1.113883.4.1",
        private_key_path=str(key_path),
        jwks_url="https://keys.example.test/jwks",
        jwt_kid="test-kid",
        http_client=http,
    )
    yield client, key, requests
    key_path.unlink(missing_ok=True)


def test_token_request_signs_assertion_and_does_not_return_or_log_token(client_and_key):
    client, key, requests = client_and_key
    assert client._access_token() == "mock-secret-token"
    request_body = dict(httpx.QueryParams(requests[0].content.decode()))
    assertion = request_body["client_assertion"]
    header_part, claims_part, signature_part = assertion.split(".")
    header = json.loads(base64.urlsafe_b64decode(header_part + "=="))
    claims = json.loads(base64.urlsafe_b64decode(claims_part + "=="))
    signature = base64.urlsafe_b64decode(signature_part + "==")
    key.public_key().verify(
        signature,
        f"{header_part}.{claims_part}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    assert header["alg"] == "RS256"
    assert header["jku"] == "https://keys.example.test/jwks"
    assert claims["aud"] == "https://fhir.example.test/oauth2/token"
    assert "mock-secret-token" not in assertion


def test_patient_search_counts_patient_resources_and_maps_provenance(client_and_key):
    patient = {"resourceType": "Patient", "id": "sandbox-patient-id", "gender": "female"}
    responses = [
        {"resourceType": "Bundle", "type": "searchset", "total": 1,
         "entry": [{"resource": patient}, {"resource": {"resourceType": "OperationOutcome", "issue": []}}]},
    ]

    def handler(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "opaque"})
        assert request.url.params["identifier"] == "urn:oid:2.16.840.1.113883.4.1|MRN-TEST"
        return httpx.Response(200, json=responses.pop(0))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client, _, _ = client_and_key
    client.http = http
    result = client.search_patient("MRN-TEST")
    assert result.bundle_total == 1
    assert result.entry_count == 2
    assert result.patients == [patient]
    assert len(result.operation_outcomes) == 1
    canonical = map_fhir_patient(result.patients[0], source="epic_sandbox")
    assert canonical.source == "epic_sandbox"
    assert canonical.source_patient_id == "sandbox-patient-id"


@pytest.mark.parametrize("bundle", [
    {"resourceType": "Bundle", "type": "searchset", "total": 0,
     "entry": [{"resource": {"resourceType": "OperationOutcome", "issue": [{"severity": "warning", "code": "processing"}]}}]},
    {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []},
])
def test_empty_search_and_operation_outcome_are_not_patients(client_and_key, bundle):
    client, _, _ = client_and_key

    def handler(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "opaque"})
        return httpx.Response(200, json=bundle)

    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    result = client.search_patient("MRN-TEST")
    assert result.patients == []
    assert result.bundle_total == 0
    assert result.entry_count == len(bundle["entry"])


@pytest.mark.parametrize("status", [401, 403])
def test_auth_and_authorization_errors_do_not_include_remote_body(client_and_key, status):
    client, _, _ = client_and_key

    def handler(request):
        return httpx.Response(status, text="secret upstream details")

    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(EpicFHIRClientError, match=f"HTTP {status}") as error:
        client._access_token()
    assert "secret upstream details" not in str(error.value)


def test_malformed_fhir_response_is_rejected_safely(client_and_key):
    client, _, _ = client_and_key

    def handler(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "opaque"})
        return httpx.Response(200, text="not-json")

    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(EpicFHIRClientError, match="not valid JSON"):
        client.search_patient("MRN-TEST")


def test_unexpected_fhir_structure_is_rejected(client_and_key):
    client, _, _ = client_and_key

    def handler(request):
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "opaque"})
        return httpx.Response(200, json={"resourceType": "Patient", "id": "not-a-bundle"})

    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(EpicFHIRClientError, match="unexpected FHIR response"):
        client.search_patient("MRN-TEST")


def test_valid_same_origin_pagination_returns_patients_across_pages(client_and_key):
    client, _, _ = client_and_key
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "opaque"})
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json={
                "resourceType": "Bundle", "type": "searchset", "total": 1,
                "entry": [{"resource": {"resourceType": "Patient", "id": "patient-1"}}],
            })
        return httpx.Response(200, json={
            "resourceType": "Bundle", "type": "searchset", "total": 1,
            "entry": [],
            "link": [{"relation": "next", "url": "/r4/Patient?page=2"}],
        })

    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    result = client.search_patient("MRN-TEST")
    assert result.bundle_total == 1
    assert result.entry_count == 1
    assert [p["id"] for p in result.patients] == ["patient-1"]
    assert all(request.headers.get("authorization") == "Bearer opaque" for request in calls[1:])


def test_pagination_is_supported_but_cannot_send_bearer_token_to_another_host(client_and_key):
    client, _, _ = client_and_key
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "opaque"})
        return httpx.Response(200, json={
            "resourceType": "Bundle", "type": "searchset", "total": 1,
            "entry": [], "link": [{"relation": "next", "url": "https://evil.example/steal"}],
        })

    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(EpicFHIRClientError, match="unsafe pagination"):
        client.search_patient("MRN-TEST")
    assert len(requests) == 2
