from fastapi import FastAPI

from backend.app.agents.cluster_signal.api import router as cluster_router
from backend.app.canonical.api import router as canonical_router
from backend.app.detection.api import router as detection_router
from backend.app.ingestion.api.fhir import router as fhir_router
from backend.app.ingestion.documents.api import router as document_router
from backend.app.ingestion.hl7.api import router as hl7_router
from backend.app.agents.audit_ledger.router import router as audit_ledger_router


app = FastAPI(
    title="SIGNAL MVP",
    description="Public Health Reporting Intelligence Layer",
    version="0.1.0",
)


# ---------------------------------------------------------
# Ingestion APIs
# ---------------------------------------------------------

# FHIR ingestion
app.include_router(fhir_router)

# HL7 v2 ingestion
app.include_router(hl7_router)

# Unstructured document ingestion
app.include_router(document_router)

# Audit ledger
app.include_router(audit_ledger_router)


# ---------------------------------------------------------
# Canonical Data APIs
# ---------------------------------------------------------

# Read-only access to the standardized SIGNAL patient context
app.include_router(canonical_router)

# Candidate detection
app.include_router(detection_router)

# Population-level cluster analysis
app.include_router(cluster_router)


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "signal-mvp",
    }
