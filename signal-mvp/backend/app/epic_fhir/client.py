from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class EpicFHIRClientError(RuntimeError):
    """Safe-to-display Epic integration error without remote response content."""


@dataclass(frozen=True)
class PatientSearchResult:
    bundle_total: int | None
    entry_count: int
    patients: list[dict[str, Any]]
    operation_outcomes: list[dict[str, Any]]
    raw_bundles: list[dict[str, Any]] = field(default_factory=list)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class EpicFHIRClient:
    """Small OAuth client for Epic's documented SMART Backend Services flow."""

    def __init__(
        self,
        *,
        client_id: str,
        token_url: str,
        fhir_base_url: str,
        patient_identifier_system: str,
        private_key_path: str,
        jwks_url: str,
        jwt_kid: str | None = None,
        timeout_seconds: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.token_url = self._https_url(token_url, "token endpoint")
        self.fhir_base_url = self._https_url(fhir_base_url, "FHIR base URL").rstrip("/") + "/"
        self.patient_identifier_system = patient_identifier_system.strip()
        self.private_key_path = Path(private_key_path)
        self.jwks_url = self._https_url(jwks_url, "JWKS URL")
        self.jwt_kid = jwt_kid
        self.timeout_seconds = timeout_seconds
        self.http = http_client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)

    def close(self) -> None:
        self.http.close()

    @staticmethod
    def _https_url(value: str, label: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise EpicFHIRClientError(f"Epic {label} must use HTTPS.")
        return value

    def _assertion(self) -> str:
        try:
            key = serialization.load_pem_private_key(
                self.private_key_path.read_bytes(), password=None
            )
        except Exception as exc:
            raise EpicFHIRClientError("Epic private key could not be loaded.") from exc

        now = int(time.time())
        header: dict[str, str] = {"alg": "RS256", "typ": "JWT", "jku": self.jwks_url}
        if self.jwt_kid:
            header["kid"] = self.jwt_kid
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_url,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "nbf": now,
            "exp": now + 300,
        }
        signing_input = ".".join(
            _b64url(json.dumps(part, separators=(",", ":")).encode())
            for part in (header, claims)
        ).encode("ascii")
        try:
            signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise EpicFHIRClientError("Epic JWT assertion could not be signed.") from exc
        return signing_input.decode("ascii") + "." + _b64url(signature)

    def _access_token(self) -> str:
        try:
            response = self.http.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": self._assertion(),
                },
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise EpicFHIRClientError("Epic token request failed.") from exc
        if response.status_code in (401, 403):
            raise EpicFHIRClientError(f"Epic token request was rejected (HTTP {response.status_code}).")
        if response.status_code < 200 or response.status_code >= 300:
            raise EpicFHIRClientError(f"Epic token request failed (HTTP {response.status_code}).")
        try:
            body = response.json()
        except ValueError as exc:
            raise EpicFHIRClientError("Epic token response was not valid JSON.") from exc
        token = body.get("access_token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise EpicFHIRClientError("Epic token response did not contain an access token.")
        return token

    def search_patient(self, identifier: str, *, max_pages: int = 10) -> PatientSearchResult:
        if not identifier.strip():
            raise EpicFHIRClientError("A Patient identifier is required.")
        token = self._access_token()
        url = urljoin(self.fhir_base_url, "Patient")
        identifier_value = identifier.strip()
        if "|" not in identifier_value and self.patient_identifier_system:
            identifier_value = f"{self.patient_identifier_system}|{identifier_value}"
        params: dict[str, str] | None = {"identifier": identifier_value, "_count": "100"}
        seen: set[str] = set()
        entries: list[dict[str, Any]] = []
        patients: list[dict[str, Any]] = []
        outcomes: list[dict[str, Any]] = []
        raw_bundles: list[dict[str, Any]] = []
        bundle_total: int | None = None

        for _ in range(max_pages):
            if url in seen:
                raise EpicFHIRClientError("Epic Patient search pagination repeated a page.")
            seen.add(url)
            self._validate_page_url(url)
            try:
                response = self.http.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
                    timeout=self.timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise EpicFHIRClientError("Epic Patient search request failed.") from exc
            params = None
            if response.status_code in (401, 403):
                raise EpicFHIRClientError(f"Epic Patient search was rejected (HTTP {response.status_code}).")
            if response.status_code < 200 or response.status_code >= 300:
                raise EpicFHIRClientError(f"Epic Patient search failed (HTTP {response.status_code}).")
            try:
                bundle = response.json()
            except ValueError as exc:
                raise EpicFHIRClientError("Epic Patient search response was not valid JSON.") from exc
            if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle" or bundle.get("type") != "searchset":
                raise EpicFHIRClientError("Epic Patient search returned an unexpected FHIR response.")
            raw_bundles.append(bundle)
            total = bundle.get("total")
            if bundle_total is None and isinstance(total, int):
                bundle_total = total
            page_entries = bundle.get("entry", [])
            if not isinstance(page_entries, list):
                raise EpicFHIRClientError("Epic Patient search returned malformed Bundle entries.")
            entries.extend(e for e in page_entries if isinstance(e, dict))
            for entry in page_entries:
                resource = entry.get("resource") if isinstance(entry, dict) else None
                if not isinstance(resource, dict):
                    continue
                if resource.get("resourceType") == "Patient":
                    patients.append(resource)
                elif resource.get("resourceType") == "OperationOutcome":
                    outcomes.append(resource)
            next_link = next(
                (link.get("url") for link in bundle.get("link", [])
                 if isinstance(link, dict) and link.get("relation") == "next"),
                None,
            ) if isinstance(bundle.get("link", []), list) else None
            if not next_link:
                return PatientSearchResult(bundle_total, len(entries), patients, outcomes, raw_bundles)
            if not isinstance(next_link, str):
                raise EpicFHIRClientError("Epic Patient search returned an invalid next-page link.")
            url = urljoin(url, next_link)

        raise EpicFHIRClientError("Epic Patient search exceeded the safe pagination limit.")

    def search_patient_resources(
        self, resource_type: str, patient_id: str, *, category: str | None = None, max_pages: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch one patient's resources of an allowlisted FHIR type, following next links."""
        allowed = {"Condition", "Encounter", "DiagnosticReport", "DocumentReference", "Observation"}
        if resource_type not in allowed:
            raise EpicFHIRClientError("Epic resource type is not enabled for import.")
        if not patient_id.strip():
            raise EpicFHIRClientError("A FHIR Patient id is required.")
        token = self._access_token()
        url = urljoin(self.fhir_base_url, resource_type)
        params: dict[str, str] | None = {"patient": patient_id.strip(), "_count": "100"}
        if category:
            if resource_type != "Observation":
                raise EpicFHIRClientError("Observation category can only be used for Observation searches.")
            params["category"] = category
        seen: set[str] = set()
        resources: list[dict[str, Any]] = []
        for _ in range(max_pages):
            if url in seen:
                raise EpicFHIRClientError("Epic resource pagination repeated a page.")
            seen.add(url)
            self._validate_page_url(url)
            try:
                response = self.http.get(
                    url, params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
                    timeout=self.timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise EpicFHIRClientError("Epic resource search request failed.") from exc
            params = None
            if response.status_code in (401, 403):
                raise EpicFHIRClientError(f"Epic resource search was rejected (HTTP {response.status_code}).")
            if response.status_code < 200 or response.status_code >= 300:
                raise EpicFHIRClientError(f"Epic resource search failed (HTTP {response.status_code}).")
            try:
                bundle = response.json()
            except ValueError as exc:
                raise EpicFHIRClientError("Epic resource search response was not valid JSON.") from exc
            if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle" or bundle.get("type") != "searchset":
                raise EpicFHIRClientError("Epic resource search returned an unexpected FHIR response.")
            entries = bundle.get("entry", [])
            if not isinstance(entries, list):
                raise EpicFHIRClientError("Epic resource search returned malformed Bundle entries.")
            for entry in entries:
                resource = entry.get("resource") if isinstance(entry, dict) else None
                if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
                    resources.append(resource)
            links = bundle.get("link", [])
            next_link = next((item.get("url") for item in links if isinstance(item, dict) and item.get("relation") == "next"), None) if isinstance(links, list) else None
            if not next_link:
                return resources
            if not isinstance(next_link, str):
                raise EpicFHIRClientError("Epic resource search returned an invalid next-page link.")
            url = urljoin(url, next_link)
        raise EpicFHIRClientError("Epic resource search exceeded the safe pagination limit.")

    def _validate_page_url(self, url: str) -> None:
        base = urlparse(self.fhir_base_url)
        page = urlparse(url)
        if page.scheme != "https" or page.netloc != base.netloc or not page.path.startswith(base.path):
            raise EpicFHIRClientError("Epic Patient search returned an unsafe pagination link.")
