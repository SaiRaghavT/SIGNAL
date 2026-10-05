from fastapi import APIRouter, HTTPException

from .schemas import (
    FormRenderingRequest,
    FormRenderingResponse,
)
from .service import FormRenderingService


router = APIRouter(
    prefix="/api/agents/form-rendering",
    tags=["Form Rendering"],
)

service = FormRenderingService()


@router.post(
    "/render",
    response_model=FormRenderingResponse,
)
def render_form(
    request: FormRenderingRequest,
) -> FormRenderingResponse:

    try:
        return service.render_form(request)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc