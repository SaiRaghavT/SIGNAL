from fastapi import APIRouter, HTTPException

from .schemas import (
    CaseAssemblyRequest,
    CaseAssemblyResponse,
)
from .service import CaseAssemblyService


router = APIRouter(
    prefix="/api/agents/case-assembly",
    tags=["Case Assembly"],
)

service = CaseAssemblyService()


@router.post(
    "/assemble",
    response_model=CaseAssemblyResponse,
)
def assemble_case(
    request: CaseAssemblyRequest,
) -> CaseAssemblyResponse:

    try:
        return service.assemble(request)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc