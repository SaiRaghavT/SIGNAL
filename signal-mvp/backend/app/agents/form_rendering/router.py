from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .schemas import (
    FormDefinitionResponse,
    FormRenderingRequest,
    FormRenderingResponse,
)
from .service import FormRenderingService, get_rendered_pdf_path
from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM


router = APIRouter(
    prefix="/api/agents/form-rendering",
    tags=["Form Rendering"],
)

service = FormRenderingService()


@router.get("/forms/{form_id}", response_model=FormDefinitionResponse)
def get_form_definition(form_id: str) -> FormDefinitionResponse:
    if form_id != TEXAS_MEASLES_FORM["form_id"]:
        raise HTTPException(status_code=404, detail=f"Reporting form not found: {form_id}")
    return FormDefinitionResponse(**TEXAS_MEASLES_FORM)


@router.post(
    "/render",
    response_model=FormRenderingResponse,
)
def render_form(
    request: FormRenderingRequest,
) -> FormRenderingResponse:

    try:
        result = service.render_form(request)
        if not result.render_id:
            raise HTTPException(
                status_code=500,
                detail="Form rendering did not return a render identifier.",
            )
        retrieval_url = f"{router.prefix}/{result.render_id}"
        result.retrieval_url = retrieval_url
        result.rendered_document = retrieval_url
        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/{render_id}",
    response_class=FileResponse,
    name="retrieve_rendered_form",
)
def retrieve_rendered_form(render_id: str) -> FileResponse:
    pdf_path = get_rendered_pdf_path(render_id)
    if pdf_path is None:
        raise HTTPException(
            status_code=404,
            detail="Rendered form not found.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"signal-form-{render_id}.pdf",
        content_disposition_type="inline",
    )
