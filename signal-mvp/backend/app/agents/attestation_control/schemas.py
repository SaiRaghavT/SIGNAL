from typing import Optional

from pydantic import BaseModel


class AttestationRequest(BaseModel):
    case_reference: str
    reviewer_id: str
    reviewer_role: str

    attestation_status: str

    comments: Optional[str] = None


class AttestationResponse(BaseModel):
    case_reference: str
    reviewer_id: str
    reviewer_role: str

    attestation_status: str

    authorized: bool

    message: str

    comments: Optional[str] = None