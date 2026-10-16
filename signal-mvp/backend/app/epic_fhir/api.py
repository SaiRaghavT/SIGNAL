from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.config.settings import settings
from backend.app.database import get_db
from backend.app.epic_fhir.client import EpicFHIRClient, EpicFHIRClientError, PatientSearchResult
from backend.app.ingestion.fhir.service import ingest_fhir_bundle


router = APIRouter(prefix="/api/epic", tags=["Epic FHIR Sandbox"])


class PatientLookupRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=256)
    include_fhir_response: bool = False


def _configured_client() -> EpicFHIRClient:
    required = (
        settings.epic_client_id,
        settings.epic_private_key_path,
        settings.epic_jwks_url,
    )
    if not all(required):
        raise HTTPException(
            status_code=503,
            detail="Epic sandbox integration is not configured on this server.",
        )
    return EpicFHIRClient(
        client_id=settings.epic_client_id or "",
        token_url=settings.epic_token_url,
        fhir_base_url=settings.epic_fhir_base_url,
        patient_identifier_system=settings.epic_patient_identifier_system,
        private_key_path=settings.epic_private_key_path or "",
        jwks_url=settings.epic_jwks_url or "",
        jwt_kid=settings.epic_jwt_kid,
        timeout_seconds=settings.epic_http_timeout_seconds,
    )


def _search_result(request: PatientLookupRequest) -> PatientSearchResult:
    if request.include_fhir_response and not settings.epic_raw_response_enabled:
        raise HTTPException(
            status_code=403,
            detail="Raw Epic FHIR responses are disabled on this server.",
        )
    client = _configured_client()
    try:
        return client.search_patient(request.identifier)
    except EpicFHIRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()


def _search_summary(result: PatientSearchResult) -> dict[str, Any]:
    return {
        "bundle_total": result.bundle_total,
        "entry_count": result.entry_count,
        "patient_count": len(result.patients),
        "operation_outcome_count": len(result.operation_outcomes),
    }


def _attach_raw_response(
    payload: dict[str, Any],
    request: PatientLookupRequest,
    result: PatientSearchResult,
) -> dict[str, Any]:
    if request.include_fhir_response:
        payload["fhir_bundles"] = result.raw_bundles
    return payload


@router.post("/patients/search")
def search_epic_patient(request: PatientLookupRequest) -> dict[str, Any]:
    """Search Epic and optionally return the raw FHIR Bundle pages."""
    result = _search_result(request)
    status = "success" if result.patients else "no_match"
    response: dict[str, Any] = {"status": status, **_search_summary(result)}
    return _attach_raw_response(response, request, result)


@router.post("/patients/import")
def import_epic_patient(
    request: PatientLookupRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Find one Epic R4 Patient by identifier and ingest it canonically."""
    result = _search_result(request)

    if not result.patients:
        response = {"status": "no_match", **_search_summary(result)}
        return _attach_raw_response(response, request, result)
    if len(result.patients) != 1:
        raise HTTPException(
            status_code=409,
            detail="Epic identifier search returned multiple Patients; no records were imported.",
        )

    patient = result.patients[0]
    if patient.get("resourceType") != "Patient" or not patient.get("id"):
        raise HTTPException(status_code=502, detail="Epic returned an invalid Patient resource.")
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": patient}],
    }
    try:
        ingestion = ingest_fhir_bundle(db=db, payload=bundle, source="epic_sandbox")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Epic Patient could not be mapped into canonical data.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Epic Patient ingestion failed.") from exc

    response = {
        "status": "success",
        "source": "epic_sandbox",
        **_search_summary(result),
        "ingestion": ingestion,
    }
    return _attach_raw_response(response, request, result)


@router.post("/patients/import-chart")
def import_epic_patient_chart(
    request: PatientLookupRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Import one Patient and the supported chart resources returned by Epic."""
    client = _configured_client()
    try:
        result = client.search_patient(request.identifier)
        if len(result.patients) != 1:
            if not result.patients:
                return {"status": "no_match", **_search_summary(result)}
            raise HTTPException(status_code=409, detail="Epic identifier search returned multiple Patients; no records were imported.")
        patient = result.patients[0]
        patient_id = patient.get("id")
        if not isinstance(patient_id, str) or not patient_id:
            raise HTTPException(status_code=502, detail="Epic returned an invalid Patient resource.")
        resources_by_type: dict[str, list[dict[str, Any]]] = {"Patient": [patient]}
        counts: dict[str, int] = {"Patient": 1}
        for resource_type in ("Encounter", "Condition", "DiagnosticReport", "DocumentReference"):
            found = client.search_patient_resources(resource_type, patient_id)
            resources_by_type[resource_type] = found
            counts[resource_type] = len(found)
        observations: dict[str, dict[str, Any]] = {}
        observation_searches: dict[str, str] = {}
        for category in ("laboratory", "vital-signs", "social-history"):
            try:
                found = client.search_patient_resources("Observation", patient_id, category=category)
            except EpicFHIRClientError:
                observation_searches[category] = "unsupported_or_rejected"
                continue
            observation_searches[category] = "success"
            for observation in found:
                observation_id = observation.get("id")
                if isinstance(observation_id, str):
                    observations[observation_id] = observation
        resources_by_type["Observation"] = list(observations.values())
        counts["Observation"] = len(observations)
        # Commit resource groups separately so one malformed upstream chart
        # item cannot discard its other valid canonical records.
        groups = (
            ("Patient", ("Patient",)),
            ("Encounter", ("Patient", "Encounter")),
            ("Condition", ("Patient", "Encounter", "Condition")),
            ("Observation", ("Patient", "Encounter", "Observation")),
            ("DiagnosticReport", ("Patient", "Encounter", "Observation", "DiagnosticReport")),
            ("DocumentReference", ("Patient", "Encounter", "DocumentReference")),
        )
        aggregate: dict[str, int] = {}
        rejected_groups: list[str] = []
        rejected_resource_counts: dict[str, int] = {}
        count_key = {"Patient": "patients", "Encounter": "encounters", "Condition": "conditions",
                     "Observation": "observations", "DiagnosticReport": "lab_results",
                     "DocumentReference": "clinical_documents"}
        for group_name, included_types in groups:
            if group_name != "Patient" and not resources_by_type.get(group_name):
                continue
            entries = [
                {"resource": item}
                for resource_type in included_types
                for item in resources_by_type.get(resource_type, [])
            ]
            try:
                result = ingest_fhir_bundle(
                    db=db,
                    payload={"resourceType": "Bundle", "type": "collection", "entry": entries},
                    source="epic_sandbox",
                )
            except ValueError:
                if group_name == "DocumentReference":
                    rejected = 0

                    def ingest_documents(items: list[dict[str, Any]]) -> int:
                        nonlocal rejected
                        if not items:
                            return 0
                        entries = [
                            {"resource": item}
                            for resource_type in ("Patient", "Encounter")
                            for item in resources_by_type.get(resource_type, [])
                        ] + [{"resource": item} for item in items]
                        try:
                            document_result = ingest_fhir_bundle(
                                db=db,
                                payload={"resourceType": "Bundle", "type": "collection", "entry": entries},
                                source="epic_sandbox",
                            )
                            return document_result.get("counts", {}).get("clinical_documents", 0)
                        except ValueError:
                            if len(items) == 1:
                                rejected += 1
                                return 0
                            midpoint = len(items) // 2
                            return ingest_documents(items[:midpoint]) + ingest_documents(items[midpoint:])

                    aggregate["clinical_documents"] = ingest_documents(resources_by_type[group_name])
                    if rejected:
                        rejected_resource_counts[group_name] = rejected
                    continue
                rejected_groups.append(group_name)
                continue
            name = count_key[group_name]
            aggregate[name] = result.get("counts", {}).get(name, 0)
        ingestion = {"status": "partial" if rejected_groups or rejected_resource_counts else "success", "counts": aggregate}
        return {"status": "success", "source": "epic_sandbox", "resource_counts": counts,
                "observation_searches": observation_searches, "rejected_resource_groups": rejected_groups,
                "rejected_resource_counts": rejected_resource_counts,
                "ingestion": ingestion}
    except EpicFHIRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Epic chart could not be mapped into canonical data.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Epic chart ingestion failed.") from exc
    finally:
        client.close()
