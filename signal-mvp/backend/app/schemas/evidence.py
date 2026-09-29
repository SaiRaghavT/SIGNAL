from pydantic import BaseModel, Field


class ClinicalEvidence(BaseModel):
    document_id: str | None = None
    patient_id: str | None = None
    source_type: str | None = None
    source_title: str | None = None

    evidence_type: str
    concept: str
    evidence_text: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class EvidenceResponse(BaseModel):
    evidence: list[ClinicalEvidence] = Field(
        default_factory=list
    )