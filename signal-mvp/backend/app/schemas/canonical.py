from datetime import datetime, date
from typing import Any

from pydantic import BaseModel, Field


class Patient(BaseModel):
    patient_id: str
    source_patient_id: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    address: dict[str, Any] | None = None


class Encounter(BaseModel):
    encounter_id: str
    facility_id: str | None = None
    encounter_type: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class Condition(BaseModel):
    condition_id: str
    code: str | None = None
    code_system: str | None = None
    display: str | None = None
    status: str | None = None
    onset_date: date | None = None


class Observation(BaseModel):
    observation_id: str
    code: str | None = None
    code_system: str | None = None
    display: str | None = None
    value: Any = None
    status: str | None = None
    effective_time: datetime | None = None


class LabResult(BaseModel):
    lab_result_id: str
    test_name: str | None = None
    result: str | None = None
    status: str | None = None
    specimen: str | None = None
    effective_time: datetime | None = None


class ClinicalDocument(BaseModel):
    document_id: str
    patient_id: str
    document_type: str | None = None
    title: str | None = None
    document_date: datetime | None = None
    text: str | None = None


class PatientContext(BaseModel):
    patient: Patient
    encounters: list[Encounter] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    clinical_documents: list[ClinicalDocument] = Field(default_factory=list)


class PatientListCondition(BaseModel):
    code: str | None = None
    display: str | None = None


class PatientListItem(BaseModel):
    patient_id: str
    source_patient_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    condition: str | None = None
    severity: str | None = None
    facility: str | None = None
    conditions: list[PatientListCondition] = Field(default_factory=list)


class PatientListResponse(BaseModel):
    items: list[PatientListItem] = Field(default_factory=list)
    page: int
    page_size: int
    total: int
    pages: int
    facilities: list[str] = Field(default_factory=list)
