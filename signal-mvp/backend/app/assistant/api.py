from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.assistant.demo_service import chat_with_synthetic_demo


router = APIRouter(prefix="/api/assistant", tags=["Assistant"])
demo_router = APIRouter(prefix="/api/assistant/demo", tags=["Assistant Demo"])


class AssistantChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    selected_patient_id: str | None = Field(default=None, max_length=32)


@router.post("/chat")
def chat(_request: AssistantChatRequest) -> dict[str, str]:
    """Safe integration boundary until server authentication is available.

    The current demo login is verified only by the browser. Patient and case
    APIs do not provide a trusted backend identity or record-level access
    checks, so this endpoint must not retrieve or transmit patient data.
    """
    raise HTTPException(
        status_code=503,
        detail=(
            "SIGNAL Assistant is not enabled because server-side user "
            "authentication and record-level authorization are not configured. "
            "No patient records were accessed."
        ),
    )


@demo_router.post("/chat")
def demo_chat(request: AssistantChatRequest) -> dict:
    """Answer from the fixed synthetic dataset only; never access real records."""
    return chat_with_synthetic_demo(
        question=request.question,
        selected_patient_id=request.selected_patient_id,
    )
